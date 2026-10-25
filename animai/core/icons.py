"""
Line icons (Lucide, ISC license, 2000+ icons) for concepts that have no diagram of their
own: people, places, objects, ideas. Names are lowercase-hyphenated, e.g. "lightbulb",
"users", "landmark", "factory", "dna", "brain", "coins", "globe", "swords", "scroll".
Unknown names fall back to the closest match by name or tag.
"""
from __future__ import annotations

import difflib
import json
from functools import lru_cache
from pathlib import Path

from animlib import Mobject, SVGMobject, VGroup, DOWN

from .media import Label
from .theme import get_theme

__all__ = ["Icon", "IconLabel", "find_icons"]

_ASSET = Path(__file__).resolve().parent.parent / "assets" / "icons" / "lucide.json"


@lru_cache(maxsize=1)
def _data() -> dict:
    return json.loads(_ASSET.read_text(encoding="utf-8"))


def find_icons(query: str, limit: int = 10) -> list[str]:
    """Icon names matching a word, by name first, then by tag (e.g. "money" -> coins, banknote...)."""
    q = query.lower().strip().replace(" ", "-")
    icons, tags = _data()["icons"], _data()["tags"]
    words = q.split("-")
    exact = [n for n in icons if n == q]
    by_word = sorted((n for n in icons if all(w in n.split("-") for w in words)), key=len)
    by_tag = [n for n, t in tags.items() if any(q.replace("-", " ") == x.lower() for x in t)]
    by_substring = sorted((n for n in icons if q in n), key=len)
    fuzzy = difflib.get_close_matches(q, list(icons), n=limit, cutoff=0.6)
    out = []
    for n in exact + by_word + by_tag + fuzzy + by_substring:
        if n not in out:
            out.append(n)
    return out[:limit]


def _resolve(name: str) -> str:
    icons = _data()["icons"]
    if name in icons:
        return name
    matches = find_icons(name, 1)
    if not matches:
        raise ValueError(f"No icon matches {name!r}")
    print(f"@@WARNING icon {name!r} not found, using {matches[0]!r}", flush=True)
    return matches[0]


class Icon(SVGMobject):
    """
    A line icon. `size` is its height in scene units; `color` defaults to the theme's text
    color. Use find_icons("keyword") to discover names.

    Example: Icon("lightbulb", size=1.2, color=get_theme().accent)
    """

    def __init__(self, name: str, size: float = 1.0, color=None, stroke_width: float = 3.0,
                 **kwargs):
        self.icon_name = _resolve(name)
        inner = _data()["icons"][self.icon_name]
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
               'stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
               f'{inner}</svg>')
        super().__init__(svg_string=svg, height=size, **kwargs)
        self.set_fill(opacity=0)
        self.set_stroke(color or get_theme().text, width=stroke_width)


class IconLabel(VGroup):
    """
    An icon with a caption underneath, for concept grids ("Farmers", "Merchants", "Clergy").

    Example: VGroup(IconLabel("wheat", "Farmers"), IconLabel("coins", "Merchants")).arrange(RIGHT, buff=1)
    """

    def __init__(self, icon: str, text: str, size: float = 1.0, color=None, label_size="small",
                 **kwargs):
        self.icon = Icon(icon, size=size, color=color)
        self.label = Label(text, size=label_size)
        self.label.next_to(self.icon, DOWN, buff=0.2)
        super().__init__(self.icon, self.label, **kwargs)
