"""Tests for TTSService (Kokoro only)."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_kokoro_mp3(tmp_path):
    """Evita chamadas HTTP reais ao Kokoro."""
    mp3 = tmp_path / "test.mp3"
    mp3.write_bytes(b"\x00\x00")

    with patch("aurion.tts._generate_kokoro_mp3", return_value=str(mp3)):
        with patch("aurion.tts._play_audio"):
            yield mp3


def test_speak_uses_kokoro(mock_kokoro_mp3):
    from aurion.tts import TTSService

    tts = TTSService()
    with patch.object(tts._engine, "speak") as mock_speak:
        tts.speak("Olá")
        mock_speak.assert_called_once_with("Olá")


def test_speak_blocking_uses_kokoro(mock_kokoro_mp3):
    from aurion.tts import TTSService

    tts = TTSService()
    with patch.object(tts._engine, "speak_blocking") as mock_blocking:
        tts.speak_blocking("Resposta longa")
        mock_blocking.assert_called_once_with("Resposta longa")


def test_no_pyttsx3_fallback_on_kokoro_error():
    from aurion.tts import TTSService

    tts = TTSService()
    with patch.object(
        tts._engine, "speak", side_effect=RuntimeError("Kokoro indisponível")
    ):
        with pytest.raises(RuntimeError, match="Kokoro"):
            tts.speak("teste")


def test_list_voices():
    from aurion.tts import _KokoroEngine

    engine = _KokoroEngine()
    engine._available_voices = ["pf_dora", "pm_alex"]
    voices = engine.list_voices()
    assert len(voices) == 2
    assert voices[0]["id"] == "pf_dora"


def test_split_text_short():
    from aurion.tts import split_text_for_tts

    text = "Olá, tudo bem?"
    assert split_text_for_tts(text, max_chars=400) == [text]


def test_split_text_long():
    from aurion.tts import split_text_for_tts

    s1 = "A previsão para hoje é de sol com algumas nuvens pela manhã."
    s2 = "À tarde pode chover fraco na região sul do estado."
    s3 = "A temperatura máxima deve ficar em torno de vinte e oito graus."
    text = f"{s1} {s2} {s3}"
    chunks = split_text_for_tts(text, max_chars=80)
    assert len(chunks) > 1
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")
    assert all(len(c) <= 80 for c in chunks)


def test_speak_blocking_splits_long_text(mock_kokoro_mp3):
    from aurion.tts import TTSService

    long_text = "Frase um. " * 30
    tts = TTSService()
    with patch("aurion.tts.split_text_for_tts", return_value=["parte 1", "parte 2"]) as mock_split:
        with patch.object(tts._engine, "_speak_chunks") as mock_chunks:
            tts.speak_blocking(long_text)
            mock_split.assert_called_once_with(long_text)
            mock_chunks.assert_called_once_with(["parte 1", "parte 2"])


def test_plugin_interface_extension():
    from aurion.tts import TTSEngine

    class MockEngine(TTSEngine):
        def speak(self, text): ...
        def speak_blocking(self, text): ...
        def list_voices(self): return []
        def test_voice(self, voice_id, text): ...

    assert isinstance(MockEngine(), TTSEngine)
