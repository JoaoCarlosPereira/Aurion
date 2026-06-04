"""Testes unitários do engine de wake word (Vosk).

Todos os testes usam mocks do `vosk.KaldiRecognizer` — não exigem hardware,
modelos baixados nem rede. Cobrem inicialização, processamento (com e sem
detecção), validação de sensibilidade, timeout, ciclo de vida e degradação
graciosa quando o vosk está indisponível.
"""

from __future__ import annotations

import json
import struct

import pytest

from svc.wakeword import WakeWordConfig, WakeWordEngine


# --- Stubs/mocks do Vosk ------------------------------------------------------


class FakeKaldiRecognizer:
    """Reconhecedor Kaldi falso controlável pelos testes."""

    def __init__(self, model, samprate, grammar=None):
        self.frame_length = 1600
        self.sample_rate = samprate
        self.deleted = False
        self.detect_next = False
        self._grammar = grammar
        self._last_text = ""

    def AcceptWaveform(self, audio):
        if self.detect_next:
            self.detect_next = False
            self._last_text = "aurion"
            return True
        self._last_text = "silencio"
        return True

    def Result(self):
        return json.dumps({"text": self._last_text})

    def SetGrammar(self, grammar):
        self._grammar = grammar

    def delete(self):
        self.deleted = True


class FakeVoskModel:
    """Modelo Vosk falso."""

    def __init__(self, path):
        self.path = path
        self.deleted = False

    def delete(self):
        self.deleted = True


class FakeVosk:
    """Módulo `vosk` falso, com `Model` e `KaldiRecognizer` controláveis."""

    def __init__(self):
        self.last_model_path: str | None = None
        self.last_grammar: str | None = None
        self.model_instance = FakeVoskModel("")
        self.recognizer_instance = FakeKaldiRecognizer(None, 16000)
        self.raise_on_model = False
        self.raise_on_recognizer = False

    def Model(self, path):
        self.last_model_path = path
        if self.raise_on_model:
            raise RuntimeError("falha simulada ao carregar modelo")
        return self.model_instance

    def KaldiRecognizer(self, model, samprate, grammar=None):
        self.last_grammar = grammar
        if self.raise_on_recognizer:
            raise RuntimeError("falha simulada ao criar reconhecedor")
        return self.recognizer_instance


# --- Fixtures -----------------------------------------------------------------


@pytest.fixture
def fake_vosk(monkeypatch):
    """Injeta um `vosk` falso via `_load_vosk`."""
    fake = FakeVosk()

    def _load():
        return fake

    monkeypatch.setattr("svc.wakeword._load_vosk", _load)
    return fake


@pytest.fixture
def unavailable_vosk(monkeypatch):
    """Simula vosk indisponível (degradação graciosa)."""
    monkeypatch.setattr("svc.wakeword._load_vosk", lambda: None)


# --- Helpers ------------------------------------------------------------------


def _silence_frame(samples: int = 1600) -> bytes:
    """Gera um frame PCM int16 de silêncio (bytes little-endian)."""
    return struct.pack(f"<{samples}h", *([0] * samples))


# --- Inicialização ------------------------------------------------------------


def test_inicializacao_vosk_modelo_valido(fake_vosk):
    """Teste de inicialização do Vosk com modelo válido."""
    engine = WakeWordEngine()
    assert engine.start() is True
    assert engine.is_running is True
    assert engine.is_degraded is False
    # Verifica que o path do modelo foi repassado
    assert fake_vosk.last_model_path is not None
    # Verifica que a gramática contém a keyword
    grammar = json.loads(fake_vosk.last_grammar)
    assert "aurion" in grammar
    engine.stop()


def test_start_idempotente(fake_vosk):
    """start() repetido não reinicializa o reconhecedor."""
    engine = WakeWordEngine()
    assert engine.start() is True
    recognizer1 = engine._recognizer
    assert engine.start() is True
    assert engine._recognizer is recognizer1
    engine.stop()


# --- Processamento ------------------------------------------------------------


def test_processamento_sem_detecao(fake_vosk):
    """Teste de processamento de frame de áudio sem detecção."""
    engine = WakeWordEngine()
    engine.start()
    assert engine.process(_silence_frame()) is False
    engine.stop()


def test_processamento_com_detecao_e_callback(fake_vosk):
    """Teste de processamento com detecção (mock) e disparo de callback."""
    chamado = {"count": 0}

    def cb():
        chamado["count"] += 1

    engine = WakeWordEngine(on_detected=cb)
    engine.start()
    fake_vosk.recognizer_instance.detect_next = True
    assert engine.process(_silence_frame()) is True
    assert chamado["count"] == 1
    engine.stop()


def test_processamento_aceita_lista_de_ints(fake_vosk):
    """process() aceita lista de ints já decodificada além de bytes."""
    engine = WakeWordEngine()
    engine.start()
    fake_vosk.recognizer_instance.detect_next = True
    assert engine.process([0] * 1600) is True
    engine.stop()


def test_processamento_com_engine_parado_retorna_false(fake_vosk):
    """process() sem start() não detecta e não quebra."""
    engine = WakeWordEngine()
    assert engine.process(_silence_frame()) is False


def test_processamento_erro_interno_nao_propaga(fake_vosk):
    """Erro no AcceptWaveform é logado e retorna False (não derrupa loop)."""
    engine = WakeWordEngine()
    engine.start()

    def boom(audio):
        raise RuntimeError("erro no Vosk")

    fake_vosk.recognizer_instance.AcceptWaveform = boom
    assert engine.process(_silence_frame()) is False
    engine.stop()


async def test_process_async(fake_vosk):
    """A versão assíncrona delega ao process síncrono via thread pool."""
    engine = WakeWordEngine()
    engine.start()
    fake_vosk.recognizer_instance.detect_next = True
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
    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        WakeWordConfig(sensitivity=-0.1)
    with pytest.raises(Exception):  # noqa: B017
        WakeWordConfig(sensitivity=1.1)


def test_sensibilidade_customizada(fake_vosk):
    """Sensibilidade customizada é armazenada corretamente."""
    engine = WakeWordEngine(WakeWordConfig(sensitivity=0.8))
    assert engine.sensitivity == 0.8
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


# --- Keyword ------------------------------------------------------------------


def test_keyword_padrao():
    """Teste de palavra de ativação padrão."""
    engine = WakeWordEngine()
    assert engine.keyword == "aurion"


def test_keyword_customizada(fake_vosk):
    """Keyword customizada é repassada ao Vosk na gramática."""
    engine = WakeWordEngine(WakeWordConfig(keyword="alexa"))
    engine.start()
    grammar = json.loads(fake_vosk.last_grammar)
    assert "alexa" in grammar
    engine.stop()


# --- Fallback de modelo -------------------------------------------------------


def test_modelo_customizado(fake_vosk):
    """model_path customizado é repassado ao modelo Vosk."""
    engine = WakeWordEngine(WakeWordConfig(model_path="/caminho/modelo"))
    engine.start()
    assert fake_vosk.last_model_path == "/caminho/modelo"
    engine.stop()


# --- Ciclo de vida ------------------------------------------------------------


def test_ciclo_de_vida_iniciar_parar(fake_vosk):
    """Teste de gerenciamento de ciclo de vida (iniciar/parar)."""
    engine = WakeWordEngine()
    assert engine.is_running is False
    engine.start()
    assert engine.is_running is True
    engine.stop()
    assert engine.is_running is False
    assert engine._recognizer is None


def test_stop_idempotente(fake_vosk):
    """stop() pode ser chamado múltiplas vezes sem erro."""
    engine = WakeWordEngine()
    engine.start()
    engine.stop()
    engine.stop()  # não deve levantar
    assert engine.is_running is False


def test_frame_length_e_sample_rate(fake_vosk):
    """Engine expõe frame_length e sample_rate."""
    engine = WakeWordEngine()
    assert engine.sample_rate == 16000
    engine.start()
    assert engine.sample_rate == 16000
    assert engine.frame_length == 1600
    engine.stop()


# --- test_model ---------------------------------------------------------------


def test_test_model_carregamento_ok(fake_vosk):
    """Teste de carregamento de modelo: test_model() retorna True com Vosk ok."""
    engine = WakeWordEngine()
    assert engine.test_model() is True
    assert engine.is_running is False


def test_test_model_engine_ja_iniciado(fake_vosk):
    """test_model() em engine já iniciado retorna True."""
    engine = WakeWordEngine()
    engine.start()
    assert engine.test_model() is True
    assert engine.is_running is True
    engine.stop()


# --- Degradação graciosa (vosk indisponível) ----------------------------------


def test_degradacao_graciosa_quando_indisponivel(unavailable_vosk):
    """Sem vosk, o engine entra em modo no-op e nunca detecta."""
    engine = WakeWordEngine()
    assert engine.start() is False
    assert engine.is_running is True
    assert engine.is_degraded is True
    assert engine.process(_silence_frame()) is False
    engine.stop()


def test_degradacao_nao_dispara_callback(unavailable_vosk):
    """Em modo no-op o callback nunca é chamado."""
    chamado = {"count": 0}
    engine = WakeWordEngine(on_detected=lambda: chamado.__setitem__("count", 1))
    engine.start()
    engine.process(_silence_frame())
    assert chamado["count"] == 0
    engine.stop()


def test_test_model_degradado_retorna_false(unavailable_vosk):
    """test_model() retorna False quando o vosk está indisponível."""
    engine = WakeWordEngine()
    assert engine.test_model() is False


def test_falha_no_modelo_degrada(fake_vosk):
    """Erro no Model() aciona degradação graciosa."""
    fake_vosk.raise_on_model = True
    engine = WakeWordEngine()
    assert engine.start() is False
    assert engine.is_degraded is True
    assert engine.process(_silence_frame()) is False
    engine.stop()


def test_falha_no_reconhecedor_degrada(fake_vosk):
    """Erro no KaldiRecognizer aciona degradação graciosa."""
    fake_vosk.raise_on_recognizer = True
    engine = WakeWordEngine()
    assert engine.start() is False
    assert engine.is_degraded is True
    assert engine.process(_silence_frame()) is False
    engine.stop()


async def test_load_vosk_real_indisponivel():
    """No ambiente de teste o vosk real não está instalado: retorna None."""
    import svc.wakeword as wakeword

    assert wakeword._load_vosk() is None


# --- Fuzzy matching -----------------------------------------------------------


def test_is_wake_word_exato(fake_vosk):
    """Texto idêntico à keyword é reconhecido."""
    engine = WakeWordEngine()
    assert engine._is_wake_word("aurion") is True
    engine.stop()


def test_is_wake_word_substring(fake_vosk):
    """Texto que contém a keyword é reconhecido por substring."""
    engine = WakeWordEngine()
    assert engine._is_wake_word("oi aurion") is True
    assert engine._is_wake_word("tchau aurion") is True
    assert engine._is_wake_word("outra coisa") is False
    engine.stop()


def test_is_wake_word_case_insensitive(fake_vosk):
    """Detecção é case-insensitive."""
    engine = WakeWordEngine()
    assert engine._is_wake_word("AURION") is True
    assert engine._is_wake_word("AuRiOn") is True
    engine.stop()
