"""Testes da API REST completa (task_11).

Cobre os endpoints de teste de conexão (``POST /api/test/stt``,
``POST /api/test/tts``, ``GET /api/test/tts/voices``), o rate limiting básico
dos endpoints de teste e os endpoints avançados de configuração
(``PUT /api/config/audio`` e ``POST /api/config/reset``).

Nenhum teste usa hardware, binários ou rede: os serviços STT/TTS são
substituídos por *fakes* via ``app.dependency_overrides`` (factories), e o
Config Manager aponta para um ``config.json`` temporário (``tmp_path``).
"""

from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import config as config_api
from api import test as test_api
from config.settings import ConfigManager
from svc.stt import STTConfig as ServiceSTTConfig
from svc.tts import TTSConfig as ServiceTTSConfig


# --- Fakes dos serviços ------------------------------------------------------


class _FakeSTTService:
    """Fake do ``STTService`` que retorna um resultado de ``test_model`` fixo."""

    def __init__(self, available: bool, config: ServiceSTTConfig | None = None) -> None:
        self._available = available
        self.config = config or ServiceSTTConfig()

    async def test_model(self) -> bool:
        return self._available


class _FakeTTSService:
    """Fake do ``TTSService`` que emite chunks de áudio simulados.

    Se ``error`` for informado, ``synthesize`` levanta a exceção (simulando
    ambas as engines indisponíveis). ``chunks`` controla quantos chunks de áudio
    são produzidos (0 simula nenhum áudio gerado).
    """

    def __init__(
        self,
        chunks: list[bytes] | None = None,
        error: Exception | None = None,
        config: ServiceTTSConfig | None = None,
        voices: list[str] | None = None,
    ) -> None:
        self._chunks = chunks if chunks is not None else [b"a", b"b"]
        self._error = error
        self.config = config or ServiceTTSConfig()
        self._voices = voices if voices is not None else ["pt-BR-FabioNeural"]

    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        if self._error is not None:
            raise self._error
        for chunk in self._chunks:
            yield chunk

    async def list_voices(self) -> list[str]:
        return list(self._voices)


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    """Caminho de um config.json isolado por teste (não versionado)."""
    return tmp_path / "config.json"


@pytest_asyncio.fixture
async def manager(config_path: Path) -> ConfigManager:
    """Config Manager apontando para um config.json temporário, carregado."""
    mgr = ConfigManager(config_path)
    await mgr.load()
    return mgr


def _make_test_app(manager: ConfigManager) -> FastAPI:
    """Monta um app com o router de teste e dependências base sobrescritas.

    Inclui um rate limiter isolado (limpo) para não vazar estado entre testes.
    """
    app = FastAPI()
    app.include_router(test_api.router)
    app.dependency_overrides[test_api.get_config_manager_dep] = lambda: manager
    limiter = test_api._RateLimiter()
    app.dependency_overrides[test_api.get_rate_limiter] = lambda: limiter
    return app


# --- POST /api/test/stt ------------------------------------------------------


def test_stt_sucesso(manager: ConfigManager):
    """STT disponível: success=True e mensagem de operacional."""
    app = _make_test_app(manager)
    app.dependency_overrides[test_api.get_stt_service_factory] = lambda: (
        lambda m: _FakeSTTService(available=True)
    )
    resp = TestClient(app).post("/api/test/stt")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "operacional" in body["message"].lower()
    assert body["details"]["model"] == "ggml-base-q4"


def test_stt_modelo_inexistente(manager: ConfigManager):
    """STT com modelo inexistente/indisponível: success=False."""
    app = _make_test_app(manager)
    app.dependency_overrides[test_api.get_stt_service_factory] = lambda: (
        lambda m: _FakeSTTService(
            available=False, config=ServiceSTTConfig(model="modelo-inexistente")
        )
    )
    resp = TestClient(app).post("/api/test/stt")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["details"]["model"] == "modelo-inexistente"


# --- POST /api/test/tts ------------------------------------------------------


def test_tts_edge_sucesso(manager: ConfigManager):
    """edge-tts disponível: streaming produz chunks -> success=True."""
    app = _make_test_app(manager)
    app.dependency_overrides[test_api.get_tts_service_factory] = lambda: (
        lambda m: _FakeTTSService(chunks=[b"x", b"y", b"z"])
    )
    resp = TestClient(app).post("/api/test/tts")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["details"]["chunks"] == 3
    assert body["details"]["external_enabled"] is False


def test_tts_externo_streaming_sucesso(manager: ConfigManager):
    """TTS externo habilitado com streaming bem-sucedido: success=True."""
    app = _make_test_app(manager)
    external_config = ServiceTTSConfig()
    external_config.external.enabled = True
    app.dependency_overrides[test_api.get_tts_service_factory] = lambda: (
        lambda m: _FakeTTSService(chunks=[b"ext1", b"ext2"], config=external_config)
    )
    resp = TestClient(app).post("/api/test/tts")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["details"]["external_enabled"] is True
    assert body["details"]["chunks"] == 2


def test_tts_externo_indisponivel_fallback(manager: ConfigManager):
    """TTS externo indisponível mas fallback (edge-tts) produz áudio: success.

    O fallback automático é responsabilidade de ``TTSService.synthesize``; aqui
    o fake já entrega chunks (simulando o resultado do fallback), validando que
    o endpoint considera o teste bem-sucedido quando há áudio gerado.
    """
    app = _make_test_app(manager)
    external_config = ServiceTTSConfig()
    external_config.external.enabled = True
    app.dependency_overrides[test_api.get_tts_service_factory] = lambda: (
        lambda m: _FakeTTSService(chunks=[b"fallback"], config=external_config)
    )
    resp = TestClient(app).post("/api/test/tts")

    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_tts_ambas_engines_falham(manager: ConfigManager):
    """Ambas as engines falham (synthesize levanta): success=False com erro."""
    from svc.tts import TTSError

    app = _make_test_app(manager)
    app.dependency_overrides[test_api.get_tts_service_factory] = lambda: (
        lambda m: _FakeTTSService(error=TTSError("sem engines disponíveis"))
    )
    resp = TestClient(app).post("/api/test/tts")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "sem engines" in body["message"].lower()


def test_tts_sem_audio(manager: ConfigManager):
    """Streaming não produz chunks: success=False sem erro."""
    app = _make_test_app(manager)
    app.dependency_overrides[test_api.get_tts_service_factory] = lambda: (
        lambda m: _FakeTTSService(chunks=[])
    )
    resp = TestClient(app).post("/api/test/tts")

    assert resp.status_code == 200
    assert resp.json()["success"] is False


# --- GET /api/test/tts/voices ------------------------------------------------


def test_listagem_vozes(manager: ConfigManager):
    """GET /api/test/tts/voices retorna as vozes disponíveis e a contagem."""
    app = _make_test_app(manager)
    vozes = ["pt-BR-FabioNeural", "pt-BR-FranciscaNeural"]
    app.dependency_overrides[test_api.get_tts_service_factory] = lambda: (
        lambda m: _FakeTTSService(voices=vozes)
    )
    resp = TestClient(app).get("/api/test/tts/voices")

    assert resp.status_code == 200
    body = resp.json()
    assert body["voices"] == vozes
    assert body["count"] == 2


# --- Rate limiting -----------------------------------------------------------


def test_rate_limiting_excede_limite(manager: ConfigManager):
    """Após exceder o limite da janela, o endpoint retorna 429."""
    app = FastAPI()
    app.include_router(test_api.router)
    app.dependency_overrides[test_api.get_config_manager_dep] = lambda: manager
    app.dependency_overrides[test_api.get_stt_service_factory] = lambda: (
        lambda m: _FakeSTTService(available=True)
    )
    # Limitador estreito: 2 requisições por janela.
    limiter = test_api._RateLimiter(max_requests=2, window_seconds=100.0)
    app.dependency_overrides[test_api.get_rate_limiter] = lambda: limiter

    client = TestClient(app)
    assert client.post("/api/test/stt").status_code == 200
    assert client.post("/api/test/stt").status_code == 200
    # Terceira excede o limite.
    resp = client.post("/api/test/stt")
    assert resp.status_code == 429
    assert resp.json()["detail"]["code"] == "RATE_LIMITED"


def test_rate_limiter_janela_desliza():
    """A janela deslizante libera novas requisições conforme o tempo avança."""
    clock = {"t": 0.0}
    limiter = test_api._RateLimiter(
        max_requests=1, window_seconds=10.0, time_func=lambda: clock["t"]
    )
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False
    # Avança além da janela: a requisição antiga expira.
    clock["t"] = 11.0
    assert limiter.allow("ip") is True


def test_rate_limiter_isola_por_chave():
    """Chaves (IPs) diferentes têm contadores independentes."""
    limiter = test_api._RateLimiter(max_requests=1, window_seconds=100.0)
    assert limiter.allow("ip-a") is True
    assert limiter.allow("ip-b") is True
    assert limiter.allow("ip-a") is False


# --- Endpoints avançados de configuração -------------------------------------


@pytest.fixture
def config_client(manager: ConfigManager) -> TestClient:
    """Cliente com o router de config e o manager temporário injetado."""
    app = FastAPI()
    app.include_router(config_api.router)
    app.dependency_overrides[config_api.get_config_manager_dep] = lambda: manager
    return TestClient(app)


def test_reset_configuracoes(config_client: TestClient):
    """POST /api/config/reset restaura os valores padrão."""
    # Altera um valor primeiro.
    config_client.put("/api/config", json={"wake_word": {"sensitivity": 0.95}})
    resp = config_client.post("/api/config/reset")

    assert resp.status_code == 200
    body = resp.json()
    assert body["wake_word"]["sensitivity"] == 0.5
    assert body["audio"]["sample_rate"] == 16000
    # O reset não expõe o token do Hermes.
    assert "auth_token" not in body["hermes"]


def test_put_audio_config_avancada(config_client: TestClient):
    """PUT /api/config/audio atualiza os parâmetros avançados de áudio."""
    resp = config_client.put(
        "/api/config/audio",
        json={
            "sample_rate": 48000,
            "channels": 2,
            "chunk_size": 2048,
            "silence_threshold": 500,
        },
    )
    assert resp.status_code == 200
    audio = resp.json()["audio"]
    assert audio["sample_rate"] == 48000
    assert audio["channels"] == 2
    assert audio["chunk_size"] == 2048
    assert audio["silence_threshold"] == 500


def test_put_audio_config_merge_parcial(config_client: TestClient):
    """PUT /api/config/audio preserva campos de áudio não informados."""
    resp = config_client.put("/api/config/audio", json={"channels": 2})
    assert resp.status_code == 200
    audio = resp.json()["audio"]
    assert audio["channels"] == 2
    # Demais campos permanecem nos padrões.
    assert audio["sample_rate"] == 16000
    assert audio["chunk_size"] == 1024


def test_put_audio_config_min_invalido_422(config_client: TestClient):
    """sample_rate abaixo do mínimo do modelo retorna 422 (Pydantic)."""
    resp = config_client.put("/api/config/audio", json={"sample_rate": 1000})
    assert resp.status_code == 422


def test_put_audio_config_max_invalido_400(config_client: TestClient):
    """sample_rate acima do máximo de sanidade retorna 400 (validação avançada)."""
    resp = config_client.put("/api/config/audio", json={"sample_rate": 1_000_000})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "AUDIO_INVALID_CONFIG"


def test_put_audio_config_channels_max_400(config_client: TestClient):
    """channels acima do máximo de sanidade retorna 400."""
    resp = config_client.put("/api/config/audio", json={"channels": 99})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "AUDIO_INVALID_CONFIG"
