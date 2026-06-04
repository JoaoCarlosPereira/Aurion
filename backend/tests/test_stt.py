"""Testes do serviço STT (Speech-to-Text) com whisper.cpp.

Todos os testes usam mocks/monkeypatch do transcritor: não exigem o binário
whisper.cpp, hardware de áudio ou rede. Cobrem inicialização, transcrição,
silêncio, forçamento de idioma PT-BR, otimizações (threads/beam_size),
timeout, fallback, buffering e validação do modelo.
"""

from __future__ import annotations

import asyncio

import numpy as np
import pytest

from svc import stt as stt_module
from svc.stt import STTConfig, STTService, _apply_whisper_params, _whisper_language_code


# --- Helpers / fixtures locais ------------------------------------------------


def _voice_audio(seconds: float = 2.0, sample_rate: int = stt_module.SAMPLE_RATE) -> np.ndarray:
    """Gera um sinal senoidal float32 simulando fala (acima do limiar de silêncio)."""
    t = np.linspace(0, seconds, int(seconds * sample_rate), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def _silence_audio(seconds: float = 2.0, sample_rate: int = stt_module.SAMPLE_RATE) -> np.ndarray:
    """Gera áudio de silêncio (zeros) com duração suficiente para passar o buffer."""
    return np.zeros(int(seconds * sample_rate), dtype=np.float32)


class FakeTranscriber:
    """Transcritor falso que registra o áudio recebido e retorna texto fixo."""

    def __init__(self, text: str = "olá mundo") -> None:
        self.text = text
        self.calls: list[np.ndarray] = []

    def transcribe(self, audio: np.ndarray) -> str:
        self.calls.append(audio)
        return self.text


class FakeParams:
    """Imita o objeto de parâmetros do whisper.cpp com atributos configuráveis."""

    def __init__(self) -> None:
        self.language = ""
        self.n_threads = 0
        self.beam_size = 0
        self.max_context = 0


class FakeWhisper:
    """Imita o transcritor real do whisper.cpp, expondo `params`."""

    def __init__(self) -> None:
        self.params = FakeParams()

    def transcribe(self, audio: np.ndarray) -> str:
        return "transcrição whisper"


@pytest.fixture
def fake_transcriber() -> FakeTranscriber:
    return FakeTranscriber()


# --- Transcrição básica -------------------------------------------------------


async def test_transcricao_audio_valido_retorna_texto(fake_transcriber: FakeTranscriber):
    """Áudio válido (mock) deve retornar texto não vazio."""
    service = STTService(transcriber=fake_transcriber)
    texto = await service.transcribe(_voice_audio())
    assert texto == "olá mundo"
    assert len(fake_transcriber.calls) == 1


async def test_transcricao_aceita_bytes_pcm(fake_transcriber: FakeTranscriber):
    """Bytes PCM 16-bit (formato do PyAudio) devem ser aceitos e transcritos."""
    pcm = (_voice_audio() * 32767).astype(np.int16).tobytes()
    service = STTService(transcriber=fake_transcriber)
    texto = await service.transcribe(pcm)
    assert texto == "olá mundo"
    # O transcritor recebe float32 normalizado.
    assert fake_transcriber.calls[0].dtype == np.float32


async def test_transcricao_silencio_retorna_vazio(fake_transcriber: FakeTranscriber):
    """Áudio de silêncio deve retornar texto vazio sem chamar o transcritor."""
    service = STTService(transcriber=fake_transcriber)
    texto = await service.transcribe(_silence_audio())
    assert texto == ""
    assert fake_transcriber.calls == []


# --- Buffering (1-2s) ---------------------------------------------------------


async def test_buffer_insuficiente_retorna_vazio(fake_transcriber: FakeTranscriber):
    """Áudio menor que a janela mínima (1s) não é transcrito (buffer 1-2s)."""
    service = STTService(STTConfig(min_buffer_seconds=1.0), transcriber=fake_transcriber)
    texto = await service.transcribe(_voice_audio(seconds=0.3))
    assert texto == ""
    assert fake_transcriber.calls == []


async def test_buffer_suficiente_transcreve(fake_transcriber: FakeTranscriber):
    """Áudio acima da janela mínima é transcrito normalmente."""
    service = STTService(STTConfig(min_buffer_seconds=1.0), transcriber=fake_transcriber)
    texto = await service.transcribe(_voice_audio(seconds=1.5))
    assert texto == "olá mundo"


# --- Forçamento de idioma e otimizações --------------------------------------


def test_forcamento_idioma_pt_br():
    """O idioma 'pt-BR' da config deve ser convertido para o código whisper 'pt'."""
    assert _whisper_language_code("pt-BR") == "pt"
    assert _whisper_language_code("pt") == "pt"
    assert _whisper_language_code("") == "pt"


def test_aplica_params_idioma_threads_beam():
    """`_apply_whisper_params` força idioma PT-BR e aplica threads/beam_size."""
    params = FakeParams()
    config = STTConfig(language="pt-BR", threads=4, beam_size=3, max_context=10)
    _apply_whisper_params(params, config)
    assert params.language == "pt"
    assert params.n_threads == 4
    assert params.beam_size == 3
    assert params.max_context == 10


async def test_carregamento_whisper_aplica_config(monkeypatch: pytest.MonkeyPatch):
    """Ao carregar o whisper.cpp, idioma e otimizações são aplicados aos params."""
    fake = FakeWhisper()

    class _FakeWhisperFactory:
        @staticmethod
        def from_pretrained(model: str) -> FakeWhisper:
            fake.model = model
            return fake

    # Simula o módulo whispercpp com a classe Whisper.
    fake_module = type("_M", (), {"Whisper": _FakeWhisperFactory})
    monkeypatch.setitem(__import__("sys").modules, "whispercpp", fake_module)

    config = STTConfig(model="ggml-base-q4", threads=2, beam_size=1)
    service = STTService(config)
    assert await service.test_model() is True
    assert fake.params.language == "pt"
    assert fake.params.n_threads == 2
    assert fake.params.beam_size == 1


# --- Timeout ------------------------------------------------------------------


async def test_timeout_retorna_vazio():
    """Transcrição que excede o timeout configurado retorna texto vazio."""

    class SlowTranscriber:
        def transcribe(self, audio: np.ndarray) -> str:
            import time

            time.sleep(0.5)  # mais lento que o timeout abaixo
            return "tarde demais"

    service = STTService(STTConfig(timeout=0.05), transcriber=SlowTranscriber())
    texto = await service.transcribe(_voice_audio())
    assert texto == ""


# --- Fallback / degradação graciosa ------------------------------------------


async def test_fallback_engine_quando_whisper_indisponivel(monkeypatch: pytest.MonkeyPatch):
    """Sem whisper.cpp e com fallback não implementado, degrada para texto vazio."""
    # Garante que o import do whispercpp falhe.
    monkeypatch.setitem(__import__("sys").modules, "whispercpp", None)
    service = STTService(STTConfig(fallback_engine="vosk"))
    texto = await service.transcribe(_voice_audio())
    assert texto == ""
    assert await service.test_model() is False


async def test_whisper_indisponivel_sem_excecao(monkeypatch: pytest.MonkeyPatch):
    """Import do whisper.cpp falhando não deve propagar exceção (degradação)."""
    monkeypatch.setitem(__import__("sys").modules, "whispercpp", None)
    service = STTService()
    # Não levanta; retorna vazio.
    assert await service.transcribe(_voice_audio()) == ""


# --- test_model() -------------------------------------------------------------


async def test_test_model_sucesso_com_transcritor_injetado(fake_transcriber: FakeTranscriber):
    """test_model() retorna True quando há transcritor carregado."""
    service = STTService(transcriber=fake_transcriber)
    assert await service.test_model() is True


async def test_test_model_modelo_inexistente(monkeypatch: pytest.MonkeyPatch):
    """Erro ao carregar modelo inexistente -> test_model() retorna False."""

    class _FailingFactory:
        @staticmethod
        def from_pretrained(model: str):
            raise FileNotFoundError(f"modelo '{model}' não encontrado")

    fake_module = type("_M", (), {"Whisper": _FailingFactory})
    monkeypatch.setitem(__import__("sys").modules, "whispercpp", fake_module)

    service = STTService(STTConfig(model="ggml-inexistente"))
    assert await service.test_model() is False


# --- Configuração -------------------------------------------------------------


def test_config_padrao_reflete_techspec():
    """A config padrão deve refletir os valores do config.json.example."""
    config = STTConfig()
    assert config.engine == "whisper.cpp"
    assert config.model == "ggml-base-q4"
    assert config.language == "pt-BR"
    assert config.threads == 2
    assert config.beam_size == 1
    assert config.max_context == -1
