"""Locating FFmpeg and LaTeX, which may be installed but not yet on PATH."""
from __future__ import annotations

import glob
import os
import shutil
import sys
from pathlib import Path

_LOCALAPPDATA = os.getenv("LOCALAPPDATA", "")
_PROGRAMFILES = os.getenv("ProgramFiles", r"C:\Program Files")

_SEARCH_DIRS = {
    "ffmpeg": [
        f"{_LOCALAPPDATA}/Microsoft/WinGet/Links",
        f"{_LOCALAPPDATA}/Microsoft/WinGet/Packages/Gyan.FFmpeg*/ffmpeg-*/bin",
        "C:/ffmpeg/bin",
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ],
    "latex": [
        f"{_LOCALAPPDATA}/Programs/MiKTeX/miktex/bin/x64",
        f"{_PROGRAMFILES}/MiKTeX/miktex/bin/x64",
        "C:/texlive/*/bin/windows",
        "C:/texlive/*/bin/win64",
        "/Library/TeX/texbin",
        "/usr/local/texlive/*/bin/*",
    ],
}


def find_tool_dir(tool: str, env_var: str) -> Path | None:
    exe = tool + (".exe" if sys.platform == "win32" else "")
    override = os.getenv(env_var)
    if override:
        p = Path(override)
        return p if p.is_dir() else p.parent
    found = shutil.which(tool)
    if found:
        return Path(found).parent
    for pattern in _SEARCH_DIRS[tool]:
        for candidate in sorted(glob.glob(pattern), reverse=True):
            if (Path(candidate) / exe).exists():
                return Path(candidate)
    return None


FFMPEG_DIR = find_tool_dir("ffmpeg", "FFMPEG_DIR")
LATEX_DIR = find_tool_dir("latex", "LATEX_DIR")


def ffmpeg_bin() -> str:
    if FFMPEG_DIR:
        return str(FFMPEG_DIR / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"))
    return "ffmpeg"


def tool_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """A copy of the environment with FFmpeg and LaTeX on PATH."""
    env = dict(os.environ if base is None else base)
    extra = [str(d) for d in (FFMPEG_DIR, LATEX_DIR) if d]
    env["PATH"] = os.pathsep.join(extra + [env.get("PATH", "")])
    return env
