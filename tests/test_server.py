"""Tests for FastAPI server endpoints."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from aurion.database import init_db


def _setup_test_db():
    """Creates a temp DB file with tables and seeds."""
    path = os.path.join(tempfile.gettempdir(), "aurion_server_test.db")
    init_db(path)
    return path


def _teardown_test_db(path):
    try:
        os.unlink(path)
    except OSError:
        pass


# Global test DB path
_test_db_path = None


@pytest.fixture(scope="session", autouse=True)
def session_db():
    global _test_db_path
    _test_db_path = _setup_test_db()
    yield _test_db_path
    _teardown_test_db(_test_db_path)


@pytest.fixture
def app(session_db):
    with patch("aurion.server._db_path", session_db), \
         patch("aurion.server._hermes_client") as mock_hermes, \
         patch("aurion.server._tts_service") as mock_tts, \
         patch("aurion.server._listener") as mock_listener, \
         patch("aurion.server._discovery") as mock_disc:

        mock_hermes.base_url = "http://localhost:9999"
        mock_hermes.send_command = MagicMock(return_value={
            "response": "ok", "status": "success"
        })
        mock_tts.list_voices.return_value = [
            {"id": "v1", "name": "Test Voice", "lang": "pt-BR"}
        ]
        mock_tts.set_voice = MagicMock()
        mock_tts.test_voice = MagicMock()
        mock_tts.speak = MagicMock()
        mock_listener._running = False
        mock_listener.start = MagicMock()
        mock_listener.stop = MagicMock()
        mock_disc.services = {}
        mock_disc.health_check.return_value = {}

        from aurion import server as aurion_server
        yield aurion_server.app


@pytest.fixture
async def client(app, session_db):
    with patch("aurion.server._db_path", session_db), \
         patch("aurion.server._hermes_client") as mock_hermes, \
         patch("aurion.server._tts_service") as mock_tts, \
         patch("aurion.server._listener") as mock_listener, \
         patch("aurion.server._discovery") as mock_disc:

        mock_hermes.base_url = "http://localhost:9999"
        mock_hermes.send_command = MagicMock(return_value={
            "response": "ok", "status": "success"
        })
        mock_tts.list_voices.return_value = [
            {"id": "v1", "name": "Test Voice", "lang": "pt-BR"}
        ]
        mock_tts.set_voice = MagicMock()
        mock_tts.test_voice = MagicMock()
        mock_tts.speak = MagicMock()
        mock_listener._running = False
        mock_listener.start = MagicMock()
        mock_listener.stop = MagicMock()
        mock_disc.services = {}
        mock_disc.health_check.return_value = {}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.mark.asyncio
async def test_status_endpoint(client):
    resp = await client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "listening" in data
    assert "hermes_connected" in data


@pytest.mark.asyncio
async def test_history_endpoint(client):
    resp = await client.get("/api/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_logs_endpoint(client):
    resp = await client.get("/api/logs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_voices_endpoint(client):
    resp = await client.get("/api/voices")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_listen_start(client):
    resp = await client.post("/api/listen/start")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_listen_stop(client):
    resp = await client.post("/api/listen/stop")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_config_endpoint(client):
    resp = await client.get("/api/config")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_config_port_endpoint(client):
    resp = await client.get("/api/config/port")
    assert resp.status_code == 200
    assert "port" in resp.json()


@pytest.mark.asyncio
async def test_update_config(client):
    resp = await client.post("/api/config", json={"key": "test_key", "value": "test_value"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_voice_test(client):
    resp = await client.post("/api/voices/test", json={"voice_id": "v1", "text": "test"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_command_endpoint_success(client):
    """POST /api/command com sucesso retorna resposta do Hermes."""
    from unittest.mock import AsyncMock

    with patch("aurion.server._hermes_client") as mock_hermes:
        mock_hermes.send_command = AsyncMock(return_value={
            "response": "Hello world", "status": "success"
        })
        resp = await client.post("/api/command", json={
            "input_text": "hello", "source": "web"
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == "Hello world"


@pytest.mark.asyncio
async def test_command_endpoint_hermes_error(client):
    """POST /api/command retorna 502 quando Hermes falha."""
    from aurion.hermes import HermesError

    with patch("aurion.server._hermes_client") as mock_hermes:
        mock_hermes.send_command = MagicMock(side_effect=HermesError("Down"))
        resp = await client.post("/api/command", json={
            "input_text": "fail command", "source": "web"
        })

    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_history_detail_not_found(client):
    with patch("aurion.server.list_commands", return_value=[]):
        resp = await client.get("/api/history/9999")
    assert resp.status_code == 404
