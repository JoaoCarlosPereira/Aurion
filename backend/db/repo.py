"""Repository pattern assíncrono para a tabela `interactions`.

Concentra todas as operações de persistência de interações (CRUD e consultas
filtradas), isolando o restante da aplicação dos detalhes de SQL/aiosqlite.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import aiosqlite

from db.database import Database
from db.models import Channel, Interaction, InteractionCreate, Status

# Colunas na mesma ordem do esquema, reutilizadas em SELECT/INSERT.
_COLUMNS = (
    "id",
    "timestamp",
    "channel",
    "input_text",
    "output_text",
    "output_audio_url",
    "duration_ms",
    "status",
    "error_message",
)
_COLUMNS_SQL = ", ".join(_COLUMNS)


def _row_to_interaction(row: aiosqlite.Row) -> Interaction:
    """Converte uma linha do banco em um modelo `Interaction`."""
    return Interaction(
        id=row["id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        channel=row["channel"],
        input_text=row["input_text"],
        output_text=row["output_text"],
        output_audio_url=row["output_audio_url"],
        duration_ms=row["duration_ms"],
        status=row["status"],
        error_message=row["error_message"],
    )


class InteractionRepository:
    """Operações de persistência para interações."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def _conn(self) -> aiosqlite.Connection:
        return self._db.connection

    async def create_interaction(self, data: InteractionCreate) -> Interaction:
        """Insere uma nova interação gerando `id` (UUID) e `timestamp` (UTC)."""
        interaction = Interaction(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            **data.model_dump(),
        )
        await self._conn.execute(
            f"INSERT INTO interactions ({_COLUMNS_SQL}) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                interaction.id,
                interaction.timestamp.isoformat(),
                interaction.channel,
                interaction.input_text,
                interaction.output_text,
                interaction.output_audio_url,
                interaction.duration_ms,
                interaction.status,
                interaction.error_message,
            ),
        )
        await self._conn.commit()
        return interaction

    # Campos que podem ser atualizados após a criação (ex.: completar a resposta
    # do Hermes em um comando inicialmente registrado como "processing").
    _UPDATABLE_FIELDS = (
        "output_text",
        "output_audio_url",
        "duration_ms",
        "status",
        "error_message",
    )

    async def update_interaction(
        self, interaction_id: str, **fields: object
    ) -> Interaction | None:
        """Atualiza campos mutáveis de uma interação e retorna o registro atualizado.

        Retorna `None` se a interação não existir. Levanta `ValueError` se algum
        campo informado não for atualizável.
        """
        invalid = set(fields) - set(self._UPDATABLE_FIELDS)
        if invalid:
            raise ValueError(f"Campos não atualizáveis: {sorted(invalid)}")
        if not fields:
            return await self.get_interaction_by_id(interaction_id)

        assignments = ", ".join(f"{col} = ?" for col in fields)
        params = list(fields.values())
        params.append(interaction_id)
        async with self._conn.execute(
            f"UPDATE interactions SET {assignments} WHERE id = ?", params
        ) as cursor:
            updated = cursor.rowcount
        await self._conn.commit()
        if updated == 0:
            return None
        return await self.get_interaction_by_id(interaction_id)

    async def get_interaction_by_id(self, interaction_id: str) -> Interaction | None:
        """Retorna a interação pelo ID ou `None` se não existir."""
        async with self._conn.execute(
            f"SELECT {_COLUMNS_SQL} FROM interactions WHERE id = ?",
            (interaction_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return _row_to_interaction(row) if row is not None else None

    async def list_interactions(
        self,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
    ) -> list[Interaction]:
        """Lista interações paginadas (DESC por timestamp), com busca opcional.

        A busca por texto aplica `LIKE` sobre `input_text` e `output_text`.
        """
        sql = f"SELECT {_COLUMNS_SQL} FROM interactions"
        params: list[object] = []
        if search:
            sql += " WHERE input_text LIKE ? OR output_text LIKE ?"
            term = f"%{search}%"
            params.extend([term, term])
        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self._conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_interaction(row) for row in rows]

    async def delete_all_interactions(self) -> int:
        """Remove todas as interações e retorna a quantidade removida."""
        async with self._conn.execute(
            "DELETE FROM interactions"
        ) as cursor:
            deleted = cursor.rowcount
        await self._conn.commit()
        return deleted

    async def get_interactions_by_channel(
        self,
        channel: Channel,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Interaction]:
        """Lista interações de um canal específico, DESC por timestamp."""
        async with self._conn.execute(
            f"SELECT {_COLUMNS_SQL} FROM interactions WHERE channel = ? "
            f"ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (channel, limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_interaction(row) for row in rows]

    async def get_interactions_by_status(
        self,
        status: Status,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Interaction]:
        """Lista interações de um status específico, DESC por timestamp."""
        async with self._conn.execute(
            f"SELECT {_COLUMNS_SQL} FROM interactions WHERE status = ? "
            f"ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (status, limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_interaction(row) for row in rows]

    async def get_recent_interactions(self, limit: int = 10) -> list[Interaction]:
        """Retorna as interações mais recentes (DESC por timestamp)."""
        async with self._conn.execute(
            f"SELECT {_COLUMNS_SQL} FROM interactions "
            f"ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_interaction(row) for row in rows]
