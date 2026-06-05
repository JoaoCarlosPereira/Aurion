"""Tests for Aurion package structure and imports."""

import importlib
import subprocess
import sys


def test_package_import():
    """aurion pode ser importado sem erro."""
    import aurion
    assert hasattr(aurion, "__version__")
    assert isinstance(aurion.__version__, str)
    assert aurion.__version__


def test_package_version():
    """aurion.__version__ retorna string válida."""
    import aurion
    parts = aurion.__version__.split(".")
    assert len(parts) >= 2
    for part in parts[:3]:
        part.strip()
        int(part)


def test_submodules_importable():
    """Todos os submódulos podem ser importados separadamente."""
    modules = [
        "aurion.server",
        "aurion.listener",
        "aurion.hermes",
        "aurion.tts",
        "aurion.discovery",
        "aurion.database",
    ]
    for module_name in modules:
        mod = importlib.import_module(module_name)
        assert mod is not None


def test_requirements_install():
    """pip install -r requirements.txt instala sem erros."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"pip install failed: {result.stderr}"


def test_pytest_collect():
    """pytest --collect-only lista todos os testes stub."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert result.returncode == 0, f"pytest collect failed: {result.stderr}"
    assert "test_package" in result.stdout
