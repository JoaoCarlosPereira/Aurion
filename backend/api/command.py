"""Endpoints REST de comando (POST /api/command, GET /api/command/{id}).

Implementa o fluxo completo de envio de comando por texto (TechSpec Seção 3.1):

1. Recebe ``{"message": "..."}`` e registra imediatamente uma interação no banco
   (via ``InteractionRepository``, task_02) marcando o canal como ``"web"``.
2. Encaminha a mensagem ao Hermes Agent (via ``HermesBridge``, task_04).
3. Mede a duração do processamento em milissegundos e atualiza a interação com o
   resultado final (``success``/``error``/``timeout``), persistindo a resposta ou
   o erro.
4. Retorna o ``id`` da interação e o ``status`` de processamento.

Degradação graciosa: falhas do Hermes (indisponível, timeout, erro HTTP) são
convertidas em uma interação com status de erro e em uma resposta de erro
padronizada (``APIError``, TechSpec Seção 10.2), sem derrubar o servidor.

O wiring final (registro do router e provisão das dependências) é feito na
task_18. Este módulo apenas expõe o objeto ``router`` e as dependências
``get_repository_dep`` / ``get_config_manager_dep`` / ``get_hermes_bridge_factory``,
que podem ser sobrescritas via ``app.dependency_overrides`` em testes (sem rede).
"""

from __future__ import annotations

import time
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from config.settings import ConfigManager, get_config_manager
from db.models import InteractionCreate, Status
from db.repo import InteractionRepository
from models.interaction import CommandAccepted, CommandRequest, Interaction
from models.response import APIError
from svc.hermes_bridge import HermesBridge, HermesError

router = APIRouter(prefix="/api/command", tags=["command"])

# Canal usado para comandos enviados via API REST (TechSpec Seção 3.3).
CHANNEL_WEB = "web"

# Códigos de erro padronizados desta camada (TechSpec Seção 10.2).
ERR_NOT_FOUND = "INTERACTION_NOT_FOUND"


# --- Dependências (sobrescritíveis em testes) --------------------------------


def get_repository_dep() -> InteractionRepository:
    """Dependência que fornece o repositório de interações.

    O wiring real (banco singleton) é feito na task_18. Em testes, esta
    dependência é sobrescrita via ``app.dependency_overrides`` por um
    repositório apontando para um banco em memória.
    """
    # Resolução tardia para evitar exigir o banco inicializado no import.
    from db.database import get_database

    return InteractionRepository(get_database())


def get_config_manager_dep() -> ConfigManager:
    """Dependência que fornece o Config Manager (singleton da aplicação)."""
    return get_config_manager()


def get_hermes_bridge_factory() -> Callable[[ConfigManager], HermesBridge]:
    """Fornece a factory que cria um ``HermesBridge`` a partir da configuração.

    Isolada como dependência para permitir substituição por um cliente mockado
    em testes (sem rede real).
    """

    def _factory(manager: ConfigManager) -> HermesBridge:
        config = manager._config  # type: ignore[attr-defined]
        hermes_config = config.hermes if config is not None else None
        return HermesBridge(hermes_config)

    return _factory


# --- Endpoints ---------------------------------------------------------------


@router.post("", status_code=202, response_model=CommandAccepted)
async def post_command(
    body: CommandRequest,
    repo: InteractionRepository = Depends(get_repository_dep),
    manager: ConfigManager = Depends(get_config_manager_dep),
    bridge_factory: Callable[[ConfigManager], HermesBridge] = Depends(
        get_hermes_bridge_factory
    ),
) -> CommandAccepted:
    """Envia um comando de texto ao Hermes, persiste e retorna o id/status.

    Registra a interação no canal ``"web"``, encaminha ao Hermes, mede a duração
    em milissegundos e atualiza a interação com o resultado. Retorna sempre
    ``202`` com ``{"id": ..., "status": "processing"}``; o resultado final pode
    ser consultado em ``GET /api/command/{id}``.

    Em caso de falha do Hermes, a interação é gravada com status de erro
    (``error``/``timeout``) e mensagem legível em PT-BR; a resposta HTTP
    continua sendo ``202`` (o erro é refletido no status da interação).
    """
    # 1) Registra a interação com status inicial. O esquema do banco só admite
    # 'success'/'error'/'timeout'; usamos 'error' como marcador transitório de
    # "processando", atualizado logo a seguir com o resultado real.
    interaction = await repo.create_interaction(
        InteractionCreate(
            channel=CHANNEL_WEB,
            input_text=body.message,
            status="error",
            error_message="processing",
        )
    )

    # Garante a configuração carregada antes de montar o cliente do Hermes.
    await manager.get()
    bridge = bridge_factory(manager)

    # 2) Encaminha ao Hermes medindo a duração do processamento.
    start = time.perf_counter()
    try:
        response = await bridge.send_command(body.message)
    except HermesError as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        # Timeout do Hermes mapeia para o status 'timeout'; demais falhas para
        # 'error' (TechSpec Seções 3.3 e 10.1).
        status: Status = "timeout" if exc.code == "HERMES_TIMEOUT" else "error"
        await repo.update_interaction(
            interaction.id,
            duration_ms=duration_ms,
            status=status,
            error_message=exc.error.message,
        )
    else:
        # 3) Sucesso: persiste a resposta e a duração.
        duration_ms = int((time.perf_counter() - start) * 1000)
        await repo.update_interaction(
            interaction.id,
            output_text=response.reply,
            duration_ms=duration_ms,
            status="success",
            error_message=None,
        )

    # 4) Resposta imediata padronizada.
    return CommandAccepted(id=interaction.id, status="processing")


@router.get("/{interaction_id}", response_model=Interaction)
async def get_command(
    interaction_id: str,
    repo: InteractionRepository = Depends(get_repository_dep),
) -> Interaction:
    """Consulta o status/resposta de um comando pelo id da interação.

    Retorna a interação persistida ou ``404`` (``APIError``) se não existir.
    """
    interaction = await repo.get_interaction_by_id(interaction_id)
    if interaction is None:
        raise HTTPException(
            status_code=404,
            detail=APIError(
                code=ERR_NOT_FOUND,
                message="Interação não encontrada.",
                details={"id": interaction_id},
            ).model_dump(),
        )
    return interaction
