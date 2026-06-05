"""Tira screenshot da tela usando mss."""

import os

from langchain.tools import tool


@tool("capture_screenshot", return_direct=True)
def take_screenshot(output_path: str | None = None) -> str:
    """
    Captures the current screen and saves it to a file using the 'mss' library.
    Use this tool when the user says:
    - "Take a screenshot"
    - "Capture the screen"
    - "Save a screenshot"
    """
    if output_path is None:
        output_path = os.getenv("AURION_SCREENSHOT_PATH", os.path.expanduser("./screenshot.png"))

    try:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        import mss
        import mss.tools

        with mss.mss() as sct:
            monitor = sct.monitors[1]  # [1] = main monitor
            screenshot = sct.grab(monitor)
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=output_path)

        return f"Screenshot captured and saved to {output_path}."
    except ImportError:
        return "Failed: 'mss' library not installed. Run: pip install mss"
    except Exception as e:
        return f"Failed to capture screenshot: {str(e)}"
