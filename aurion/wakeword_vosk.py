"""Detecção offline de wake word com Vosk (gramática restrita, pt-BR)."""

from __future__ import annotations

import audioop
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("aurion.wakeword")

_DEFAULT_MODEL = (
    Path(__file__).resolve().parent.parent / "models" / "vosk-model-small-pt-0.3"
)
_VOSK_RATE = 16000


def resolve_model_path() -> str | None:
    configured = os.getenv("VOSK_MODEL_PATH", "").strip()
    if configured and Path(configured).exists():
        return configured
    if _DEFAULT_MODEL.exists():
        return str(_DEFAULT_MODEL)
    return None


def vosk_available() -> bool:
    if resolve_model_path() is None:
        return False
    try:
        import vosk  # noqa: F401

        return True
    except ImportError:
        return False


def _grammar_for_trigger(trigger_word: str) -> str:
    """Gramática Vosk — apenas palavras presentes no vocabulário pt."""
    from aurion.listener import _normalize

    trigger = _normalize(trigger_word)
    # Palavras validadas no vosk-model-small-pt-0.3 (demais geram warning e são ignoradas)
    words = {trigger, "hermes", "[unk]"}
    return json.dumps(sorted(words))


def _pick_input_rate(pa, mic_index: int | None) -> int:
    """Escolhe taxa de amostragem suportada pelo dispositivo."""
    preferred = [48000, 44100, 32000, 22050, 16000, 8000]
    if mic_index is not None:
        default = int(pa.get_device_info_by_index(mic_index)["defaultSampleRate"])
        preferred = [default] + [r for r in preferred if r != default]
    for rate in preferred:
        try:
            if pa.is_format_supported(
                rate,
                input_device=mic_index,
                input_channels=1,
                input_format=__import__("pyaudio").paInt16,
            ):
                return rate
        except Exception:
            continue
    return _VOSK_RATE


class VoskWakeDetector:
    """Escuta contínua do microfone e detecta wake word via Vosk."""

    def __init__(self, trigger_word: str, mic_index: int | None = None) -> None:
        self.trigger_word = trigger_word.lower()
        self.mic_index = mic_index
        self._model = None
        self._recognizer = None
        self._pa = None
        self._stream = None
        self._device_rate = _VOSK_RATE
        self._read_chunk = 12000
        self._ratecv_state = None
        self.available = False
        self.mic_open_failed = False
        self._init_engine()

    def _init_engine(self) -> None:
        model_path = resolve_model_path()
        if model_path is None:
            logger.warning("Modelo Vosk não encontrado — wake word usará Google STT")
            return
        try:
            import vosk
            from vosk import Model

            vosk.SetLogLevel(-1)
            self._model = Model(model_path)
            grammar = _grammar_for_trigger(self.trigger_word)
            self._recognizer = vosk.KaldiRecognizer(self._model, _VOSK_RATE, grammar)
            self.available = True
            logger.info(
                "Vosk wake word pronto (modelo=%s, trigger='%s')",
                model_path,
                self.trigger_word,
            )
        except Exception as exc:
            logger.warning("Vosk indisponível (%s) — fallback para Google STT", exc)
            self.available = False

    def _open_stream(self) -> bool:
        import pyaudio

        if self.mic_open_failed:
            return False

        self._pa = pyaudio.PyAudio()
        self._device_rate = _pick_input_rate(self._pa, self.mic_index)
        self._read_chunk = max(4000, int(4000 * self._device_rate / _VOSK_RATE))
        try:
            self._stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self._device_rate,
                input=True,
                input_device_index=self.mic_index,
                frames_per_buffer=self._read_chunk,
            )
            logger.info(
                "Vosk microfone aberto (índice=%s, %s Hz → %s Hz)",
                self.mic_index,
                self._device_rate,
                _VOSK_RATE,
            )
            return True
        except Exception as exc:
            logger.error(
                "Vosk: falha ao abrir microfone (índice %s): %s",
                self.mic_index,
                exc,
            )
            self.mic_open_failed = True
            self._close_stream()
            return False

    def _close_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

    def reset(self) -> None:
        self._ratecv_state = None
        if self._recognizer is not None:
            self._recognizer.Reset()

    def _resample(self, data: bytes) -> bytes:
        if self._device_rate == _VOSK_RATE:
            return data
        data, self._ratecv_state = audioop.ratecv(
            data, 2, 1, self._device_rate, _VOSK_RATE, self._ratecv_state
        )
        return data

    def listen_chunk(self) -> str | None:
        """Lê um chunk do microfone; retorna texto se wake word reconhecida."""
        if not self.available or self._recognizer is None or self.mic_open_failed:
            return None
        if self._stream is None and not self._open_stream():
            return None
        try:
            data = self._stream.read(self._read_chunk, exception_on_overflow=False)
        except Exception as exc:
            logger.warning("Vosk: erro ao ler microfone: %s", exc)
            self._close_stream()
            return None

        data = self._resample(data)
        if self._recognizer.AcceptWaveform(data):
            result = json.loads(self._recognizer.Result())
            text = result.get("text", "").strip().lower()
            if text and text != "[unk]":
                return text
        return None

    def close(self) -> None:
        self._close_stream()
        self._model = None
        self._recognizer = None
        self.available = False
