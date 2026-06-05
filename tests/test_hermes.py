"""Tests for HermesClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aurion.hermes import HermesClient, HermesError, HermesResponse


@pytest.fixture
def client():
    return HermesClient(api_url="http://localhost:9999/v1", timeout=5.0)


@pytest.mark.asyncio
async def test_send_command_success(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Comando executado"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    mock_resp.raise_for_status.return_value = None

    mock_async_client = AsyncMock()
    mock_async_client.post = AsyncMock(return_value=mock_resp)
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=None)

    with patch("aurion.hermes.httpx.AsyncClient", return_value=mock_async_client):
        result = await client.send_command("test command")

    assert isinstance(result, dict)
    assert result["response"] == "Comando executado"
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_send_command_http_502(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 502
    exc = httpx.HTTPStatusError(
        "Bad Gateway", request=MagicMock(), response=mock_resp
    )

    mock_async_client = AsyncMock()
    mock_async_client.post = AsyncMock(side_effect=exc)
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=None)

    with patch("aurion.hermes.httpx.AsyncClient", return_value=mock_async_client):
        with pytest.raises(HermesError):
            await client.send_command("fail command")


@pytest.mark.asyncio
async def test_send_command_retry_once(client):
    mock_async_client = AsyncMock()
    mock_async_client.__aenter__ = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    mock_async_client.__aexit__ = AsyncMock(return_value=None)

    with patch("aurion.hermes.httpx.AsyncClient", return_value=mock_async_client):
        with pytest.raises(HermesError):
            await client.send_command("retry test")

    assert mock_async_client.__aenter__.call_count == 2


@pytest.mark.asyncio
async def test_format_for_tts(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "São quinze horas e trinta minutos."}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 8},
    }
    mock_resp.raise_for_status.return_value = None

    mock_async_client = AsyncMock()
    mock_async_client.post = AsyncMock(return_value=mock_resp)
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=None)

    with patch("aurion.hermes.httpx.AsyncClient", return_value=mock_async_client):
        result = await client.format_for_tts("São 15:30.")

    assert result == "São quinze horas e trinta minutos."
    payload = mock_async_client.post.call_args.kwargs["json"]
    assert payload["messages"][0]["role"] == "system"
    assert "TTS" in payload["messages"][0]["content"]
    assert "15:30" in payload["messages"][1]["content"]


@pytest.mark.asyncio
async def test_format_for_tts_disabled(client):
    with patch("aurion.hermes.os.getenv", return_value="false"):
        result = await client.format_for_tts("Texto original.")
    assert result == "Texto original."


@pytest.mark.asyncio
async def test_custom_timeout():
    c = HermesClient(api_url="http://localhost:9999/v1", timeout=60.0)
    assert c.timeout == 60.0


def test_load_hermes_url_from_env():
    with patch("aurion.hermes.os.getenv", return_value="http://custom-hermes:3000/v1"):
        url = HermesClient._load_api_url()
    assert url == "http://custom-hermes:3000/v1"


def test_load_hermes_url_default():
    with patch("aurion.hermes.os.getenv", return_value=None):
        url = HermesClient._load_api_url()
    assert url is None


def test_hermes_response_model_valid():
    resp = HermesResponse(**{"response": "Hello", "status": "success"})
    assert resp.response == "Hello"
    assert resp.status == "success"


def test_hermes_response_model_invalid():
    with pytest.raises(Exception):
        HermesResponse(**{"response": "Hello"})


def test_hermes_error_attributes():
    err = HermesError("Connection failed", status_code=502)
    assert err.message == "Connection failed"
    assert err.status_code == 502


@pytest.mark.asyncio
async def test_send_command_with_history():
    client = HermesClient(api_url="http://localhost:9999/v1", timeout=5.0)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Sim, chove amanhã."}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    mock_resp.raise_for_status.return_value = None

    mock_async_client = AsyncMock()
    mock_async_client.post = AsyncMock(return_value=mock_resp)
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=None)

    history = [
        {"role": "user", "content": "qual a previsao do tempo"},
        {"role": "assistant", "content": "Hoje está ensolarado."},
    ]

    with patch("aurion.hermes.httpx.AsyncClient", return_value=mock_async_client):
        result = await client.send_command(
            "e amanha?", voice_mode=True, history=history
        )

    assert result["response"] == "Sim, chove amanhã."
    payload = mock_async_client.post.call_args.kwargs["json"]
    roles = [m["role"] for m in payload["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert payload["messages"][-1]["content"] == "e amanha?"
