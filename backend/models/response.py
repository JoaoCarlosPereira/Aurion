"""Modelos de resposta da API e estrutura de erro padronizada.

Define o modelo de erro ``APIError`` conforme a TechSpec (Seção 10.2) e a
resposta padronizada do Hermes (``HermesResponse``), reutilizados pelo Hermes
Bridge (``svc/hermes_bridge.py``) e pela camada de API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from db.models import Interaction


class APIError(BaseModel):
    """Estrutura de erro padronizada da API (TechSpec Seção 10.2).

    - ``code``: código estável e legível por máquina (ex.: ``HERMES_UNAVAILABLE``).
    - ``message``: mensagem legível em PT-BR para exibição ao usuário.
    - ``details``: informações adicionais opcionais (ex.: status HTTP, tentativas).
    """

    code: str
    message: str
    details: dict | None = None


class HermesResponse(BaseModel):
    """Resposta padronizada de um comando enviado ao Hermes Agent.

    - ``reply``: texto de resposta do Hermes extraído do corpo da resposta.
    - ``status_code``: código HTTP retornado pelo Hermes.
    - ``raw``: corpo bruto da resposta (JSON decodificado) para uso avançado.
    """

    reply: str
    status_code: int = 200
    raw: dict = Field(default_factory=dict)


class HistoryList(BaseModel):
    """Resposta paginada do ``GET /api/history`` (TechSpec Seção 3.1).

    - ``items``: interações da página atual (mais recentes primeiro).
    - ``limit`` / ``offset``: parâmetros de paginação efetivamente aplicados.
    - ``count``: quantidade de itens retornados nesta página.
    """

    items: list[Interaction]
    limit: int
    offset: int
    count: int


class DeleteResult(BaseModel):
    """Resposta do ``DELETE /api/history``: quantidade de registros removidos."""

    deleted: int

