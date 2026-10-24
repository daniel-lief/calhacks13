from animai import *


class SuccessionCheck(AnimaiScene):
    """Second step's square must stay hidden until its step starts (no early flash)."""

    def construct(self):
        a = Circle(radius=1, fill_opacity=0.8, color=BLUE).shift(LEFT * 3)
        b = Square(side_length=2, fill_opacity=0.8, color=RED).shift(RIGHT * 3)
        existing = Triangle(color=GREEN, fill_opacity=0.8).shift(DOWN * 2.5)
        self.add(existing)
        self.play(Succession(FadeIn(a), FadeIn(b), existing.animate.shift(UP * 2.5)), run_time=3)
        self.wait()
