"""Text, cards and other general-purpose building blocks that follow the active theme."""
from __future__ import annotations

import numpy as np

from manimlib import (
    Animation, AnimationGroup, Arrow, Circle, Code, Dot, FadeIn, LaggedStart, Mobject,
    RoundedRectangle, Text, Transform, VGroup, UP, DOWN, LEFT, RIGHT, UR, ORIGIN,
)

from .style import Panel, soft_shadow
from .theme import get_theme

__all__ = [
    "TEXT_SIZES", "Label", "Title", "BulletList", "Card", "QuoteCard", "Callout", "CodeBlock",
    "Badge", "StatPill",
]

TEXT_SIZES = {"title": 76, "heading": 54, "body": 40, "label": 34, "small": 28, "tiny": 22}


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
        heading = size in ("title", "heading")
        super().__init__(
            text, font_size=_size(size), font=font or (theme.heading_font if heading else theme.font),
            weight="SEMIBOLD" if bold else theme.text_weight, slant="ITALIC" if italic else "NORMAL",
            fill_color=color or theme.text, **kwargs,
        )
        if max_width and self.get_width() > max_width:
            self.set_width(max_width)


class Title(VGroup):
    """
    A heading with a short accent bar beneath it, placed at the top of the frame by default.
    AnimaiScene.set_title() swaps titles for you between sections.

    Example: Title("How Vaccines Work")
    """

    def __init__(self, text: str, size="heading", color=None, underline: bool = True,
                 to_top: bool = True, **kwargs):
        theme = get_theme()
        self.text = Label(text, size=size, color=color, bold=True, max_width=12.5)
        parts = [self.text]
        if underline and theme.name != "bubble":
            w = min(max(self.text.get_width() * 0.22, 0.9), 2.2)
            self.underline = RoundedRectangle(width=w, height=0.075, corner_radius=0.0375,
                                              fill_color=theme.accent, fill_opacity=1, stroke_width=0)
            self.underline.next_to(self.text, DOWN, buff=0.18)
            parts.append(self.underline)
        super().__init__(*parts, **kwargs)
        if to_top:
            self.move_to(np.array([0, 3.22, 0]))
        if theme.name != "bubble":
            self.text.set_backstroke(theme.background, 8)


class BulletList(VGroup):
    """
    Bulleted lines of text. Reveal one at a time with `self.play(FadeIn(bl.items[i], shift=RIGHT*0.2))`
    or all at once with `bl.reveal()`. `numbered=True` shows 1, 2, 3 badges instead of dots.
    Keep items short (under ~8 words).

    Example: BulletList("Kinetic energy", "Potential energy", "Thermal energy", size="body")
    """

    def __init__(self, *items: str, size="body", bullet_color=None, buff: float = 0.38,
                 numbered: bool = False, max_width: float = 12.0, **kwargs):
        theme = get_theme()
        c = bullet_color or theme.accent
        rows = []
        unit = _size(size) / 40
        for i, item in enumerate(items):
            text = Label(item, size=size)
            if numbered:
                disc = Circle(radius=0.24 * unit, fill_color=c, fill_opacity=1, stroke_width=0)
                num = Label(str(i + 1), size=_size(size) * 0.6, color=theme.background, bold=True)
                marker = VGroup(disc, num.move_to(disc))
            else:
                marker = RoundedRectangle(width=0.16 * unit, height=0.16 * unit,
                                          corner_radius=0.05 * unit, fill_color=c, fill_opacity=1,
                                          stroke_width=0)
            marker.next_to(text, LEFT, buff=0.3 * unit)
            rows.append(VGroup(marker, text))
        super().__init__(*rows, **kwargs)
        self.arrange(DOWN, aligned_edge=LEFT, buff=buff)
        if self.get_width() > max_width:
            self.set_width(max_width)
        self.items = list(rows)

    def reveal(self, lag_ratio: float = 0.35, **kwargs) -> Animation:
        return LaggedStart(*(FadeIn(r, shift=RIGHT * 0.3) for r in self.items),
                           lag_ratio=lag_ratio, **kwargs)


class Card(VGroup):
    """
    A raised panel holding `content` (any mobject), with an optional title above it. Use
    for definitions, key facts, side notes. `card.content` is the inner mobject.

    Example: Card(Label("Speed of light: 3e8 m/s", size="body"), title="Fact")
    """

    def __init__(self, content: Mobject, title: str | None = None, padding: float = 0.4,
                 width: float | None = None, color=None, **kwargs):
        theme = get_theme()
        c = color or theme.accent
        self.content = content
        body = content
        if title:
            self.title = Label(title if theme.name == "bubble" else title.upper(),
                               size="tiny", color=c, bold=True)
            body = VGroup(self.title, content).arrange(DOWN, aligned_edge=LEFT, buff=0.22)
        w = max(width or 0, body.get_width() + 2 * padding)
        h = body.get_height() + 2 * padding
        self.panel = Panel(w, h, color=theme.outline, tint=0.0, corner_radius=0.2)
        self.stripe = RoundedRectangle(width=0.09, height=h - 0.3, corner_radius=0.045,
                                       fill_color=c, fill_opacity=1, stroke_width=0)
        self.panel.move_to(body)
        self.stripe.move_to(self.panel.shape.get_left() + RIGHT * 0.17)
        if theme.name == "bubble":
            self.stripe.set_opacity(0)
        body.shift(RIGHT * 0.08)
        super().__init__(self.panel, self.stripe, body, **kwargs)


class Badge(VGroup):
    """A small pill-shaped tag, e.g. Badge("O(n log n)") or Badge("1914", color=theme.secondary)."""

    def __init__(self, text: str, color=None, size="small", **kwargs):
        theme = get_theme()
        c = color or theme.primary
        label = Label(text, size=size, color=c, bold=True)
        h = label.get_height() + 0.3
        pill = RoundedRectangle(width=label.get_width() + 0.5, height=h, corner_radius=h / 2,
                                fill_color=c, fill_opacity=0.16, stroke_color=c, stroke_width=2)
        pill.move_to(label)
        if theme.name == "bubble":
            pill.set_fill(theme.pill, 1).set_stroke(width=0)
            label.set_color(theme.accent if color is None else theme.text)
        super().__init__(pill, label, **kwargs)


class StatPill(Badge):
    """Figma-style counter: muted label and pink value on an opaque blush pill.

    Example: counter = StatPill("Pass", 0); self.play(counter.set_value(1))
    """

    def __init__(self, label: str, value, size=24, **kwargs):
        theme = get_theme()
        self.label_text, self.value, self.size = label, value, size
        words = Label(label, size=size, color=theme.muted)
        number = Label(str(value), size=size, color=theme.accent)
        content = VGroup(words, number).arrange(RIGHT, buff=.08)
        h = content.get_height() + .3
        pill = RoundedRectangle(width=content.get_width() + .34, height=h,
                                corner_radius=h / 2, fill_color=theme.pill,
                                fill_opacity=1, stroke_width=0).move_to(content)
        VGroup.__init__(self, pill, content, **kwargs)

    def set_value(self, value) -> Animation:
        new = StatPill(self.label_text, value, self.size)
        new.set_height(self.get_height()).move_to(self)
        self.value = value
        return Transform(self, new)


class QuoteCard(VGroup):
    """
    A quotation with attribution on a raised panel, styled for primary sources in history
    or literature.

    Example: QuoteCard("I came, I saw, I conquered.", "Julius Caesar", "47 BC")
    """

    def __init__(self, quote: str, author: str, date: str | None = None,
                 width: float = 9.0, **kwargs):
        theme = get_theme()
        mark = Text("“", font=theme.serif_font, font_size=140, weight=theme.text_weight,
                    fill_color=theme.accent)
        body = Text(_wrap(quote, 40), font=theme.serif_font, font_size=38,
                    weight=theme.text_weight,
                    slant="NORMAL" if theme.name == "bubble" else "ITALIC",
                    fill_color=theme.text, alignment="LEFT")
        if body.get_width() > width:
            body.set_width(width)
        attribution = Label("— " + author + (f", {date}" if date else ""), size="small",
                            color=theme.muted)
        attribution.next_to(body, DOWN, buff=0.4, aligned_edge=RIGHT)
        mark.set_height(0.6).next_to(body, LEFT, buff=0.35, aligned_edge=UP)
        content = VGroup(mark, body, attribution)
        self.panel = Panel(content.get_width() + 1.0, content.get_height() + 0.9,
                           color=theme.outline, tint=0.0, corner_radius=0.22)
        self.panel.move_to(content)
        super().__init__(self.panel, content, **kwargs)
        self.quote, self.attribution = body, attribution


class Callout(VGroup):
    """
    A label on a small pill with an arrow pointing at `target` (a mobject or point).
    `direction` is where the label sits relative to the target.

    Example: Callout(nucleus, "Nucleus: holds the DNA", direction=UR)
    """

    def __init__(self, target, text: str, direction=UR, distance: float = 1.5,
                 color=None, size="small", **kwargs):
        theme = get_theme()
        c = color or theme.accent
        point = target.get_center() if isinstance(target, Mobject) else np.array(target, dtype=float)
        d = np.array(direction, dtype=float)
        d = d / (np.linalg.norm(d) or 1)
        edge = target.get_boundary_point(d) if isinstance(target, Mobject) else point
        text_mob = Label(text, size=size, color=c, bold=True)
        h = text_mob.get_height() + 0.28
        pill = RoundedRectangle(width=text_mob.get_width() + 0.45, height=h, corner_radius=h / 2,
                                fill_color=theme.surface, fill_opacity=1, stroke_color=c,
                                stroke_width=2)
        self.label = VGroup(pill, text_mob.move_to(pill))
        if theme.name == "bubble":
            pill.set_stroke(width=0)
            text_mob.set_color(theme.accent)
        self.label.move_to(edge + d * distance)
        self.label.shift(d * self.label.get_width() / 2 * abs(d[0]) * 0.5)
        start = self.label.get_boundary_point(-d)
        self.arrow = Arrow(start, edge, buff=0.1, thickness=3, fill_color=c, path_arc=-0.25)
        super().__init__(self.arrow, self.label, **kwargs)


class CodeBlock(VGroup):
    """
    Syntax-highlighted code in an editor-style window. `highlight_line(n)` returns an
    animation that moves a highlight bar to line n (1-based) for stepping through an
    algorithm; `line(n)` returns that line's glyphs.

    Example:
        code = CodeBlock("def add(a, b):\\n    return a + b", language="python")
        self.play(FadeIn(code)); self.play(code.highlight_line(2))
    """

    def __init__(self, code: str, language: str = "python", font_size: int = 24,
                 padding: float = 0.35, style: str | None = None, **kwargs):
        theme = get_theme()
        self.source_lines = code.strip("\n").split("\n")
        if theme.name == "bubble" and style is None:
            from .syntax import FigmaCodeStyle
            style = FigmaCodeStyle
        self.code = Code(code.strip("\n"), font=theme.mono_font,
                         font_size=20 if theme.name == "bubble" and font_size == 24 else font_size,
                         language=language, code_style=style or "monokai")
        bar_h = 0 if theme.name == "bubble" else 0.42
        w = self.code.get_width() + 2 * padding
        h = self.code.get_height() + 2 * padding + bar_h
        self.panel = Panel(w, h, color=theme.outline if theme.light else "#2A2F3A",
                           surface=theme.surface if theme.light else "#16181D", tint=0.0, corner_radius=0.18,
                           stroke_width=1.5)
        self.panel.move_to(self.code).shift(UP * bar_h / 2)
        top_left = self.panel.shape.get_corner(UP + LEFT)
        self.window_dots = VGroup(*(
            Dot(radius=0.065, fill_color=c).move_to(top_left + np.array([0.3 + 0.24 * i, -bar_h / 2 - 0.02, 0]))
            for i, c in enumerate(("#FF5F57", "#FEBC2E", "#28C840"))
        ))
        if theme.name == "bubble":
            self.window_dots.set_opacity(0)
        self.highlight = RoundedRectangle(
            width=w - 0.2, height=self._line_height * 1.1, corner_radius=0.06,
            fill_color=theme.accent, fill_opacity=0.2, stroke_width=0,
        )
        self.highlight.move_to(self._line_center(1)).set_opacity(0)
        super().__init__(self.panel, self.window_dots, self.highlight, self.code, **kwargs)

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
            color or get_theme().accent, opacity=0.2)
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
