"""Render-time regression checks for fonts, animated bounds and card lifecycle."""
from animai import *

THEME = "bubble"


class BubbleStyleCheck(AnimaiScene):
    def construct(self):
        assert Label("Fredoka").font == "Fredoka"
        assert Label("Fredoka").weight == "SEMIBOLD"
        assert CodeBlock("return True").code.font == "JetBrains Mono"

        number = BinaryNumber(5)
        self.show(number, "main", run_time=.05)
        old_panel = self._region_panels["main"]
        self.play(number.set_value(255), run_time=.05)
        assert number.decimal.get_right()[0] < region("main").x1 - .2
        self.hide(number, run_time=.05)
        assert not self.is_on_screen(old_panel)
        assert not self._region_panels

        array = ArrayViz([3, 1, 2])
        self.show(array, "left", run_time=.05)
        old_panel = self._region_panels["left"]
        self.play(array.swap(0, 1), run_time=.05)
        assert array.values == [1, 3, 2]
        self.show(Node("Same card"), "left", replace=False, run_time=.05)
        assert self._region_panels["left"] is old_panel
        self.show(StackViz([1, 2]), "left", run_time=.05)
        assert not self.is_on_screen(old_panel)
        self.fade_out_all(.05)
        assert not self._region_panels
        assert self.is_on_screen(self.backdrop)

        counter = StatPill("Pass", 0).scale(.7)
        original_height = counter.get_height()
        self.show(counter, "right", run_time=.05)
        self.play(counter.set_value(123), run_time=.05)
        assert abs(counter.get_height() - original_height) < 1e-5
        assert counter.value == 123
        self.fade_out_all(.05)
        self.set_title("Style checks passed", run_time=.05)
        self.show(Card(Label("Fonts, animation, bounds and cleanup", size=28)), "main", run_time=.05)
