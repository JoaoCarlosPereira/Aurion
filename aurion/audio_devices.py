"""Audio device management — lista e seleciona microfones e alto-falantes."""

import logging
import re
import subprocess
import threading

logger = logging.getLogger("aurion.audio")

_lock = threading.Lock()

_APLAY_HW_RE = re.compile(r"\(hw:(\d+),(\d+)\)")
_APLAY_DEVICE_CARD_RE = re.compile(r"(?:plug)?hw:(\d+)")
_VOLUME_CONTROLS = ("Master", "Speaker", "Headphone", "PCM", "Front", "Surround")
_NAMED_ALSA_DEVICES = frozenset({
    "default", "sysdefault", "dmix", "front", "hdmi",
    "surround40", "surround51", "surround71",
})

# ── Estado global ──────────────────────────────────────────────────

_mic_index: int | None = None
_speaker_index: int | None = None

# Cache de dispositivos (preenchido via refresh)
_mic_list: list[dict] = []
_speaker_list: list[dict] = []


def get_mic_index() -> int | None:
    global _mic_index
    return _mic_index


def set_mic_index(index: int | None) -> None:
    global _mic_index
    _mic_index = index
    logger.info("Microfone selecionado: %s", index)


def get_speaker_index() -> int | None:
    global _speaker_index
    return _speaker_index


def set_speaker_index(index: int | None) -> None:
    global _speaker_index
    _speaker_index = index
    logger.info("Alto-falante selecionado: %s", index)


def _is_usb_microphone(name: str) -> bool:
    """Detecta microfone USB pelo nome ALSA/PyAudio."""
    return "usb" in name.lower()


# ── Listagem de dispositivos ──────────────────────────────────────

def _list_pyaudio_mics() -> list[dict]:
    """Lista microfones via PyAudio (usado pelo SpeechRecognition)."""
    import pyaudio

    pa = pyaudio.PyAudio()
    mics: list[dict] = []
    mic_ids: list[int] = []

    try:
        default_input = pa.get_default_input_device_info()["index"]
    except (OSError, IOError):
        default_input = None

    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info.get("maxInputChannels", 0) > 0:
            name = info.get("name", f"Device {i}")
            is_default = default_input is not None and i == default_input
            mics.append({
                "index": i,
                "name": name,
                "channels": info.get("maxInputChannels", 0),
                "sample_rate": info.get("defaultSampleRate", 0),
                "is_default": is_default,
                "is_usb": _is_usb_microphone(name),
            })
            if is_default:
                mic_ids.insert(0, i)
            elif i not in mic_ids:
                mic_ids.append(i)

    pa.terminate()
    return mics


def _list_sounddevice_speakers() -> list[dict]:
    """Lista alto-falantes via sounddevice (usado no playback TTS)."""
    import sounddevice as sd

    devices = sd.query_devices()
    speakers: list[dict] = []

    default_output = sd.default.device[1]

    for i, dev in enumerate(devices):
        if dev.get("max_output_channels", 0) > 0 and dev.get("hostapi") is not None:
            is_default = i == default_output
            speakers.append({
                "index": i,
                "name": dev.get("name", f"Device {i}"),
                "channels": dev.get("max_output_channels", 0),
                "sample_rate": dev.get("default_samplerate", 0),
                "is_default": is_default,
            })

    return speakers


def _mic_candidate_order(
    preferred: int | None,
    *,
    prefer_usb: bool,
) -> list[int | None]:
    """Ordem de tentativa: USB (padrão) → preferido → default → demais."""
    mics = get_microphones()
    seen: set[int | None] = set()
    ordered: list[int | None] = []

    def _add(idx: int | None) -> None:
        if idx not in seen:
            seen.add(idx)
            ordered.append(idx)

    if prefer_usb:
        for mic in mics:
            if _is_usb_microphone(mic.get("name", "")):
                _add(mic["index"])

    if preferred is not None:
        _add(preferred)

    for mic in mics:
        if mic.get("is_default"):
            _add(mic["index"])

    _add(None)

    for mic in mics:
        _add(mic["index"])

    return ordered


def refresh_devices() -> dict:
    """Atualiza o cache de dispositivos e retorna ambos."""
    global _mic_list, _speaker_list
    with _lock:
        _mic_list = _list_pyaudio_mics()
        _speaker_list = _list_sounddevice_speakers()
        _mic_list.sort(key=lambda m: (not m.get("is_usb", False), m["index"]))
    return {
        "microphones": _mic_list,
        "speakers": _speaker_list,
    }


def get_microphones() -> list[dict]:
    with _lock:
        return list(_mic_list)


def get_speakers() -> list[dict]:
    with _lock:
        return list(_speaker_list)


def _aplay_from_name(name: str) -> str | None:
    """Converte nome sounddevice/ALSA em dispositivo aplay."""
    match = _APLAY_HW_RE.search(name)
    if match:
        return f"plughw:{match.group(1)},{match.group(2)}"
    base = name.split(":", 1)[0].strip()
    if name in _NAMED_ALSA_DEVICES:
        return name
    if base in _NAMED_ALSA_DEVICES:
        return base
    return None


def get_aplay_device(speaker_index: int | None = None) -> str:
    """Converte índice sounddevice para dispositivo ALSA usado pelo aplay."""
    idx = get_speaker_index() if speaker_index is None else speaker_index

    with _lock:
        speakers = list(_speaker_list)
    if not speakers:
        refresh_devices()
        with _lock:
            speakers = list(_speaker_list)

    if idx is not None:
        name = next((s["name"] for s in speakers if s["index"] == idx), None)
        if name:
            device = _aplay_from_name(name)
            if device:
                return device
        logger.warning("Alto-falante índice %s não encontrado ou sem mapeamento ALSA", idx)

    for s in speakers:
        if "analog" in s["name"].lower():
            device = _aplay_from_name(s["name"])
            if device:
                return device
    for s in speakers:
        device = _aplay_from_name(s["name"])
        if device:
            return device
    return "default"


def get_aplay_candidates(speaker_index: int | None = None) -> list[str]:
    """Lista dispositivos ALSA para tentativa de reprodução, em ordem de preferência."""
    with _lock:
        speakers = list(_speaker_list)
    if not speakers:
        refresh_devices()
        with _lock:
            speakers = list(_speaker_list)

    idx = get_speaker_index() if speaker_index is None else speaker_index
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(device: str | None) -> None:
        if device and device not in seen:
            seen.add(device)
            ordered.append(device)

    by_index = {s["index"]: s for s in speakers}
    selected = by_index.get(idx) if idx is not None else None

    # Preferir saída analógica (alto-falantes físicos) antes de HDMI
    for s in speakers:
        if "analog" in s["name"].lower():
            _add(_aplay_from_name(s["name"]))

    if selected:
        _add(_aplay_from_name(selected["name"]))

    for s in speakers:
        _add(_aplay_from_name(s["name"]))

    _add("default")
    return ordered


def _card_from_aplay_device(device: str) -> int | None:
    """Extrai número da placa ALSA de um dispositivo aplay (ex.: plughw:1,0 → 1)."""
    match = _APLAY_DEVICE_CARD_RE.search(device)
    return int(match.group(1)) if match else None


def _output_alsa_cards() -> list[int]:
    """Placas ALSA usadas pelos alto-falantes detectados."""
    cards: list[int] = []
    seen: set[int] = set()
    for speaker in get_speakers():
        match = _APLAY_HW_RE.search(speaker.get("name", ""))
        if match:
            card = int(match.group(1))
            if card not in seen:
                seen.add(card)
                cards.append(card)
    return cards or [1]


def set_system_volume_max(card: int | None = None) -> None:
    """Define volume ALSA no máximo (100%) e desmuta saídas antes da reprodução."""
    cards = [card] if card is not None else _output_alsa_cards()
    for alsa_card in cards:
        for control in _VOLUME_CONTROLS:
            try:
                subprocess.run(
                    ["amixer", "-c", str(alsa_card), "sset", control, "100%", "unmute"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return
            except Exception as exc:
                logger.debug("amixer card=%s control=%s: %s", alsa_card, control, exc)
    logger.debug("Volume ALSA definido no máximo (cards=%s)", cards)


def resolve_mic_index(preferred: int | None = None, *, prefer_usb: bool | None = None) -> int | None:
    """Retorna um índice de microfone que o PyAudio consegue abrir."""
    import speech_recognition as sr

    if prefer_usb is None:
        prefer_usb = preferred is None

    candidates = _mic_candidate_order(preferred, prefer_usb=prefer_usb)

    for idx in candidates:
        try:
            mic = sr.Microphone(device_index=idx)
            with mic as source:
                pass
            if preferred is not None and idx != preferred:
                name = next(
                    (m["name"] for m in get_microphones() if m["index"] == idx),
                    str(idx),
                )
                if prefer_usb and _is_usb_microphone(name):
                    logger.info("Microfone USB selecionado: índice %s (%s)", idx, name)
                else:
                    logger.warning(
                        "Microfone índice %s indisponível; usando índice %s (%s)",
                        preferred,
                        idx,
                        name,
                    )
            elif prefer_usb and idx is not None:
                name = next(
                    (m["name"] for m in get_microphones() if m["index"] == idx),
                    "",
                )
                if _is_usb_microphone(name):
                    logger.info("Microfone USB selecionado: índice %s (%s)", idx, name)
            return idx
        except Exception:
            continue

    logger.error("Nenhum microfone disponível para escuta")
    return None


def resolve_speaker_index(preferred: int | None = None) -> int | None:
    """Retorna índice sounddevice válido para reprodução."""
    with _lock:
        speakers = list(_speaker_list)
    if not speakers:
        refresh_devices()
        with _lock:
            speakers = list(_speaker_list)
    if not speakers:
        return None

    by_index = {s["index"]: s for s in speakers}
    candidates: list[int] = []
    if preferred is not None and preferred in by_index:
        candidates.append(preferred)
    for s in speakers:
        if s.get("is_default") and s["index"] not in candidates:
            candidates.append(s["index"])
    for s in speakers:
        if "analog" in s["name"].lower() and s["index"] not in candidates:
            candidates.append(s["index"])
    for s in speakers:
        if s["index"] not in candidates:
            candidates.append(s["index"])

    resolved = candidates[0]
    if preferred is not None and preferred != resolved:
        logger.warning(
            "Alto-falante índice %s indisponível; usando índice %s (%s)",
            preferred,
            resolved,
            by_index[resolved]["name"],
        )
    return resolved
