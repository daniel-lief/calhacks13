"""
Charts for data-driven explanations: economics, demographics, history, science results.
Values are real numbers you pass in; layout, labels and animation are handled here.
"""
from __future__ import annotations

import numpy as np

from manimlib import (
    Animation, AnimationGroup, AnnularSector, Axes, Dot, FadeIn, GrowFromEdge, LaggedStart,
    Line, Mobject, Rectangle, ShowCreation, Succession, Transform, UpdateFromAlphaFunc,
    RoundedRectangle, VGroup, VMobject, VectorizedPoint, Write, UP, DOWN, LEFT, RIGHT, DR, ORIGIN,
    TAU, PI,
)

from animai.core.media import Label
from animai.core.scaling import ScaleTracker
from animai.core.style import rounded_bar
from animai.core.theme import get_theme, palette_color

__all__ = ["BarPlot", "LinePlot", "PieChart", "format_number"]


def format_number(v: float, unit: str = "") -> str:
    """Readable number: 1234567 -> '1.2M', 0.256 -> '0.26', 42 -> '42'."""
    a = abs(v)
    if a >= 1e9:
        s = f"{v / 1e9:.1f}B"
    elif a >= 1e6:
        s = f"{v / 1e6:.1f}M"
    elif a >= 1e4:
        s = f"{v / 1e3:.0f}k"
    elif float(v).is_integer():
        s = f"{int(v):,}"
    elif a >= 10:
        s = f"{v:.1f}"
    else:
        s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s.replace(".0B", "B").replace(".0M", "M") + unit


class BarPlot(VGroup):
    """
    Bar chart with category labels and value labels. horizontal=True gives a ranking
    chart. `plot.grow()` animates bars rising from zero; `plot.animate_values(new_values,
    sort=True)` morphs to new data (bar-chart race when horizontal and sorted);
    `plot.highlight(i)` emphasizes one bar. `plot.bars[i]`, `plot.value_labels[i]`.

    Example:
        plot = BarPlot([3.2, 5.1, 1.4], ["Coal", "Gas", "Solar"], unit=" TW")
        self.show(plot, "main", animation=plot.grow())
        self.play(plot.animate_values([2.1, 5.6, 3.9]))
    """

    def __init__(self, values, labels=None, max_value: float | None = None, colors=None,
                 width: float = 9.0, height: float = 4.5, horizontal: bool = False,
                 unit: str = "", show_values: bool = True, size="small", **kwargs):
        theme = get_theme()
        self.values = [float(v) for v in values]
        self.labels_text = list(labels) if labels else [""] * len(self.values)
        self.colors = list(colors) if colors else [palette_color(i) for i in range(len(self.values))]
        self.fixed_max = max_value
        self.max_value = max_value or max(max(self.values), 1e-9) * 1.1
        self.horizontal, self.unit, self.size = horizontal, unit, size
        self.width, self.height = width, height
        n = len(self.values)
        self.slot = (height if horizontal else width) / n
        self.bar_thickness = self.slot * 0.68
        self.tracker = ScaleTracker()  # Design space: baseline starts at the origin

        self.baseline = (Line(ORIGIN, UP * height) if horizontal else Line(ORIGIN, RIGHT * width))
        self.baseline.set_stroke(theme.baseline if theme.name == "bubble" else theme.muted, 3)
        self.grid = self._grid()
        self.bars = VGroup(*(self._bar(i, v, i) for i, v in enumerate(self.values)))
        self.category_labels = VGroup(*(self._category_label(i, i) for i in range(n)))
        self.value_labels = VGroup(*(self._value_label(i, v, i) for i, v in enumerate(self.values)))
        if not show_values:
            self.value_labels.set_opacity(0)
        super().__init__(self.grid, self.baseline, self.bars, self.category_labels,
                         self.value_labels, *self.tracker.mobjects, **kwargs)
        self.center()

    # Bars and labels are built in design space and mapped through the tracker, so
    # updates stay aligned after the plot has been moved or resized
    def _origin(self):
        return ORIGIN

    def _length(self, v):
        span = self.width if self.horizontal else self.height
        return max(v / self.max_value * span, 0.001)

    def _slot_center(self, slot):
        if self.horizontal:  # Slot 0 at the top
            return self._origin() + UP * (self.height - (slot + 0.5) * self.slot)
        return self._origin() + RIGHT * (slot + 0.5) * self.slot

    def _grid(self):
        """Faint gridlines with value ticks, in design space."""
        theme = get_theme()
        grid = VGroup()
        step = _nice_step(self.max_value, 5)
        span = self.width if self.horizontal else self.height
        for v in np.arange(step, self.max_value + 1e-9, step):
            d = v / self.max_value * span
            if self.horizontal:
                line = Line(RIGHT * d, RIGHT * d + UP * self.height)
                tick = Label(format_number(v), size="tiny", color=theme.muted).next_to(line, DOWN, buff=0.12)
            else:
                line = Line(UP * d, UP * d + RIGHT * self.width)
                tick = Label(format_number(v), size="tiny", color=theme.muted).next_to(line, LEFT, buff=0.15)
            line.set_stroke(theme.outline, 1.5, opacity=0.7)
            grid.add(VGroup(line, tick))
        return self.tracker.adopt(grid)

    def _bar(self, i, v, slot):
        length = self._length(v)
        r = min(0.13 if get_theme().name == "bubble" else 0.09, self.bar_thickness / 2, length / 2)
        if self.horizontal:
            bar = (rounded_bar(self.bar_thickness, length, r).rotate(-PI / 2)
                   if get_theme().name == "bubble" else
                   RoundedRectangle(width=length, height=self.bar_thickness, corner_radius=r))
            bar.move_to(self._slot_center(slot) + RIGHT * length / 2)
        else:
            bar = (rounded_bar(self.bar_thickness, length, r) if get_theme().name == "bubble" else
                   RoundedRectangle(width=self.bar_thickness, height=length, corner_radius=r))
            bar.move_to(self._slot_center(slot) + UP * length / 2)
        bar.set_fill(self.colors[i], 1 if get_theme().name == "bubble" else 0.92).set_stroke(self.colors[i], 0)
        return self.tracker.adopt(bar)

    def _category_label(self, i, slot):
        label = Label(self.labels_text[i], size=self.size,
                      max_width=(2.6 if self.horizontal else self.slot * 0.95))
        if self.horizontal:
            label.next_to(self._slot_center(slot), LEFT, buff=0.2)
        else:
            label.next_to(self._slot_center(slot), DOWN, buff=0.2)
        return self.tracker.adopt(label)

    def _value_label(self, i, v, slot):
        label = Label(format_number(v, self.unit), size=self.size, color=get_theme().text, bold=True)
        end = self._slot_center(slot) + (RIGHT if self.horizontal else UP) * self._length(v)
        label.next_to(end, RIGHT if self.horizontal else UP, buff=0.12)
        return self.tracker.adopt(label)

    def grow(self, lag_ratio: float = 0.12, **kwargs) -> Animation:
        edge = LEFT if self.horizontal else DOWN
        return AnimationGroup(
            FadeIn(self.grid), ShowCreation(self.baseline), FadeIn(self.category_labels),
            LaggedStart(*(GrowFromEdge(b, edge) for b in self.bars), lag_ratio=lag_ratio),
            LaggedStart(*(FadeIn(v) for v in self.value_labels), lag_ratio=lag_ratio),
            **kwargs,
        )

    def animate_values(self, new_values, sort: bool = False, **kwargs) -> Animation:
        """Morph bars and labels to `new_values` (same order as originally given)."""
        new_values = [float(v) for v in new_values]
        anims = []
        if self.fixed_max is None or max(new_values) > self.fixed_max:
            self.max_value = max(max(new_values), 1e-9) * 1.1  # Rescale like a bar-chart race
            anims.append(Transform(self.grid, self._grid()))
        order = list(range(len(new_values)))
        if sort:
            order = sorted(order, key=lambda i: -new_values[i])
        slot_of = {i: s for s, i in enumerate(order)}
        for i, v in enumerate(new_values):
            s = slot_of[i]
            anims.append(Transform(self.bars[i], self._bar(i, v, s)))
            anims.append(Transform(self.value_labels[i], self._value_label(i, v, s)))
            anims.append(self.category_labels[i].animate.move_to(self._category_label(i, s)))
        self.values = new_values
        return AnimationGroup(*anims, **kwargs)

    def highlight(self, i: int, dim_others: bool = True) -> Animation:
        anims = [self.bars[i].animate.set_fill(get_theme().accent, 1)]
        if dim_others:
            anims += [b.animate.set_fill(opacity=0.3) for j, b in enumerate(self.bars) if j != i]
        return AnimationGroup(*anims)


class LinePlot(VGroup):
    """
    Line chart of one or more series over shared x values, with axes, tick labels,
    axis titles and a legend. Any x/y ranges work (e.g. years 1900-2020).

    series: {"name": [y values]} (or a single list). `plot.lines[name]`;
    `plot.draw()` animates the lines being drawn; `plot.c2p(x, y)` converts data
    coordinates to a scene point (use it to place dots, labels, annotations);
    `plot.point(name, i)` is the i-th data point of a series.

    Example:
        years = list(range(1900, 2021, 10))
        plot = LinePlot(years, {"World": [1.6, 1.8, 1.9, 2.1, 2.3, 2.5, 3.0, 3.7, 4.4, 5.3, 6.1, 6.9, 7.8]},
                        x_label="Year", y_label="Population (billions)")
        self.show(plot, "main", animation=plot.draw())
        self.play(FadeIn(Dot(plot.c2p(1960, 3.0), fill_color=get_theme().accent)))
    """

    def __init__(self, x_values, series, x_label: str = "", y_label: str = "",
                 y_range: tuple | None = None, colors=None, width: float = 10.0,
                 height: float = 5.0, legend: bool = True, smooth: bool = False,
                 size="small", **kwargs):
        theme = get_theme()
        if not isinstance(series, dict):
            series = {"": list(series)}
        xs = np.array(x_values, dtype=float)
        all_y = np.concatenate([np.array(v, dtype=float) for v in series.values()])
        x_step = _nice_step(xs.max() - xs.min())
        if y_range is None:
            lo, hi = min(0.0, float(all_y.min())), float(all_y.max())
            y_step = _nice_step(hi - lo)
            y_range = (np.floor(lo / y_step) * y_step, np.ceil(hi * 1.05 / y_step) * y_step, y_step)
        y_lo, y_hi, y_step = (list(y_range) + [_nice_step(y_range[1] - y_range[0])])[:3]
        # ManimGL draws axes through coordinate 0, so build them on offset data
        self.x0, self.y0 = float(xs.min()), float(y_lo)
        self.axes = Axes(x_range=(0, xs.max() - self.x0, x_step), y_range=(0, y_hi - y_lo, y_step),
                         width=width, height=height,
                         axis_config={"stroke_color": theme.muted, "stroke_width": 2,
                                      "include_tip": False, "include_ticks": True})
        ticks = VGroup()
        first_x = np.ceil(self.x0 / x_step) * x_step
        for x in np.arange(first_x, xs.max() + 1e-9, x_step):
            t = Label(_fmt_tick(x), size="tiny", color=theme.muted)
            t.next_to(self.c2p(x, y_lo), DOWN, buff=0.15)
            ticks.add(t)
        self.grid = VGroup()
        for y in np.arange(y_lo, y_hi + 1e-9, y_step):
            t = Label(format_number(y), size="tiny", color=theme.muted)
            t.next_to(self.c2p(self.x0, y), LEFT, buff=0.15)
            ticks.add(t)
            if y > y_lo:
                self.grid.add(Line(self.c2p(self.x0, y), self.c2p(xs.max(), y),
                                   stroke_color=theme.outline, stroke_width=1.5, stroke_opacity=0.7))
        self.tick_labels = ticks
        parts = [self.grid, self.axes, ticks]
        if x_label:
            self.x_label = Label(x_label, size=size, color=theme.muted)
            self.x_label.next_to(ticks, DOWN, buff=0.25).match_x(self.axes.x_axis)
            parts.append(self.x_label)
        if y_label:
            self.y_label = Label(y_label, size=size, color=theme.muted)
            self.y_label.rotate(PI / 2)
            self.y_label.next_to(ticks, LEFT, buff=0.25).match_y(self.axes.y_axis)
            parts.append(self.y_label)
        self.lines, self._data = {}, {}
        for i, (name, ys) in enumerate(series.items()):
            color = colors[i] if colors else palette_color(i)
            pts = [self.c2p(x, y) for x, y in zip(xs, ys)]
            line = VMobject(stroke_color=color, stroke_width=5.5)
            if smooth:
                line.set_points_smoothly(pts)
            else:
                line.set_points_as_corners(pts)
            self.lines[name] = line
            self._data[name] = (xs, np.array(ys, dtype=float))
        parts += list(self.lines.values())
        self.end_markers = VGroup()
        for name, line in self.lines.items():
            color = line.get_stroke_color()
            marker = VGroup(Dot(line.get_end(), radius=0.13, fill_color=color, fill_opacity=0.3),
                            Dot(line.get_end(), radius=0.07, fill_color=color))
            self.end_markers.add(marker)
        parts.append(self.end_markers)
        self.legend = VGroup()
        if legend and any(name for name in self.lines):
            for name, line in self.lines.items():
                swatch = Line(LEFT * 0.2, RIGHT * 0.2, stroke_color=line.get_stroke_color(), stroke_width=5)
                self.legend.add(VGroup(swatch, Label(name, size="tiny")).arrange(RIGHT, buff=0.15))
            self.legend.arrange(DOWN, aligned_edge=LEFT, buff=0.12)
            self.legend.next_to(self.c2p(self.x0, y_hi), DR, buff=0.2)
            parts.append(self.legend)
        super().__init__(*parts, **kwargs)

    def c2p(self, x: float, y: float) -> np.ndarray:
        """Scene point for data coordinates (x, y)."""
        return self.axes.c2p(x - self.x0, y - self.y0)

    def point(self, name: str, i: int) -> np.ndarray:
        xs, ys = self._data[name]
        return self.c2p(xs[i], ys[i])

    def draw(self, run_time: float = 3.0, **kwargs) -> Animation:
        intro = [ShowCreation(self.axes), FadeIn(self.tick_labels), FadeIn(self.grid)]
        for attr in ("x_label", "y_label"):
            if hasattr(self, attr):
                intro.append(FadeIn(getattr(self, attr)))
        return Succession(
            AnimationGroup(*intro, run_time=1.2),
            AnimationGroup(*(ShowCreation(l, rate_func=lambda t: t) for l in self.lines.values()),
                           FadeIn(self.legend), run_time=run_time),
            FadeIn(self.end_markers, scale=0.5, run_time=0.4),
            **kwargs,
        )


def _nice_step(span: float, target_ticks: int = 6) -> float:
    if span <= 0:
        return 1.0
    raw = span / target_ticks
    mag = 10 ** np.floor(np.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return float(m * mag)
    return float(10 * mag)


def _fmt_tick(x: float) -> str:
    return str(int(round(x))) if abs(x - round(x)) < 1e-9 else f"{x:g}"


class PieChart(VGroup):
    """
    Pie (or donut, with donut=True) chart with labels showing name and percentage.
    `pie.build()` sweeps the slices in; `pie.explode(i)` pulls one slice out;
    `pie.sectors[i]`, `pie.slice_labels[i]`.

    Example: PieChart([36, 23, 22, 10, 9], ["Coal", "Gas", "Renewables", "Nuclear", "Oil"])
    """

    def __init__(self, values, labels, colors=None, radius: float = 2.2, donut: bool = False,
                 show_percent: bool = True, size="small", **kwargs):
        total = float(sum(values))
        self.fractions = [v / total for v in values]
        self.radius = radius
        self.inner = radius * 0.55 if donut else 0.0
        self.colors = list(colors) if colors else [palette_color(i) for i in range(len(values))]
        self.tracker = ScaleTracker()  # Tracks the pie's center and scale as the chart moves
        self.sectors = VGroup()
        self.slice_labels = VGroup()
        self._angles = []
        start = PI / 2
        for i, f in enumerate(self.fractions):
            angle = -f * TAU
            self._angles.append((start, angle))
            self.sectors.add(self._sector(i, angle))
            mid = start + angle / 2
            text = labels[i] + (f"  {f * 100:.0f}%" if show_percent else "")
            label = Label(text, size=size)
            direction = np.array([np.cos(mid), np.sin(mid), 0])
            label.move_to(direction * (radius + 0.35))
            label.shift(direction * label.get_width() / 2 * abs(direction[0]))
            self.slice_labels.add(label)
            start += angle
        super().__init__(*self.tracker.mobjects, self.sectors, self.slice_labels, **kwargs)

    def _sector(self, i, angle, start=None):
        start = self._angles[i][0] if start is None else start
        if abs(angle) < 1e-4:
            angle = -1e-4
        s = self.tracker.scale()
        return AnnularSector(angle=angle, start_angle=start, inner_radius=self.inner * s,
                             outer_radius=self.radius * s, arc_center=self.tracker.origin(),
                             fill_color=self.colors[i], fill_opacity=1 if get_theme().name == "bubble" else 0.9,
                             stroke_width=2, stroke_color=get_theme().surface if get_theme().name == "bubble"
                             else get_theme().background)

    def build(self, run_time: float = 2.0, **kwargs) -> Animation:
        def update(group, alpha):
            for i, sector in enumerate(group):
                start, angle = self._angles[i]
                sector.become(self._sector(i, angle * alpha, PI / 2 + (start - PI / 2) * alpha))

        return Succession(
            UpdateFromAlphaFunc(self.sectors, update, run_time=run_time),
            LaggedStart(*(FadeIn(l) for l in self.slice_labels), lag_ratio=0.15),
            **kwargs,
        )

    def explode(self, i: int, distance: float = 0.35) -> Animation:
        start, angle = self._angles[i]
        mid = start + angle / 2
        d = np.array([np.cos(mid), np.sin(mid), 0]) * distance * self.tracker.scale()
        return AnimationGroup(self.sectors[i].animate.shift(d), self.slice_labels[i].animate.shift(d))
