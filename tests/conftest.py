"""Shared fixtures for Aurion tests."""

import queue
import pytest


@pytest.fixture
def command_queue():
    """Provide a fresh queue.Queue for command passing tests."""
    return queue.Queue()


@pytest.fixture
def mock_hermes_response():
    """Provide a mock Hermes Agent response."""
    return {"response": "Comando executado com sucesso", "status": "success"}


@pytest.fixture
def mock_voice_list():
    """Provide a mock voice list for TTS tests."""
    return [
        type("Voice", (), {"id": "voice0", "name": "Google Brasil", "lang": "pt-BR"})(),
        type("Voice", (), {"id": "voice1", "name": "Microsoft Paula", "lang": "pt-BR"})(),
        type("Voice", (), {"id": "voice2", "name": "Generic English", "lang": "en-US"})(),
    ]
