"""Tests for ServiceDiscovery."""

import sys
from unittest.mock import MagicMock, patch

import pytest


def test_manual_config_uses_env():
    """Fallback manual usa variaveis de ambiente quando discover retorna vazio."""
    from aurion.discovery import ServiceDiscovery

    with patch("aurion.discovery.os.getenv", return_value="http://custom-hermes:3000"):
        disc = ServiceDiscovery()
        config = disc._load_manual_config()

    assert "hermes" in config
    assert config["hermes"] == "http://custom-hermes:3000"


def test_manual_config_default_port():
    """Fallback usa porta padrao quando variavel nao esta definida."""
    from aurion.discovery import ServiceDiscovery

    with patch("aurion.discovery.os.getenv", return_value=None):
        disc = ServiceDiscovery()
        config = disc._load_manual_config()

    assert config["ollama"] == "http://localhost:11434"
    assert config["kokoro"] == "http://localhost:8000"


def test_discover_returns_empty_when_zeroconf_not_available():
    """discover() retorna dict manual quando zeroconf nao disponivel."""
    from aurion.discovery import ServiceDiscovery

    disc = ServiceDiscovery()

    # Patch inside the module's namespace where zeroconf gets imported
    with patch.dict(sys.modules, {"zeroconf": None}):
        # Remove cached import if present
        if "aurion.discovery" in sys.modules:
            del sys.modules["aurion.discovery"]
        from aurion.discovery import ServiceDiscovery as SD2
        disc2 = SD2()
        result = disc2.discover(timeout=0.1)
        assert isinstance(result, dict)


def test_health_check():
    """Health-check valida conexao com servico descoberto."""
    from aurion.discovery import ServiceDiscovery

    disc = ServiceDiscovery()
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_client_instance = MagicMock()
    mock_client_instance.get = MagicMock(return_value=mock_resp)

    with patch("aurion.discovery.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=None)
        result = disc.health_check({"hermes": "http://localhost:8080"})

    assert result["hermes"] is True


def test_health_check_fails():
    """Health-check retorna False quando servico esta offline."""
    from aurion.discovery import ServiceDiscovery

    disc = ServiceDiscovery()

    mock_client_instance = MagicMock()
    mock_client_instance.get = MagicMock(side_effect=Exception("Connection refused"))

    with patch("aurion.discovery.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=None)
        result = disc.health_check({"hermes": "http://localhost:8080"})

    assert result["hermes"] is False


def test_services_discovered():
    """discover() retorna dict com servicos encontrados (mock zeroconf)."""

    # ServiceListener must be a real class (not MagicMock) so the
    # code can subclass it without hitting mock attribute errors.
    class _FakeServiceListener:
        pass

    mock_zc = MagicMock()
    mock_browser_cls = MagicMock()

    # Patch zeroconf at the module level before importing
    with patch.dict(sys.modules, {"zeroconf": MagicMock(Zeroconf=mock_zc, ServiceBrowser=mock_browser_cls, ServiceListener=_FakeServiceListener)}):
        if "aurion.discovery" in sys.modules:
            del sys.modules["aurion.discovery"]

        from aurion.discovery import ServiceDiscovery

        disc = ServiceDiscovery()
        with patch("aurion.discovery.time.sleep"):
            result = disc.discover(timeout=0.1)

        assert isinstance(result, dict)
