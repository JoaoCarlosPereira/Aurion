"""Testes do Config Manager: modelos, persistência em JSON e API REST.

Cobre validação de modelos Pydantic, leitura/escrita de `config.json` (via
`tmp_path`, sem depender de arquivo versionado), atualização parcial (merge),
reset, serialização e os endpoints GET/PUT /api/config — incluindo a garantia
de que o token do Hermes não é exposto.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.config import get_config_manager_dep, router
from config.models import (
    AppConfig,
    AudioConfig,
    HermesConfig,
    STTConfig,
    TTSConfig,
    WakeWordConfig,
)
from config.settings import ConfigManager


# --- Fixtures locais ---------------------------------------------------------


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


@pytest.fixture
def client(manager: ConfigManager) -> TestClient:
    """Cliente HTTP com o router de config e o manager temporário injetado."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_config_manager_dep] = lambda: manager
    return TestClient(app)


def _write_full_config(path: Path) -> dict:
    """Escreve um config.json completo e válido, retornando o dict gravado."""
    data = AppConfig().model_dump()
    data["hermes"]["auth_token"] = "segredo-do-hermes"
    data["wake_word"]["sensitivity"] = 0.8
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


# --- Testes de modelos -------------------------------------------------------


def test_modelos_valores_padrao():
    """Os modelos expõem os valores padrão da TechSpec (Seção 4.2)."""
    cfg = AppConfig()
    assert cfg.hermes.endpoint == "http://localhost:8080"
    assert cfg.stt.engine == "whisper.cpp"
    assert cfg.tts.voice == "pt-BR-FabioNeural"
    assert cfg.tts.external.enabled is False
    assert cfg.wake_word.sensitivity == 0.5
    assert cfg.audio.sample_rate == 16000
    assert cfg.database.path == "aurion.db"


def test_validacao_faixa_sensibilidade():
    """Sensibilidade fora de 0.0-1.0 deve falhar na validação."""
    WakeWordConfig(sensitivity=0.0)
    WakeWordConfig(sensitivity=1.0)
    with pytest.raises(ValidationError):
        WakeWordConfig(sensitivity=1.5)
    with pytest.raises(ValidationError):
        WakeWordConfig(sensitivity=-0.1)


def test_validacao_sample_rate():
    """sample_rate aceita 16000 e rejeita valores abaixo do mínimo."""
    assert AudioConfig(sample_rate=16000).sample_rate == 16000
    with pytest.raises(ValidationError):
        AudioConfig(sample_rate=1000)


def test_validacao_volume_tts():
    """Volume do TTS deve respeitar a faixa 0-100."""
    assert TTSConfig(volume=0).volume == 0
    assert TTSConfig(volume=100).volume == 100
    with pytest.raises(ValidationError):
        TTSConfig(volume=101)


def test_validacao_tipos_stt():
    """STTConfig rejeita threads abaixo de 1 e valida tipos."""
    assert STTConfig(threads=4).threads == 4
    with pytest.raises(ValidationError):
        STTConfig(threads=0)


# --- Testes de persistência --------------------------------------------------


@pytest.mark.asyncio
async def test_leitura_config_completo(config_path: Path):
    """Lê um config.json válido com todas as chaves."""
    data = _write_full_config(config_path)
    mgr = ConfigManager(config_path)
    cfg = await mgr.load()
    assert cfg.hermes.auth_token == data["hermes"]["auth_token"]
    assert cfg.wake_word.sensitivity == 0.8
    assert cfg.audio.sample_rate == 16000
    assert cfg.database.path == "aurion.db"


@pytest.mark.asyncio
async def test_fallback_valores_padrao(config_path: Path):
    """Sem arquivo no disco, usa os valores padrão."""
    assert not config_path.exists()
    mgr = ConfigManager(config_path)
    cfg = await mgr.load()
    assert cfg == AppConfig()


@pytest.mark.asyncio
async def test_serializacao_desserializacao(config_path: Path):
    """Salvar e recarregar produz uma configuração equivalente (round-trip)."""
    mgr = ConfigManager(config_path)
    await mgr.load()
    await mgr.update({"tts": {"voice": "pt-BR-FranciscaNeural"}})

    # Recarrega de um novo manager apontando para o mesmo arquivo.
    mgr2 = ConfigManager(config_path)
    cfg2 = await mgr2.load()
    assert cfg2.tts.voice == "pt-BR-FranciscaNeural"

    # O arquivo é JSON válido e contém todas as seções.
    on_disk = json.loads(config_path.read_text(encoding="utf-8"))
    assert set(on_disk) == {
        "database",
        "hermes",
        "stt",
        "tts",
        "wake_word",
        "audio",
    }


@pytest.mark.asyncio
async def test_persistencia_em_arquivo(config_path: Path, manager: ConfigManager):
    """A atualização grava o arquivo config.json no disco."""
    assert not config_path.exists()
    await manager.update({"hermes": {"endpoint": "http://nova:9000"}})
    assert config_path.exists()
    on_disk = json.loads(config_path.read_text(encoding="utf-8"))
    assert on_disk["hermes"]["endpoint"] == "http://nova:9000"


@pytest.mark.asyncio
async def test_atualizacao_parcial_merge(manager: ConfigManager):
    """Atualização parcial preserva campos não informados (merge profundo)."""
    await manager.update({"wake_word": {"sensitivity": 0.9}})
    cfg = await manager.update({"tts": {"voice": "pt-BR-AntonioNeural"}})
    # O wake_word atualizado antes deve permanecer.
    assert cfg.wake_word.sensitivity == 0.9
    # E o engine do wake_word não foi sobrescrito.
    assert cfg.wake_word.engine == "porcupine"
    assert cfg.tts.voice == "pt-BR-AntonioNeural"
    # Demais valores do TTS preservados.
    assert cfg.tts.engine == "edge-tts"


@pytest.mark.asyncio
async def test_atualizacao_aninhada_tts_externo(manager: ConfigManager):
    """Merge profundo funciona em sub-config aninhada (tts.external)."""
    cfg = await manager.update(
        {"tts": {"external": {"enabled": True, "api_key": "chave"}}}
    )
    assert cfg.tts.external.enabled is True
    assert cfg.tts.external.api_key == "chave"
    # Campos não informados de external preservados.
    assert cfg.tts.external.format == "mp3"


@pytest.mark.asyncio
async def test_reset_para_padrao(manager: ConfigManager):
    """Reset restaura todos os valores padrão."""
    await manager.update({"wake_word": {"sensitivity": 0.95}})
    cfg = await manager.reset()
    assert cfg == AppConfig()
    assert cfg.wake_word.sensitivity == 0.5


@pytest.mark.asyncio
async def test_validacao_no_update(manager: ConfigManager):
    """Atualização com valor inválido é rejeitada por Pydantic."""
    with pytest.raises(ValidationError):
        await manager.update({"wake_word": {"sensitivity": 2.0}})


@pytest.mark.asyncio
async def test_override_variavel_ambiente(config_path: Path, monkeypatch):
    """Variável de ambiente AURION_* sobrescreve valor do arquivo/padrão."""
    monkeypatch.setenv("AURION_HERMES__ENDPOINT", "http://env-host:7777")
    mgr = ConfigManager(config_path)
    cfg = await mgr.load()
    assert cfg.hermes.endpoint == "http://env-host:7777"


# --- Testes da API REST ------------------------------------------------------


def test_get_config_retorna_tudo(client: TestClient):
    """GET /api/config retorna todas as seções de configuração."""
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {
        "database",
        "hermes",
        "stt",
        "tts",
        "wake_word",
        "audio",
    }
    assert body["audio"]["sample_rate"] == 16000


def test_get_config_nao_expoe_token_hermes(client: TestClient, manager: ConfigManager):
    """GET /api/config NÃO expõe o token do Hermes."""
    # Define um token via PUT para garantir que ele existe em memória/disco.
    resp = client.put("/api/config", json={"hermes": {"auth_token": "top-secret"}})
    assert resp.status_code == 200
    # Nem o PUT nem o GET retornam o token.
    assert "auth_token" not in resp.json()["hermes"]
    body = client.get("/api/config").json()
    assert "auth_token" not in body["hermes"]
    # Mas o token foi de fato persistido internamente.
    assert "top-secret" in json.dumps(json.loads(manager.config_path.read_text()))


def test_put_config_atualizacao_parcial(client: TestClient):
    """PUT /api/config atualiza apenas os campos enviados."""
    resp = client.put(
        "/api/config",
        json={"wake_word": {"sensitivity": 0.7}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["wake_word"]["sensitivity"] == 0.7
    # Campos não enviados permanecem nos padrões.
    assert body["tts"]["voice"] == "pt-BR-FabioNeural"


def test_put_config_validacao_422(client: TestClient):
    """PUT /api/config com sensibilidade inválida retorna 422."""
    resp = client.put(
        "/api/config",
        json={"wake_word": {"sensitivity": 5.0}},
    )
    assert resp.status_code == 422


def test_validacao_endpoint_hermes(client: TestClient):
    """PUT aceita atualizar o endpoint do Hermes e persiste o valor."""
    resp = client.put(
        "/api/config",
        json={"hermes": {"endpoint": "http://hermes.local:8080"}},
    )
    assert resp.status_code == 200
    assert resp.json()["hermes"]["endpoint"] == "http://hermes.local:8080"
