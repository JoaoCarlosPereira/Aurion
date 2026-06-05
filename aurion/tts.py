"""TTSService — Motor de texto-para-fala exclusivamente via Kokoro."""

import logging
import os
import re
import tempfile
import threading
import time
from abc import ABC, abstractmethod

from dotenv import load_dotenv

logger = logging.getLogger("aurion.tts")
load_dotenv()

# (conexão, leitura) — respostas longas do Hermes podem demorar a sintetizar
_KOKORO_CONNECT_TIMEOUT = 10
_KOKORO_READ_TIMEOUT = int(os.getenv("KOKORO_READ_TIMEOUT", "180"))
_KOKORO_RETRIES = int(os.getenv("KOKORO_RETRIES", "3"))
_KOKORO_CHUNK_CHARS = int(os.getenv("KOKORO_CHUNK_CHARS", "400"))


def split_text_for_tts(text: str, max_chars: int | None = None) -> list[str]:
    """Divide texto longo em pedaços para síntese sequencial no Kokoro."""
    limit = max_chars or _KOKORO_CHUNK_CHARS
    text = " ".join(text.split())
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    sentences = re.split(r"(?<=[.!?…])\s+", text)

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= limit:
            _append_chunk(chunks, sentence, limit)
            continue
        for clause in re.split(r"(?<=[,;:])\s+", sentence):
            clause = clause.strip()
            if not clause:
                continue
            if len(clause) <= limit:
                _append_chunk(chunks, clause, limit)
            else:
                for part in _split_by_words(clause, limit):
                    _append_chunk(chunks, part, limit)

    return chunks


def _append_chunk(chunks: list[str], piece: str, limit: int) -> None:
    """Adiciona pedaço, fundindo com o anterior se couber."""
    if not piece:
        return
    if chunks and len(chunks[-1]) + 1 + len(piece) <= limit:
        chunks[-1] = f"{chunks[-1]} {piece}"
    else:
        chunks.append(piece)


def _split_by_words(text: str, limit: int) -> list[str]:
    """Último recurso: quebra por palavras respeitando o limite."""
    words = text.split()
    chunks: list[str] = []
    buffer = ""
    for word in words:
        candidate = f"{buffer} {word}".strip() if buffer else word
        if len(candidate) <= limit:
            buffer = candidate
        else:
            if buffer:
                chunks.append(buffer)
            buffer = word
    if buffer:
        chunks.append(buffer)
    return chunks


class TTSEngine(ABC):
    """Interface para provedores de TTS."""

    @abstractmethod
    def speak(self, text: str) -> None:
        ...

    @abstractmethod
    def speak_blocking(self, text: str) -> None:
        ...

    @abstractmethod
    def list_voices(self) -> list[dict]:
        ...

    @abstractmethod
    def test_voice(self, voice_id: str, text: str) -> None:
        ...


def _generate_kokoro_mp3(api_url: str, voice: str, text: str) -> str:
    """Gera MP3 via API Kokoro com retentativas. Retorna caminho do arquivo."""
    import requests

    url = f"{api_url.rstrip('/')}/v1/audio/speech"
    payload = {"model": "kokoro", "input": text, "voice": voice}
    timeout = (_KOKORO_CONNECT_TIMEOUT, _KOKORO_READ_TIMEOUT)
    last_error: Exception | None = None

    for attempt in range(1, _KOKORO_RETRIES + 1):
        try:
            logger.info(
                "Kokoro TTS (tentativa %d/%d): '%s'...",
                attempt,
                _KOKORO_RETRIES,
                text[:50],
            )
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.write(resp.content)
            tmp.close()
            logger.info("Kokoro TTS: MP3 gerado (%d bytes)", len(resp.content))
            return tmp.name
        except Exception as exc:
            last_error = exc
            logger.warning("Kokoro tentativa %d falhou: %s", attempt, exc)
            if attempt < _KOKORO_RETRIES:
                time.sleep(1.5 * attempt)

    raise RuntimeError(f"Kokoro indisponível após {_KOKORO_RETRIES} tentativas") from last_error


def _play_audio(path: str) -> None:
    """Toca MP3 (bloqueante) com lock compartilhado com saudação/oi."""
    import subprocess

    from aurion.greeting import _play_lock, _run_aplay_wav

    with _play_lock:
        try:
            wav_path = path.replace(".mp3", ".wav")
            subprocess.run(
                ["ffmpeg", "-y", "-i", path, wav_path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _run_aplay_wav(wav_path)
            os.unlink(path)
            os.unlink(wav_path)
            logger.info("Kokoro TTS: reprodução concluída")
        except Exception as e:
            logger.error("Falha ao reproduzir áudio Kokoro: %s", e)
            try:
                os.unlink(path)
            except OSError:
                pass
            raise


class _KokoroEngine(TTSEngine):
    """Motor Kokoro via API HTTP — único motor de voz do Aurion."""

    def __init__(self) -> None:
        self.api_url = os.getenv("KOKORO_API_URL", "http://localhost:8880")
        self.voice = os.getenv("KOKORO_VOICE", "pf_dora")
        self._available_voices: list[str] = []
        self._load_voices_sync()
        logger.info(
            "Kokoro inicializado -> %s (voice=%s, %d vozes)",
            self.api_url,
            self.voice,
            len(self._available_voices),
        )

    def _load_voices_sync(self) -> None:
        try:
            import requests

            resp = requests.get(
                f"{self.api_url.rstrip('/')}/voices",
                timeout=(_KOKORO_CONNECT_TIMEOUT, 15),
            )
            resp.raise_for_status()
            self._available_voices = resp.json()["voices"]
        except Exception as e:
            logger.warning("Falha ao carregar vozes do Kokoro: %s", e)

    def _speak_chunks(self, chunks: list[str]) -> None:
        """Sintetiza e reproduz cada pedaço em sequência."""
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            logger.info(
                "Kokoro chunk %d/%d (%d caracteres): '%s'...",
                index,
                total,
                len(chunk),
                chunk[:40],
            )
            mp3_path = _generate_kokoro_mp3(self.api_url, self.voice, chunk)
            _play_audio(mp3_path)

    def speak(self, text: str) -> None:
        """Gera áudio e toca em thread (não bloqueia o caller)."""
        chunks = split_text_for_tts(text)
        threading.Thread(
            target=self._speak_chunks,
            args=(chunks,),
            daemon=True,
            name="kokoro-play",
        ).start()

    def speak_blocking(self, text: str) -> None:
        """Gera áudio e toca até terminar (modo conversa)."""
        self._speak_chunks(split_text_for_tts(text))

    def list_voices(self) -> list[dict]:
        return [{"id": v, "name": v, "lang": "multi"} for v in self._available_voices]

    def test_voice(self, voice_id: str, text: str) -> None:
        original = self.voice
        self.voice = voice_id
        try:
            self.speak_blocking(text)
        finally:
            self.voice = original


class TTSService:
    """Serviço TTS — sempre Kokoro (sem fallback pyttsx3)."""

    def __init__(self, engine: TTSEngine | None = None) -> None:
        self._engine: TTSEngine = engine or _KokoroEngine()
        self._current_voice_id: str | None = None
        logger.info("TTSService usando Kokoro exclusivamente")

    def speak(self, text: str) -> None:
        self._engine.speak(text)

    def speak_blocking(self, text: str) -> None:
        self._engine.speak_blocking(text)

    def list_voices(self) -> list[dict]:
        return self._engine.list_voices()

    def test_voice(self, voice_id: str, text: str) -> None:
        self._engine.test_voice(voice_id, text)

    def set_voice(self, voice_id: str) -> None:
        self._current_voice_id = voice_id
        if isinstance(self._engine, _KokoroEngine):
            self._engine.voice = voice_id
        logger.info("Voz Kokoro alterada para: %s", voice_id)

    def get_current_voice(self) -> str | None:
        return self._current_voice_id
