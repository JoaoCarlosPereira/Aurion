"""Greeting module — gera e reproduz saudação pré-gravada com Kokoro TTS.

Gera um MP3 de saudação uma vez e o reproduz rapidamente na inicialização
de main.py ou do servidor FastAPI, evitando latência de geração em tempo real.
"""

import logging
import os
import subprocess
import tempfile
import threading
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

from aurion.audio_devices import get_aplay_device, get_aplay_candidates, set_system_volume_max

logger = logging.getLogger("aurion.greeting")
load_dotenv()

# Directories
_BASE_DIR = Path(__file__).resolve().parent
_SOUNDS_DIR = _BASE_DIR / "sounds"
# Evita dois aplay ao mesmo tempo (trava microfone no ALSA)
_play_lock = threading.Lock()


def _get_greeting_text() -> str:
    """Retorna a saudação fixa de apresentação."""
    return "Olá! Eu sou Aurion e estou pronta para ajudar."


def get_or_generate_greeting() -> str:
    """Retorna o caminho do arquivo MP3 de saudação.

    Gera o arquivo se não existir ou se o texto da saudação mudou.
    """
    _SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
    greeting_mp3 = _SOUNDS_DIR / "saudacao.mp3"
    greeting_text = _get_greeting_text()
    text_file = _SOUNDS_DIR / "saudacao.txt"

    # Verifica se o MP3 já existe e corresponde ao texto atual
    if greeting_mp3.exists() and text_file.exists():
        saved_text = text_file.read_text(encoding="utf-8").strip()
        if saved_text == greeting_text:
            logger.info("Saudação em cache: %s", greeting_mp3)
            return str(greeting_mp3)

    # Gera a saudação via Kokoro TTS
    api_url = os.getenv("KOKORO_API_URL", "http://localhost:8880")
    voice = os.getenv("KOKORO_VOICE", "pf_dora")

    logger.info("Gerando saudação via Kokoro TTS...")
    logger.info("Saudação: '%s'", greeting_text)

    try:
        resp = requests.post(
            f"{api_url}/v1/audio/speech",
            json={"model": "kokoro", "input": greeting_text, "voice": voice},
            timeout=60,
        )
        resp.raise_for_status()
        mp3_data = resp.content

        greeting_mp3.write_bytes(mp3_data)
        text_file.write_text(greeting_text, encoding="utf-8")
        logger.info("Saudação gerada: %d bytes", len(mp3_data))
        return str(greeting_mp3)

    except Exception as e:
        logger.error("Falha ao gerar saudação via Kokoro: %s", e)
        logger.warning("Saudação não pôde ser reproduzida")
        return ""


def _aplay_candidates() -> list[str]:
    """Lista de dispositivos ALSA para tentativa de reprodução."""
    return get_aplay_candidates()


def _run_aplay_wav(wav_path: str) -> None:
    """Toca WAV via aplay, com fallback entre dispositivos ALSA."""
    set_system_volume_max()
    last_error: Exception | None = None
    for device in _aplay_candidates():
        try:
            subprocess.run(
                ["aplay", "-D", device, wav_path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.debug("Reproduzido via ALSA device: %s", device)
            return
        except subprocess.CalledProcessError as exc:
            last_error = exc
            logger.warning("Falha ao reproduzir em %s: %s", device, exc)
    if last_error:
        raise last_error


def play_greeting(*, blocking: bool = False) -> None:
    """Reproduz o arquivo de saudação. Com blocking=True, aguarda o fim da reprodução."""
    mp3_path = get_or_generate_greeting()
    if not mp3_path:
        logger.error("Saudação indisponível — arquivo não gerado")
        return

    def _play():
        try:
            wav_path = mp3_path.replace(".mp3", ".wav")
            subprocess.run(
                ["ffmpeg", "-y", "-i", mp3_path, wav_path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _run_aplay_wav(wav_path)
            logger.info("Saudação reproduzida com sucesso")
        except subprocess.CalledProcessError as e:
            logger.error("Erro ao reproduzir saudação: %s", e)
        except FileNotFoundError:
            logger.error("ffmpeg ou aplay não encontrados no sistema")
        except Exception as e:
            logger.error("Erro ao reproduzir saudação: %s", e)

    if blocking:
        _play()
        return

    threading.Thread(target=_play, daemon=True).start()


def _run_aplay(mp3_path: Path, filename: str) -> None:
    """Converte MP3 e toca via aplay (bloqueante, com lock)."""
    with _play_lock:
        try:
            wav_path = str(mp3_path).replace(".mp3", ".wav")
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(mp3_path), wav_path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _run_aplay_wav(wav_path)
            os.unlink(wav_path)
            logger.info("Áudio reproduzido: %s", filename)
        except subprocess.CalledProcessError as e:
            logger.error("Erro ao reproduzir %s: %s", filename, e)
        except FileNotFoundError:
            logger.error("ffmpeg ou aplay não encontrados no sistema")
        except Exception as e:
            logger.error("Erro ao reproduzir %s: %s", filename, e)


def _play_single_mp3(filename: str, *, blocking: bool = False) -> None:
    """Reproduz um único arquivo MP3 fixo de sounds/."""
    mp3_path = _SOUNDS_DIR / filename
    if not mp3_path.exists():
        logger.warning("Arquivo de áudio não encontrado: %s", mp3_path)
        return

    if blocking:
        _run_aplay(mp3_path, filename)
        return

    threading.Thread(target=_run_aplay, args=(mp3_path, filename), daemon=True).start()


def play_oi(*, blocking: bool = False) -> None:
    """Reproduz o áudio fixo 'Oi'."""
    _play_single_mp3("oi.mp3", blocking=blocking)


def play_certo_um_momento(*, blocking: bool = False) -> None:
    """Reproduz o áudio fixo 'Certo, um momento por favor'."""
    _play_single_mp3("certo_um_momento.mp3", blocking=blocking)


def get_system_spoken_phrases() -> list[str]:
    """Frases fixas reproduzidas pelo Aurion (para filtro de eco)."""
    phrases: list[str] = [_get_greeting_text(), "Oi?", "Certo, um momento por favor"]
    for name in ("oi", "certo_um_momento", "saudacao"):
        text_file = _SOUNDS_DIR / f"{name}.txt"
        if text_file.exists():
            text = text_file.read_text(encoding="utf-8").strip()
            if text:
                phrases.append(text)
    return list(dict.fromkeys(phrases))
