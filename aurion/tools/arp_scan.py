"""ARP scan — lista dispositivos na rede local."""

import platform
import subprocess
from langchain.tools import tool


@tool("arp_scan_terminal", return_direct=True)
def arp_scan_terminal() -> str:
    """
    Runs 'arp -a' to list all devices on the local network.
    Example queries:
    - "Show me the ARP table"
    - "Run arp scan"
    - "Find all devices on my network"
    """
    system = platform.system()

    if system == "Darwin":
        apple_script = '''
        tell application "Terminal"
            activate
            do script "arp -a"
        end tell
        '''
        subprocess.Popen(["osascript", "-e", apple_script])
        return "All devices on your network are now being listed in Terminal."

    elif system == "Windows":
        try:
            result = subprocess.run(
                ["arp", "-a"], capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip() if result.stdout else "ARP table is empty."
        except FileNotFoundError:
            return "ARP command not found. Is Windows?"
        except subprocess.TimeoutExpired:
            return "ARP scan timed out."
        except Exception as e:
            return f"Error running ARP scan: {e}"

    else:
        try:
            result = subprocess.run(
                ["arp", "-a"], capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip() if result.stdout else "ARP table is empty."
        except Exception as e:
            return f"ARP scan not supported on {system}. Error: {e}"
