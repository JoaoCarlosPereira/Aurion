"""Testes unitários do engine de wake word (Porcupine).

Todos os testes usam mocks/monkeypatch do `pvporcupine` — não exigem hardware,
binários nativos nem rede. Cobrem inicialização, processamento (com e sem
detecção), validação de sensibilidade, timeout, fallback de modelo, ciclo de
vida e degradação graciosa quando o `pvporcupine` está indisponível.
"""

from __future__ import annotations

import struct

import pytest
from pydantic import ValidationError

import svc.wakeword as wakeword
from svc.wakeword import WakeWordConfig, WakeWordEngine


# --- Stubs/mocks do Porcupine -------------------------------------------------


class FakePorcupineHandle:
    """Handle falso do Porcupine controlável pelos testes.

    `detect_at` define em qual chamada de `process` a detecção ocorre. Quando
    None, nunca detecta (retorna -1).
    """

    def __init__(self, frame_length: int = 512, sample_rate: int = 16000):
        self.frame_length = frame_length
        self.sample_rate = sample_rate
        self.deleted = False
        self.detect_next = False

    def process(self, pcm):
        if self.detect_next:
            self.detect_next = False
            return 0  # índice da keyword detectada
        return -1

    def delete(self):
        self.deleted = True


class FakePvporcupine:
    """Módulo `pvporcupine` falso, com `create` controlável."""

    KEYWORDS = ["porcupine", "bumblebee"]

    def __init__(self):
        self.last_kwargs: dict | None = None
        self.handle = FakePorcupineHandle()
        self.raise_on_create = False

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self.raise_on_create:
            raise RuntimeError("falha simulada de inicialização")
        return self.handle


@pytest.fixture
def fake_pv(monkeypatch):
    """Injeta um `pvporcupine` falso via `_load_pvporcupine`."""
    fake = FakePvporcupine()
    monkeypatch.setattr(wakeword, "_load_pvporcupine", lambda: fake)
    return fake


@pytest.fixture
def unavailable_pv(monkeypatch):
    """Simula `pvporcupine` indisponível (degradação graciosa)."""
    monkeypatch.setattr(wakeword, "_load_pvporcupine", lambda: None)


def _silence_frame(samples: int = 512) -> bytes:
    """Gera um frame PCM int16 de silêncio (bytes little-endian)."""
    return struct.pack(f"<{samples}h", *([0] * samples))


# --- Inicialização ------------------------------------------------------------


def test_inicializacao_porcupine_modelo_valido(fake_pv):
    """Teste de inicialização do Porcupine com modelo válido."""
    engine = WakeWordEngine()
    assert engine.start() is True
    assert engine.is_running is True
    assert engine.is_degraded is False
    assert fake_pv.last_kwargs is not None
    # Sensibilidade padrão é repassada ao Porcupine.
    assert fake_pv.last_kwargs["sensitivities"] == [0.5]
    engine.stop()


def test_start_idempotente(fake_pv):
    """start() repetido não reinicializa o Porcupine."""
    engine = WakeWordEngine()
    assert engine.start() is True
    handle1 = engine._handle
    assert engine.start() is True
    assert engine._handle is handle1
    engine.stop()


# --- Processamento ------------------------------------------------------------


def test_processamento_sem_deteccao(fake_pv):
    """Teste de processamento de frame de áudio sem detecção."""
    engine = WakeWordEngine()
    engine.start()
    assert engine.process(_silence_frame()) is False
    engine.stop()


def test_processamento_com_deteccao_e_callback(fake_pv):
    """Teste de processamento com detecção (mock) e disparo de callback."""
    chamado = {"count": 0}

    def cb():
        chamado["count"] += 1

    engine = WakeWordEngine(on_detected=cb)
    engine.start()
    fake_pv.handle.detect_next = True
    assert engine.process(_silence_frame()) is True
    assert chamado["count"] == 1
    engine.stop()


def test_processamento_aceita_lista_de_ints(fake_pv):
    """process() aceita lista de ints já decodificada além de bytes."""
    engine = WakeWordEngine()
    engine.start()
    fake_pv.handle.detect_next = True
    assert engine.process([0] * 512) is True
    engine.stop()


def test_processamento_com_engine_parado_retorna_false(fake_pv):
    """process() sem start() não detecta e não quebra."""
    engine = WakeWordEngine()
    assert engine.process(_silence_frame()) is False


def test_processamento_erro_interno_nao_propaga(fake_pv):
    """Erro no process do Porcupine é logado e retorna False (não derruba loop)."""
    engine = WakeWordEngine()
    engine.start()

    def boom(pcm):
        raise RuntimeError("erro no Porcupine")

    engine._handle.process = boom
    assert engine.process(_silence_frame()) is False
    engine.stop()


async def test_process_async(fake_pv):
    """A versão assíncrona delega ao process síncrono via thread pool."""
    engine = WakeWordEngine()
    engine.start()
    fake_pv.handle.detect_next = True
    assert await engine.process_async(_silence_frame()) is True
    assert await engine.process_async(_silence_frame()) is False
    engine.stop()


# --- Sensibilidade ------------------------------------------------------------


def test_sensibilidade_padrao_05():
    """Teste de sensibilidade padrão (0.5)."""
    engine = WakeWordEngine()
    assert engine.sensitivity == 0.5


def test_sensibilidade_extremos_validos():
    """Teste de validação de sensibilidade nos extremos (0.0 e 1.0)."""
    assert WakeWordConfig(sensitivity=0.0).sensitivity == 0.0
    assert WakeWordConfig(sensitivity=1.0).sensitivity == 1.0


def test_sensibilidade_fora_da_faixa_rejeitada():
    """Teste de validação de sensibilidade fora da faixa (<0 e >1)."""
    with pytest.raises(ValidationError):
        WakeWordConfig(sensitivity=-0.1)
    with pytest.raises(ValidationError):
        WakeWordConfig(sensitivity=1.1)


def test_sensibilidade_customizada_repassada(fake_pv):
    """Sensibilidade customizada é repassada ao Porcupine na inicialização."""
    engine = WakeWordEngine(WakeWordConfig(sensitivity=0.8))
    engine.start()
    assert fake_pv.last_kwargs["sensitivities"] == [0.8]
    engine.stop()


# --- Timeout ------------------------------------------------------------------


def test_timeout_padrao():
    """Teste de timeout configurável: padrão 10s."""
    engine = WakeWordEngine()
    assert engine.wake_word_timeout == 10


def test_timeout_customizado():
    """Teste de timeout configurável: valor customizado."""
    engine = WakeWordEngine(WakeWordConfig(wake_word_timeout=5))
    assert engine.wake_word_timeout == 5


def test_timeout_negativo_rejeitado():
    """Timeout negativo é rejeitado na validação da config."""
    with pytest.raises(ValidationError):
        WakeWordConfig(wake_word_timeout=-1)


# --- Fallback de modelo -------------------------------------------------------


def test_fallback_modelo_inexistente_usa_keyword_embutida(fake_pv):
    """Teste de fallback: .ppn inexistente recai para keyword embutida."""
    engine = WakeWordEngine(
        WakeWordConfig(keyword_path="/caminho/inexistente/aurion.ppn")
    )
    engine.start()
    # Sem keyword_paths; usa 'keywords' (embutida) como fallback.
    assert "keyword_paths" not in fake_pv.last_kwargs
    assert "keywords" in fake_pv.last_kwargs
    engine.stop()


def test_modelo_ppn_personalizado_carregado(fake_pv, tmp_path):
    """Quando o .ppn existe, ele é usado via keyword_paths."""
    ppn = tmp_path / "aurion.ppn"
    ppn.write_bytes(b"modelo-fake")
    engine = WakeWordEngine(WakeWordConfig(keyword_path=str(ppn)))
    engine.start()
    assert fake_pv.last_kwargs["keyword_paths"] == [str(ppn)]
    engine.stop()


# --- Ciclo de vida ------------------------------------------------------------


def test_ciclo_de_vida_iniciar_parar(fake_pv):
    """Teste de gerenciamento de ciclo de vida (iniciar/parar)."""
    engine = WakeWordEngine()
    assert engine.is_running is False
    engine.start()
    assert engine.is_running is True
    handle = engine._handle
    engine.stop()
    assert engine.is_running is False
    assert engine._handle is None
    assert handle.deleted is True


def test_stop_idempotente(fake_pv):
    """stop() pode ser chamado múltiplas vezes sem erro."""
    engine = WakeWordEngine()
    engine.start()
    engine.stop()
    engine.stop()  # não deve levantar
    assert engine.is_running is False


def test_frame_length_e_sample_rate(fake_pv):
    """Engine expõe frame_length e sample_rate do handle quando ativo."""
    engine = WakeWordEngine()
    # Antes de iniciar, valores padrão.
    assert engine.sample_rate == 16000
    engine.start()
    assert engine.sample_rate == 16000
    assert engine.frame_length == 512
    engine.stop()


# --- test_model ---------------------------------------------------------------


def test_test_model_carregamento_ok(fake_pv):
    """Teste de carregamento de modelo: test_model() retorna True com Porcupine ok."""
    engine = WakeWordEngine()
    assert engine.test_model() is True
    # test_model preserva o estado: como estava parado, volta a parado.
    assert engine.is_running is False


def test_test_model_engine_ja_iniciado(fake_pv):
    """test_model() em engine já iniciado retorna True sem pará-lo."""
    engine = WakeWordEngine()
    engine.start()
    assert engine.test_model() is True
    assert engine.is_running is True
    engine.stop()


# --- Degradação graciosa (pvporcupine indisponível) ---------------------------


def test_degradacao_graciosa_quando_indisponivel(unavailable_pv):
    """Sem pvporcupine, o engine entra em modo no-op e nunca detecta."""
    engine = WakeWordEngine()
    assert engine.start() is False
    assert engine.is_running is True
    assert engine.is_degraded is True
    assert engine.process(_silence_frame()) is False
    engine.stop()


def test_degradacao_nao_dispara_callback(unavailable_pv):
    """Em modo no-op o callback nunca é chamado."""
    chamado = {"count": 0}
    engine = WakeWordEngine(on_detected=lambda: chamado.__setitem__("count", 1))
    engine.start()
    engine.process(_silence_frame())
    assert chamado["count"] == 0
    engine.stop()


def test_test_model_degradado_retorna_false(unavailable_pv):
    """test_model() retorna False quando o Porcupine está indisponível."""
    engine = WakeWordEngine()
    assert engine.test_model() is False


def test_falha_na_criacao_degrada(fake_pv):
    """Erro no pvporcupine.create() aciona degradação graciosa (modo no-op)."""
    fake_pv.raise_on_create = True
    engine = WakeWordEngine()
    assert engine.start() is False
    assert engine.is_degraded is True
    assert engine.process(_silence_frame()) is False
    engine.stop()


async def test_load_pvporcupine_real_indisponivel():
    """No ambiente de teste o pvporcupine real não está instalado: retorna None."""
    # Não deve levantar; degrada para None.
    assert wakeword._load_pvporcupine() is None
