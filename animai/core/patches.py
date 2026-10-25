"""Small fixes to ManimGL behavior that would otherwise trip up generated scenes."""
from __future__ import annotations

import functools
import re

from animlib import AnimationGroup, Scene, Succession, Tex, TexText, VMobject
from animlib.mobject.svg.string_mobject import StringMobject

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


# How the engine puts animated objects on screen, and why Animai changes it:
#
# 1. For grouped animations (AnimationGroup, LaggedStart, Succession) the engine adds the
#    animation's temporary Group to the scene. Scene.add first removes that Group's members
#    from the scene, which splits apart any component (a linked list, a chart) whose parts
#    are being animated, so parts added to that component later never appear.
# 2. Succession only begins its first step, yet its whole Group goes on screen at once, so
#    objects introduced by later steps flash on screen fully drawn until their step begins.
#
# Instead, Animai adds only the individual objects each animation introduces (never the
# temporary Group), and a Succession adds a step's objects when that step starts.

def _drawn_on_screen(mob, on_screen) -> bool:
    if id(mob) in on_screen:
        return True
    drawn = [m for m in mob.get_family() if m.has_points()]
    return bool(drawn) and all(id(m) in on_screen for m in drawn)


def _entering_mobjects(anim, on_screen: set) -> list:
    """Objects `anim` (as it starts) introduces that aren't on screen yet."""
    if isinstance(anim, Succession):
        return _entering_mobjects(anim.animations[0], on_screen) if anim.animations else []
    if isinstance(anim, AnimationGroup):
        out = []
        for sub in anim.animations:
            for mob in _entering_mobjects(sub, on_screen):
                out.append(mob)
                on_screen.update(id(m) for m in mob.get_family())
        return out
    return [] if _drawn_on_screen(anim.mobject, on_screen) else [anim.mobject]


def _attach_scene(anim, scene) -> None:
    if isinstance(anim, AnimationGroup):
        if isinstance(anim, Succession):
            anim._scene = scene
        for sub in anim.animations:
            _attach_scene(sub, scene)


def _add_entering(scene, anim) -> None:
    on_screen = {id(m) for m in scene.get_mobject_family_members()}
    for mob in _entering_mobjects(anim, on_screen):
        scene.add(mob)


def _begin_animations(self, animations) -> None:
    for animation in animations:
        _attach_scene(animation, self)
        animation.begin()
        _add_entering(self, animation)


def _patched_succession_interpolate(interpolate):
    @functools.wraps(interpolate)
    def wrapper(self, alpha):
        before = self.active_animation
        interpolate(self, alpha)
        scene = getattr(self, "_scene", None)
        if scene is not None and self.active_animation is not before:
            _add_entering(scene, self.active_animation)
    return wrapper


def _patched_succession_finish(finish):
    @functools.wraps(finish)
    def wrapper(self):
        finish(self)
        scene = getattr(self, "_scene", None)
        if scene is not None:  # Steps never reached (e.g. when skipping) end in their final state
            index = self.animations.index(self.active_animation)
            for anim in self.animations[index + 1:]:
                _add_entering(scene, anim)
    return wrapper


def apply_patches() -> None:
    global _applied
    if _applied:
        return
    _applied = True
    VMobject.__init__ = _honor_color_kwarg(VMobject.__init__)
    StringMobject.__init__ = _honor_color_kwarg(StringMobject.__init__)
    Tex.__init__ = _patch_tex_init(Tex.__init__)
    Succession.interpolate = _patched_succession_interpolate(Succession.interpolate)
    Succession.finish = _patched_succession_finish(Succession.finish)
    Scene.begin_animations = _begin_animations
