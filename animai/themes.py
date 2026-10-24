"""
Visual themes. Every Animai component takes its colors and fonts from the active theme,
so a whole video changes look by setting one module-level constant in the scene file:

    THEME = "paper"

The renderer reads that constant before the engine starts (default colors are fixed at
import time), and `AnimaiScene` applies the background.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

__all__ = ["Theme", "THEMES", "get_theme", "set_theme", "palette_color"]


def _default_font() -> str:
    if sys.platform == "win32":
        return "Segoe UI"
    if sys.platform == "darwin":
        return "Helvetica Neue"
    return "DejaVu Sans"


@dataclass(frozen=True)
class Theme:
    """Colors and fonts for a video. Use the semantic names rather than raw colors."""
    name: str
    background: str
    text: str          # Main text and default line color
    muted: str         # Secondary text, axes, gridlines, de-emphasized elements
    surface: str       # Fill of cards, boxes and nodes
    outline: str       # Border of cards, boxes and nodes
    primary: str       # The main subject of the current idea
    secondary: str     # The thing it's compared with or acted on
    accent: str        # Highlights, emphasis, "look here"
    positive: str      # Correct / gain / growth
    negative: str      # Wrong / loss / danger
    palette: tuple[str, ...] = field(default_factory=tuple)  # Categorical series colors
    font: str = field(default_factory=_default_font)
    mono_font: str = "Consolas"
    serif_font: str = "Georgia"


THEMES: dict[str, Theme] = {
    # 3Blue1Brown look: black background, bright blue/yellow
    "classic": Theme(
        name="classic", background="#000000", text="#FFFFFF", muted="#888888",
        surface="#15191F", outline="#4A5560",
        primary="#58C4DD", secondary="#F7D96F", accent="#FFFF00",
        positive="#83C167", negative="#FC6255",
        palette=("#58C4DD", "#F0AC5F", "#83C167", "#FC6255", "#9A72AC", "#5CD0B3", "#E07BB8", "#C9C9C9"),
    ),
    # Dark green slate with chalk pastels: friendly for intro science, biology
    "chalkboard": Theme(
        name="chalkboard", background="#1E2B24", text="#F2F2EC", muted="#9AA79F",
        surface="#26362D", outline="#5E7166",
        primary="#8FD3E8", secondary="#F5E19A", accent="#FFB3A7",
        positive="#B5E39C", negative="#F28C8C",
        palette=("#8FD3E8", "#F5E19A", "#B5E39C", "#F28C8C", "#C9B3E6", "#F6B979", "#9EE0CF", "#E8E8E0"),
    ),
    # Warm parchment with ink tones: history, literature, social sciences
    "paper": Theme(
        name="paper", background="#F4EEDF", text="#2B2621", muted="#8A7F70",
        surface="#EAE1CC", outline="#B9AA8F",
        primary="#2F5D8A", secondary="#A8442F", accent="#C7891E",
        positive="#4F7A3A", negative="#A8322B",
        palette=("#2F5D8A", "#A8442F", "#4F7A3A", "#C7891E", "#6B4C8A", "#2E7D78", "#8A5A3C", "#5C5C5C"),
        font="Georgia",
    ),
    # Navy engineering drawing: physics, engineering, computer systems
    "blueprint": Theme(
        name="blueprint", background="#0E2341", text="#E8F1FF", muted="#7F96B8",
        surface="#15305A", outline="#4D6E9E",
        primary="#7FD1FF", secondary="#FFD479", accent="#FFFFFF",
        positive="#8BE28B", negative="#FF8A80",
        palette=("#7FD1FF", "#FFD479", "#8BE28B", "#FF8A80", "#C3A6FF", "#7FF0D8", "#FFB26B", "#D0DCEB"),
    ),
}

_current: Theme | None = None


def get_theme() -> Theme:
    """The active theme (set by `set_theme`, the ANIMAI_THEME env var, or 'classic')."""
    global _current
    if _current is None:
        _current = THEMES.get(os.environ.get("ANIMAI_THEME", "classic"), THEMES["classic"])
    return _current


def set_theme(name: str) -> Theme:
    global _current
    if name not in THEMES:
        raise ValueError(f"Unknown theme {name!r}; choose from {', '.join(THEMES)}")
    _current = THEMES[name]
    return _current


def palette_color(i: int) -> str:
    """The i-th categorical color of the active theme (wraps around)."""
    p = get_theme().palette
    return p[i % len(p)]
