"""Ferramentas migradas do Jarvis para o Aurion."""

from aurion.tools.OCR import read_text_from_latest_image
from aurion.tools.arp_scan import arp_scan_terminal
from aurion.tools.duckduckgo import duckduckgo_search_tool
from aurion.tools.matrix import matrix_mode
from aurion.tools.screenshot import take_screenshot
from aurion.tools.time import get_time

__all__ = [
    "get_time",
    "duckduckgo_search_tool",
    "read_text_from_latest_image",
    "take_screenshot",
    "arp_scan_terminal",
    "matrix_mode",
]
