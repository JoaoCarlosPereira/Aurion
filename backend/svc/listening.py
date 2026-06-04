"""Listening Service — loop principal de escuta do Aurion.

Implementa o "cérebro" do sistema (TechSpec Seção 5.1): um serviço que roda em
uma **thread dedicada** (ADR-002, para mitigar o GIL e não bloquear o event loop
do FastAPI) operando em loop contínuo:

```
[Captura PyAudio 16kHz/1canal] -> [Wake Word] -> (detectado)
    -> [Captura fala até silêncio (VAD)] -> [STT] -> [Hermes] -> [TTS]
    -> [Roteamento da resposta (local/web)] -> [Persiste interação] -> [Reinicia]
```

Princípios de projeto:

- **Thread dedicada + event loop próprio**: o PyAudio captura áudio de forma
  síncrona/bloqueante; por isso o loop roda em uma thread separada. Os serviços
  do pipeline (STT, Hermes, TTS, repositório) são assíncronos, então a thread
  cria seu próprio ``asyncio`` event loop para acioná-los via
  ``run_coroutine``-like (``loop.run_until_complete``).
- **Import lazy do PyAudio + degradação graciosa**: o ``pyaudio`` não está
  disponível em todos os ambientes (CI/testes). O import é feito sob demanda; se
  indisponível, o serviço entra em modo degradado (estado ``error``) e não
  consome CPU em busy-loop, conforme TechSpec Seção 10 ("Microfone inacessível").
- **Notificação de estado**: cada transição (idle/listening/detecting/stt/
  processing/tts/error) é notificada via um callback opcional (síncrono), que o
  endpoint de WebSocket (task_10) consome para broadcast. O serviço também
  mantém o estado corrente acessível em ``state``.
- **Roteamento da resposta**: o áudio sintetizado é roteado para o speaker local
  (canal ``local``) e/ou entregue via callback de áudio (canal ``web``,
  WebSocket). A reprodução é progressiva: começa a rotear assim que os primeiros
  chunks do TTS chegam.
- **Tolerância a falhas por etapa**: uma exceção em qualquer etapa do pipeline é
  registrada, notificada como estado ``error``, persistida (quando possível) e o
  loop **continua** (não derruba o serviço).
- **Métricas de latência**: a duração de cada etapa é medida e a duração total é
  persistida em ``duration_ms``; as latências por etapa ficam disponíveis na
  última execução para diagnóstico.

Este módulo NÃO edita ``main.py`` nem o router (wiring é da task_18). Os
serviços (wakeword/stt/tts/hermes) e o repositório são injetados no construtor.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:  # pragma: no cover - apenas para type hints
    import numpy as np

from db.models import InteractionCreate
from svc.hermes_bridge import HermesBridge, HermesError
from svc.stt import STTService
from svc.tts import TTSService
from svc.wakeword import WakeWordEngine

logger = logging.getLogger(__name__)

# Estados do sistema notificados via WebSocket (TechSpec Seção 6.2).
SystemState = Literal[
    "idle", "listening", "detecting", "stt", "processing", "tts", "error"
]

# Canal de origem/destino da interação (TechSpec Seção 3.3).
Channel = Literal["local", "web"]

# Callback de notificação de estado: recebe o novo estado e uma mensagem opcional.
StateCallback = Callable[[SystemState, str | None], None]

# Callback de roteamento de áudio para a web (WebSocket): recebe cada chunk de
# áudio sintetizado (bytes). Pode ser síncrono ou assíncrono.
AudioCallback = Callable[[bytes], None] | Callable[[bytes], Awaitable[None]]


class ListeningConfig:
    """Parâmetros operacionais do loop de escuta (independente de ``config.json``).

    Mantido como classe simples (não Pydantic) para evitar acoplamento com o
    Config Manager; o wiring (task_18) pode preencher estes valores a partir do
    bloco ``audio`` do ``AppConfig``.
    """

    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
        silence_threshold: int = 300,
        wake_word_timeout: float = 10.0,
        silence_duration: float = 1.5,
        max_utterance_seconds: float = 15.0,
        channel: Channel = "local",
    ) -> None:
        """Inicializa a configuração do loop.

        Args:
            sample_rate: taxa de amostragem da captura (16kHz por padrão).
            channels: número de canais (mono por padrão).
            chunk_size: frames por leitura do stream PyAudio.
            silence_threshold: limiar de amplitude (RMS PCM int16) abaixo do qual
                o frame é considerado silêncio (VAD).
            wake_word_timeout: tempo (s) aguardando fala após detecção do wake
                word antes de voltar ao modo escuta.
            silence_duration: duração (s) de silêncio contínuo que encerra a
                captura de fala (VAD, faixa típica 1-3s).
            max_utterance_seconds: limite máximo (s) de captura de uma fala.
            channel: canal padrão das interações originadas neste serviço.
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.silence_threshold = silence_threshold
        self.wake_word_timeout = wake_word_timeout
        self.silence_duration = silence_duration
        self.max_utterance_seconds = max_utterance_seconds
        self.channel = channel


def _load_pyaudio():
    """Importa o ``pyaudio`` de forma lazy (degradação graciosa).

    Retorna o módulo importado ou ``None`` se a biblioteca não estiver
    disponível no ambiente (ex.: CI/testes sem hardware de áudio).
    """
    try:
        import pyaudio  # type: ignore[import-not-found]

        return pyaudio
    except Exception as exc:  # noqa: BLE001 — qualquer falha de import degrada.
        logger.warning(
            "pyaudio indisponível (%s); Listening Service operará em modo degradado.",
            exc,
        )
        return None


def _frame_rms(frame: bytes) -> float:
    """Calcula a amplitude RMS de um frame PCM int16 (little-endian).

    Usada pelo VAD para distinguir fala de silêncio. Implementada com a stdlib
    (``struct``) para não exigir ``numpy`` no caminho crítico do loop.
    """
    if not frame:
        return 0.0
    import struct

    count = len(frame) // 2
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", frame[: count * 2])
    total = 0
    for sample in samples:
        total += sample * sample
    return (total / count) ** 0.5


class ListeningService:
    """Serviço de escuta contínua que orquestra o pipeline de voz do Aurion.

    Orquestra, em uma thread dedicada: captura de áudio (PyAudio) -> detecção de
    wake word -> captura de fala até silêncio (VAD) -> STT -> Hermes -> TTS ->
    roteamento da resposta -> persistência -> notificação de estado.

    Os serviços e o repositório são injetados, permitindo que os testes os
    substituam por mocks (sem hardware/binários/rede).
    """

    def __init__(
        self,
        *,
        wakeword: WakeWordEngine,
        stt: STTService,
        hermes: HermesBridge,
        tts: TTSService,
        repository: object,
        config: ListeningConfig | None = None,
        on_state: StateCallback | None = None,
        on_audio: AudioCallback | None = None,
    ) -> None:
        """Inicializa o serviço com as dependências do pipeline.

        Args:
            wakeword: engine de detecção de wake word.
            stt: serviço de Speech-to-Text.
            hermes: bridge HTTP para o Hermes Agent.
            tts: serviço de Text-to-Speech.
            repository: repositório de interações (``InteractionRepository``);
                tipado como ``object`` para evitar acoplamento com a camada de db.
            config: parâmetros operacionais do loop (usa padrões se omitido).
            on_state: callback de notificação de estado (WebSocket, task_10).
            on_audio: callback de roteamento de áudio para a web (WebSocket).
        """
        self._wakeword = wakeword
        self._stt = stt
        self._hermes = hermes
        self._tts = tts
        self._repository = repository
        self._config = config or ListeningConfig()
        self._on_state = on_state
        self._on_audio = on_audio

        # Estado de ciclo de vida.
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._state: SystemState = "idle"
        self._degraded = False
        self._lock = threading.Lock()

        # Latências (ms) por etapa da última execução do pipeline (diagnóstico).
        self._last_latencies: dict[str, float] = {}

    # --- Propriedades --------------------------------------------------------

    @property
    def state(self) -> SystemState:
        """Estado corrente do sistema."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Indica se a thread de escuta está ativa."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_degraded(self) -> bool:
        """Indica se o serviço está em modo degradado (PyAudio indisponível)."""
        return self._degraded

    @property
    def config(self) -> ListeningConfig:
        """Configuração operacional do loop."""
        return self._config

    @property
    def last_latencies(self) -> dict[str, float]:
        """Latências (ms) por etapa medidas na última execução do pipeline."""
        return dict(self._last_latencies)

    # --- Ciclo de vida -------------------------------------------------------

    def start(self) -> None:
        """Inicia o loop de escuta em uma thread dedicada (idempotente)."""
        with self._lock:
            if self.is_running:
                logger.debug("Listening Service já está em execução; ignorando start.")
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="aurion-listening",
                daemon=True,
            )
            self._thread.start()
            logger.info("Listening Service iniciado (thread dedicada).")

    def stop(self, timeout: float = 5.0) -> None:
        """Sinaliza o encerramento e aguarda a thread terminar (graceful shutdown).

        Args:
            timeout: tempo máximo (s) aguardando a thread encerrar.
        """
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None
        self._set_state("idle")
        logger.info("Listening Service encerrado.")

    # --- Loop principal (executa na thread dedicada) -------------------------

    def _run_loop(self) -> None:
        """Ponto de entrada da thread: prepara o event loop e roda o loop de escuta.

        Cria um ``asyncio`` event loop exclusivo desta thread para acionar os
        serviços assíncronos do pipeline. Garante o fechamento do loop e do
        stream de áudio ao encerrar.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            self._listen_forever(loop)
        except Exception as exc:  # noqa: BLE001 — protege a thread de crashar.
            logger.exception("Erro fatal no loop de escuta: %s", exc)
            self._set_state("error", "Erro fatal no loop de escuta.")
        finally:
            try:
                loop.close()
            except Exception:  # noqa: BLE001 - defensivo no shutdown
                pass

    def _listen_forever(self, loop: asyncio.AbstractEventLoop) -> None:
        """Loop contínuo de captura, detecção e processamento de comandos.

        Abre o stream de áudio (PyAudio) e, enquanto não for sinalizado o
        encerramento, detecta o wake word e processa cada comando. Em modo
        degradado (PyAudio indisponível), apenas marca o estado de erro e
        retorna sem consumir CPU.
        """
        pyaudio_module = _load_pyaudio()
        if pyaudio_module is None:
            self._degraded = True
            self._set_state(
                "error",
                "Microfone indisponível: PyAudio não instalado.",
            )
            return

        # Inicia o engine de wake word (pode degradar para no-op internamente).
        try:
            self._wakeword.start()
        except Exception as exc:  # noqa: BLE001 - não derruba o loop
            logger.error("Falha ao iniciar o wake word engine: %s", exc)

        stream, audio = self._open_stream(pyaudio_module)
        if stream is None:
            self._degraded = True
            self._set_state("error", "Não foi possível abrir o stream de áudio.")
            return

        self._set_state("listening")
        try:
            while not self._stop_event.is_set():
                self._listen_once(loop, stream)
        finally:
            self._close_stream(stream, audio)

    def _open_stream(self, pyaudio_module):
        """Abre o stream de captura PyAudio (16kHz, mono) — ponto de mock nos testes.

        Returns:
            Tupla ``(stream, audio)`` com o stream aberto e a instância PyAudio,
            ou ``(None, None)`` em caso de falha (degradação graciosa).
        """
        try:
            audio = pyaudio_module.PyAudio()
            stream = audio.open(
                format=pyaudio_module.paInt16,
                channels=self._config.channels,
                rate=self._config.sample_rate,
                input=True,
                frames_per_buffer=self._config.chunk_size,
            )
            return stream, audio
        except Exception as exc:  # noqa: BLE001 - degradação graciosa
            logger.error("Falha ao abrir o stream de áudio PyAudio: %s", exc)
            return None, None

    def _close_stream(self, stream, audio) -> None:
        """Fecha e libera o stream de áudio e a instância PyAudio (defensivo)."""
        for closer in (
            lambda: stream.stop_stream(),
            lambda: stream.close(),
            lambda: audio.terminate() if audio is not None else None,
        ):
            try:
                closer()
            except Exception as exc:  # noqa: BLE001 - não propaga no shutdown
                logger.debug("Erro ao liberar recurso de áudio: %s", exc)

    def _listen_once(self, loop: asyncio.AbstractEventLoop, stream) -> None:
        """Executa uma iteração: detecta wake word e, se houver, processa o comando.

        Mantida pública-ish para que os testes exercitem uma única iteração sem
        loop infinito. Exceções são tratadas para não derrubar o loop principal.
        """
        try:
            detected = self._await_wake_word(stream)
            if not detected:
                return

            self._set_state("detecting", "Wake word detectada.")
            audio_bytes = self._capture_utterance(stream)
            if not audio_bytes:
                # Timeout sem fala: volta ao modo escuta (TechSpec 5.2).
                self._set_state("listening")
                return

            self._process_command(loop, audio_bytes)
        except Exception as exc:  # noqa: BLE001 - o loop deve continuar
            logger.exception("Erro na iteração do loop de escuta: %s", exc)
            self._set_state("error", "Falha ao processar comando de voz.")
        finally:
            # Após processar (ou falhar), retorna ao modo escuta se ainda ativo.
            if not self._stop_event.is_set():
                self._set_state("listening")

    # --- Etapas do pipeline --------------------------------------------------

    def _read_frame(self, stream) -> bytes:
        """Lê um frame de áudio do stream, tolerando overflow do buffer."""
        try:
            return stream.read(
                self._config.chunk_size, exception_on_overflow=False
            )
        except TypeError:
            # Mocks/streams simples podem não aceitar o kwarg; tenta sem ele.
            return stream.read(self._config.chunk_size)

    def _await_wake_word(self, stream) -> bool:
        """Lê frames e processa no wake word engine até detectar ou ser parado.

        Returns:
            True se a wake word foi detectada; False se o serviço foi sinalizado
            para parar antes da detecção.
        """
        while not self._stop_event.is_set():
            frame = self._read_frame(stream)
            if not frame:
                return False
            if self._wakeword.process(frame):
                return True
        return False

    def _capture_utterance(self, stream) -> bytes:
        """Captura a fala após o wake word até detectar silêncio (VAD).

        Acumula frames enquanto houver voz; encerra quando o silêncio contínuo
        atinge ``silence_duration`` (TechSpec: 1-3s) ou ao atingir o limite
        ``max_utterance_seconds``. Se nenhuma fala for detectada dentro de
        ``wake_word_timeout``, retorna bytes vazios (volta ao modo escuta).

        Returns:
            Áudio PCM 16-bit concatenado da fala capturada (``bytes``), ou vazio.
        """
        chunk_seconds = self._config.chunk_size / float(self._config.sample_rate)
        max_silence_chunks = max(1, int(self._config.silence_duration / chunk_seconds))
        max_total_chunks = max(1, int(self._config.max_utterance_seconds / chunk_seconds))
        timeout_chunks = max(1, int(self._config.wake_word_timeout / chunk_seconds))

        frames: list[bytes] = []
        silence_run = 0
        speech_started = False
        chunks_read = 0

        while not self._stop_event.is_set():
            frame = self._read_frame(stream)
            if not frame:
                break
            chunks_read += 1

            is_silence = _frame_rms(frame) < self._config.silence_threshold

            if not speech_started:
                # Aguardando o início da fala: descarta silêncio inicial até o
                # timeout; ao primeiro frame com voz, começa a acumular.
                if is_silence:
                    if chunks_read >= timeout_chunks:
                        return b""
                    continue
                speech_started = True

            frames.append(frame)

            if is_silence:
                silence_run += 1
                if silence_run >= max_silence_chunks:
                    break
            else:
                silence_run = 0

            if len(frames) >= max_total_chunks:
                break

        return b"".join(frames)

    def _process_command(
        self, loop: asyncio.AbstractEventLoop, audio_bytes: bytes
    ) -> None:
        """Conduz o pipeline STT -> Hermes -> TTS -> roteamento -> persistência.

        Mede a latência de cada etapa, notifica os estados intermediários e
        persiste a interação (sucesso ou erro). Não propaga exceções: falhas são
        registradas e persistidas, e o loop principal continua.
        """
        self._last_latencies = {}
        started = time.monotonic()
        input_text = ""
        output_text: str | None = None
        status: Literal["success", "error", "timeout"] = "success"
        error_message: str | None = None

        try:
            # --- STT -------------------------------------------------------
            self._set_state("stt", "Transcrevendo a fala.")
            input_text = self._timed(
                loop, "stt", self._stt.transcribe(audio_bytes)
            )
            if not input_text:
                logger.info("STT não produziu texto; descartando comando.")
                return

            # --- Hermes ----------------------------------------------------
            self._set_state("processing", "Consultando o Hermes.")
            try:
                hermes_response = self._timed(
                    loop, "hermes", self._hermes.send_command(input_text)
                )
                output_text = hermes_response.reply
            except HermesError as exc:
                status = (
                    "timeout"
                    if exc.code.endswith("TIMEOUT")
                    else "error"
                )
                error_message = exc.error.message
                self._set_state("error", error_message)
                logger.error("Hermes indisponível: %s", error_message)
                return

            # --- TTS + roteamento -----------------------------------------
            self._set_state("tts", "Sintetizando a resposta.")
            self._timed(
                loop, "tts", self._route_response(output_text)
            )
        except Exception as exc:  # noqa: BLE001 - persiste o erro e continua
            status = "error"
            error_message = f"Falha no pipeline: {exc}"
            self._set_state("error", error_message)
            logger.exception("Erro no processamento do comando: %s", exc)
        finally:
            total_ms = (time.monotonic() - started) * 1000.0
            self._last_latencies["total"] = total_ms
            # Só persiste se houve algum texto de entrada (caso contrário não há
            # interação significativa a registrar).
            if input_text or error_message:
                self._persist_interaction(
                    loop,
                    input_text=input_text,
                    output_text=output_text,
                    duration_ms=int(total_ms),
                    status=status,
                    error_message=error_message,
                )

    async def _route_response(self, text: str) -> None:
        """Roteia a resposta sintetizada (TTS) progressivamente.

        Consome o gerador assíncrono de chunks do TTS e os encaminha assim que
        chegam (reprodução progressiva): para o canal ``web``, entrega cada
        chunk ao callback de áudio (WebSocket); para o canal ``local``, agrega os
        chunks para reprodução no speaker (``_play_local``).
        """
        local_chunks: list[bytes] = []
        async for chunk in self._tts.synthesize(text):
            if not chunk:
                continue
            if self._config.channel == "web" and self._on_audio is not None:
                await self._emit_audio(chunk)
            else:
                local_chunks.append(chunk)
        if local_chunks:
            self._play_local(b"".join(local_chunks))

    async def _emit_audio(self, chunk: bytes) -> None:
        """Entrega um chunk de áudio ao callback web, tolerando callbacks sync/async."""
        if self._on_audio is None:
            return
        try:
            result = self._on_audio(chunk)
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:  # noqa: BLE001 - não derruba o pipeline
            logger.error("Falha ao rotear áudio para a web: %s", exc)

    def _play_local(self, audio: bytes) -> None:
        """Reproduz o áudio no speaker local (ponto de extensão/mock nos testes).

        A reprodução real depende de hardware/biblioteca de saída; aqui o método
        é mantido como ponto de extensão e apenas registra a entrega, mantendo o
        serviço testável sem hardware.
        """
        logger.debug("Reproduzindo %d bytes de áudio no speaker local.", len(audio))

    def _persist_interaction(
        self,
        loop: asyncio.AbstractEventLoop,
        *,
        input_text: str,
        output_text: str | None,
        duration_ms: int,
        status: Literal["success", "error", "timeout"],
        error_message: str | None,
    ) -> None:
        """Persiste a interação no banco via repositório (degradação graciosa).

        Erros de persistência são registrados mas não propagados, para não
        derrubar o loop de escuta.
        """
        data = InteractionCreate(
            channel=self._config.channel,
            input_text=input_text or "",
            output_text=output_text,
            duration_ms=duration_ms,
            status=status,
            error_message=error_message,
        )
        try:
            loop.run_until_complete(self._repository.create_interaction(data))
        except Exception as exc:  # noqa: BLE001 - não derruba o loop
            logger.error("Falha ao persistir interação: %s", exc)

    # --- Utilitários ---------------------------------------------------------

    def _timed(
        self,
        loop: asyncio.AbstractEventLoop,
        stage: str,
        coro: Awaitable,
    ):
        """Executa uma coroutine medindo sua latência (ms) e registrando-a.

        Roda a coroutine de forma síncrona no event loop da thread dedicada e
        armazena a duração da etapa em ``_last_latencies[stage]``.
        """
        start = time.monotonic()
        try:
            return loop.run_until_complete(coro)
        finally:
            self._last_latencies[stage] = (time.monotonic() - start) * 1000.0

    def _set_state(self, state: SystemState, message: str | None = None) -> None:
        """Atualiza o estado corrente e notifica via callback (sem propagar erro)."""
        self._state = state
        if self._on_state is None:
            return
        try:
            self._on_state(state, message)
        except Exception as exc:  # noqa: BLE001 - callback não derruba o serviço
            logger.error("Callback de estado falhou: %s", exc)
