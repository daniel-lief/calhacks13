"""Settings and discovery of the external tools rendering depends on."""
from __future__ import annotations

import glob
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env.local")  # Convex deployment URL + worker secret

CONVEX_URL = os.getenv("CONVEX_URL", "")
WORKER_SECRET = os.getenv("WORKER_SECRET", "")
WORKER_POLL_SECONDS = float(os.getenv("WORKER_POLL_SECONDS", "3"))

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data")).resolve()
JOBS_DIR = DATA_DIR / "jobs"
STATS_PATH = DATA_DIR / "stats.json"       # pre-Convex likes/views, read once by import_to_convex.py
SAMPLES_DIR = Path(__file__).resolve().parent / "samples"   # the six samples, imported into Convex as @animai
AUDIO_CACHE_DIR = DATA_DIR / "audio_cache"
FRONTEND_DIR = ROOT / "frontend"

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
CLAUDE_EFFORT = os.getenv("CLAUDE_EFFORT", "medium")

# USD per million tokens (input, output). Cache writes bill at 1.25x input, reads at 0.1x.
MODEL_PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),  # prompts up to 100K tokens
}
# Models that accept server-side refusal fallbacks (`fallbacks: "default"`)
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-opus-5"}
MAX_REPAIR_ATTEMPTS = int(os.getenv("MAX_REPAIR_ATTEMPTS", "4"))
RENDER_TIMEOUT_SECONDS = int(os.getenv("RENDER_TIMEOUT_SECONDS", "1800"))
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "1"))
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AndrewMultilingualNeural")

# Optional YouTube research. Tokens stay on the server; no credentials reach the browser.
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "") or os.getenv("APIFY_API_TOKEN", "")
RESEARCH_ENABLED = os.getenv("RESEARCH_ENABLED", "true").lower() not in {"0", "false", "no"}
RESEARCH_MAX_VIDEOS = max(1, min(3, int(os.getenv("RESEARCH_MAX_VIDEOS", "3"))))
RESEARCH_TIMEOUT_SECONDS = max(30, min(300, int(os.getenv("RESEARCH_TIMEOUT_SECONDS", "180"))))
RESEARCH_MAX_APIFY_USD = max(.04, float(os.getenv("RESEARCH_MAX_APIFY_USD", "0.50")))
RESEARCH_CACHE_TTL_SECONDS = 86400
RESEARCH_CACHE_DIR = DATA_DIR / "research_cache"
RESEARCH_MODEL = os.getenv("RESEARCH_MODEL", CLAUDE_MODEL)

_LOCALAPPDATA = os.getenv("LOCALAPPDATA", "")
_PROGRAMFILES = os.getenv("ProgramFiles", r"C:\Program Files")

# Common install locations that may not be on PATH yet (e.g. right after a winget install)
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


def _find_tool_dir(tool: str, env_var: str) -> Path | None:
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


FFMPEG_DIR = _find_tool_dir("ffmpeg", "FFMPEG_DIR")
LATEX_DIR = _find_tool_dir("latex", "LATEX_DIR")


def tool_env() -> dict[str, str]:
    """Environment for subprocesses, with ffmpeg and LaTeX on PATH."""
    env = os.environ.copy()
    extra = [str(d) for d in (FFMPEG_DIR, LATEX_DIR) if d]
    env["PATH"] = os.pathsep.join(extra + [env.get("PATH", "")])
    return env


def ffmpeg_bin() -> str:
    if FFMPEG_DIR:
        return str(FFMPEG_DIR / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"))
    return "ffmpeg"


def has_anthropic_credentials() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def tts_available() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False
