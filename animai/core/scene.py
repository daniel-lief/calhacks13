"""AnimaiScene: the base class for narrated educational videos."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

from manimlib import (
    Animation, FadeIn, FadeOut, GrowFromCenter, LaggedStart, Mobject, RoundedRectangle, Scene,
    Write, VGroup, UP, DOWN, IN, ORIGIN,
)
from manimlib.mobject.svg.string_mobject import StringMobject

from . import narration
from .layout import fit, region, overlaps
from .media import Badge, BulletList, Callout, Card, Label, QuoteCard, Title
from .style import Panel, enter, exit_anim, make_backdrop
from .theme import get_theme

__all__ = ["AnimaiScene", "Voiceover"]

SEGMENT_GAP = 0.35  # Breathing room after each narrated beat
BACKDROP_DEPTH = 15.0
# Shown at their designed size by default; everything else is enlarged to fill its region
_TEXT_LIKE = (StringMobject, Title, BulletList, Card, QuoteCard, Badge, Callout)


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
        self.backdrop = make_backdrop(theme)
        # Push the backdrop well behind the scene (enlarged to look the same) so the depth it
        # writes never hides the back half of 3D objects such as molecules
        f = self.frame.get_focal_distance()
        self.backdrop.scale((f + BACKDROP_DEPTH) / f, about_point=ORIGIN).shift(IN * BACKDROP_DEPTH)
        self.add(self.backdrop)
        self._segments: list[dict] = []
        self._regions: dict[str, Mobject] = {}
        self._region_panels: dict[str, Mobject] = {}
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
             run_time: float = 1.0, replace: bool = True, scale_up: bool | None = None, **kwargs):
        """
        Fit `mob` into a region and animate it in. Diagrams, charts and other visuals are
        enlarged to fill the region (text keeps its size unless scale_up=True). Whatever
        this scene previously showed in that region (or in any region it overlaps) fades
        out first when replace=True, so successive ideas don't pile up. Pass where=None to
        keep mob's current position.

        `animation` is an animation class (FadeIn, Write, ShowCreation, GrowFromCenter...)
        or a ready-made animation such as `bullets.reveal()`; the default is a soft rise-in.
        """
        framed = (self.theme.name == "bubble" and where is not None
                  and not isinstance(mob, _TEXT_LIKE) and not hasattr(mob, "panel"))
        if where is not None:
            if scale_up is None:
                scale_up = not isinstance(mob, _TEXT_LIKE) and getattr(mob, "auto_scale", True)
            if scale_up:
                fit(mob, where, buff=0.55 if framed else 0.3, scale_up=True, max_scale=1.8)
            else:
                fit(mob, where, buff=0.55 if framed else 0.15)
        outgoing = []
        if replace:
            for name, old in list(self._regions.items()):
                if self.is_on_screen(old) and (name == where or overlaps(old, mob, 0.05)):
                    outgoing.append(old)
                    panel = self._region_panels.pop(name, None)
                    if panel is not None:
                        outgoing.append(panel)
                    del self._regions[name]
        anims = [exit_anim(_frozen(m)) for m in outgoing]
        if framed and not (not replace and where in self._region_panels):
            r = region(where)
            panel = Panel(r.width - 0.12, r.height - 0.12, tint=0, corner_radius=0.23)
            panel.move_to(r.center)
            # Keep the card behind both halves of rotating 3D molecules.
            f = self.frame.get_focal_distance()
            panel.scale((f + 4) / f, about_point=ORIGIN).shift(IN * 4)
            self._region_panels[where] = panel
            anims.append(FadeIn(panel))
        if isinstance(animation, Animation):
            anims.append(animation)
        else:
            anims.append((animation or enter)(mob, **kwargs))
        self.play(*anims, run_time=run_time)
        self.add(mob)  # Register the whole group even if the animation added its parts
        if self._title is not None and self.is_on_screen(self._title):
            self.bring_to_front(self._title)  # Titles stay readable over maps and diagrams
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
                panel = self._region_panels.pop(item, None)
                if panel is not None:
                    mobs.append(panel)
                if mob is not None:
                    mobs.append(mob)
            else:
                mobs.append(item)
                for k, v in list(self._regions.items()):
                    if v is item:
                        del self._regions[k]
                        panel = self._region_panels.pop(k, None)
                        if panel is not None:
                            mobs.append(panel)
        mobs = [m for m in mobs if self.is_on_screen(m)]
        if mobs:
            self.play(*(exit_anim(_frozen(m)) for m in mobs), run_time=run_time)

    def set_title(self, text: str, run_time: float = 1.0, **kwargs) -> Mobject:
        """Show a section title at the top, sliding out the previous one if present."""
        new = Title(text, **kwargs)
        if self._title is not None and self.is_on_screen(self._title):
            self.play(FadeOut(self._title, shift=UP * 0.35), FadeIn(new, shift=UP * 0.35),
                      run_time=run_time)
        else:
            anims = [FadeIn(new.text, shift=UP * 0.25)]
            if len(new.submobjects) > 1:
                anims.append(GrowFromCenter(new.submobjects[1]))
            self.play(*anims, run_time=run_time)
        self.add(new)
        self._title = new
        return new

    def title_card(self, title: str, subtitle: str | None = None, run_time: float = 1.6):
        """Big centered title (and optional subtitle) for the opening of a video."""
        theme = get_theme()
        t = Label(title, size=96 if theme.name == "bubble" else "title", bold=True, max_width=11.5)
        bar = RoundedRectangle(width=1.6, height=0.09, corner_radius=0.045,
                               fill_color=theme.accent, fill_opacity=1, stroke_width=0)
        if theme.name == "bubble":
            bar.set_opacity(0)
        group = VGroup(t, bar)
        if subtitle:
            group.add(Label(subtitle, size="body",
                            color=theme.accent if theme.name == "bubble" else theme.muted,
                            max_width=11))
        group.arrange(DOWN, buff=0.38).move_to(region("full").center)
        anims = [Write(t), GrowFromCenter(bar)]
        anims += [FadeIn(m, shift=UP * 0.2) for m in group.submobjects[2:]]
        self.play(LaggedStart(*anims, lag_ratio=0.3), run_time=run_time)
        return group

    def fade_out_all(self, run_time: float = 1.0, **kwargs):
        """Fade out everything on screen (use between sections)."""
        mobjects = [m for m in self.mobjects if m is not self.frame and m is not self.backdrop]
        if mobjects:
            self.play(*(FadeOut(_frozen(m)) for m in mobjects), run_time=run_time, **kwargs)
        self._regions.clear()
        self._region_panels.clear()
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
