"""Modelos Pydantic da camada de API para comandos e interações.

Define os modelos de entrada (corpo do ``POST /api/command``) e de saída
(status de comando e itens de histórico) usados pelos endpoints REST de comando
e histórico (TechSpec Seção 3.1).

Reutiliza o modelo de domínio ``Interaction`` (``db/models.py``, task_02) como
representação canônica de uma interação persistida; aqui são definidos apenas os
modelos específicos da fronteira HTTP, evitando duplicar o esquema de dados.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Reexporta o modelo de domínio e os aliases de tipo para que a camada de API
# possa importar tudo de um único módulo.
from db.models import Channel, Interaction, Status  # noqa: F401

# Estado de processamento de um comando. Diferente de ``Status`` (resultado
# final persistido), ``processing`` indica que o comando ainda está em curso.
CommandState = Literal["processing", "success", "error", "timeout"]


class CommandRequest(BaseModel):
    """Corpo do ``POST /api/command``: a mensagem de texto do usuário.

    A mensagem não pode ser vazia (após remoção de espaços); a validação por
    comprimento mínimo garante uma resposta 422 clara quando ausente.
    """

    message: str = Field(min_length=1, description="Comando do usuário em texto.")


class CommandAccepted(BaseModel):
    """Resposta imediata do ``POST /api/command`` (TechSpec Seção 3.1).

    Retorna o ``id`` da interação recém-criada e o ``status`` de processamento.
    """

    id: str
    status: CommandState = "processing"
