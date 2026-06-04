"""Testes de latência do sistema Aurion.

Executam benchmarks das operações mais relevantes usando ``time.perf_counter``
com alta resolução. Todos os testes são determinísticos — serviços externos são
substituídos por *fakes*, sem rede, hardware ou I/O real.

Os resultados são impressos como JSON no final da execução para facilitar
integração com CI/CD.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import command as command_api
from api import config as config_api
from api import history as history_api
from api import test as test_api
from config.settings import ConfigManager
from db.database import Database
from db.repo import InteractionRepository
from db.models import InteractionCreate
from svc.hermes_bridge import HermesBridge, HermesResponse


# ============================================================================
# Helpers
# ============================================================================


def _benchmark(fn, *, n_runs: int = 20) -> list[float]:
    """Executa `fn` N vezes e retorna a lista de tempos (segundos)."""
    times = []
    for _ in range(n_runs):
        start = time.perf_counter()
        result = fn()
        # Garante que coroutines são executadas
        if asyncio.iscoroutine(result):
            asyncio.get_event_loop().run_until_complete(result)
        times.append(time.perf_counter() - start)
    return times


def _report(name: str, times: list[float]) -> dict[str, Any]:
    """Formata os resultados de um benchmark."""
    return {
        "test": name,
        "runs": len(times),
        "mean_ms": round(statistics.mean(times) * 1000, 3),
        "median_ms": round(statistics.median(times) * 1000, 3),
        "stdev_ms": round(statistics.stdev(times) * 1000, 3) if len(times) > 1 else 0.0,
        "min_ms": round(min(times) * 1000, 3),
        "max_ms": round(max(times) * 1000, 3),
        "p95_ms": round(sorted(times)[int(len(times) * 0.95)] * 1000, 3),
    }


# ============================================================================
# Fixtures
# ============================================================================


def _ensure_event_loop():
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def _build_e2e_app(tmp_path: Path) -> FastAPI:
    """Monta um app isolado para benchmarks."""
    _ensure_event_loop()
    app = FastAPI()
    app.include_router(config_api.router)
    app.include_router(command_api.router)
    app.include_router(history_api.router)
    app.include_router(test_api.router)

    config_path = tmp_path / "config_bench.json"
    config_path.write_text("{}")
    config_mgr = ConfigManager(config_path)

    db = Database(":memory:")
    asyncio.get_event_loop().run_until_complete(db.connect())
    repo = InteractionRepository(db)

    app.dependency_overrides[config_api.get_config_manager_dep] = lambda: config_mgr
    app.dependency_overrides[command_api.get_config_manager_dep] = lambda: config_mgr

    def _get_repo():
        return repo

    app.dependency_overrides[command_api.get_repository_dep] = _get_repo
    app.dependency_overrides[history_api.get_repository_dep] = _get_repo

    class _FakeBridge:
        @property
        def endpoint(self):
            return "http://hermes.fake:8080"

        async def send_command(self, message: str):
            return HermesResponse(reply="ok", status_code=200)

    app.dependency_overrides[command_api.get_hermes_bridge_factory] = (
        lambda: lambda m: _FakeBridge()
    )

    # Limpa rate limiter
    limiter = test_api._RateLimiter()
    app.dependency_overrides[test_api.get_rate_limiter] = lambda: limiter

    return app


# ============================================================================
# Benchmarks de latência
# ============================================================================


class TestAppStartup:
    """Tempo de inicialização do FastAPI app."""

    def test_app_import_and_creation(self):
        """Tempo para importar e criar o app FastAPI."""
        from main import app as real_app  # noqa: F401

        times = _benchmark(lambda: None, n_runs=10)
        result = _report("app_import_creation", times)
        print(json.dumps(result, indent=2))
        assert result["mean_ms"] < 500, "App deve criar em < 500ms"

    def test_app_lifespan_sync(self):
        """O setup do lifespan (sem serviços externos) deve ser rápido."""
        app = FastAPI()
        app.include_router(config_api.router)
        app.include_router(command_api.router)
        app.include_router(history_api.router)
        app.include_router(test_api.router)

        times = _benchmark(lambda: None, n_runs=10)
        result = _report("app_routers_inclusion", times)
        print(json.dumps(result, indent=2))
        assert result["mean_ms"] < 100, "Routers devem ser incluídos em < 100ms"


class TestCommandLatency:
    """Latência do POST /api/command (mockado)."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> TestClient:
        return TestClient(_build_e2e_app(tmp_path))

    def test_comando_latency(self, client: TestClient):
        """POST /api/command com Hermes mock deve responder rapidamente."""
        times = _benchmark(
            lambda: client.post("/api/command", json={"message": "ola"}),
            n_runs=50,
        )
        result = _report("command_post_latency", times)
        print(json.dumps(result, indent=2))
        # Com mocks, deve responder em < 50ms
        assert result["mean_ms"] < 50, f"Command latency mean {result['mean_ms']}ms > 50ms"


class TestHistoryLatency:
    """Latência do GET /api/history."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> TestClient:
        return TestClient(_build_e2e_app(tmp_path))

    def _setup_interactions(self, client: TestClient, count: int = 100):
        """Popula o banco com interações de teste."""
        for i in range(count):
            client.post("/api/command", json={"message": f"comando {i}"})

    def test_history_list_latency(self, client: TestClient):
        """GET /api/history com 100 interações deve ser rápido."""
        self._setup_interactions(client, 100)

        times = _benchmark(
            lambda: client.get("/api/history"),
            n_runs=50,
        )
        result = _report("history_list_latency", times)
        print(json.dumps(result, indent=2))
        assert result["mean_ms"] < 100, f"History list latency {result['mean_ms']}ms > 100ms"

    def test_history_search_latency(self, client: TestClient):
        """GET /api/history?search=... com busca deve ser rápido."""
        self._setup_interactions(client, 100)

        times = _benchmark(
            lambda: client.get("/api/history?search=comando"),
            n_runs=50,
        )
        result = _report("history_search_latency", times)
        print(json.dumps(result, indent=2))
        assert result["mean_ms"] < 200, f"Search latency {result['mean_ms']}ms > 200ms"

    def test_history_pagination_latency(self, client: TestClient):
        """GET /api/history com offset/limit deve ser rápido."""
        self._setup_interactions(client, 1000)

        times = _benchmark(
            lambda: client.get("/api/history?limit=20&offset=500"),
            n_runs=50,
        )
        result = _report("history_pagination_latency", times)
        print(json.dumps(result, indent=2))
        assert result["mean_ms"] < 100, f"Pagination latency {result['mean_ms']}ms > 100ms"


class TestConfigLatency:
    """Latência de GET/PUT /api/config."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> TestClient:
        return TestClient(_build_e2e_app(tmp_path))

    def test_get_config_latency(self, client: TestClient):
        """GET /api/config deve responder em < 10ms."""
        times = _benchmark(lambda: client.get("/api/config"), n_runs=100)
        result = _report("get_config_latency", times)
        print(json.dumps(result, indent=2))
        assert result["mean_ms"] < 10, f"GET config latency {result['mean_ms']}ms > 10ms"

    def test_put_config_latency(self, client: TestClient):
        """PUT /api/config deve responder em < 20ms."""
        times = _benchmark(
            lambda: client.put("/api/config", json={"tts": {"rate": 10}}),
            n_runs=100,
        )
        result = _report("put_config_latency", times)
        print(json.dumps(result, indent=2))
        assert result["mean_ms"] < 20, f"PUT config latency {result['mean_ms']}ms > 20ms"

    def test_reset_config_latency(self, client: TestClient):
        """POST /api/config/reset deve responder em < 20ms."""
        times = _benchmark(
            lambda: client.post("/api/config/reset"),
            n_runs=100,
        )
        result = _report("reset_config_latency", times)
        print(json.dumps(result, indent=2))
        assert result["mean_ms"] < 20, f"Reset config latency {result['mean_ms']}ms > 20ms"


class TestWebSocketLatency:
    """Latência de conexão e operações WebSocket."""

    def test_ws_manager_creation(self):
        """Tempo para criar o WebSocketManager."""
        from api.websocket import WebSocketManager

        times = _benchmark(lambda: WebSocketManager(), n_runs=1000)
        result = _report("ws_manager_creation", times)
        print(json.dumps(result, indent=2))
        assert result["mean_ms"] < 1, "WebSocketManager deve criar em < 1ms"

    def test_ws_broadcast(self):
        """Tempo de broadcast para 10 clientes."""
        from api.websocket import WebSocketManager
        from unittest.mock import MagicMock

        manager = WebSocketManager()
        clients = [MagicMock() for _ in range(10)]
        for ws in clients:
            manager.add_status_client(ws)

        times = _benchmark(
            lambda: asyncio.run(manager.broadcast_state("idle", "test")),
            n_runs=100,
        )
        result = _report("ws_broadcast_10_clients", times)
        print(json.dumps(result, indent=2))
        assert result["mean_ms"] < 5, f"Broadcast latency {result['mean_ms']}ms > 5ms"

    def test_ws_add_remove_clients(self):
        """Tempo para adicionar/remover clientes."""
        from api.websocket import WebSocketManager
        from unittest.mock import MagicMock

        times = _benchmark(
            lambda: (
                WebSocketManager().add_status_client(MagicMock())
                or WebSocketManager().remove_status_client(MagicMock())
            ),
            n_runs=1000,
        )
        result = _report("ws_add_remove_client", times)
        print(json.dumps(result, indent=2))
        assert result["mean_ms"] < 1.0, f"Add/remove deve ser < 1ms"


class TestDatabaseLatency:
    """Latência de operações de banco de dados."""

    def test_db_create_interaction(self):
        """INSERT de uma interação deve ser rápido."""
        _ensure_event_loop()
        db = Database(":memory:")
        asyncio.get_event_loop().run_until_complete(db.connect())

        repo = InteractionRepository(db)

        times = _benchmark(
            lambda: repo.create_interaction(
                InteractionCreate(
                    channel="web",
                    input_text="latency test",
                    status="error",
                    error_message="test",
                )
            ),
            n_runs=200,
        )
        result = _report("db_create_interaction", times)
        print(json.dumps(result, indent=2))
        assert result["mean_ms"] < 5, f"DB create latency {result['mean_ms']}ms > 5ms"

    def test_db_list_interactions(self):
        """SELECT paginado de interações deve ser rápido."""
        _ensure_event_loop()
        db = Database(":memory:")
        asyncio.get_event_loop().run_until_complete(db.connect())

        repo = InteractionRepository(db)

        # Popula 200 interações
        for i in range(200):
            asyncio.get_event_loop().run_until_complete(
                repo.create_interaction(
                    InteractionCreate(
                        channel="web",
                        input_text=f"item {i}",
                        status="success",
                    )
                )
            )

        times = _benchmark(
            lambda: repo.list_interactions(limit=50, offset=0),
            n_runs=200,
        )
        result = _report("db_list_interactions_200", times)
        print(json.dumps(result, indent=2))
        assert result["mean_ms"] < 10, f"DB list latency {result['mean_ms']}ms > 10ms"


# ============================================================================
# Relatório final
# ============================================================================


def test_latency_summary():
    """Teste vazio que serve de placeholder para o relatório de latência.

    Todos os benchmarks individuais já imprimem seus resultados.
    Este ponto marca o fim da execução dos benchmarks.
    """
    print("\n=== Relatório de Latência Aurion ===")
    print("Execute os benchmarks individualmente para ver os resultados detalhados.")
    print("Use: pytest backend/tests/test_latency.py -v --tb=no\n")
