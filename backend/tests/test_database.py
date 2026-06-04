"""Testes de integração da conexão/ciclo de vida do banco (arquivo real)."""

import pytest

from db.database import (
    Database,
    close_database,
    get_database,
    init_database,
)
from db.models import InteractionCreate
from db.repo import InteractionRepository


async def test_connection_required_before_use():
    db = Database(":memory:")
    with pytest.raises(RuntimeError):
        _ = db.connection


async def test_singleton_lifecycle():
    # Antes de inicializar, get_database deve falhar.
    with pytest.raises(RuntimeError):
        get_database()

    db = await init_database(":memory:")
    assert get_database() is db

    # init_database é idempotente: não recria o singleton.
    db2 = await init_database(":memory:")
    assert db2 is db

    await close_database()
    with pytest.raises(RuntimeError):
        get_database()


async def test_real_file_persistence(tmp_path):
    """Persistência real: dados sobrevivem a fechar/reabrir o arquivo SQLite."""
    db_file = tmp_path / "aurion_test.db"

    db = Database(str(db_file))
    await db.connect()
    repo = InteractionRepository(db)
    created = await repo.create_interaction(
        InteractionCreate(channel="local", input_text="persistir isto")
    )
    await db.close()

    assert db_file.exists()

    # Reabre o mesmo arquivo e confirma que o registro persistiu.
    db_reopened = Database(str(db_file))
    await db_reopened.connect()
    repo_reopened = InteractionRepository(db_reopened)
    fetched = await repo_reopened.get_interaction_by_id(created.id)
    await db_reopened.close()

    assert fetched is not None
    assert fetched.input_text == "persistir isto"
