"""Fixtures compartilhadas dos testes da camada de persistência."""

import pytest_asyncio

from db.database import Database
from db.repo import InteractionRepository


@pytest_asyncio.fixture
async def database():
    """Banco em memória, isolado por teste, com esquema criado."""
    db = Database(":memory:")
    await db.connect()
    try:
        yield db
    finally:
        await db.close()


@pytest_asyncio.fixture
async def repo(database):
    """Repositório de interações apontando para o banco em memória."""
    return InteractionRepository(database)
