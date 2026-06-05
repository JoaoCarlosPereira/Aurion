"""Matrix mode — efeito visual estilo Matrix."""

import platform
import shutil
import subprocess
import sys
import tempfile

from langchain.tools import tool


@tool("matrix_mode", return_direct=True)
def matrix_mode() -> str:
    """
    Activates 'Matrix Mode' — a green rain of characters on the terminal.
    Use this tool when the user says something like:
    - "Enter matrix mode"
    - "Activate matrix mode"
    - "Go into matrix mode"
    """
    system = platform.system()

    if system == "Windows":
        python_script = r'''
import random
import time
import os
import sys

os.system("color 0A")
chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!@#$%^&*"

def get_terminal_size():
    try:
        import shutil
        return shutil.get_terminal_size()
    except Exception:
        return (80, 25)

width, height = get_terminal_size()
width = min(width, 120)
height = min(height, 30)

drops = [random.randint(0, height) for _ in range(width)]

print("\033[32m")
print("Welcome to the Matrix. Press Ctrl+C to exit...")
time.sleep(2)

try:
    while True:
        os.system("cls")
        screen = [[" " for _ in range(width)] for _ in range(height)]
        for i in range(width):
            if drops[i] < height:
                screen[drops[i]][i] = random.choice(chars)
            drops[i] += 1
            if drops[i] > height and random.random() > 0.95:
                drops[i] = 0
        for row in screen:
            print("".join(row))
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n\033[32mExiting Matrix...\033[0m")
    time.sleep(1)
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(python_script)
            script_path = f.name

        subprocess.Popen([sys.executable, script_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
        return "Matrix mode activated! Welcome to the Matrix, Neo. Press Ctrl+C to exit."

    elif system == "Linux":
        if shutil.which("cmatrix") is None:
            return "Matrix mode requires 'cmatrix'. Install via your package manager."
        subprocess.Popen(["gnome-terminal", "--", "cmatrix"])
        return "Matrix mode activated! Enjoy the rain, Neo."

    elif system == "Darwin":
        if shutil.which("cmatrix") is None:
            return "Matrix mode requires 'cmatrix'. Install via Homebrew: brew install cmatrix"
        subprocess.Popen([
            "osascript", "-e",
            'tell application "Terminal" to do script "cmatrix"',
            "-e", 'tell application "Terminal" to activate'
        ])
        return "Matrix mode activated, sir!"

    else:
        return f"Matrix mode is not supported on {system}."


import shutil
