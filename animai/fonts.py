"""
Installing Animai's bundled fonts (assets/fonts, all SIL Open Font License) for the current
user, so Pango finds them like any system font.

Registering fonts in-process with manimpango works but makes every text render rescan the
font list (~10 s per string on Windows), so the fonts are installed once instead:

    python -m animai.fonts            # install if missing (no admin rights needed)

The render launcher calls `ensure_installed()` automatically. No engine imports here.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"


def _user_font_dir() -> Path:
    if sys.platform == "win32":
        import os
        return Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows" / "Fonts"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Fonts"
    return Path.home() / ".local" / "share" / "fonts"


def _register_windows(path: Path) -> None:
    import ctypes
    import winreg
    name = path.stem.replace("-", " ") + " (TrueType)"
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows NT\CurrentVersion\Fonts")
    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(path))
    winreg.CloseKey(key)
    ctypes.windll.gdi32.AddFontResourceW(str(path))


def missing() -> list[Path]:
    dest = _user_font_dir()
    return [f for f in sorted(FONT_DIR.glob("*.ttf")) if not (dest / f.name).exists()]


def ensure_installed(verbose: bool = False) -> int:
    """Install any bundled fonts not yet in the user's font folder. Returns how many."""
    todo = missing()
    if not todo:
        return 0
    dest = _user_font_dir()
    dest.mkdir(parents=True, exist_ok=True)
    for f in todo:
        target = dest / f.name
        shutil.copyfile(f, target)
        if sys.platform == "win32":
            _register_windows(target)
        if verbose:
            print(f"installed {f.name}")
    if sys.platform.startswith("linux") and shutil.which("fc-cache"):
        subprocess.run(["fc-cache", "-f", str(dest)], capture_output=True)
    return len(todo)


if __name__ == "__main__":
    n = ensure_installed(verbose=True)
    print(f"{n} font(s) installed" if n else "All Animai fonts already installed")
