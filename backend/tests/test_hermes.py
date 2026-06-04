"""Testes do Hermes Bridge e do endpoint POST /api/test/hermes.

Cobrem: envio de comando com sucesso, retry com backoff exponencial, erros HTTP
(401, 404, 500), timeout, conexão recusada, ``test_connection`` (sucesso e
falha), envio do header ``Authorization`` e parsing da resposta do Hermes.

Nenhum teste usa rede real: o ``httpx.AsyncClient`` é injetado com um
``httpx.MockTransport`` (handler determinístico) via ``_create_client``, e o
``asyncio.sleep`` do backoff é substituído por um stub que apenas registra os
atrasos.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import test as test_api
from config.models import HermesConfig
from svc.hermes_bridge import (
    ERR_HTTP,
    ERR_TIMEOUT,
    ERR_UNAUTHORIZED,
    ERR_UNAVAILABLE,
    HERMES_COMMAND_PATH,
    HermesBridge,
    HermesError,
    HermesResponse,
)


# --- Helpers / fakes ---------------------------------------------------------


def _patch_client(bridge: HermesBridge, handler, *, captured: dict | None = None):
    """Injeta um ``httpx.AsyncClient`` com ``MockTransport`` no bridge.

    ``handler`` recebe um ``httpx.Request`` e devolve um ``httpx.Response`` ou
    levanta uma exceção de transporte (ex.: ``httpx.ConnectError``). Quando
    ``captured`` é informado, a última requisição vista é armazenada nele.
    """

    def _wrapped(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured["request"] = request
        return handler(request)

    transport = httpx.MockTransport(_wrapped)

    def _factory():
        return httpx.AsyncClient(
            transport=transport,
            timeout=bridge._timeout,
            headers=bridge._build_headers(),
        )

    bridge._create_client = _factory  # type: ignore[assignment]


def _patch_sleep(monkeypatch) -> list[float]:
    """Substitui ``asyncio.sleep`` no módulo do bridge por um stub sem atraso.

    Retorna a lista de atrasos solicitados, para inspeção do backoff.
    """
    delays: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        delays.append(delay)

    import svc.hermes_bridge as hb

    monkeypatch.setattr(hb.asyncio, "sleep", _fake_sleep)
    return delays


@pytest.fixture
def bridge() -> HermesBridge:
    """Bridge com configuração e parâmetros de backoff determinísticos."""
    config = HermesConfig(endpoint="http://hermes.test:8080", auth_token="segredo-123")
    return HermesBridge(config, backoff_base=0.5, backoff_factor=2.0, max_retries=3)


# --- send_command: sucesso ---------------------------------------------------


async def test_send_command_sucesso_200(bridge):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"reply": "Olá do Hermes"})

    _patch_client(bridge, handler, captured=captured)

    result = await bridge.send_command("qual a previsão do tempo?")

    assert isinstance(result, HermesResponse)
    assert result.reply == "Olá do Hermes"
    assert result.status_code == 200
    # URL e corpo enviados conforme TechSpec.
    assert str(captured["request"].url) == f"http://hermes.test:8080{HERMES_COMMAND_PATH}"
    assert captured["request"].method == "POST"


async def test_header_authorization_enviado(bridge):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"reply": "ok"})

    _patch_client(bridge, handler, captured=captured)
    await bridge.send_command("oi")

    assert captured["request"].headers["Authorization"] == "Bearer segredo-123"


async def test_header_authorization_bearer_preservado():
    bridge = HermesBridge(
        HermesConfig(endpoint="http://h:8080", auth_token="Bearer ja-formatado")
    )
    captured: dict = {}
    _patch_client(
        bridge,
        lambda req: httpx.Response(200, json={"reply": "ok"}),
        captured=captured,
    )
    await bridge.send_command("oi")
    assert captured["request"].headers["Authorization"] == "Bearer ja-formatado"


# --- parsing da resposta -----------------------------------------------------


async def test_parsing_campos_alternativos(bridge):
    _patch_client(bridge, lambda req: httpx.Response(200, json={"response": "via response"}))
    result = await bridge.send_command("x")
    assert result.reply == "via response"


async def test_parsing_resposta_texto_puro(bridge):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="resposta crua", headers={"content-type": "text/plain"})

    _patch_client(bridge, handler)
    result = await bridge.send_command("x")
    assert result.reply == "resposta crua"


async def test_parsing_resposta_sem_campo_texto(bridge):
    _patch_client(bridge, lambda req: httpx.Response(200, json={"foo": "bar"}))
    with pytest.raises(HermesError) as exc:
        await bridge.send_command("x")
    assert exc.value.code == "HERMES_INVALID_RESPONSE"


# --- retry e backoff exponencial ---------------------------------------------


async def test_retry_backoff_exponencial_falha_3x(bridge, monkeypatch):
    delays = _patch_sleep(monkeypatch)
    chamadas = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas["n"] += 1
        return httpx.Response(500, json={"erro": "interno"})

    _patch_client(bridge, handler)

    with pytest.raises(HermesError) as exc:
        await bridge.send_command("comando")

    # 3 tentativas executadas (max_retries=3).
    assert chamadas["n"] == 3
    # Backoff exponencial: base e base*factor entre as tentativas (2 esperas).
    assert delays == [0.5, 1.0]
    assert exc.value.code == ERR_UNAVAILABLE


async def test_retry_sucesso_apos_falhas(bridge, monkeypatch):
    _patch_sleep(monkeypatch)
    estado = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        estado["n"] += 1
        if estado["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"reply": "recuperado"})

    _patch_client(bridge, handler)

    result = await bridge.send_command("comando")

    assert result.reply == "recuperado"
    assert estado["n"] == 3


async def test_retry_429_e_reenviado(bridge, monkeypatch):
    delays = _patch_sleep(monkeypatch)
    estado = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        estado["n"] += 1
        if estado["n"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json={"reply": "ok"})

    _patch_client(bridge, handler)
    result = await bridge.send_command("x")

    assert result.reply == "ok"
    assert estado["n"] == 2
    assert delays == [0.5]


# --- erros HTTP definitivos (não reenviados) ---------------------------------


async def test_erro_401_unauthorized_sem_retry(bridge, monkeypatch):
    delays = _patch_sleep(monkeypatch)
    estado = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        estado["n"] += 1
        return httpx.Response(401)

    _patch_client(bridge, handler)

    with pytest.raises(HermesError) as exc:
        await bridge.send_command("x")

    assert exc.value.code == ERR_UNAUTHORIZED
    # 4xx é definitivo: apenas uma chamada, sem backoff.
    assert estado["n"] == 1
    assert delays == []


async def test_erro_404_sem_retry(bridge, monkeypatch):
    _patch_sleep(monkeypatch)
    estado = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        estado["n"] += 1
        return httpx.Response(404)

    _patch_client(bridge, handler)

    with pytest.raises(HermesError) as exc:
        await bridge.send_command("x")

    assert exc.value.code == ERR_HTTP
    assert estado["n"] == 1


async def test_erro_500_apos_retries(bridge, monkeypatch):
    _patch_sleep(monkeypatch)
    _patch_client(bridge, lambda req: httpx.Response(500))

    with pytest.raises(HermesError) as exc:
        await bridge.send_command("x")

    assert exc.value.code == ERR_UNAVAILABLE
    assert exc.value.error.details["status_code"] == 500


# --- exceções de rede --------------------------------------------------------


async def test_timeout_de_conexao(bridge, monkeypatch):
    _patch_sleep(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("tempo esgotado", request=request)

    _patch_client(bridge, handler)

    with pytest.raises(HermesError) as exc:
        await bridge.send_command("x")

    assert exc.value.code == ERR_TIMEOUT


async def test_conexao_recusada(bridge, monkeypatch):
    _patch_sleep(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexão recusada", request=request)

    _patch_client(bridge, handler)

    with pytest.raises(HermesError) as exc:
        await bridge.send_command("x")

    assert exc.value.code == ERR_UNAVAILABLE


async def test_mensagem_vazia_levanta_erro(bridge):
    with pytest.raises(HermesError) as exc:
        await bridge.send_command("   ")
    assert exc.value.code == "HERMES_INVALID_RESPONSE"


# --- test_connection ---------------------------------------------------------


async def test_test_connection_sucesso(bridge):
    captured: dict = {}
    _patch_client(
        bridge, lambda req: httpx.Response(200, json={"status": "ok"}), captured=captured
    )

    assert await bridge.test_connection() is True
    assert captured["request"].method == "GET"


async def test_test_connection_falha(bridge, monkeypatch):
    _patch_sleep(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota", request=request)

    _patch_client(bridge, handler)

    assert await bridge.test_connection() is False


async def test_test_connection_status_erro(bridge, monkeypatch):
    _patch_sleep(monkeypatch)
    _patch_client(bridge, lambda req: httpx.Response(500))

    assert await bridge.test_connection() is False


# --- endpoint POST /api/test/hermes ------------------------------------------


def test_endpoint_hermes_sucesso():
    """POST /api/test/hermes retorna success=True quando a conexão funciona."""
    app = FastAPI()
    app.include_router(test_api.router)

    config = HermesConfig(endpoint="http://hermes.test:9000", auth_token="t")

    # Bridge com cliente mockado (sem rede real).
    bridge_obj = HermesBridge(config)
    _patch_client(bridge_obj, lambda req: httpx.Response(200, json={"status": "ok"}))

    app.dependency_overrides[test_api.get_config_manager_dep] = (
        lambda: _ManagerStub(config)
    )
    app.dependency_overrides[test_api.get_hermes_bridge_factory] = (
        lambda: (lambda manager: bridge_obj)
    )

    client = TestClient(app)
    resp = client.post("/api/test/hermes")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["endpoint"] == "http://hermes.test:9000"


def test_endpoint_hermes_falha():
    """POST /api/test/hermes retorna success=False quando a conexão falha."""
    app = FastAPI()
    app.include_router(test_api.router)

    config = HermesConfig(endpoint="http://hermes.test:9000", auth_token="t")
    bridge_obj = HermesBridge(config, max_retries=1)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("recusada", request=request)

    _patch_client(bridge_obj, handler)

    app.dependency_overrides[test_api.get_config_manager_dep] = (
        lambda: _ManagerStub(config)
    )
    app.dependency_overrides[test_api.get_hermes_bridge_factory] = (
        lambda: (lambda manager: bridge_obj)
    )

    client = TestClient(app)
    resp = client.post("/api/test/hermes")

    assert resp.status_code == 200
    assert resp.json()["success"] is False


class _ManagerStub:
    """Stub mínimo de ConfigManager para o endpoint (apenas ``get``)."""

    def __init__(self, hermes: HermesConfig) -> None:
        from config.models import AppConfig

        self._config = AppConfig(hermes=hermes)

    async def get(self):
        return self._config


# --- factory padrão do bridge ------------------------------------------------


def test_factory_padrao_usa_config_do_manager():
    """A factory padrão constrói um HermesBridge com o endpoint da config."""
    config = HermesConfig(endpoint="http://h:7000", auth_token="abc")
    manager = _ManagerStub(config)

    factory = test_api.get_hermes_bridge_factory()
    bridge_obj = factory(manager)

    assert isinstance(bridge_obj, HermesBridge)
    assert bridge_obj.endpoint == "http://h:7000"


def test_factory_padrao_sem_config_usa_padrao():
    """Sem configuração carregada, a factory cai para a HermesConfig padrão."""

    class _Empty:
        _config = None

    factory = test_api.get_hermes_bridge_factory()
    bridge_obj = factory(_Empty())

    assert isinstance(bridge_obj, HermesBridge)
    # Endpoint padrão da HermesConfig.
    assert bridge_obj.endpoint == "http://localhost:8080"
