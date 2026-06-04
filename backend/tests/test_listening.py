"""Testes unitários e de integração do Listening Service.

Todos os testes usam mocks/monkeypatch de TODOS os serviços (wakeword, STT,
Hermes, TTS), do repositório e do ``pyaudio`` — não exigem hardware, binários
nativos nem rede. Cobrem: inicialização do loop em thread dedicada, captura de
áudio (mock), detecção de wake word acionando o pipeline, VAD encerrando a
captura por silêncio, pipeline completo, notificação de estados, roteamento de
resposta local/web, persistência, graceful shutdown, tolerância a erros e
medição de latência por etapa.
"""

from __future__ import annotations

import asyncio
import struct
import sys
import types

import pytest

import svc.listening as listening_mod
from models.response import APIError, HermesResponse
from svc.hermes_bridge import HermesError
from svc.listening import ListeningConfig, ListeningService, _frame_rms


# --- Fakes / helpers ---------------------------------------------------------


def _pcm(amplitude: int, samples: int = 16) -> bytes:
    """Gera um frame PCM int16 com a amplitude informada (todos os samples iguais)."""
    return struct.pack(f"<{samples}h", *([amplitude] * samples))


# Frames de áudio "altos" (fala) e "silenciosos" usados nos testes de VAD.
_SPEECH_FRAME = _pcm(5000)
_SILENCE_FRAME = _pcm(0)


class FakeStream:
    """Stream PyAudio falso que entrega frames de uma lista pré-definida."""

    def __init__(self, frames: list[bytes]) -> None:
        self._frames = list(frames)
        self.closed = False
        self.stopped = False

    def read(self, chunk_size, exception_on_overflow=False):
        if self._frames:
            return self._frames.pop(0)
        return b""

    def stop_stream(self):
        self.stopped = True

    def close(self):
        self.closed = True


class FakePyAudioInstance:
    """Instância PyAudio falsa que devolve um ``FakeStream`` pré-configurado."""

    def __init__(self, stream: FakeStream) -> None:
        self._stream = stream
        self.terminated = False

    def open(self, **kwargs):
        self.open_kwargs = kwargs
        return self._stream

    def terminate(self):
        self.terminated = True


def _fake_pyaudio_module(stream: FakeStream) -> types.ModuleType:
    """Cria um módulo ``pyaudio`` falso para o import lazy do serviço."""
    module = types.ModuleType("pyaudio")
    module.paInt16 = 8  # type: ignore[attr-defined]
    instance = FakePyAudioInstance(stream)
    module.PyAudio = lambda: instance  # type: ignore[attr-defined]
    module._instance = instance  # type: ignore[attr-defined]
    return module


class FakeWakeWord:
    """Wake word engine falso: detecta na N-ésima chamada de ``process``."""

    def __init__(self, detect_at: int | None = 1) -> None:
        self._detect_at = detect_at
        self.calls = 0
        self.started = False

    def start(self):
        self.started = True
        return True

    def process(self, frame: bytes) -> bool:
        self.calls += 1
        return self._detect_at is not None and self.calls == self._detect_at


class FakeSTT:
    """STT falso que retorna um texto fixo (ou vazio)."""

    def __init__(self, text: str = "ligar a luz") -> None:
        self._text = text
        self.received: bytes | None = None

    async def transcribe(self, audio):
        self.received = audio
        return self._text


class FakeHermes:
    """Hermes falso que retorna uma resposta fixa ou levanta ``HermesError``."""

    def __init__(self, reply: str = "luz ligada", error: HermesError | None = None):
        self._reply = reply
        self._error = error
        self.received: str | None = None

    async def send_command(self, message: str) -> HermesResponse:
        self.received = message
        if self._error is not None:
            raise self._error
        return HermesResponse(reply=self._reply, status_code=200, raw={})


class FakeTTS:
    """TTS falso que emite chunks de áudio progressivamente."""

    def __init__(self, chunks: list[bytes] | None = None) -> None:
        self._chunks = chunks if chunks is not None else [b"a1", b"a2", b"a3"]
        self.received: str | None = None

    async def synthesize(self, text: str):
        self.received = text
        for chunk in self._chunks:
            yield chunk


class FakeRepo:
    """Repositório falso que registra as interações criadas."""

    def __init__(self) -> None:
        self.created: list[object] = []

    async def create_interaction(self, data):
        self.created.append(data)
        return data


def _make_service(
    *,
    frames: list[bytes],
    wakeword: FakeWakeWord | None = None,
    stt: FakeSTT | None = None,
    hermes: FakeHermes | None = None,
    tts: FakeTTS | None = None,
    repo: FakeRepo | None = None,
    config: ListeningConfig | None = None,
    on_state=None,
    on_audio=None,
    monkeypatch=None,
):
    """Monta um ``ListeningService`` com dependências falsas e PyAudio mockado."""
    stream = FakeStream(frames)
    if monkeypatch is not None:
        module = _fake_pyaudio_module(stream)
        monkeypatch.setitem(sys.modules, "pyaudio", module)

    service = ListeningService(
        wakeword=wakeword or FakeWakeWord(),
        stt=stt or FakeSTT(),
        hermes=hermes or FakeHermes(),
        tts=tts or FakeTTS(),
        repository=repo or FakeRepo(),
        config=config
        or ListeningConfig(
            chunk_size=16,
            sample_rate=16000,
            silence_threshold=300,
            silence_duration=0.001,
            wake_word_timeout=0.01,
            max_utterance_seconds=1.0,
        ),
        on_state=on_state,
        on_audio=on_audio,
    )
    return service, stream


# --- RMS / VAD (unidade) -----------------------------------------------------


def test_frame_rms_silencio_e_fala():
    assert _frame_rms(b"") == 0.0
    assert _frame_rms(_SILENCE_FRAME) == 0.0
    assert _frame_rms(_SPEECH_FRAME) == pytest.approx(5000.0)


# --- Ciclo de vida / thread dedicada -----------------------------------------


def test_start_inicia_thread_dedicada(monkeypatch):
    # Stream que nunca detecta: o loop fica em "listening" até o stop.
    frames = [_SILENCE_FRAME] * 1000
    service, _ = _make_service(
        frames=frames, wakeword=FakeWakeWord(detect_at=None), monkeypatch=monkeypatch
    )
    service.start()
    assert service.is_running is True
    service.stop(timeout=2.0)
    assert service.is_running is False
    assert service.state == "idle"


def test_start_idempotente(monkeypatch):
    frames = [_SILENCE_FRAME] * 1000
    service, _ = _make_service(
        frames=frames, wakeword=FakeWakeWord(detect_at=None), monkeypatch=monkeypatch
    )
    service.start()
    thread1 = service._thread
    service.start()  # segunda chamada não cria nova thread
    assert service._thread is thread1
    service.stop(timeout=2.0)


def test_graceful_shutdown_libera_stream(monkeypatch):
    frames = [_SILENCE_FRAME] * 1000
    service, stream = _make_service(
        frames=frames, wakeword=FakeWakeWord(detect_at=None), monkeypatch=monkeypatch
    )
    service.start()
    service.stop(timeout=2.0)
    assert stream.closed is True
    assert stream.stopped is True


# --- Degradação graciosa (PyAudio indisponível) ------------------------------


def test_pyaudio_indisponivel_modo_degradado(monkeypatch):
    # Força o import lazy a falhar.
    monkeypatch.setattr(listening_mod, "_load_pyaudio", lambda: None)
    estados: list[tuple] = []
    service, _ = _make_service(
        frames=[], on_state=lambda s, m: estados.append((s, m))
    )
    loop = asyncio.new_event_loop()
    try:
        service._listen_forever(loop)
    finally:
        loop.close()
    assert service.is_degraded is True
    assert service.state == "error"
    assert any(s == "error" for s, _ in estados)


# --- Detecção de wake word aciona o pipeline ---------------------------------


def test_wake_word_aciona_pipeline(monkeypatch):
    # Frame de wake word, depois fala, depois silêncio para encerrar a captura.
    frames = [_SPEECH_FRAME, _SPEECH_FRAME, _SILENCE_FRAME, _SILENCE_FRAME]
    wake = FakeWakeWord(detect_at=1)
    stt = FakeSTT("acender a luz")
    hermes = FakeHermes("luz acesa")
    tts = FakeTTS([b"x"])
    repo = FakeRepo()
    service, stream = _make_service(
        frames=frames,
        wakeword=wake,
        stt=stt,
        hermes=hermes,
        tts=tts,
        repo=repo,
        monkeypatch=monkeypatch,
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        service._listen_once(loop, stream)
    finally:
        loop.close()

    assert hermes.received == "acender a luz"
    assert tts.received == "luz acesa"
    assert len(repo.created) == 1


# --- VAD encerrando a captura por silêncio -----------------------------------


def test_vad_encerra_captura_por_silencio(monkeypatch):
    # 2 frames de fala seguidos de silêncio: a captura deve incluir a fala e
    # parar ao detectar o silêncio (silence_duration mínimo).
    frames = [_SPEECH_FRAME, _SPEECH_FRAME, _SILENCE_FRAME]
    service, stream = _make_service(frames=frames, monkeypatch=monkeypatch)
    captured = service._capture_utterance(stream)
    # Deve conter pelo menos os frames de fala.
    assert len(captured) >= len(_SPEECH_FRAME)
    assert captured.startswith(_SPEECH_FRAME)


def test_vad_timeout_sem_fala_retorna_vazio(monkeypatch):
    # Só silêncio: estoura o wake_word_timeout e retorna vazio.
    frames = [_SILENCE_FRAME] * 50
    config = ListeningConfig(
        chunk_size=16, sample_rate=16000, wake_word_timeout=0.001
    )
    service, stream = _make_service(
        frames=frames, config=config, monkeypatch=monkeypatch
    )
    captured = service._capture_utterance(stream)
    assert captured == b""


# --- Pipeline completo (integração com mocks) --------------------------------


def test_pipeline_completo_persiste_sucesso(monkeypatch):
    stt = FakeSTT("qual a previsão do tempo")
    hermes = FakeHermes("sol o dia todo")
    tts = FakeTTS([b"c1", b"c2"])
    repo = FakeRepo()
    service, _ = _make_service(
        frames=[], stt=stt, hermes=hermes, tts=tts, repo=repo
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        service._process_command(loop, _SPEECH_FRAME)
    finally:
        loop.close()

    assert len(repo.created) == 1
    interacao = repo.created[0]
    assert interacao.input_text == "qual a previsão do tempo"
    assert interacao.output_text == "sol o dia todo"
    assert interacao.status == "success"
    assert interacao.duration_ms is not None


def test_pipeline_stt_vazio_descarta_comando(monkeypatch):
    stt = FakeSTT("")  # transcrição vazia
    hermes = FakeHermes()
    repo = FakeRepo()
    service, _ = _make_service(frames=[], stt=stt, hermes=hermes, repo=repo)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        service._process_command(loop, _SPEECH_FRAME)
    finally:
        loop.close()

    assert hermes.received is None  # Hermes não foi chamado
    assert repo.created == []  # nada persistido


# --- Notificação de estados via WebSocket (callback) -------------------------


def test_notificacao_estados_pipeline(monkeypatch):
    estados: list[str] = []
    service, _ = _make_service(
        frames=[],
        stt=FakeSTT("oi"),
        hermes=FakeHermes("olá"),
        tts=FakeTTS([b"a"]),
        on_state=lambda s, m: estados.append(s),
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        service._process_command(loop, _SPEECH_FRAME)
    finally:
        loop.close()

    # Estados intermediários do pipeline devem ser emitidos na ordem.
    assert "stt" in estados
    assert "processing" in estados
    assert "tts" in estados
    assert estados.index("stt") < estados.index("processing") < estados.index("tts")


def test_callback_estado_com_erro_nao_derruba(monkeypatch):
    def _boom(state, message):
        raise RuntimeError("callback quebrado")

    service, _ = _make_service(frames=[], on_state=_boom)
    # Não deve propagar a exceção do callback.
    service._set_state("listening")
    assert service.state == "listening"


# --- Roteamento de resposta --------------------------------------------------


def test_roteamento_local_agrega_chunks(monkeypatch):
    tts = FakeTTS([b"p1", b"p2", b"p3"])
    config = ListeningConfig(channel="local")
    service, _ = _make_service(frames=[], tts=tts, config=config)
    reproduzido: list[bytes] = []
    monkeypatch.setattr(service, "_play_local", lambda audio: reproduzido.append(audio))

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(service._route_response("fala"))
    finally:
        loop.close()

    assert reproduzido == [b"p1p2p3"]


def test_roteamento_web_emite_cada_chunk(monkeypatch):
    tts = FakeTTS([b"w1", b"w2", b"w3"])
    config = ListeningConfig(channel="web")
    emitidos: list[bytes] = []
    service, _ = _make_service(
        frames=[], tts=tts, config=config, on_audio=lambda chunk: emitidos.append(chunk)
    )
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(service._route_response("fala"))
    finally:
        loop.close()

    # Reprodução progressiva: cada chunk entregue individualmente ao WebSocket.
    assert emitidos == [b"w1", b"w2", b"w3"]


def test_roteamento_web_callback_async(monkeypatch):
    tts = FakeTTS([b"x", b"y"])
    config = ListeningConfig(channel="web")
    emitidos: list[bytes] = []

    async def _async_audio(chunk):
        emitidos.append(chunk)

    service, _ = _make_service(
        frames=[], tts=tts, config=config, on_audio=_async_audio
    )
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(service._route_response("fala"))
    finally:
        loop.close()

    assert emitidos == [b"x", b"y"]


# --- Tratamento de erro no pipeline ------------------------------------------


def test_erro_hermes_persiste_erro_e_continua(monkeypatch):
    erro = HermesError(
        APIError(code="HERMES_UNAVAILABLE", message="Hermes indisponível")
    )
    hermes = FakeHermes(error=erro)
    repo = FakeRepo()
    estados: list[str] = []
    service, _ = _make_service(
        frames=[],
        stt=FakeSTT("teste"),
        hermes=hermes,
        repo=repo,
        on_state=lambda s, m: estados.append(s),
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        service._process_command(loop, _SPEECH_FRAME)
    finally:
        loop.close()

    assert "error" in estados
    assert len(repo.created) == 1
    assert repo.created[0].status == "error"
    assert "indisponível" in repo.created[0].error_message


def test_erro_hermes_timeout_status(monkeypatch):
    erro = HermesError(APIError(code="HERMES_TIMEOUT", message="tempo limite"))
    hermes = FakeHermes(error=erro)
    repo = FakeRepo()
    service, _ = _make_service(
        frames=[], stt=FakeSTT("teste"), hermes=hermes, repo=repo
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        service._process_command(loop, _SPEECH_FRAME)
    finally:
        loop.close()

    assert repo.created[0].status == "timeout"


def test_erro_tts_persiste_erro(monkeypatch):
    class BrokenTTS:
        async def synthesize(self, text):
            raise RuntimeError("falha no TTS")
            yield  # pragma: no cover

    repo = FakeRepo()
    service, _ = _make_service(
        frames=[], stt=FakeSTT("teste"), tts=BrokenTTS(), repo=repo
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        service._process_command(loop, _SPEECH_FRAME)
    finally:
        loop.close()

    assert repo.created[0].status == "error"


def test_erro_persistencia_nao_derruba(monkeypatch):
    class BrokenRepo:
        async def create_interaction(self, data):
            raise RuntimeError("banco fora do ar")

    service, _ = _make_service(
        frames=[], stt=FakeSTT("teste"), repo=BrokenRepo()
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Não deve propagar exceção mesmo com o repositório falhando.
        service._process_command(loop, _SPEECH_FRAME)
    finally:
        loop.close()


# --- Medição de latência por etapa -------------------------------------------


def test_latencia_por_etapa(monkeypatch):
    service, _ = _make_service(
        frames=[], stt=FakeSTT("oi"), hermes=FakeHermes("ola"), tts=FakeTTS([b"a"])
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        service._process_command(loop, _SPEECH_FRAME)
    finally:
        loop.close()

    latencias = service.last_latencies
    assert "stt" in latencias
    assert "hermes" in latencias
    assert "tts" in latencias
    assert "total" in latencias
    assert all(v >= 0 for v in latencias.values())


# --- Captura de áudio via PyAudio (mock) -------------------------------------


def test_read_frame_le_do_stream(monkeypatch):
    frames = [_SPEECH_FRAME]
    service, stream = _make_service(frames=frames, monkeypatch=monkeypatch)
    frame = service._read_frame(stream)
    assert frame == _SPEECH_FRAME


def test_await_wake_word_detecta(monkeypatch):
    frames = [_SILENCE_FRAME, _SILENCE_FRAME, _SPEECH_FRAME]
    wake = FakeWakeWord(detect_at=3)
    service, stream = _make_service(
        frames=frames, wakeword=wake, monkeypatch=monkeypatch
    )
    assert service._await_wake_word(stream) is True
    assert wake.calls == 3
