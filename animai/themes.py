"""
Visual themes. Every Animai component takes its colors and fonts from the active theme,
so a whole video changes look by setting one module-level constant in the scene file:

    THEME = "paper"

The renderer reads that constant before the engine starts (default colors are fixed at
import time), and `AnimaiScene` applies the background and backdrop.

This module has no engine imports, so the render launcher can use it.
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from dataclasses import dataclass, field, replace

__all__ = ["Theme", "THEMES", "get_theme", "set_theme", "palette_color"]


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
    font: str = "Fira Sans"            # Bundled in assets/fonts
    heading_font: str = "Fira Sans"
    mono_font: str = "Fira Mono"
    serif_font: str = "Crimson Text"
    land: str = "#1A212C"              # Map land fill
    land_border: str = "#2C3646"       # Map country borders
    shadow: str = "#000000"            # Soft drop shadows under cards and nodes
    shadow_opacity: float = 0.45
    backdrop: str = "vignette"         # "vignette" (soft radial light), "grid", or "none"
    backdrop_color: str = "#121821"    # Vignette center color, or grid line color
    light: bool = False                # Light background (affects default stroke colors)
    text_weight: str = "NORMAL"
    pill: str = "#F8E1E5"
    baseline: str = "#D9D9D9"
    on_color: str = "#EFEDE7"
    visual_style: str = "legacy"       # Geometry/typography family, independent of palette ID
    decorative: tuple[str, ...] = ("#D9D9D9", "#FDDFAB", "#E8EDCC", "#FCDDA8")
    code_text: str = "#000000"
    code_keyword: str = "#E45E7F"
    code_function: str = "#3186E1"
    code_literal: str = "#BE9931"


THEMES: dict[str, Theme] = {
    # Figma animai / THE IMAGE (1:38). The default video identity.
    "bubble": Theme(
        name="bubble", background="#F5D9C8", text="#583F41", muted="#9D8084",
        surface="#FBF5F2", outline="#D9D9D9",
        primary="#A6C7EA", secondary="#ECD288", accent="#EF7D99",
        positive="#AAD9B0", negative="#F0B3BC",
        palette=("#ECD288", "#F0B3BC", "#A6C7EA", "#F1C29D", "#C7B6ED", "#AAD9B0"),
        font="Fredoka", heading_font="Fredoka", mono_font="JetBrains Mono", serif_font="Fredoka",
        text_weight="SEMIBOLD", land="#E8EDCC", land_border="#FBF5F2",
        shadow="#000000", shadow_opacity=0.07,
        backdrop="peach", backdrop_color="#FEEAE0", light=True, visual_style="bubble",
    ),
    # 3Blue1Brown look: near-black with a soft center glow, bright blues and warm accents
    "classic": Theme(
        name="classic", background="#000000", text="#F4F6FA", muted="#8B95A5",
        surface="#141A23", outline="#344050",
        primary="#58C4DD", secondary="#F4B860", accent="#FFE066",
        positive="#7BD389", negative="#FF6B6B",
        palette=("#58C4DD", "#F4A259", "#7BD389", "#FF6B6B", "#B388EB", "#4FD1C5", "#F78FB3", "#C8D1DC"),
        backdrop_color="#111823",
    ),
    # Dark green slate with chalk pastels and a hand-lettered font: intro science, biology
    "chalkboard": Theme(
        name="chalkboard", background="#1B2A23", text="#F3F1E7", muted="#A3B1A8",
        surface="#223A2F", outline="#4F665A",
        primary="#8ED1E6", secondary="#F6DE8D", accent="#FFB4A2",
        positive="#B5E39C", negative="#F28C8C",
        palette=("#8ED1E6", "#F6DE8D", "#B5E39C", "#F28C8C", "#C9B3E6", "#F6B979", "#9EE0CF", "#E8E8E0"),
        font="Patrick Hand", heading_font="Patrick Hand",
        land="#26402F", land_border="#4F665A", shadow_opacity=0.35,
        backdrop_color="#26392F",
    ),
    # Warm parchment with ink tones and a book serif: history, literature, social sciences
    "paper": Theme(
        name="paper", background="#F1E9D8", text="#2A241D", muted="#857A6A",
        surface="#FBF7EE", outline="#C9BBA0",
        primary="#2E5E8C", secondary="#B0472F", accent="#C98A16",
        positive="#4D7C3A", negative="#A6322B",
        palette=("#2E5E8C", "#B0472F", "#4D7C3A", "#C98A16", "#6B4C8A", "#2E7D78", "#8A5A3C", "#5C5C5C"),
        font="Crimson Text", heading_font="Crimson Text",
        land="#E4D7BC", land_border="#BCA985", shadow="#5B4A2F", shadow_opacity=0.18,
        backdrop_color="#FAF4E7", light=True,
    ),
    # Field-notes atlas: cream grid paper, ink outlines, soft pastels, condensed serif headings
    # (work in progress: components don't yet use hard shadows, dashed connectors or captions)
    "atlas": Theme(
        name="atlas", background="#ECEBE2", text="#1F2A28", muted="#6F736C",
        surface="#F8F5EC", outline="#1F2A28",
        primary="#7ECDC4", secondary="#F4C552", accent="#E8664A",
        positive="#6DBA8F", negative="#E8553B",
        palette=("#7ECDC4", "#F4C552", "#EE9F86", "#CDB4EA", "#A9C9EE", "#A8D5BA", "#F3B6C8", "#D9D4C3"),
        font="Fira Sans", heading_font="Instrument Serif", mono_font="IBM Plex Mono",
        serif_font="Instrument Serif",
        land="#E2E0D4", land_border="#B8B6A8", shadow="#1F2A28", shadow_opacity=0.9,
        backdrop="grid", backdrop_color="#DFDED4", light=True,
    ),
    # Navy engineering drawing with a faint grid: physics, engineering, systems
    "blueprint": Theme(
        name="blueprint", background="#0B1D37", text="#E9F2FF", muted="#89A3C7",
        surface="#122C52", outline="#3E6597",
        primary="#7FD1FF", secondary="#FFD479", accent="#FFFFFF",
        positive="#8BE28B", negative="#FF8A80",
        palette=("#7FD1FF", "#FFD479", "#8BE28B", "#FF8A80", "#C3A6FF", "#7FF0D8", "#FFB26B", "#D0DCEB"),
        land="#15335C", land_border="#3E6597", shadow="#020A16", shadow_opacity=0.5,
        backdrop="grid", backdrop_color="#17335C",
    ),
}

# The web picker and engine share this color-only catalogue. Every selectable
# variant inherits the original bubble geometry, fonts, weights and effects.
_catalog = json.loads((Path(__file__).parent / "assets" / "video-themes.json").read_text(encoding="utf-8"))
_bubble = THEMES["bubble"]
_color_fields = {
    "background", "backdrop_color", "surface", "text", "muted", "outline",
    "primary", "secondary", "accent", "positive", "negative", "palette",
    "land", "land_border", "shadow", "pill", "baseline", "on_color", "decorative",
    "code_text", "code_keyword", "code_function", "code_literal",
}
for _entry in _catalog:
    _colors = _entry["colors"]
    if set(_colors) - _color_fields:
        raise ValueError("Video palettes may override colors only")
    _colors = {k: tuple(v) if isinstance(v, list) else v for k, v in _colors.items()}
    THEMES[_entry["id"]] = replace(_bubble, name=_entry["id"], **_colors)

_current: Theme | None = None


def get_theme() -> Theme:
    """The active theme (set by `set_theme`, the ANIMAI_THEME env var, or 'bubble')."""
    global _current
    if _current is None:
        _current = THEMES.get(os.environ.get("ANIMAI_THEME", "bubble"), THEMES["bubble"])
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
