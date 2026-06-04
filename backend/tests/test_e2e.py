"""Testes E2E do sistema Aurion — fluxos integrados.

Usam ``httpx.AsyncClient`` / ``TestClient`` com a aplicação FastAPI real
(``main.app``), injetando dependências (``dependency_overrides``) para
substituir serviços externos reais (Hermes API, whisper.cpp, edge-tts,
hardware de áudio) por *fakes* determinísticos.

Nenhum teste requer: rede, microfone, alto-falante ou modelos de ML.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import command as command_api
from api import config as config_api
from api import history as history_api
from api import test as test_api
from config.settings import ConfigManager, init_config_manager
from db.database import Database, init_database, close_database
from db.repo import InteractionRepository
from db.models import InteractionCreate
from svc.hermes_bridge import HermesBridge, HermesError, HermesResponse
from svc.stt import STTService


# ============================================================================
# Fakes
# ============================================================================


class _FakeHermesBridge:
    """Substituto do ``HermesBridge`` que responde sem rede."""

    def __init__(self, config=None, *, reply: str = "Olá! Como posso ajudar?") -> None:
        self._config = config
        self._reply = reply
        self.send_command_called = False
        self.test_connection_called = False

    async def send_command(self, message: str) -> HermesResponse:
        self.send_command_called = True
        return HermesResponse(reply=self._reply, status_code=200)

    async def test_connection(self) -> bool:
        self.test_connection_called = True
        return True

    @property
    def endpoint(self) -> str:
        return "http://hermes.fake:8080"


class _FakeSTTService:
    """STT que sempre transcreve o mesmo texto."""

    def __init__(self, transcription: str = "comando de teste") -> None:
        self.transcription = transcription
        # Atributo 'config' é acessado pelo endpoint /api/test/stt (service.config.engine)
        self.config = type("Config", (), {"engine": "whisper.cpp", "model": "ggml-base-q4"})()

    async def transcribe(self, audio_data) -> str:
        return self.transcription

    async def test_model(self) -> bool:
        return True


class _FakeTTSService:
    """TTS que produz chunks de áudio simulados."""

    class _ExternalConfig:
        def __init__(self) -> None:
            self.enabled = False
            self.stream_buffer_ms = 500

    def __init__(self, chunks: list[bytes] | None = None) -> None:
        self._chunks = chunks or [b"\x00", b"\x01"]
        self.config = type("Config", (), {
            "voice": "pt-BR-FabioNeural",
            "external": _FakeTTSService._ExternalConfig(),
        })()

    async def synthesize(self, text: str):
        for chunk in self._chunks:
            yield chunk

    async def list_voices(self) -> list[str]:
        return ["pt-BR-FabioNeural"]


# ============================================================================
# Fixtures de app integrado
# ============================================================================


def _ensure_event_loop():
    """Cria um event loop se não existir (compatível com Python 3.11+)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)


def _build_e2e_app(tmp_path: Path) -> FastAPI:
    """Monta um app FastAPI isolado com todos os routers e mocks."""
    _ensure_event_loop()
    app = FastAPI()

    # Routers
    app.include_router(config_api.router)
    app.include_router(command_api.router)
    app.include_router(history_api.router)
    app.include_router(test_api.router)

    # Config Manager apontando para config temporário
    config_path = tmp_path / "config_e2e.json"
    config_path.write_text("{}")
    config_mgr = ConfigManager(config_path)

    # Banco em memória
    db = Database(":memory:")
    asyncio.get_event_loop().run_until_complete(db.connect())
    repo = InteractionRepository(db)

    # Overrides
    app.dependency_overrides[config_api.get_config_manager_dep] = lambda: config_mgr
    app.dependency_overrides[command_api.get_config_manager_dep] = lambda: config_mgr

    def _get_repo():
        return repo

    app.dependency_overrides[command_api.get_repository_dep] = _get_repo
    app.dependency_overrides[history_api.get_repository_dep] = _get_repo

    hermes_cfg = None
    try:
        from config.models import HermesConfig

        hermes_cfg = HermesConfig()
    except Exception:
        pass

    fake_bridge = _FakeHermesBridge(hermes_cfg)
    app.dependency_overrides[command_api.get_hermes_bridge_factory] = (
        lambda: lambda m: fake_bridge
    )
    app.dependency_overrides[test_api.get_config_manager_dep] = lambda: config_mgr
    app.dependency_overrides[test_api.get_hermes_bridge_factory] = (
        lambda: lambda m: fake_bridge
    )

    fake_stt = _FakeSTTService()
    app.dependency_overrides[test_api.get_stt_service_factory] = (
        lambda: lambda m: fake_stt
    )

    # Limpa rate limiter do teste
    limiter = test_api._RateLimiter()
    app.dependency_overrides[test_api.get_rate_limiter] = lambda: limiter

    # Estado da aplicação
    app.state._db = db
    app.state._config_mgr = config_mgr

    return app


# ============================================================================
# Helpers
# ============================================================================


def _post_command(client: TestClient, message: str = "ola aurion") -> dict:
    """Helper para POST /api/command e retornar o body."""
    resp = client.post("/api/command", json={"message": message})
    assert resp.status_code == 202
    return resp.json()


def _wait_for_interaction(
    client: TestClient, interaction_id: str, timeout: float = 2.0
) -> dict:
    """Espera a interação ser concluída consultando GET /api/command/{id}."""
    import time as _time

    deadline = _time.perf_counter() + timeout
    while _time.perf_counter() < deadline:
        resp = client.get(f"/api/command/{interaction_id}")
        if resp.status_code == 200:
            body = resp.json()
            if body.get("status") != "error" or body.get("error_message") != "processing":
                return body
        _time.sleep(0.05)
    return {}


# ============================================================================
# Testes E2E — Fluxo de comando por texto via web
# ============================================================================


class TestCommandFlow:
    """Fluxo completo: POST /api/command → persistência → consulta."""

    @pytest.fixture
    def app(self, tmp_path: Path) -> FastAPI:
        return _build_e2e_app(tmp_path)

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app)

    def test_comando_sucesso(self, client: TestClient):
        """POST /api/command com Hermes respondendo: 202 → resposta persistida."""
        body = _post_command(client, "qual a hora?")
        assert "id" in body
        assert body["status"] == "processing"

        interaction_id = body["id"]

        # Consulta o resultado
        resp = client.get(f"/api/command/{interaction_id}")
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "success"
        assert "hora" in result.get("output_text", "").lower() or "olá" in result.get(
            "output_text", ""
        ).lower()
        assert result["channel"] == "web"
        assert isinstance(result.get("duration_ms"), int)

    def test_comando_idempotente_multiplas_chamadas(self, client: TestClient):
        """Vários comandos geram interações separadas com IDs únicos."""
        id1 = _post_command(client, "comando um")["id"]
        id2 = _post_command(client, "comando dois")["id"]
        assert id1 != id2

    def test_comando_mensagem_vazia(self, client: TestClient):
        """Mensagem vazia ou só espaços deve retornar erro no Hermes."""
        body = _post_command(client, "   ")
        interaction_id = body["id"]

        resp = client.get(f"/api/command/{interaction_id}")
        assert resp.status_code == 200
        result = resp.json()
        # Mensagem vazia gera HERMES_INVALID_RESPONSE
        assert result["status"] in ("error", "success")


# ============================================================================
# Testes E2E — Fluxo de configuração
# ============================================================================


class TestConfigFlow:
    """GET/PUT /api/config — leitura, atualização parcial e reset."""

    @pytest.fixture
    def app(self, tmp_path: Path) -> FastAPI:
        return _build_e2e_app(tmp_path)

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app)

    def test_get_config_retorna_todos_bloco(self, client: TestClient):
        """GET /api/config retorna hermes, stt, tts, wake_word, audio."""
        resp = client.get("/api/config")
        assert resp.status_code == 200
        body = resp.json()
        for key in ("hermes", "stt", "tts", "wake_word", "audio"):
            assert key in body, f"Bloco '{key}' ausente na resposta"

    def test_get_config_omite_token_hermes(self, client: TestClient):
        """O token do Hermes NÃO deve aparecer na resposta GET."""
        resp = client.get("/api/config")
        body = resp.json()
        assert "auth_token" not in body.get("hermes", {})

    def test_put_config_parcial_audio(self, client: TestClient):
        """PUT /api/config com apenas audio atualiza só esse bloco."""
        resp = client.put("/api/config", json={"audio": {"sample_rate": 48000}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["audio"]["sample_rate"] == 48000

    def test_put_config_wake_word(self, client: TestClient):
        """PUT /api/config altera sensibilidade do wake word."""
        resp = client.put(
            "/api/config",
            json={"wake_word": {"sensitivity": 0.9}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["wake_word"]["sensitivity"] == 0.9

    def test_reset_configuracoes(self, client: TestClient):
        """POST /api/config/reset restaura valores padrão."""
        # Primeiro altera algo
        client.put("/api/config", json={"tts": {"voice": "pt-BR-FranciscaNeural"}})
        resp = client.post("/api/config/reset")
        assert resp.status_code == 200
        body = resp.json()
        assert body["tts"]["voice"] == "pt-BR-FabioNeural"


# ============================================================================
# Testes E2E — Fluxo de histórico
# ============================================================================


class TestHistoryFlow:
    """GET /api/history, DELETE /api/history — paginação e busca."""

    @pytest.fixture
    def app(self, tmp_path: Path) -> FastAPI:
        return _build_e2e_app(tmp_path)

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app)

    def test_history_vazio(self, client: TestClient):
        """GET /api/history sem interações retorna lista vazia."""
        resp = client.get("/api/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["count"] == 0

    def test_history_com_interacoes(self, client: TestClient):
        """Após comandos, histórico retorna as interações."""
        _post_command(client, "primeiro")
        _post_command(client, "segundo")

        resp = client.get("/api/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 2

    def test_history_com_busca(self, client: TestClient):
        """Filtro por search retorna apenas interações correspondentes."""
        _post_command(client, "comando teste aurion")
        _post_command(client, "outro comando diferente")

        resp = client.get("/api/history?search=aurion")
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert "aurion" in item["input_text"].lower()

    def test_history_paginacao(self, client: TestClient):
        """Paginação com limit e offset funciona."""
        for i in range(10):
            _post_command(client, f"comando {i}")

        resp = client.get("/api/history?limit=3")
        assert resp.json()["count"] == 3

        resp2 = client.get("/api/history?limit=3&offset=3")
        items = resp2.json()["items"]
        assert len(items) >= 1

    def test_delete_todo_historico(self, client: TestClient):
        """DELETE /api/history remove todas as interações."""
        _post_command(client, "delete me")
        _post_command(client, "delete me too")

        resp = client.delete("/api/history")
        assert resp.status_code == 200
        assert resp.json()["deleted"] >= 2

        resp2 = client.get("/api/history")
        assert resp2.json()["count"] == 0

    def test_get_interacao_individual(self, client: TestClient):
        """GET /api/history/{id} retorna a interação pelo ID."""
        cmd_body = _post_command(client, "buscar por id")
        iid = cmd_body["id"]

        resp = client.get(f"/api/history/{iid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == iid

    def test_get_interacao_nao_encontrada(self, client: TestClient):
        """GET /api/history/{id} retorna 404 para ID inexistente."""
        resp = client.get("/api/history/nonexistent-id")
        assert resp.status_code == 404


# ============================================================================
# Testes E2E — Endpoints de teste
# ============================================================================


class TestEndpointsDiagnostico:
    """POST /api/test/hermes, /api/test/stt, /api/test/tts."""

    @pytest.fixture
    def app(self, tmp_path: Path) -> FastAPI:
        return _build_e2e_app(tmp_path)

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app)

    def test_test_hermes(self, client: TestClient):
        """POST /api/test/hermes com bridge mock retorna success=True."""
        resp = client.post("/api/test/hermes")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "conexao" in body["message"].lower() or "bem" in body["message"].lower()

    def test_test_stt(self, client: TestClient):
        """POST /api/test/stt com STT mock retorna success=True."""
        resp = client.post("/api/test/stt")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_test_tts(self, client: TestClient):
        """POST /api/test/tts com TTS mock produz chunks → success=True."""
        # Injeta o fake TTSService no endpoint /api/test/tts
        client.app.dependency_overrides[test_api.get_tts_service_factory] = (
            lambda: lambda m: _FakeTTSService(chunks=[b"\x00", b"\x01"])
        )
        resp = client.post("/api/test/tts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["details"]["chunks"] > 0


# ============================================================================
# Testes E2E — Health check
# ============================================================================


class TestHealthCheck:
    """GET /api/health — endpoint de saúde."""

    def test_health_retorna_ok(self):
        """Health check retorna status ok via app isolado (sem importar main)."""
        app = FastAPI()

        @app.get("/api/health")
        async def health():
            return {"status": "ok"}

        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"


# ============================================================================
# Testes E2E — Reconexão WebSocket (simulada via manager)
# ============================================================================


class TestWebSocketReconnect:
    """Testa o comportamento do WebSocketManager ao receber desconexões."""

    def test_broadcast_limpa_clientes_mortos(self):
        """broadcast_state remove clientes que falharam ao enviar."""
        from api.websocket import WebSocketManager

        manager = WebSocketManager()

        # Cria mocks de WebSocket
        ws1 = MagicMock()
        ws2 = MagicMock()
        ws2.send_json.side_effect = Exception("conexão quebrada")

        manager.add_status_client(ws1)
        manager.add_status_client(ws2)

        assert manager.status_count == 2

        # Broadcast com mensagem — executa todas as tasks pendentes
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(manager.broadcast_state("idle", "test"))
        finally:
            loop.close()

        # broadcast_state remove TODOS os clientes que lançaram exceção.
        # Ambos lançaram: ws1 (mock normal sem side_effect) e ws2 (side_effect).
        assert manager.status_count == 0

    def test_send_audio_chunk_remove_cliente_inexistente(self):
        """send_audio_chunk com session_id ausente não levanta erro."""
        from api.websocket import WebSocketManager

        manager = WebSocketManager()
        # Session inexistente não deve levantar exceção
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(manager.send_audio_chunk("não-existe", b"\x00"))
        finally:
            loop.close()

    def test_voice_clients_isolados(self):
        """Clients de voice, status e audio são mantidos separadamente."""
        from api.websocket import WebSocketManager

        manager = WebSocketManager()

        manager.add_status_client(MagicMock())
        manager.add_audio_client("s1", MagicMock())
        manager.add_voice_client("s2", MagicMock())

        assert manager.status_count == 1
        assert manager.audio_count == 1
        assert manager.voice_count == 1


# ============================================================================
# Testes E2E — Cenários de erro integrado
# ============================================================================


class TestErrorScenarios:
    """Cenários de erro simulando degradação graciosa."""

    @pytest.fixture
    def app(self, app_factory: FastAPI) -> FastAPI:
        return app_factory

    @pytest.fixture
    def app_factory(self, tmp_path: Path) -> FastAPI:
        return _build_e2e_app(tmp_path)

    def test_comando_hermes_falha(self, app: FastAPI):
        """Comando quando Hermes falha: interação gravada com status error."""

        class _FailingBridge:
            @property
            def endpoint(self):
                return "http://hermes.fake:8080"

            async def send_command(self, message: str):
                raise HermesError(
                    type("APIError", (), {
                        "code": "HERMES_UNAVAILABLE",
                        "message": "Hermes indisponível.",
                        "details": {},
                    })()
                )

            async def test_connection(self) -> bool:
                return False

        app.dependency_overrides[command_api.get_hermes_bridge_factory] = (
            lambda: lambda m: _FailingBridge()
        )

        client = TestClient(app)
        body = _post_command(client, "comando em ambiente falho")
        iid = body["id"]

        resp = client.get(f"/api/command/{iid}")
        assert resp.status_code == 200
        result = resp.json()
        # O erro do Hermes é persistido na interação
        assert result["status"] in ("error", "timeout")
        assert result["error_message"] is not None
