"""Text, cards and other general-purpose building blocks that follow the active theme."""
from __future__ import annotations

import numpy as np

from manimlib import (
    Animation, Arrow, Dot, FadeIn, Line, Mobject, RoundedRectangle, Text, Code, Transform,
    VGroup, Rectangle, UP, DOWN, LEFT, RIGHT, UR, ORIGIN, SMALL_BUFF, MED_SMALL_BUFF,
)

from .theme import get_theme

__all__ = [
    "TEXT_SIZES", "Label", "Title", "BulletList", "Card", "QuoteCard", "Callout", "CodeBlock",
    "Badge",
]

TEXT_SIZES = {"title": 64, "heading": 46, "body": 34, "label": 30, "small": 24, "tiny": 20}


def _size(size) -> float:
    return TEXT_SIZES.get(size, size) if isinstance(size, str) else size


class Label(Text):
    """
    Theme-colored text. `size` is a preset ("title", "heading", "body", "label", "small",
    "tiny") or a font size. `color` defaults to the theme's text color; `bold`/`italic`
    style the whole string; `max_width` shrinks long text to fit.

    Example: Label("Mitochondria", size="label", color=get_theme().primary)
    """

    def __init__(self, text: str, size="label", color=None, bold: bool = False,
                 italic: bool = False, font: str | None = None, max_width: float | None = None,
                 **kwargs):
        theme = get_theme()
        super().__init__(
            text, font_size=_size(size), font=font or theme.font,
            weight="BOLD" if bold else "NORMAL", slant="ITALIC" if italic else "NORMAL",
            fill_color=color or theme.text, **kwargs,
        )
        if max_width and self.get_width() > max_width:
            self.set_width(max_width)


class Title(VGroup):
    """
    A heading with a short accent underline, placed at the top of the frame by default.
    AnimaiScene.set_title() swaps titles for you between sections.

    Example: Title("How Vaccines Work")
    """

    def __init__(self, text: str, size="heading", color=None, underline: bool = True,
                 to_top: bool = True, **kwargs):
        theme = get_theme()
        self.text = Label(text, size=size, color=color, bold=True, max_width=12.5)
        parts = [self.text]
        if underline:
            self.underline = Line(LEFT, RIGHT, stroke_color=theme.accent, stroke_width=4)
            self.underline.set_width(min(self.text.get_width() * 0.35, 3))
            self.underline.next_to(self.text, DOWN, buff=0.15)
            parts.append(self.underline)
        super().__init__(*parts, **kwargs)
        if to_top:
            self.move_to(np.array([0, 3.25, 0]))
        self.text.set_backstroke(theme.background, 8)
        self.set_z_index(10)


class BulletList(VGroup):
    """
    Bulleted lines of text. Reveal one at a time with `self.play(FadeIn(bl.items[i], shift=RIGHT*0.2))`
    or all at once with `bl.reveal()`. Keep items short (under ~8 words).

    Example: BulletList("Kinetic energy", "Potential energy", "Thermal energy", size="body")
    """

    def __init__(self, *items: str, size="body", bullet_color=None, buff: float = 0.32,
                 max_width: float = 12.0, **kwargs):
        theme = get_theme()
        rows = []
        for item in items:
            text = Label(item, size=size)
            dot = Dot(radius=0.07 * _size(size) / 34, fill_color=bullet_color or theme.accent)
            dot.next_to(text, LEFT, buff=0.25)
            rows.append(VGroup(dot, text))
        super().__init__(*rows, **kwargs)
        self.arrange(DOWN, aligned_edge=LEFT, buff=buff)
        if self.get_width() > max_width:
            self.set_width(max_width)
        self.items = list(rows)

    def reveal(self, lag_ratio: float = 0.35, **kwargs) -> Animation:
        from manimlib import LaggedStart
        return LaggedStart(*(FadeIn(r, shift=RIGHT * 0.25) for r in self.items),
                           lag_ratio=lag_ratio, **kwargs)


class Card(VGroup):
    """
    A rounded panel holding `content` (any mobject), with an optional title above it.
    Use for definitions, key facts, side notes. `card.content` is the inner mobject.

    Example: Card(Label("Speed of light: 3e8 m/s", size="body"), title="Fact")
    """

    def __init__(self, content: Mobject, title: str | None = None, padding: float = 0.35,
                 width: float | None = None, color=None, **kwargs):
        theme = get_theme()
        self.content = content
        inner = [content]
        if title:
            self.title = Label(title, size="small", color=color or theme.accent, bold=True)
            group = VGroup(self.title, content).arrange(DOWN, aligned_edge=LEFT, buff=0.2)
            inner = [group]
        body = VGroup(*inner)
        w = max(width or 0, body.get_width() + 2 * padding)
        self.panel = RoundedRectangle(
            width=w, height=body.get_height() + 2 * padding, corner_radius=0.18,
            fill_color=theme.surface, fill_opacity=1, stroke_color=color or theme.outline,
            stroke_width=2,
        )
        self.panel.move_to(body)
        super().__init__(self.panel, body, **kwargs)


class Badge(VGroup):
    """A small pill-shaped tag, e.g. Badge("O(n log n)") or Badge("1914", color=theme.secondary)."""

    def __init__(self, text: str, color=None, size="small", **kwargs):
        theme = get_theme()
        c = color or theme.primary
        label = Label(text, size=size, color=c, bold=True)
        pill = RoundedRectangle(width=label.get_width() + 0.4, height=label.get_height() + 0.25,
                                corner_radius=(label.get_height() + 0.25) / 2,
                                fill_color=c, fill_opacity=0.15, stroke_color=c, stroke_width=2)
        pill.move_to(label)
        super().__init__(pill, label, **kwargs)


class QuoteCard(VGroup):
    """
    A quotation with attribution, styled for primary sources in history or literature.

    Example: QuoteCard("I came, I saw, I conquered.", "Julius Caesar", "47 BC")
    """

    def __init__(self, quote: str, author: str, date: str | None = None,
                 width: float = 9.0, **kwargs):
        theme = get_theme()
        mark = Text("“", font=theme.serif_font, font_size=120, fill_color=theme.accent)
        body = Text(_wrap(quote, 42), font=theme.serif_font, font_size=34,
                    slant="ITALIC", fill_color=theme.text, alignment="LEFT")
        if body.get_width() > width:
            body.set_width(width)
        attribution = Label("— " + author + (f", {date}" if date else ""), size="small",
                            color=theme.muted)
        attribution.next_to(body, DOWN, buff=0.35, aligned_edge=RIGHT)
        mark.set_height(0.55).next_to(body, LEFT, buff=0.3, aligned_edge=UP)
        super().__init__(mark, body, attribution, **kwargs)
        self.quote, self.attribution = body, attribution


class Callout(VGroup):
    """
    A label with an arrow pointing at `target` (a mobject or point). `direction` is where
    the label sits relative to the target.

    Example: Callout(nucleus, "Nucleus: holds the DNA", direction=UR)
    """

    def __init__(self, target, text: str, direction=UR, distance: float = 1.6,
                 color=None, size="small", **kwargs):
        theme = get_theme()
        c = color or theme.accent
        point = target.get_center() if isinstance(target, Mobject) else np.array(target, dtype=float)
        d = np.array(direction, dtype=float)
        d = d / (np.linalg.norm(d) or 1)
        edge = target.get_boundary_point(d) if isinstance(target, Mobject) else point
        self.label = Label(text, size=size, color=c)
        self.label.move_to(edge + d * distance)
        self.label.shift(d * self.label.get_width() / 2 * abs(d[0]) * 0.5)
        start = self.label.get_boundary_point(-d)
        self.arrow = Arrow(start, edge, buff=0.12, thickness=2.5, fill_color=c)
        super().__init__(self.arrow, self.label, **kwargs)


class CodeBlock(VGroup):
    """
    Syntax-highlighted code on a dark panel. `highlight_line(n)` returns an animation that
    moves a highlight bar to line n (1-based) for stepping through an algorithm;
    `line(n)` returns that line's glyphs.

    Example:
        code = CodeBlock("def add(a, b):\\n    return a + b", language="python")
        self.play(FadeIn(code)); self.play(code.highlight_line(2))
    """

    def __init__(self, code: str, language: str = "python", font_size: int = 22,
                 padding: float = 0.3, style: str = "monokai", **kwargs):
        theme = get_theme()
        self.source_lines = code.strip("\n").split("\n")
        self.code = Code(code.strip("\n"), font=theme.mono_font, font_size=font_size,
                         language=language, code_style=style)
        self.panel = RoundedRectangle(
            width=self.code.get_width() + 2 * padding, height=self.code.get_height() + 2 * padding,
            corner_radius=0.15, fill_color="#1B1D23", fill_opacity=1,
            stroke_color=theme.outline, stroke_width=1.5,
        ).move_to(self.code)
        self.highlight = Rectangle(
            width=self.panel.get_width() - 0.1, height=self._line_height * 1.05,
            fill_color=theme.accent, fill_opacity=0.18, stroke_width=0,
        )
        self.highlight.move_to(self._line_center(1)).set_opacity(0)
        super().__init__(self.panel, self.highlight, self.code, **kwargs)

    @property
    def _line_height(self) -> float:
        """Measured live, so it stays right after the block is resized."""
        return self.code.get_height() / max(len(self.source_lines), 1)

    def _line_center(self, n: int) -> np.ndarray:
        top = self.code.get_top()[1]
        y = top - (n - 0.5) * self._line_height
        return np.array([self.panel.get_center()[0], y, 0.0])

    def line(self, n: int) -> VGroup:
        """The glyphs of line n (1-based)."""
        center_y = self._line_center(n)[1]
        half = self._line_height / 2
        return VGroup(*(g for g in self.code.submobjects
                        if abs(g.get_center()[1] - center_y) < half))

    def highlight_line(self, n: int, color=None) -> Animation:
        target = self.highlight.copy().move_to(self._line_center(n)).set_fill(
            color or get_theme().accent, opacity=0.18)
        return Transform(self.highlight, target)


def _wrap(text: str, width: int) -> str:
    words, lines, line = text.split(), [], ""
    for w in words:
        if line and len(line) + 1 + len(w) > width:
            lines.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        lines.append(line)
    return "\n".join(lines)
