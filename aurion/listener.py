"""VoiceListener — Módulo de escuta contínua com wake word e modo conversa."""

import logging
import os
import queue
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from aurion.audio_devices import get_mic_index, resolve_mic_index

logger = logging.getLogger("aurion.listener")

_OI_PLAYBACK_DELAY = 0.35
_UTTERANCE_SILENCE_SEC = float(os.getenv("VOICE_UTTERANCE_SILENCE_SEC", "2.5"))
_CONVERSATION_PAUSE_THRESHOLD = float(os.getenv("VOICE_PAUSE_THRESHOLD", "1.0"))
_WAKE_PHRASE_LIMIT = float(os.getenv("VOICE_WAKE_PHRASE_LIMIT", "12"))
_CONVERSATION_PHRASE_LIMIT = float(os.getenv("VOICE_CONVERSATION_PHRASE_LIMIT", "15"))
_TOKEN_SIMILARITY = 0.80
_PHRASE_SIMILARITY = 0.85
_DEFAULT_WAKE_ALIASES = frozenset(
    {
        "hermes", "hermess", "herme", "harmes", "airmes", "hemes",
        "herms", "ormes", "ermis", "ermess", "er", "erm", "erme",
    }
)
_EXIT_WORDS = frozenset({"pare", "parar", "stop", "cancela", "cancelar", "sair", "desliga"})
_ECHO_SIMILARITY = float(os.getenv("VOICE_ECHO_SIMILARITY", "0.55"))
_RESPONSE_WAIT_SEC = float(os.getenv("VOICE_RESPONSE_WAIT_SEC", "600"))
_MIC_ERROR_RESTART_THRESHOLD = int(os.getenv("VOICE_MIC_ERROR_RESTART", "3"))
_LISTEN_HANG_GRACE_SEC = float(os.getenv("VOICE_LISTEN_HANG_GRACE", "2.0"))
_WAKE_ACCUMULATE_SEC = float(os.getenv("VOICE_WAKE_ACCUMULATE_SEC", "2.5"))
_WAKE_PREFIX_MAX_LEN = int(os.getenv("VOICE_WAKE_PREFIX_MAX_LEN", "5"))


@dataclass
class VoiceCommand:
    """Item da fila de comandos de voz."""

    text: str
    wait_response: bool = False
    voice_mode: bool = False


def _normalize(text: str) -> str:
    text = text.lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _wake_aliases() -> frozenset[str]:
    extra = os.getenv("TRIGGER_ALIASES", "")
    aliases = set(_DEFAULT_WAKE_ALIASES)
    for part in extra.split(","):
        part = _normalize(part)
        if part:
            aliases.add(part)
    return frozenset(aliases)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", _normalize(text), flags=re.UNICODE)


def _is_wake_token(word: str, trigger: str, aliases: frozenset[str]) -> bool:
    if word == trigger or word in aliases:
        return True
    if SequenceMatcher(None, trigger, word).ratio() >= _TOKEN_SIMILARITY:
        return True
    return False


def is_wake_word(text: str, trigger_word: str) -> bool:
    """Detecta wake word na frase inteira ou em qualquer token."""
    trigger = _normalize(trigger_word)
    norm = _normalize(text)
    if not norm or not trigger:
        return False
    aliases = _wake_aliases()

    if trigger in norm:
        return True
    if norm.replace(" ", "") == trigger:
        return True
    if norm == trigger:
        return True
    if SequenceMatcher(None, trigger, norm).ratio() >= _PHRASE_SIMILARITY:
        return True
    # Google STT costuma devolver só o começo da wake word ("er", "erm")
    if (
        2 <= len(norm) <= _WAKE_PREFIX_MAX_LEN
        and trigger.startswith(norm)
    ):
        return True
    for word in _tokenize(text):
        if _is_wake_token(word, trigger, aliases):
            return True
    return False


def is_exit_phrase(text: str, trigger_word: str) -> bool:
    """Detecta 'Érmes pare' (ou alias + pare/parar/cancela)."""
    tokens = set(_tokenize(text))
    if not tokens & _EXIT_WORDS:
        return False
    return is_wake_word(text, trigger_word)


def extract_command_tail(text: str, trigger_word: str) -> str:
    """Remove a wake word e retorna o restante da frase como comando."""
    trigger = _normalize(trigger_word)
    aliases = _wake_aliases()
    words = _tokenize(text)
    kept = [w for w in words if not _is_wake_token(w, trigger, aliases)]
    return " ".join(kept)


def is_likely_echo(transcript: str, reference: str, threshold: float | None = None) -> bool:
    """Detecta se a fala capturada é eco da última resposta TTS."""
    limit = threshold if threshold is not None else _ECHO_SIMILARITY
    heard = _normalize(transcript)
    spoken = _normalize(reference)
    if not heard or not spoken:
        return False
    if len(heard) >= 8 and (heard in spoken or spoken in heard):
        return True
    min_len = min(len(heard), len(spoken))
    ratio_limit = limit if min_len >= 6 else max(limit, 0.85)
    if SequenceMatcher(None, heard, spoken).ratio() >= ratio_limit:
        return True
    heard_words = heard.split()
    if len(heard_words) >= 3:
        window = " ".join(heard_words[: min(6, len(heard_words))])
        if window in spoken:
            return True
    return False


_SYSTEM_ECHO_FRAGMENTS = (
    "certo um momento",
    "um momento por favor",
    "estou pronta para ajudar",
    "eu sou aurion",
    "sou aurion",
)


def is_system_phrase_echo(transcript: str) -> bool:
    """Detecta eco de áudios fixos do sistema (saudação, oi, um momento)."""
    from aurion.greeting import get_system_spoken_phrases

    heard = _normalize(transcript)
    if not heard:
        return False

    for fragment in _SYSTEM_ECHO_FRAGMENTS:
        if fragment in heard:
            return True

    for phrase in get_system_spoken_phrases():
        if is_likely_echo(transcript, phrase, threshold=0.85):
            return True

    return False


def is_spurious_transcript(transcript: str, last_response: str = "") -> bool:
    """Ignora transcrições que são eco do sistema ou da última resposta."""
    if is_system_phrase_echo(transcript):
        return True
    if last_response and is_likely_echo(transcript, last_response):
        return True
    return False


def parse_queue_item(item: object) -> tuple[str, bool, bool]:
    """Normaliza item da fila para (texto, aguardar_resposta, modo_voz)."""
    if isinstance(item, VoiceCommand):
        return item.text, item.wait_response, item.voice_mode
    if isinstance(item, dict):
        return (
            str(item.get("text", "")),
            bool(item.get("wait_response", False)),
            bool(item.get("voice_mode", False)),
        )
    return str(item), False, False


class _ListenHungError(Exception):
    """listen() do PyAudio travou além do timeout esperado."""


def _safe_listen(recognizer, source, *, timeout: float, phrase_time_limit: float):
    """Executa listen() com watchdog — PyAudio/ALSA pode travar indefinidamente."""
    import speech_recognition as sr

    audio_box: list = []
    error_box: list[BaseException] = []

    def _target() -> None:
        try:
            audio_box.append(
                recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit,
                )
            )
        except BaseException as exc:
            error_box.append(exc)

    worker = threading.Thread(target=_target, daemon=True, name="aurion-listen-chunk")
    worker.start()
    worker.join(timeout=timeout + phrase_time_limit + _LISTEN_HANG_GRACE_SEC)
    if worker.is_alive():
        raise _ListenHungError(
            f"listen() travou após {timeout + phrase_time_limit + _LISTEN_HANG_GRACE_SEC:.0f}s"
        )
    if error_box:
        raise error_box[0]
    if not audio_box:
        raise sr.WaitTimeoutError()
    return audio_box[0]


class VoiceListener:
    """Thread de escuta contínua com wake word e modo conversa."""

    def __init__(
        self,
        command_queue: queue.Queue,
        trigger_word: str = "ermes",
        mic_index: int | None = None,
        db_path: str | None = None,
        conversation_context: object | None = None,
    ) -> None:
        self.command_queue = command_queue
        self.trigger_word = trigger_word.lower()
        self._conversation_context = conversation_context
        self._running = False
        self._thread: threading.Thread | None = None
        self._mic_index = mic_index
        self._db_path = db_path
        self._in_conversation = False
        self._response_done = threading.Event()
        self._response_done.set()
        self._response_stuck_since: float | None = None
        self._last_response_text = ""
        self._wake_parts: list[tuple[float, str]] = []
        self._conversation_silence_sec = float(
            os.getenv("CONVERSATION_SILENCE_TIMEOUT", "10")
        )
        logger.info(
            "VoiceListener configurado: trigger='%s', mic=%s, conversa_timeout=%.0fs",
            trigger_word,
            mic_index,
            self._conversation_silence_sec,
        )

    @property
    def in_conversation(self) -> bool:
        return self._in_conversation

    def _ensure_mic_ready(self) -> bool:
        """Libera escuta se TTS travou o microfone."""
        if self._response_done.is_set():
            self._response_stuck_since = None
            return True
        now = time.time()
        if self._response_stuck_since is None:
            self._response_stuck_since = now
            return False
        if now - self._response_stuck_since > 90:
            logger.warning("Escuta bloqueada por TTS — liberando microfone")
            self._response_done.set()
            self._response_stuck_since = None
            return True
        return False

    def notify_response_done(self) -> None:
        """Chamado pelo worker após TTS terminar (modo conversa)."""
        self._response_done.set()
        self._response_stuck_since = None

    def set_last_response(self, text: str) -> None:
        """Registra última resposta falada (detecção de eco)."""
        self._last_response_text = text.strip()

    def _accumulate_wake_text(self, transcript: str) -> str:
        """Junta fragmentos recentes (ex.: 'au' + 'rion' → 'au rion')."""
        now = time.time()
        self._wake_parts.append((now, transcript.strip()))
        self._wake_parts = [
            (ts, part)
            for ts, part in self._wake_parts
            if now - ts <= _WAKE_ACCUMULATE_SEC and part
        ]
        return " ".join(part for _, part in self._wake_parts)

    def _clear_wake_parts(self) -> None:
        self._wake_parts.clear()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.warning("VoiceListener já está rodando")
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="aurion-listener")
        self._thread.start()
        logger.info("VoiceListener iniciado em thread daemon")

    def ensure_running(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        if self._running:
            logger.warning("VoiceListener parou — reiniciando thread")
            self._thread = None
            self.start()
            return True
        return False

    def stop(self) -> None:
        self._running = False
        self._in_conversation = False
        self._response_done.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        logger.info("VoiceListener parado")

    def restart(self) -> None:
        """Reinicia a escuta (ex.: após troca de microfone)."""
        was_running = self._running
        self.stop()
        if was_running:
            self.start()

    def _listen_loop(self) -> None:
        while self._running:
            try:
                self._listen_session()
            except Exception as exc:
                logger.error("Sessão de escuta falhou: %s — reiniciando em 2s", exc)
                time.sleep(2)

    def _drain_pending_commands(self) -> None:
        """Descarta comandos de voz pendentes (evita fila empilhada)."""
        dropped = 0
        while True:
            try:
                self.command_queue.get_nowait()
                dropped += 1
            except queue.Empty:
                break
        if dropped:
            logger.info("Fila de voz: %d comando(s) pendente(s) descartado(s)", dropped)

    def _send_command_and_wait(self, text: str) -> None:
        """Envia comando e aguarda TTS terminar antes de reabrir o microfone."""
        from aurion.greeting import play_certo_um_momento

        play_certo_um_momento(blocking=True)
        self._response_done.clear()
        self._drain_pending_commands()
        self.command_queue.put(
            VoiceCommand(text=text, wait_response=True, voice_mode=True)
        )
        logger.info("Comando enviado à fila (conversa): '%s'", text)
        if not self._response_done.wait(timeout=_RESPONSE_WAIT_SEC):
            logger.warning(
                "Timeout aguardando resposta do motor (%.0fs)",
                _RESPONSE_WAIT_SEC,
            )
            self._response_done.set()

    def _capture_utterance(self, mic_index: int | None, recognizer) -> str | None:
        """Captura uma fala até pausa/silêncio. Retorna None se não houve fala."""
        import speech_recognition as sr

        from aurion.transcriptions import insert_transcription

        accumulated: list[str] = []
        last_speech_time: float | None = None
        capture_start = time.time()

        while time.time() - capture_start < 30:
            try:
                with sr.Microphone(device_index=mic_index) as source:
                    audio = _safe_listen(
                        recognizer,
                        source,
                        timeout=3,
                        phrase_time_limit=_CONVERSATION_PHRASE_LIMIT,
                    )
                transcript = (
                    recognizer.recognize_google(audio, language="pt-BR").strip().lower()
                )
                if is_spurious_transcript(transcript, self._last_response_text):
                    logger.info("Conversa (parcial ignorada): '%s'", transcript)
                    continue

                logger.info("Conversa (parcial): '%s'", transcript)

                if self._db_path:
                    try:
                        insert_transcription(self._db_path, transcript, "command")
                    except Exception:
                        pass

                if is_exit_phrase(transcript, self.trigger_word):
                    return transcript

                cmd_part = extract_command_tail(transcript, self.trigger_word)
                if cmd_part:
                    accumulated.append(cmd_part)
                    last_speech_time = time.time()
                elif not is_wake_word(transcript, self.trigger_word):
                    accumulated.append(transcript)
                    last_speech_time = time.time()

            except sr.WaitTimeoutError:
                if accumulated:
                    break
                return None
            except sr.UnknownValueError:
                if accumulated:
                    break
                continue
            except _ListenHungError as exc:
                logger.warning("Captura travou: %s", exc)
                break
            except Exception as exc:
                logger.error("Erro capturando fala: %s", exc)
                break

            if (
                last_speech_time is not None
                and time.time() - last_speech_time > _UTTERANCE_SILENCE_SEC
            ):
                break

        return " ".join(accumulated).strip() if accumulated else None

    def _resolve_conversation_command(self, transcript: str) -> str | None:
        """Normaliza transcrição da conversa para texto de comando."""
        if is_exit_phrase(transcript, self.trigger_word):
            return transcript
        cmd = extract_command_tail(transcript, self.trigger_word)
        if not cmd and not is_wake_word(transcript, self.trigger_word):
            return transcript
        return cmd or None

    def _run_conversation_mode(
        self, mic_index: int | None, recognizer, initial_command: str = ""
    ) -> None:
        """Modo conversa: acumula fala até pausa e só então envia ao motor."""
        self._in_conversation = True
        last_activity = time.time()
        pending_prefix = ""
        if self._conversation_context is not None:
            self._conversation_context.begin()
        logger.info(
            "Modo conversa iniciado (timeout silêncio=%.0fs, pausa_frase=%.1fs)",
            self._conversation_silence_sec,
            _UTTERANCE_SILENCE_SEC,
        )

        try:
            recognizer.pause_threshold = _CONVERSATION_PAUSE_THRESHOLD
            recognizer.non_speaking_duration = 0.6
            recognizer.phrase_threshold = 0.2

            if initial_command:
                if is_exit_phrase(initial_command, self.trigger_word):
                    logger.info("Conversa cancelada na abertura: '%s'", initial_command)
                    return
                pending_prefix = initial_command.strip()

            while self._running:
                # Não escutar enquanto Hermes/TTS processam
                if not self._ensure_mic_ready():
                    time.sleep(0.2)
                    continue

                idle = time.time() - last_activity
                if idle >= self._conversation_silence_sec:
                    logger.info(
                        "Modo conversa encerrado: %.0fs sem fala",
                        self._conversation_silence_sec,
                    )
                    break

                utterance = self._capture_utterance(mic_index, recognizer)
                if pending_prefix:
                    utterance = (
                        f"{pending_prefix} {utterance}".strip()
                        if utterance
                        else pending_prefix
                    )
                    pending_prefix = ""

                if not utterance:
                    continue

                last_activity = time.time()
                logger.info("Conversa (completa): '%s'", utterance)

                if is_exit_phrase(utterance, self.trigger_word):
                    logger.info("Modo conversa encerrado: '%s'", utterance)
                    break

                cmd = self._resolve_conversation_command(utterance)
                if not cmd:
                    continue

                if is_spurious_transcript(cmd, self._last_response_text):
                    logger.info("Ignorado (eco/fala do sistema): '%s'", cmd)
                    continue

                self._send_command_and_wait(cmd)
                last_activity = time.time()
        finally:
            self._in_conversation = False
            if self._conversation_context is not None:
                self._conversation_context.end()
            recognizer.pause_threshold = 0.9
            recognizer.non_speaking_duration = 0.5
            logger.info("Modo conversa finalizado — aguardando wake word")

    def _listen_session(self) -> None:
        import speech_recognition as sr

        from aurion.greeting import play_oi
        from aurion.transcriptions import insert_transcription

        recognizer = sr.Recognizer()
        recognizer.dynamic_energy_threshold = True
        recognizer.dynamic_energy_adjustment_ratio = 1.2
        recognizer.pause_threshold = 0.65
        recognizer.phrase_threshold = 0.2
        recognizer.non_speaking_duration = 0.4
        # Prioridade: setting UI > construtor > env var > fallback automático
        preferred = get_mic_index()
        if preferred is None:
            preferred = self._mic_index
        if preferred is None:
            env_mic = os.getenv("MIC_DEVICE_INDEX", "").strip()
            if env_mic.isdigit():
                preferred = int(env_mic)

        mic_index = resolve_mic_index(preferred)
        if mic_index is None:
            logger.error("Falha ao configurar microfone: nenhum dispositivo disponível")
            time.sleep(3)
            return

        mic = sr.Microphone(device_index=mic_index)

        try:
            with mic as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.8)
                # Evita limiar alto demais após calibração (perde fala baixa)
                recognizer.energy_threshold = min(
                    max(recognizer.energy_threshold, 200), 1200
                )
        except Exception as exc:
            logger.error("Falha ao configurar microfone (índice %s): %s", mic_index, exc)
            time.sleep(3)
            return

        logger.info(
            "Microfone pronto (índice %s) — aguardando wake word '%s'",
            mic_index,
            self.trigger_word,
        )

        consecutive_errors = 0
        was_waiting_tts = False

        while self._running:
            if self._in_conversation:
                time.sleep(0.2)
                continue

            # Não escutar enquanto TTS/resposta ainda está em reprodução
            if not self._ensure_mic_ready():
                was_waiting_tts = True
                time.sleep(0.2)
                continue

            if was_waiting_tts:
                was_waiting_tts = False
                time.sleep(_POST_TTS_MIC_DELAY_SEC)

            try:
                with sr.Microphone(device_index=mic_index) as source:
                    audio = _safe_listen(
                        recognizer,
                        source,
                        timeout=10,
                        phrase_time_limit=_WAKE_PHRASE_LIMIT,
                    )
                consecutive_errors = 0
                transcript = (
                    recognizer.recognize_google(audio, language="pt-BR").strip().lower()
                )
                logger.info("Reconhecido: '%s'", transcript)

                if self._db_path:
                    try:
                        insert_transcription(self._db_path, transcript, "wake")
                    except Exception as db_err:
                        logger.warning("Falha ao salvar transcrição: %s", db_err)

                combined = self._accumulate_wake_text(transcript)
                wake_match = is_wake_word(transcript, self.trigger_word) or is_wake_word(
                    combined, self.trigger_word
                )
                wake_text = combined if is_wake_word(combined, self.trigger_word) else transcript

                if wake_match:
                    if self._last_response_text and is_likely_echo(
                        wake_text, self._last_response_text
                    ):
                        logger.info(
                            "Ignorado (eco da última resposta): '%s'",
                            wake_text,
                        )
                        continue
                    self._clear_wake_parts()
                    logger.info(
                        "Wake word detectada em: '%s'%s",
                        wake_text,
                        f" (parcial: '{transcript}')" if wake_text != transcript else "",
                    )
                    tail = extract_command_tail(wake_text, self.trigger_word)

                    play_oi(blocking=True)
                    logger.info("Reproduzindo confirmação 'Oi'")
                    time.sleep(_OI_PLAYBACK_DELAY)

                    self._run_conversation_mode(
                        mic_index, recognizer, initial_command=tail
                    )
                    logger.info("Reiniciando sessão de microfone após conversa")
                    return

                if is_spurious_transcript(transcript, self._last_response_text):
                    logger.info("Ignorado (eco/fala do sistema): '%s'", transcript)
                    continue

                logger.info(
                    "Ignorado (sem wake word '%s'): '%s'",
                    self.trigger_word,
                    transcript,
                )

            except sr.WaitTimeoutError:
                consecutive_errors = 0
                pass
            except sr.UnknownValueError:
                consecutive_errors = 0
                logger.debug("Áudio não compreendido")
            except _ListenHungError as exc:
                consecutive_errors += 1
                logger.warning("%s (erros consecutivos=%d)", exc, consecutive_errors)
            except Exception as exc:
                consecutive_errors += 1
                logger.error(
                    "Erro na escuta: %s — retry automático (erros consecutivos=%d)",
                    exc,
                    consecutive_errors,
                )
                time.sleep(0.5)

            if consecutive_errors >= _MIC_ERROR_RESTART_THRESHOLD:
                logger.warning(
                    "Reiniciando sessão de microfone após %d erros consecutivos",
                    consecutive_errors,
                )
                return
