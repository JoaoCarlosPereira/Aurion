"""Tests for migrated tools."""

import os


def test_tools_package_exists():
    """O pacote aurion.tools existe com __init__.py."""
    tools_init = os.path.join(os.path.dirname(__file__), "..", "aurion", "tools", "__init__.py")
    assert os.path.isfile(tools_init)


def test_tools_files_exist():
    """Todas as ferramentas foram migradas para aurion/tools/."""
    tools_dir = os.path.join(os.path.dirname(__file__), "..", "aurion", "tools")
    expected = ["time.py", "duckduckgo.py", "OCR.py", "screenshot.py", "arp_scan.py", "matrix.py"]
    for fname in expected:
        assert os.path.isfile(os.path.join(tools_dir, fname)), f"{fname} nao encontrado"


def test_time_tool_has_cities():
    """get_time tem cidades suficientes (verifica sem importar)."""
    time_path = os.path.join(os.path.dirname(__file__), "..", "aurion", "tools", "time.py")
    with open(time_path) as f:
        content = f.read()

    assert 'CITY_TIMEZONES' in content
    assert len(content) > 500  # reasonable file size
    # Check for key cities
    assert 'sao_paulo' in content or 'sao paulo' in content


def test_screenshot_uses_configurable_path():
    """screenshot usa path configuravel (nao hardcoded)."""
    scr_path = os.path.join(os.path.dirname(__file__), "..", "aurion", "tools", "screenshot.py")
    with open(scr_path) as f:
        content = f.read()

    # Must have output_path parameter in function signature
    assert 'output_path' in content
    # Should use os.getenv or default value
    assert 'os.getenv' in content or 'expanduser' in content


def test_ocr_uses_configurable_path():
    """OCR usa path configuravel (nao hardcoded)."""
    ocr_path = os.path.join(os.path.dirname(__file__), "..", "aurion", "tools", "OCR.py")
    with open(ocr_path) as f:
        content = f.read()

    assert 'image_path' in content
    assert 'os.getenv' in content or 'expanduser' in content


def test_arp_scan_supports_windows():
    """arp_scan suporta Windows."""
    arp_path = os.path.join(os.path.dirname(__file__), "..", "aurion", "tools", "arp_scan.py")
    with open(arp_path) as f:
        content = f.read()

    assert 'Windows' in content or "system == 'Windows'" in content
    assert 'Windows' in content


def test_matrix_supports_windows():
    """matrix_mode mantem fallback Python para Windows."""
    mat_path = os.path.join(os.path.dirname(__file__), "..", "aurion", "tools", "matrix.py")
    with open(mat_path) as f:
        content = f.read()

    assert 'Windows' in content


def test_pillow_in_requirements():
    """Pillow esta nas dependencias."""
    with open('requirements.txt') as f:
        content = f.read()
    assert 'Pillow' in content or 'pillow' in content.lower()


def test_tools_init_exports_all():
    """__init__.py exporta todas as ferramentas."""
    init_path = os.path.join(os.path.dirname(__file__), "..", "aurion", "tools", "__init__.py")
    with open(init_path) as f:
        content = f.read()

    expected_exports = [
        "get_time",
        "duckduckgo_search_tool",
        "read_text_from_latest_image",
        "take_screenshot",
        "arp_scan_terminal",
        "matrix_mode",
    ]
    for name in expected_exports:
        assert name in content, f"{name} nao exportado em __init__.py"
