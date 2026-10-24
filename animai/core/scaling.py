"""
Keeping dynamic components consistent after they are moved or resized.

Components such as a bar chart or a linked list are built at a natural size around the
origin ("design space"), then `fit()`/`show()` scale and move them into a region. When
they later add or rearrange parts (push onto a stack, insert into a list), those parts
must land in the same transformed space. A ScaleTracker rides along inside the component
as two invisible points and maps design-space coordinates to the scene.
"""
from __future__ import annotations

import numpy as np

from manimlib import Mobject, VectorizedPoint, ORIGIN, RIGHT

__all__ = ["ScaleTracker"]

_SPAN = 0.01  # Distance between the two marker points in design space


class ScaleTracker:
    def __init__(self, origin=ORIGIN):
        origin = np.array(origin, dtype=float)
        self.origin_point = VectorizedPoint(origin)
        self.unit_point = VectorizedPoint(origin + RIGHT * _SPAN)

    @property
    def mobjects(self) -> list[Mobject]:
        """Add these to the component's group so they follow its transforms."""
        return [self.origin_point, self.unit_point]

    def scale(self) -> float:
        d = self.unit_point.get_center() - self.origin_point.get_center()
        return float(np.linalg.norm(d)) / _SPAN

    def origin(self) -> np.ndarray:
        return self.origin_point.get_center()

    def to_scene(self, p) -> np.ndarray:
        """Map a design-space point to its current scene position."""
        return self.origin() + np.array(p, dtype=float) * self.scale()

    def adopt(self, mob: Mobject) -> Mobject:
        """Transform a mobject built in design space into the component's current frame."""
        mob.scale(self.scale(), about_point=ORIGIN)
        mob.shift(self.origin())
        return mob
