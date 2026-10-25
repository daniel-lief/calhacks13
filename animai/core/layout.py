"""
Screen regions and fitting helpers, so scenes place things by intent ("left half",
"title bar") instead of hand-tuned coordinates that drift off screen or overlap.

The frame is 14.2 x 8 units centered on the origin. Regions stay inside a safe margin
and keep the bottom strip clear for captions.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from animlib import Mobject, ORIGIN, UP, DOWN, LEFT, RIGHT

__all__ = ["Region", "REGIONS", "region", "fit", "keep_in_frame", "overlaps", "resolve_overlaps"]

SAFE_X = 6.6
SAFE_TOP = 3.7
SAFE_BOTTOM = -3.1  # Below this the video player draws captions


@dataclass(frozen=True)
class Region:
    name: str
    x0: float
    x1: float
    y0: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def center(self) -> np.ndarray:
        return np.array([(self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2, 0.0])

    def point(self, direction=ORIGIN) -> np.ndarray:
        """Point on the region's boundary in `direction` (e.g. UL is the top-left corner)."""
        d = np.array(direction, dtype=float)
        return self.center + np.array([d[0] * self.width / 2, d[1] * self.height / 2, 0.0])


_MAIN_TOP = 2.6
_GAP = 0.2
_REGION_LIST = [
    Region("full", -SAFE_X, SAFE_X, SAFE_BOTTOM, SAFE_TOP),
    Region("title", -SAFE_X, SAFE_X, 2.85, SAFE_TOP),
    Region("main", -SAFE_X, SAFE_X, SAFE_BOTTOM, _MAIN_TOP),
    Region("left", -SAFE_X, -_GAP, SAFE_BOTTOM, _MAIN_TOP),
    Region("right", _GAP, SAFE_X, SAFE_BOTTOM, _MAIN_TOP),
    Region("top", -SAFE_X, SAFE_X, (SAFE_BOTTOM + _MAIN_TOP) / 2 + _GAP, _MAIN_TOP),
    Region("bottom", -SAFE_X, SAFE_X, SAFE_BOTTOM, (SAFE_BOTTOM + _MAIN_TOP) / 2 - _GAP),
    Region("stage", -SAFE_X, 2.0, SAFE_BOTTOM, _MAIN_TOP),      # Left two-thirds
    Region("sidebar", 2.4, SAFE_X, SAFE_BOTTOM, _MAIN_TOP),     # Right third
    Region("top_left", -SAFE_X, -_GAP, (SAFE_BOTTOM + _MAIN_TOP) / 2 + _GAP, _MAIN_TOP),
    Region("top_right", _GAP, SAFE_X, (SAFE_BOTTOM + _MAIN_TOP) / 2 + _GAP, _MAIN_TOP),
    Region("bottom_left", -SAFE_X, -_GAP, SAFE_BOTTOM, (SAFE_BOTTOM + _MAIN_TOP) / 2 - _GAP),
    Region("bottom_right", _GAP, SAFE_X, SAFE_BOTTOM, (SAFE_BOTTOM + _MAIN_TOP) / 2 - _GAP),
]
REGIONS: dict[str, Region] = {r.name: r for r in _REGION_LIST}


def region(name: str | Region) -> Region:
    if isinstance(name, Region):
        return name
    try:
        return REGIONS[name]
    except KeyError:
        raise ValueError(f"Unknown region {name!r}; choose from {', '.join(REGIONS)}") from None


def fit(mob: Mobject, where: str | Region = "main", buff: float = 0.15,
        scale_up: bool = False, max_scale: float = 1.6, align=ORIGIN) -> Mobject:
    """
    Scale `mob` down (or up, with scale_up=True) to fit inside a region and move it there.
    `align` pins it to a side of the region, e.g. align=UP puts it at the region's top.
    """
    r = region(where)
    avail_w, avail_h = r.width - 2 * buff, r.height - 2 * buff
    w, h = max(mob.get_width(), 1e-6), max(mob.get_height(), 1e-6)
    factor = min(avail_w / w, avail_h / h)
    if factor < 1 or scale_up:
        mob.scale(min(factor, max_scale))
    a = np.array(align, dtype=float)
    target = r.center + np.array([a[0] * (avail_w - mob.get_width()) / 2,
                                  a[1] * (avail_h - mob.get_height()) / 2, 0.0])
    mob.move_to(target)
    return mob


def keep_in_frame(mob: Mobject, buff: float = 0.0) -> Mobject:
    """Shrink and shift `mob` just enough that it lies inside the safe area."""
    full = REGIONS["full"]
    w, h = full.width - 2 * buff, full.height - 2 * buff
    if mob.get_width() > w or mob.get_height() > h:
        mob.scale(min(w / mob.get_width(), h / mob.get_height()))
    shift = np.zeros(3)
    if mob.get_left()[0] < full.x0 + buff:
        shift[0] = full.x0 + buff - mob.get_left()[0]
    elif mob.get_right()[0] > full.x1 - buff:
        shift[0] = full.x1 - buff - mob.get_right()[0]
    if mob.get_bottom()[1] < full.y0 + buff:
        shift[1] = full.y0 + buff - mob.get_bottom()[1]
    elif mob.get_top()[1] > full.y1 - buff:
        shift[1] = full.y1 - buff - mob.get_top()[1]
    mob.shift(shift)
    return mob


def _box(mob: Mobject, buff: float):
    (x0, y0, _), (x1, y1, _) = mob.get_corner(DOWN + LEFT), mob.get_corner(UP + RIGHT)
    return x0 - buff, y0 - buff, x1 + buff, y1 + buff


def overlaps(a: Mobject, b: Mobject, buff: float = 0.0) -> bool:
    ax0, ay0, ax1, ay1 = _box(a, buff / 2)
    bx0, by0, bx1, by1 = _box(b, buff / 2)
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def resolve_overlaps(*mobs: Mobject, fixed: tuple[Mobject, ...] = (), buff: float = 0.1,
                     max_iterations: int = 60) -> None:
    """
    Nudge `mobs` (typically labels) apart until no two overlap each other or any of the
    `fixed` mobjects, moving along whichever axis needs the smaller push.
    """
    movable = list(mobs)
    for _ in range(max_iterations):
        moved = False
        for i, a in enumerate(movable):
            for b in movable[i + 1:] + list(fixed):
                if a is b or not overlaps(a, b, buff):
                    continue
                ax0, ay0, ax1, ay1 = _box(a, buff / 2)
                bx0, by0, bx1, by1 = _box(b, buff / 2)
                push_x = min(bx1 - ax0, ax1 - bx0)
                push_y = min(by1 - ay0, ay1 - by0)
                ca, cb = a.get_center(), b.get_center()
                if push_x < push_y:
                    sign = 1 if ca[0] >= cb[0] else -1
                    vec = RIGHT * sign * push_x
                else:
                    sign = 1 if ca[1] >= cb[1] else -1
                    vec = UP * sign * push_y
                if b in fixed:
                    a.shift(vec)
                else:
                    a.shift(vec / 2)
                    b.shift(-vec / 2)
                moved = True
        for m in movable:
            keep_in_frame(m)
        if not moved:
            return
