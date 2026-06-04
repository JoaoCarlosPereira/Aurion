"""Conexão e inicialização do banco de dados SQLite (aiosqlite).

Gerencia uma conexão assíncrona única (singleton) com o SQLite, cria o esquema
da tabela `interactions` e os índices obrigatórios automaticamente na
inicialização, conforme a TechSpec (Seção 4.1) e a ADR-002.
"""

from __future__ import annotations

import aiosqlite

# Caminho padrão do banco quando nenhum é informado via config.json.
DEFAULT_DB_PATH = "aurion.db"

# Esquema idêntico à TechSpec (Seção 4.1). `IF NOT EXISTS` garante criação
# idempotente a cada inicialização.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS interactions (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    channel TEXT NOT NULL CHECK(channel IN ('local', 'web')),
    input_text TEXT NOT NULL,
    output_text TEXT,
    output_audio_url TEXT,
    duration_ms INTEGER,
    status TEXT NOT NULL CHECK(status IN ('success', 'error', 'timeout')),
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_channel ON interactions(channel);
CREATE INDEX IF NOT EXISTS idx_interactions_status ON interactions(status);
"""


class Database:
    """Encapsula uma conexão assíncrona com o SQLite e seu ciclo de vida."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    @property
    def db_path(self) -> str:
        return self._db_path

    @property
    def connection(self) -> aiosqlite.Connection:
        """Retorna a conexão ativa ou levanta erro se o banco não foi iniciado."""
        if self._conn is None:
            raise RuntimeError(
                "Banco de dados não inicializado. Chame connect() antes de usar."
            )
        return self._conn

    async def connect(self) -> None:
        """Abre a conexão (idempotente) e garante o esquema criado."""
        if self._conn is not None:
            return
        self._conn = await aiosqlite.connect(self._db_path)
        # Linhas acessíveis por nome de coluna, facilitando o mapeamento para modelos.
        self._conn.row_factory = aiosqlite.Row
        # Habilita validação das constraints e integridade referencial.
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._create_schema()

    async def _create_schema(self) -> None:
        """Cria a tabela `interactions` e os índices obrigatórios."""
        await self.connection.executescript(SCHEMA_SQL)
        await self.connection.commit()

    async def close(self) -> None:
        """Fecha a conexão, se aberta."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None


# --- Singleton de ciclo de vida da aplicação ---------------------------------

_database: Database | None = None


def get_database() -> Database:
    """Retorna a instância singleton do banco, exigindo init prévia."""
    if _database is None:
        raise RuntimeError(
            "Banco de dados não inicializado. Chame init_database() na startup."
        )
    return _database


async def init_database(db_path: str = DEFAULT_DB_PATH) -> Database:
    """Inicializa o singleton do banco e abre a conexão."""
    global _database
    if _database is None:
        _database = Database(db_path)
    await _database.connect()
    return _database


async def close_database() -> None:
    """Fecha e descarta o singleton do banco."""
    global _database
    if _database is not None:
        await _database.close()
        _database = None
