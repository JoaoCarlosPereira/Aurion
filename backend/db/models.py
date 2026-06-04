"""Modelos Pydantic da camada de persistência de interações.

Define o modelo completo de uma interação (`Interaction`) conforme a TechSpec
(Seção 3.3) e o modelo de entrada para criação (`InteractionCreate`), no qual
`id` e `timestamp` são gerados pela camada de repositório.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Tipos de canal e status reutilizados pelos modelos e validados via CHECK no banco.
Channel = Literal["local", "web"]
Status = Literal["success", "error", "timeout"]


class InteractionCreate(BaseModel):
    """Dados necessários para registrar uma nova interação.

    `id` e `timestamp` não fazem parte deste modelo: são gerados em
    `InteractionRepository.create_interaction`.
    """

    channel: Channel
    input_text: str
    output_text: str | None = None
    output_audio_url: str | None = None
    duration_ms: int | None = None
    status: Status = "success"
    error_message: str | None = None


class Interaction(BaseModel):
    """Representa uma interação persistida na tabela `interactions`."""

    id: str
    timestamp: datetime
    channel: Channel
    input_text: str
    output_text: str | None = None
    output_audio_url: str | None = None
    duration_ms: int | None = None
    status: Status
    error_message: str | None = None
