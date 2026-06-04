"""Testes unitários do repositório de interações e do esquema do banco."""

import uuid

import aiosqlite
import pytest

from db.database import Database
from db.models import InteractionCreate
from db.repo import InteractionRepository


async def _insert_raw(
    database: Database,
    interaction_id: str,
    timestamp: str,
    channel: str = "local",
    status: str = "success",
    input_text: str = "x",
    output_text: str | None = None,
) -> None:
    """Insere uma linha diretamente, contornando os modelos Pydantic.

    Usado para testar ordenação determinística e as constraints CHECK do banco.
    """
    await database.connection.execute(
        "INSERT INTO interactions "
        "(id, timestamp, channel, input_text, output_text, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (interaction_id, timestamp, channel, input_text, output_text, status),
    )
    await database.connection.commit()


# --- CREATE / READ -----------------------------------------------------------


async def test_create_interaction_inserts_row(repo, database):
    created = await repo.create_interaction(
        InteractionCreate(channel="local", input_text="liste os arquivos")
    )

    # ID gerado é um UUID válido e timestamp é timezone-aware.
    assert uuid.UUID(created.id)
    assert created.timestamp.tzinfo is not None
    assert created.status == "success"

    # Verifica o INSERT consultando diretamente o banco.
    async with database.connection.execute(
        "SELECT COUNT(*) AS c FROM interactions WHERE id = ?", (created.id,)
    ) as cursor:
        row = await cursor.fetchone()
    assert row["c"] == 1


async def test_get_interaction_by_id_returns_record(repo):
    created = await repo.create_interaction(
        InteractionCreate(
            channel="web",
            input_text="qual a hora",
            output_text="são 10h",
            duration_ms=120,
            status="success",
        )
    )
    fetched = await repo.get_interaction_by_id(created.id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.input_text == "qual a hora"
    assert fetched.output_text == "são 10h"
    assert fetched.channel == "web"
    assert fetched.duration_ms == 120


async def test_get_interaction_by_id_not_found(repo):
    assert await repo.get_interaction_by_id("inexistente") is None


# --- UPDATE ------------------------------------------------------------------


async def test_update_interaction_changes_fields(repo):
    created = await repo.create_interaction(
        InteractionCreate(channel="web", input_text="processando", status="success")
    )

    updated = await repo.update_interaction(
        created.id,
        output_text="tarefa concluída",
        duration_ms=345,
        status="success",
    )

    assert updated is not None
    assert updated.id == created.id
    assert updated.output_text == "tarefa concluída"
    assert updated.duration_ms == 345
    # Persistiu no banco.
    refetched = await repo.get_interaction_by_id(created.id)
    assert refetched.output_text == "tarefa concluída"


async def test_update_interaction_not_found(repo):
    assert await repo.update_interaction("inexistente", status="error") is None


async def test_update_interaction_rejects_unknown_field(repo):
    created = await repo.create_interaction(
        InteractionCreate(channel="local", input_text="x")
    )
    with pytest.raises(ValueError):
        await repo.update_interaction(created.id, input_text="imutável")


async def test_update_interaction_no_fields_returns_current(repo):
    created = await repo.create_interaction(
        InteractionCreate(channel="local", input_text="sem mudanças")
    )
    result = await repo.update_interaction(created.id)
    assert result is not None
    assert result.id == created.id


# --- LIST / PAGINAÇÃO / BUSCA ------------------------------------------------


async def test_list_interactions_pagination(repo, database):
    for i in range(5):
        await _insert_raw(
            database, f"id-{i}", f"2026-06-04T10:0{i}:00+00:00", input_text=f"cmd {i}"
        )

    page = await repo.list_interactions(limit=2, offset=0)
    assert len(page) == 2
    # DESC por timestamp: id-4 e id-3 primeiro.
    assert [p.id for p in page] == ["id-4", "id-3"]

    page2 = await repo.list_interactions(limit=2, offset=2)
    assert [p.id for p in page2] == ["id-2", "id-1"]


async def test_list_interactions_search_like(repo):
    await repo.create_interaction(
        InteractionCreate(channel="local", input_text="abrir o navegador")
    )
    await repo.create_interaction(
        InteractionCreate(channel="local", input_text="fechar a janela")
    )
    await repo.create_interaction(
        InteractionCreate(
            channel="web", input_text="tocar música", output_text="navegador aberto"
        )
    )

    # Busca por 'navegador' deve casar em input_text e output_text.
    results = await repo.list_interactions(search="navegador")
    texts = {r.input_text for r in results}
    assert "abrir o navegador" in texts
    assert "tocar música" in texts  # casou via output_text
    assert "fechar a janela" not in texts


# --- FILTROS -----------------------------------------------------------------


async def test_get_interactions_by_channel(repo):
    await repo.create_interaction(InteractionCreate(channel="local", input_text="a"))
    await repo.create_interaction(InteractionCreate(channel="web", input_text="b"))
    await repo.create_interaction(InteractionCreate(channel="web", input_text="c"))

    web = await repo.get_interactions_by_channel("web")
    assert len(web) == 2
    assert all(r.channel == "web" for r in web)


async def test_get_interactions_by_status(repo):
    await repo.create_interaction(
        InteractionCreate(channel="local", input_text="a", status="success")
    )
    await repo.create_interaction(
        InteractionCreate(
            channel="local", input_text="b", status="error", error_message="falhou"
        )
    )
    await repo.create_interaction(
        InteractionCreate(channel="local", input_text="c", status="timeout")
    )

    errors = await repo.get_interactions_by_status("error")
    assert len(errors) == 1
    assert errors[0].status == "error"
    assert errors[0].error_message == "falhou"


# --- DELETE ------------------------------------------------------------------


async def test_delete_all_interactions(repo):
    for _ in range(3):
        await repo.create_interaction(
            InteractionCreate(channel="local", input_text="x")
        )

    deleted = await repo.delete_all_interactions()
    assert deleted == 3
    assert await repo.list_interactions() == []


# --- ORDENAÇÃO ---------------------------------------------------------------


async def test_order_desc_by_timestamp(repo, database):
    await _insert_raw(database, "old", "2026-06-01T08:00:00+00:00")
    await _insert_raw(database, "new", "2026-06-04T08:00:00+00:00")
    await _insert_raw(database, "mid", "2026-06-02T08:00:00+00:00")

    ordered = await repo.list_interactions()
    assert [r.id for r in ordered] == ["new", "mid", "old"]

    recent = await repo.get_recent_interactions(limit=2)
    assert [r.id for r in recent] == ["new", "mid"]


# --- CONSTRAINTS CHECK -------------------------------------------------------


async def test_check_constraint_channel(database):
    with pytest.raises(aiosqlite.IntegrityError):
        await _insert_raw(
            database, "bad", "2026-06-04T08:00:00+00:00", channel="invalido"
        )


async def test_check_constraint_status(database):
    with pytest.raises(aiosqlite.IntegrityError):
        await _insert_raw(
            database, "bad", "2026-06-04T08:00:00+00:00", status="invalido"
        )


# --- ESQUEMA / ÍNDICES -------------------------------------------------------


async def test_table_created_automatically(database):
    async with database.connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='interactions'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row is not None
    assert row["name"] == "interactions"


async def test_required_indexes_created(database):
    async with database.connection.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    ) as cursor:
        rows = await cursor.fetchall()
    names = {r["name"] for r in rows}
    assert {
        "idx_interactions_timestamp",
        "idx_interactions_channel",
        "idx_interactions_status",
    }.issubset(names)


async def test_pragma_index_list_reports_indexes(database):
    async with database.connection.execute(
        "PRAGMA index_list('interactions')"
    ) as cursor:
        rows = await cursor.fetchall()
    index_names = {r["name"] for r in rows}
    assert "idx_interactions_timestamp" in index_names
