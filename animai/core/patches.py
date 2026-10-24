"""Small fixes to ManimGL behavior that would otherwise trip up generated scenes."""
from __future__ import annotations

import functools
import re

from manimlib import Tex, TexText, VMobject
from manimlib.mobject.svg.string_mobject import StringMobject

_applied = False


def _honor_color_kwarg(init):
    # ManimGL documents `color=` as overriding fill and stroke color, but classes which
    # pass explicit defaults (Dot, Circle, Arrow, Text, Tex...) silently ignore it.
    @functools.wraps(init)
    def wrapper(self, *args, **kwargs):
        color = kwargs.get("color")
        if color is not None:
            kwargs["fill_color"] = color
            if not isinstance(self, StringMobject):
                kwargs["stroke_color"] = color
        init(self, *args, **kwargs)
    return wrapper


# ManimGL's Tex parser mangles the spacing commands \; \: \! when braces follow them
# ("Argument of \text@ has an extra }"). Rewrite them to equivalent \mskip forms.
_TEX_SPACING = {"\\;": "\\mskip\\thickmuskip ", "\\:": "\\mskip\\medmuskip ",
                "\\!": "\\mskip-\\thinmuskip "}
_TEX_SPACING_RE = re.compile(r"(?<!\\)\\[;:!]")


def fix_tex_spacing(s):
    return _TEX_SPACING_RE.sub(lambda m: _TEX_SPACING[m.group()], s) if isinstance(s, str) else s


def _patch_tex_init(init):
    @functools.wraps(init)
    def wrapper(self, *tex_strings, **kwargs):
        if isinstance(self, TexText):  # Text mode: \mskip is math-only
            return init(self, *tex_strings, **kwargs)
        for key in ("t2c", "tex_to_color_map"):
            if isinstance(kwargs.get(key), dict):
                kwargs[key] = {fix_tex_spacing(k): v for k, v in kwargs[key].items()}
        init(self, *map(fix_tex_spacing, tex_strings), **kwargs)
    return wrapper


def apply_patches() -> None:
    global _applied
    if _applied:
        return
    _applied = True
    VMobject.__init__ = _honor_color_kwarg(VMobject.__init__)
    StringMobject.__init__ = _honor_color_kwarg(StringMobject.__init__)
    Tex.__init__ = _patch_tex_init(Tex.__init__)
