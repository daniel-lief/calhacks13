from __future__ import annotations

from animlib.constants import BLACK
from animlib.logger import log
from animlib.mobject.numbers import Integer
from animlib.mobject.types.vectorized_mobject import VGroup

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from animlib.mobject.mobject import Mobject


def print_family(mobject: Mobject, n_tabs: int = 0) -> None:
    """For debugging purposes"""
    log.debug("\t" * n_tabs + str(mobject) + " " + str(id(mobject)))
    for submob in mobject.submobjects:
        print_family(submob, n_tabs + 1)


def index_labels(
    mobject: Mobject, 
    label_height: float = 0.15
) -> VGroup:
    labels = VGroup()
    for n, submob in enumerate(mobject):
        label = Integer(n)
        label.set_height(label_height)
        label.move_to(submob)
        label.set_backstroke(BLACK, 5)
        labels.add(label)
    return labels
