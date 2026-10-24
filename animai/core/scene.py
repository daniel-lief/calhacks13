"""AnimaiScene: the base class for narrated educational videos."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

from manimlib import (
    Animation, FadeIn, FadeOut, FadeTransform, Mobject, Scene, Write, VGroup, UP, DOWN,
)

from . import narration
from .layout import fit, region, overlaps
from .media import Label, Title
from .theme import get_theme

__all__ = ["AnimaiScene", "Voiceover"]

SEGMENT_GAP = 0.35  # Breathing room after each narrated beat


class Voiceover:
    """Handle yielded by `AnimaiScene.voiceover()`."""

    def __init__(self, scene: "AnimaiScene", text: str, duration: float):
        self.scene = scene
        self.text = text
        self.duration = duration
        self.start_time = scene.get_time()

    def get_remaining_duration(self, buff: float = 0.0) -> float:
        """Seconds of speech left in this beat (never negative)."""
        elapsed = self.scene.get_time() - self.start_time
        return max(self.duration - elapsed - buff, 0.0)


class AnimaiScene(Scene):
    """
    Base class for every Animai video. Adds narration, theme background, captions, and
    region-based placement on top of ManimGL's Scene.
    """

    def setup(self):
        super().setup()
        theme = get_theme()
        self.set_background_color(theme.background)
        self.theme = theme
        self._segments: list[dict] = []
        self._regions: dict[str, Mobject] = {}
        self._title: Mobject | None = None

    # --- Narration -------------------------------------------------------------

    @contextmanager
    def voiceover(self, text: str):
        """
        Speak `text` while the block's animations play. On exit, waits out any speech
        that remains so visuals never run ahead of the voice. Yields a Voiceover with
        `.duration` and `.get_remaining_duration()`.
        """
        text = " ".join(text.split())
        clip = narration.synthesize(text)
        index = len(self._segments)
        print(f"@@SEGMENT {index}", flush=True)

        start = self.get_time()
        if clip.path and not self.skip_animations:
            self.add_sound(clip.path)
        tracker = Voiceover(self, text, clip.duration)
        yield tracker

        remaining = tracker.get_remaining_duration()
        if remaining > 0:
            self.wait(remaining)
        self._segments.append({
            "index": index,
            "text": text,
            "start": round(start, 3),
            "speech_end": round(start + clip.duration, 3),
            "end": round(self.get_time(), 3),
        })
        self.wait(SEGMENT_GAP)

    # --- Placement -------------------------------------------------------------

    def place(self, mob: Mobject, where: str = "main", buff: float = 0.15,
              scale_up: bool = False, align=None) -> Mobject:
        """Fit `mob` into a named region without adding it to the scene."""
        kwargs = {"align": align} if align is not None else {}
        return fit(mob, where, buff=buff, scale_up=scale_up, **kwargs)

    def show(self, mob: Mobject, where: str | None = "main", animation=None,
             run_time: float = 1.0, replace: bool = True, scale_up: bool = False, **kwargs):
        """
        Fit `mob` into a region and animate it in. Whatever this scene previously showed in
        that region (or in any region it overlaps) fades out first when replace=True,
        so successive ideas don't pile up. Pass where=None to keep mob's current position.

        `animation` is an animation class (FadeIn, Write, ShowCreation, GrowFromCenter...)
        or a ready-made animation such as `bullets.reveal()`.
        """
        if where is not None:
            fit(mob, where, scale_up=scale_up)
        outgoing = []
        if replace:
            for name, old in list(self._regions.items()):
                if self.is_on_screen(old) and (name == where or overlaps(old, mob, 0.05)):
                    outgoing.append(old)
                    del self._regions[name]
        anims = [FadeOut(_frozen(m)) for m in outgoing]
        if isinstance(animation, Animation):
            anims.append(animation)
        else:
            anims.append((animation or FadeIn)(mob, **kwargs))
        self.play(*anims, run_time=run_time)
        self.add(mob)  # Register the whole group even if the animation added its parts
        self._regions[where or f"_free_{id(mob)}"] = mob
        return mob

    def is_on_screen(self, mob: Mobject) -> bool:
        on_screen = set(map(id, self.get_mobject_family_members()))
        return any(id(m) in on_screen for m in mob.get_family())

    def hide(self, *names_or_mobs, run_time: float = 0.8):
        """Fade out region contents (by region name) or specific mobjects."""
        mobs = []
        for item in names_or_mobs:
            if isinstance(item, str):
                mob = self._regions.pop(item, None)
                if mob is not None:
                    mobs.append(mob)
            else:
                mobs.append(item)
                for k, v in list(self._regions.items()):
                    if v is item:
                        del self._regions[k]
        mobs = [m for m in mobs if self.is_on_screen(m)]
        if mobs:
            self.play(*(FadeOut(_frozen(m)) for m in mobs), run_time=run_time)

    def set_title(self, text: str, run_time: float = 1.0, **kwargs) -> Mobject:
        """Show a section title at the top, transforming from the previous one if present."""
        new = Title(text, **kwargs)
        if self._title is not None and self.is_on_screen(self._title):
            self.play(FadeTransform(self._title, new), run_time=run_time)
        else:
            self.play(Write(new.text), *(FadeIn(m) for m in new.submobjects[1:]), run_time=run_time)
        self.add(new)
        self._title = new
        return new

    def title_card(self, title: str, subtitle: str | None = None, run_time: float = 1.5):
        """Big centered title (and optional subtitle) for the opening of a video."""
        theme = get_theme()
        t = Label(title, size="title", bold=True, max_width=12.5)
        group = VGroup(t)
        if subtitle:
            s = Label(subtitle, size="body", color=theme.muted, max_width=11)
            group.add(s)
        group.arrange(DOWN, buff=0.35).move_to(region("full").center)
        self.play(Write(t), *(FadeIn(m, shift=UP * 0.2) for m in group.submobjects[1:]),
                  run_time=run_time)
        return group

    def fade_out_all(self, run_time: float = 1.0, **kwargs):
        """Fade out everything on screen (use between sections)."""
        mobjects = [m for m in self.mobjects if m is not self.frame]
        if mobjects:
            self.play(*(FadeOut(_frozen(m)) for m in mobjects), run_time=run_time, **kwargs)
        self._regions.clear()
        self._title = None

    # --- Lifecycle -------------------------------------------------------------

    def tear_down(self):
        timings_path = os.environ.get("ANIMAI_TIMINGS")
        if timings_path:
            Path(timings_path).write_text(
                json.dumps({"segments": self._segments, "duration": self.get_time()}, indent=2),
                encoding="utf-8",
            )
        super().tear_down()


def _frozen(mob: Mobject) -> Mobject:
    """Stop a mobject's updaters (e.g. a growing trail) so it can be faded out cleanly."""
    for m in mob.get_family():
        m.clear_updaters()
    return mob
