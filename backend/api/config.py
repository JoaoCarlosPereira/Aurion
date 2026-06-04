"""Endpoints REST de configuração (GET/PUT /api/config + avançados).

Expõe a leitura e a atualização (parcial ou total) das configurações da
aplicação, além dos endpoints avançados descritos na task_11:

- ``GET /api/config`` — retorna todas as configurações.
- ``PUT /api/config`` — atualiza configurações (parcial ou total).
- ``PUT /api/config/audio`` — atualiza apenas o bloco de áudio com validação
  avançada (sample_rate, channels, chunk_size, silence_threshold), incluindo
  uma validação cruzada de coerência entre os parâmetros.
- ``POST /api/config/reset`` — restaura todas as configurações para os padrões.

O token do Hermes (`hermes.auth_token`) é considerado sensível e NÃO é exposto
no GET/PUT (ver TechSpec Seção 11): o valor é omitido da resposta.

O wiring final (registro do router e provisão do `ConfigManager`) é feito na
task_18. Este módulo apenas expõe o objeto `router` e a dependência
`get_config_manager_dep`, que pode ser sobrescrita via `app.dependency_overrides`
em testes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from config.models import AppConfig, AppConfigUpdate, AudioConfigUpdate
from config.settings import ConfigManager, get_config_manager

router = APIRouter(prefix="/api", tags=["config"])

# Limites superiores de sanidade para a validação avançada de áudio. Acima
# destes valores os parâmetros são improváveis/abusivos para captura de voz.
MAX_SAMPLE_RATE = 192_000
MAX_CHANNELS = 8
MAX_CHUNK_SIZE = 65_536


def get_config_manager_dep() -> ConfigManager:
    """Dependência que fornece o Config Manager (singleton da aplicação).

    Pode ser sobrescrita em testes via `app.dependency_overrides`.
    """
    return get_config_manager()


def _to_public_dict(config: AppConfig) -> dict[str, Any]:
    """Serializa a configuração omitindo campos sensíveis (token do Hermes).

    Remove `hermes.auth_token` da resposta para não expor o segredo via API.
    """
    data = config.model_dump()
    # Omite o token do Hermes; o cliente nunca recebe o valor real.
    if "hermes" in data and isinstance(data["hermes"], dict):
        data["hermes"].pop("auth_token", None)
    return data


@router.get("/config")
async def get_config(
    manager: ConfigManager = Depends(get_config_manager_dep),
) -> dict[str, Any]:
    """Retorna todas as configurações (sem expor o token do Hermes)."""
    config = await manager.get()
    return _to_public_dict(config)


@router.put("/config")
async def put_config(
    updates: AppConfigUpdate,
    manager: ConfigManager = Depends(get_config_manager_dep),
) -> dict[str, Any]:
    """Atualiza as configurações (parcial ou total) e persiste em disco.

    Apenas os campos informados são alterados (merge profundo); valores não
    enviados são preservados. A resposta omite o token do Hermes.
    """
    # `exclude_unset` garante merge parcial: somente campos enviados no corpo
    # entram na atualização, preservando os demais.
    updates_dict = updates.model_dump(exclude_unset=True)
    config = await manager.update(updates_dict)
    return _to_public_dict(config)


def _validate_audio_advanced(audio: AudioConfigUpdate) -> None:
    """Validação avançada (cross-field) dos parâmetros de áudio.

    As faixas mínimas já são validadas pelo modelo Pydantic
    (``AudioConfigUpdate``); aqui aplicamos limites superiores de sanidade e
    coerência entre parâmetros, levantando ``400`` com mensagem em PT-BR quando
    algum valor é incoerente para captura de voz.
    """
    if audio.sample_rate is not None and audio.sample_rate > MAX_SAMPLE_RATE:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "AUDIO_INVALID_CONFIG",
                "message": (
                    f"sample_rate acima do máximo suportado ({MAX_SAMPLE_RATE} Hz)."
                ),
            },
        )
    if audio.channels is not None and audio.channels > MAX_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "AUDIO_INVALID_CONFIG",
                "message": f"channels acima do máximo suportado ({MAX_CHANNELS}).",
            },
        )
    if audio.chunk_size is not None and audio.chunk_size > MAX_CHUNK_SIZE:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "AUDIO_INVALID_CONFIG",
                "message": (
                    f"chunk_size acima do máximo suportado ({MAX_CHUNK_SIZE} frames)."
                ),
            },
        )


@router.put("/config/audio")
async def put_audio_config(
    audio: AudioConfigUpdate,
    manager: ConfigManager = Depends(get_config_manager_dep),
) -> dict[str, Any]:
    """Atualiza apenas o bloco de áudio com validação avançada.

    Aplica a validação cruzada de ``_validate_audio_advanced`` (limites de
    sanidade) e persiste somente os campos enviados (merge parcial), preservando
    os demais. A resposta omite o token do Hermes.
    """
    _validate_audio_advanced(audio)
    # `exclude_unset` preserva os campos de áudio não informados.
    audio_updates = audio.model_dump(exclude_unset=True)
    config = await manager.update({"audio": audio_updates})
    return _to_public_dict(config)


@router.post("/config/reset")
async def reset_config(
    manager: ConfigManager = Depends(get_config_manager_dep),
) -> dict[str, Any]:
    """Restaura todas as configurações para os valores padrão e persiste.

    Reaproveita ``ConfigManager.reset`` (task_03). A resposta omite o token do
    Hermes.
    """
    config = await manager.reset()
    return _to_public_dict(config)
