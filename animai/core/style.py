"""
Shared visual language: panels with soft shadows, theme backdrops, and motion defaults.
Components build their boxes from `Panel` so cards, nodes and cells all look related.
"""
from __future__ import annotations

import numpy as np

from manimlib import (
    Animation, Circle, FadeIn, FadeOut, Line, Mobject, Rectangle, RoundedRectangle, VGroup,
    VMobject, UP, DOWN, RIGHT, FRAME_WIDTH, FRAME_HEIGHT,
)

from .theme import get_theme

__all__ = ["Panel", "soft_shadow", "make_backdrop", "enter", "exit_anim", "rounded_bar"]

SHADOW_OFFSET = np.array([0.05, -0.08, 0.0])


def rounded_bar(width: float, height: float, radius: float = .13) -> VMobject:
    """THE IMAGE's chart silhouette: rounded top corners and a square baseline."""
    w, h = width / 2, height / 2
    r = min(radius, w, height)
    k = .5522847498307936
    p = lambda x, y: np.array([x, y, 0.0])
    bar = VMobject()
    bar.start_new_path(p(-w, -h)).add_line_to(p(w, -h)).add_line_to(p(w, h-r))
    bar.add_cubic_bezier_curve_to(p(w, h-r+k*r), p(w-r+k*r, h), p(w-r, h))
    bar.add_line_to(p(-w+r, h))
    bar.add_cubic_bezier_curve_to(p(-w+r-k*r, h), p(-w, h-r+k*r), p(-w, h-r))
    return bar.add_line_to(p(-w, -h)).close_path()


def soft_shadow(shape: Mobject, offset=SHADOW_OFFSET, strength: float = 1.0) -> VGroup:
    """A two-layer drop shadow shaped like `shape` (draw it behind the shape)."""
    theme = get_theme()
    layers = VGroup()
    if theme.visual_style == "bubble":
        # Figma: x=0, y=0, blur=7.9px, spread=0, black 7%.
        # Vector feather approximation; reference pixels are mapped to scene units.
        blur = 7.9 * FRAME_WIDTH / 1576
        for i in range(8, 0, -1):
            layer = shape.copy().set_stroke(width=0)
            layer.set_fill(theme.shadow, opacity=theme.shadow_opacity * strength / 8)
            layer.set_width(shape.get_width() + 2 * blur * i / 8, stretch=True)
            layer.set_height(shape.get_height() + 2 * blur * i / 8, stretch=True)
            layers.add(layer)
        return layers
    for scale, opacity in ((1.04, 0.35), (1.0, 0.65)):
        layer = shape.copy()
        layer.set_stroke(width=0)
        layer.set_fill(theme.shadow, opacity=theme.shadow_opacity * opacity * strength)
        layer.scale(scale).shift(offset)
        layers.add(layer)
    return layers


class Panel(VGroup):
    """
    A rounded box with an opaque surface, a translucent color tint, a colored border and a
    soft shadow. `panel.shape` is the bordered box (use it for boundary points),
    `panel.tint` the color layer.
    """

    def __init__(self, width: float, height: float, color=None, corner_radius: float = 0.18,
                 tint: float = 0.16, stroke_width: float = 2.5, shadow: bool = True,
                 surface=None, **kwargs):
        theme = get_theme()
        c = color or theme.outline
        if theme.visual_style == "bubble":
            stroke_width = 0
            corner_radius = max(corner_radius, 25 * FRAME_WIDTH / 1576)
            if color is None or color == theme.outline:
                tint = 0
        r = min(corner_radius, width / 2, height / 2)
        self.color = c
        self.shape = RoundedRectangle(width=width, height=height, corner_radius=r,
                                      fill_color=surface or theme.surface, fill_opacity=1,
                                      stroke_color=c, stroke_width=stroke_width)
        self.tint = RoundedRectangle(width=width, height=height, corner_radius=r,
                                     fill_color=c, fill_opacity=tint, stroke_width=0)
        parts = [self.tint]
        if shadow:
            self.shadow = soft_shadow(self.shape)
            parts.insert(0, self.shadow)
        super().__init__(*parts[:-1], self.shape, parts[-1], **kwargs)


def make_backdrop(theme=None) -> VGroup:
    """Full-frame background texture for the theme: a soft radial vignette or a fine grid."""
    theme = theme or get_theme()
    group = VGroup()
    if theme.backdrop == "peach":
        from manimlib.utils.color import interpolate_color
        # Opaque overlapping strips keep the gradient stable in the WebGPU renderer.
        n = 192
        for i in range(n):
            strip = Rectangle(width=FRAME_WIDTH + 0.04, height=FRAME_HEIGHT / n + 0.004,
                              fill_color=interpolate_color(theme.background, theme.backdrop_color,
                                                           (i + 0.5) / n),
                              fill_opacity=1, stroke_width=0)
            strip.move_to(UP * (FRAME_HEIGHT / 2 - (i + 0.5) * FRAME_HEIGHT / n))
            group.add(strip)
        # Sparse corner confetti extends THE IMAGE without crowding the teaching area.
        d = theme.decorative
        for x, y, radius, color in (
            (-5.65, 3.45, .28, d[0]), (-6.45, 2.65, .17, d[1]),
            (-4.70, 2.95, .23, d[2]), (-6.25, 3.20, .13, d[0]),
            (5.95, 3.35, .28, d[3]), (4.75, 3.00, .20, d[2]),
            (6.35, 2.65, .15, d[0]),
        ):
            group.add(Circle(radius=radius, fill_color=color, fill_opacity=1,
                             stroke_width=0).move_to(RIGHT * x + UP * y))
    elif theme.backdrop == "vignette":
        # Concentric translucent discs approximate a radial gradient toward the center
        n = 14
        for i in range(n):
            r = FRAME_WIDTH * 0.62 * (1 - i / n)
            disc = Circle(radius=r, fill_color=theme.backdrop_color,
                          fill_opacity=0.11, stroke_width=0)
            disc.stretch(0.72, 1)
            group.add(disc)
    elif theme.backdrop == "grid":
        minor, major = 0.5, 2.0
        for x in np.arange(-8, 8.01, minor):
            w = 1.6 if abs(x / major - round(x / major)) < 1e-6 else 0.8
            group.add(Line(UP * 4.5 + RIGHT * x, DOWN * 4.5 + RIGHT * x,
                           stroke_color=theme.backdrop_color, stroke_width=w))
        for y in np.arange(-4.5, 4.51, minor):
            w = 1.6 if abs(y / major - round(y / major)) < 1e-6 else 0.8
            group.add(Line(RIGHT * 8 + UP * y, -RIGHT * 8 + UP * y,
                           stroke_color=theme.backdrop_color, stroke_width=w))
    return group


def enter(mob: Mobject, **kwargs) -> Animation:
    """Default entrance: fade in while rising slightly."""
    kwargs.setdefault("shift", UP * 0.25)
    kwargs.setdefault("scale", 0.97)
    return FadeIn(mob, **kwargs)


def exit_anim(mob: Mobject, **kwargs) -> Animation:
    """Default exit: fade out while drifting slightly."""
    kwargs.setdefault("shift", UP * 0.2)
    return FadeOut(mob, **kwargs)
