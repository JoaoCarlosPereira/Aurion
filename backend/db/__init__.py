"""Pacote de persistência da Aurion.

Expõe a conexão/ciclo de vida do banco, os modelos Pydantic de interação e o
repositório de interações.
"""

from db.database import (
    DEFAULT_DB_PATH,
    Database,
    close_database,
    get_database,
    init_database,
)
from db.models import Channel, Interaction, InteractionCreate, Status
from db.repo import InteractionRepository

__all__ = [
    "DEFAULT_DB_PATH",
    "Database",
    "close_database",
    "get_database",
    "init_database",
    "Channel",
    "Interaction",
    "InteractionCreate",
    "Status",
    "InteractionRepository",
]
