"""Color-only video palette catalogue, read without importing the GPU engine."""
import json

from . import config

DEFAULT_THEME = "bubble"
VIDEO_THEMES = json.loads((config.ROOT / "animai" / "assets" / "video-themes.json").read_text(encoding="utf-8"))
THEME_IDS = frozenset(t["id"] for t in VIDEO_THEMES)


def theme_name(theme_id: str) -> str:
    return next(t["name"] for t in VIDEO_THEMES if t["id"] == theme_id)
