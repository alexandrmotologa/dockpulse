"""Cross-platform clipboard utility using native operating system tools."""

import subprocess
import sys


def copy_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard using native platform commands."""
    if not text:
        return False

    try:
        if sys.platform == "win32":
            # Use PowerShell Set-Clipboard
            process = subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            process.communicate(input=text.encode("utf-8"))
            return process.returncode == 0

        if sys.platform == "darwin":
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            process.communicate(input=text.encode("utf-8"))
            return process.returncode == 0

        # Linux / BSD: Try wl-copy (Wayland) then xclip (X11) then xsel
        for cmd in (
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ):
            try:
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                proc.communicate(input=text.encode("utf-8"))
                if proc.returncode == 0:
                    return True
            except FileNotFoundError:
                continue

        return False
    except Exception:
        return False
