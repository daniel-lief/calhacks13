"""
History and geography visuals: world/regional maps (Natural Earth country outlines),
country highlighting, city markers, routes (trade, migration, campaigns), custom
territories (empires, historical regions), zooming, and timelines with eras.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from manimlib import (
    Animation, AnimationGroup, Dot, FadeIn, LaggedStart, Line, Mobject, MoveAlongPath, Transform,
    Polygon, Rectangle, RoundedRectangle, ShowCreation, Succession, Triangle, VGroup, VMobject,
    UP, DOWN, LEFT, RIGHT, ORIGIN, PI,
)

from animai.core.layout import region as layout_region, resolve_overlaps
from animai.core.media import Label
from animai.core.scaling import ScaleTracker
from animai.core.theme import get_theme, palette_color

__all__ = ["WorldMap", "Timeline", "MAP_REGIONS", "format_year"]

_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "maps"

# (lon_min, lon_max, lat_min, lat_max)
MAP_REGIONS = {
    "world": (-180, 180, -58, 84),
    "europe": (-25, 45, 34, 71),
    "western_europe": (-11, 20, 36, 60),
    "mediterranean": (-10, 42, 28, 48),
    "middle_east": (25, 65, 10, 43),
    "africa": (-20, 55, -36, 38),
    "asia": (25, 150, -10, 60),
    "east_asia": (95, 150, 15, 55),
    "south_asia": (60, 100, 3, 38),
    "southeast_asia": (90, 145, -12, 25),
    "north_america": (-170, -50, 7, 75),
    "usa": (-127, -66, 23, 50),
    "central_america": (-118, -59, 6, 33),
    "south_america": (-85, -32, -57, 14),
    "oceania": (110, 180, -48, 0),
    "russia": (25, 180, 40, 78),
}

_ALIASES = {
    "usa": "United States of America", "us": "United States of America",
    "united states": "United States of America", "america": "United States of America",
    "uk": "United Kingdom", "britain": "United Kingdom", "great britain": "United Kingdom",
    "england": "United Kingdom", "czech republic": "Czechia", "holland": "Netherlands",
    "the netherlands": "Netherlands", "south korea": "South Korea", "north korea": "North Korea",
    "drc": "Dem. Rep. Congo", "democratic republic of the congo": "Dem. Rep. Congo",
    "congo": "Congo", "ivory coast": "Côte d'Ivoire", "burma": "Myanmar", "persia": "Iran",
    "uae": "United Arab Emirates", "bosnia": "Bosnia and Herz.", "turkey": "Turkey",
    "türkiye": "Turkey", "east timor": "Timor-Leste", "eswatini": "eSwatini",
}


@lru_cache(maxsize=1)
def _countries():
    return json.loads((_ASSETS / "countries.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _cities():
    return json.loads((_ASSETS / "cities.json").read_text(encoding="utf-8"))


def _find_country(name: str) -> dict:
    key = name.lower().strip()
    key = _ALIASES.get(key, key).lower()
    for c in _countries():
        if key in (c["name"].lower(), c["long"].lower(), (c["iso"] or "").lower()):
            return c
    raise ValueError(f"Unknown country {name!r}")


def _natural_earth(lon, lat):
    l, p = np.radians(lon), np.radians(lat)
    p2 = p * p
    p4 = p2 * p2
    x = l * (0.870700 - 0.131979 * p2 + p4 * (-0.013791 + p4 * (0.003971 * p2 - 0.001529 * p4)))
    y = p * (1.007226 + p2 * (0.015085 + p4 * (-0.044475 + 0.028874 * p2 - 0.005916 * p4)))
    return np.degrees(x), np.degrees(y)


def _clip(ring, box):
    """Sutherland-Hodgman clip of a lon/lat ring to (lon0, lon1, lat0, lat1)."""
    lon0, lon1, lat0, lat1 = box
    edges = [(0, lon0, True), (0, lon1, False), (1, lat0, True), (1, lat1, False)]
    pts = [tuple(p) for p in ring]
    for axis, bound, keep_greater in edges:
        if not pts:
            break
        out = []
        for i, cur in enumerate(pts):
            prev = pts[i - 1]
            cin = cur[axis] >= bound if keep_greater else cur[axis] <= bound
            pin = prev[axis] >= bound if keep_greater else prev[axis] <= bound
            if cin != pin:
                t = (bound - prev[axis]) / ((cur[axis] - prev[axis]) or 1e-12)
                out.append((prev[0] + t * (cur[0] - prev[0]), prev[1] + t * (cur[1] - prev[1])))
            if cin:
                out.append(cur)
        pts = out
    return pts


class WorldMap(VGroup):
    """
    A map of the world or a region, drawn from Natural Earth country outlines.

    region: "world" (default) or a MAP_REGIONS name ("europe", "middle_east", "east_asia",
    "usa", "mediterranean", ...) or a (lon_min, lon_max, lat_min, lat_max) box.
    Countries are modern borders; for historical states use `territory()`.

    Lookups: `map.country("France")` (aliases like "USA", "UK" work), `map.point(lat, lon)`.
    Animations: `highlight(["France", "Spain"], color)`, `dim_others([...])`,
    `zoom_to(["Italy"])` (enlarges the map around those countries).
    Annotations (return mobjects to animate in): `label_country(name)`,
    `marker(lat, lon, "Text")`, `city("Paris")`, `route([...], color)` through
    (lat, lon) pairs or city names, `territory([(lat, lon), ...], color, "Roman Empire")`.
    `map.travel(route)` moves a dot along a route.

    Example:
        m = WorldMap("europe"); self.show(m, "main")
        self.play(m.highlight(["France", "Germany"], get_theme().primary))
        r = m.route(["Paris", "Berlin", "Moscow"]); self.play(ShowCreation(r))
    """

    def __init__(self, region="world", width: float = 13.0, height: float = 6.0,
                 fill_color=None, border_color=None, **kwargs):
        theme = get_theme()
        box = MAP_REGIONS[region] if isinstance(region, str) else tuple(region)
        self.box = box
        lon0, lon1, lat0, lat1 = box
        self.world_view = (lon1 - lon0) >= 300
        self.lat_scale = np.cos(np.radians((lat0 + lat1) / 2))
        # Fit the projected box into width x height (design space, centered at origin)
        corners = [self._project(lo, la) for lo in (lon0, lon1) for la in (lat0, lat1)]
        if self.world_view:
            corners += [self._project(0, lat0), self._project(0, lat1)]
        xs, ys = [c[0] for c in corners], [c[1] for c in corners]
        self._cx, self._cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        self._k = min(width / (max(xs) - min(xs)), height / (max(ys) - min(ys)))
        self.tracker = ScaleTracker()
        self.fill_color = fill_color or theme.land
        self.border_color = border_color or theme.land_border

        self.countries: dict[str, VGroup] = {}
        margin = 2
        for c in _countries():
            parts = []
            for ring in c["rings"]:
                arr = np.array(ring)
                if (arr[:, 0].max() < lon0 - margin or arr[:, 0].min() > lon1 + margin or
                        arr[:, 1].max() < lat0 - margin or arr[:, 1].min() > lat1 + margin):
                    continue
                pts = ring if self.world_view else _clip(ring, box)
                if len(pts) < 3:
                    continue
                poly = VMobject(fill_color=self.fill_color, fill_opacity=1,
                                stroke_color=self.border_color, stroke_width=1)
                poly.set_points_as_corners([self._design(lo, la) for lo, la in pts] +
                                           [self._design(*pts[0])])
                parts.append(poly)
            if parts:
                group = VGroup(*parts)
                group.info = c
                self.countries[c["name"]] = group
        self.overlay = VGroup()
        self._labels: list[Mobject] = []  # Text annotations, kept apart and unscaled by zooms
        super().__init__(*self.countries.values(), self.overlay, *self.tracker.mobjects, **kwargs)

    # Coordinates
    def _project(self, lon, lat):
        if self.world_view:
            return _natural_earth(lon, lat)
        return lon * self.lat_scale, lat

    def _design(self, lon, lat):
        x, y = self._project(lon, lat)
        return np.array([(x - self._cx) * self._k, (y - self._cy) * self._k, 0.0])

    def point(self, lat: float, lon: float) -> np.ndarray:
        """Scene point for a latitude/longitude."""
        return self.tracker.to_scene(self._design(lon, lat))

    def _resolve(self, where):
        if isinstance(where, str):
            city = next((c for c in _cities() if c["name"].lower() == where.lower()), None)
            if city is None:
                raise ValueError(f"Unknown city {where!r}; pass (lat, lon) instead")
            return city["lat"], city["lon"]
        return float(where[0]), float(where[1])

    # Countries
    def country(self, name: str) -> VGroup:
        info = _find_country(name)
        if info["name"] not in self.countries:
            raise ValueError(f"{info['name']} is outside this map's region")
        return self.countries[info["name"]]

    def highlight(self, names, color=None, opacity: float = 0.8) -> Animation:
        if isinstance(names, str):
            names = [names]
        c = color or get_theme().primary
        return AnimationGroup(*(self.country(n).animate.set_fill(c, opacity=opacity) for n in names))

    def reset(self, names=None) -> Animation:
        groups = [self.country(n) for n in names] if names else list(self.countries.values())
        return AnimationGroup(*(g.animate.set_fill(self.fill_color, opacity=1) for g in groups))

    def dim_others(self, names, opacity: float = 0.35) -> Animation:
        keep = {_find_country(n)["name"] for n in names}
        return AnimationGroup(*(g.animate.set_fill(opacity=opacity).set_stroke(opacity=opacity)
                                for name, g in self.countries.items() if name not in keep))

    def label_country(self, name: str, text: str | None = None, size="small", color=None) -> Label:
        info = _find_country(name)
        lon, lat = info["label"]
        label = Label(text or info["name"], size=size, color=color or get_theme().text)
        label.move_to(self.point(lat, lon))
        label.set_backstroke(get_theme().background, 4)
        self._place_label(label)
        self.overlay.add(label)
        return label

    def _place_label(self, label: Mobject):
        resolve_overlaps(label, fixed=tuple(self._labels), buff=0.08)
        self._labels.append(label)

    # Annotations
    def marker(self, lat: float, lon: float, label: str | None = None, color=None,
               direction=UP, size="small") -> VGroup:
        theme = get_theme()
        c = color or theme.accent
        dot = Dot(self.point(lat, lon), radius=0.07, fill_color=c, stroke_color=theme.background,
                  stroke_width=1.5)
        group = VGroup(dot)
        if label:
            tag = Label(label, size=size, color=theme.text if theme.visual_style == "bubble" else c, bold=True)
            tag.next_to(dot, direction, buff=0.08)
            tag.set_backstroke(theme.surface if theme.visual_style == "bubble" else theme.background, 4)
            self._place_label(tag)
            group.add(tag)
        self.overlay.add(group)
        return group

    def city(self, name: str, label: str | None = None, **kwargs) -> VGroup:
        lat, lon = self._resolve(name)
        return self.marker(lat, lon, label if label is not None else name, **kwargs)

    def route(self, stops, color=None, curved: bool = True, width: float = 4,
              dashed: bool = False) -> VMobject:
        """A path through stops ((lat, lon) pairs or city names). Animate with ShowCreation."""
        pts = [self.point(*self._resolve(s)) for s in stops]
        path_pts = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            if curved:
                mid = (a + b) / 2
                d = b - a
                normal = np.array([-d[1], d[0], 0]) * 0.18
                for t in np.linspace(0, 1, 16)[1:]:
                    path_pts.append((1 - t) ** 2 * a + 2 * (1 - t) * t * (mid + normal) + t ** 2 * b)
            else:
                path_pts.append(b)
        path = VMobject(stroke_color=color or get_theme().accent, stroke_width=width)
        path.set_points_as_corners(path_pts)
        if dashed:
            from manimlib import DashedVMobject
            path = DashedVMobject(path, num_dashes=max(12, len(path_pts)))
        self.overlay.add(path)
        return path

    def travel(self, route: VMobject, run_time: float = 3.0, color=None) -> Animation:
        theme = get_theme()
        traveler = Dot(radius=0.1, fill_color=color or theme.accent, stroke_color=theme.background,
                       stroke_width=2)
        traveler.move_to(route.get_start())
        self.overlay.add(traveler)
        return MoveAlongPath(traveler, route, run_time=run_time)

    def territory(self, points, color=None, label: str | None = None, opacity: float = 0.45) -> VGroup:
        """A custom region from (lat, lon) vertices, e.g. an empire's approximate extent."""
        c = color or palette_color(len(self.overlay))
        poly = VMobject(fill_color=c, fill_opacity=opacity, stroke_color=c, stroke_width=2.5)
        pts = [self.point(*self._resolve(p)) for p in points]
        poly.set_points_smoothly(pts + [pts[0]])
        group = VGroup(poly)
        if label:
            tag = Label(label, size="small", color=get_theme().text, bold=True)
            tag.move_to(poly.get_center()).set_backstroke(get_theme().background, 4)
            self._place_label(tag)
            group.add(tag)
        self.overlay.add(group)
        return group

    def zoom_to(self, names, where="main", margin: float = 0.6) -> Animation:
        """Enlarge and move the map so the given countries fill a screen region."""
        groups = VGroup(*(self.country(n) for n in ([names] if isinstance(names, str) else names)))
        r = layout_region(where)
        factor = min((r.width - margin) / groups.get_width(), (r.height - margin) / groups.get_height())
        center = groups.get_center()
        target = self.copy()
        target.scale(factor, about_point=center).shift(r.center - center)
        # Text keeps its size: labels are scaled back about their own centers
        for old, new in zip(self.get_family(), target.get_family()):
            if any(old is lab for lab in self._labels):
                new.scale(1 / factor)
        return Transform(self, target)

    def build(self, run_time: float = 2.0, **kwargs) -> Animation:
        return LaggedStart(*(FadeIn(g) for g in self.countries.values()), lag_ratio=0.005,
                           run_time=run_time, **kwargs)


def format_year(year: float) -> str:
    """-500 -> '500 BC', 33 -> 'AD 33', 1914 -> '1914'."""
    y = int(round(year))
    if y < 0:
        return f"{-y} BC"
    if y < 1000:
        return f"AD {y}"
    return str(y)


class Timeline(VGroup):
    """
    A horizontal timeline from `start` to `end` (years; negative = BC) with tick labels.
    `add_event(year, "Label")` places a marker with a label (alternating above/below,
    nudged apart if crowded) and returns it; `add_era(start, end, "Name", color)` adds a
    colored band. `timeline.build()` draws the axis then the events; `timeline.cursor(year)`
    returns a pointer you can move with `timeline.move_cursor(cursor, year)`.
    `timeline.point(year)` is the scene point for a year.

    Example:
        tl = Timeline(1900, 2000)
        tl.add_event(1914, "WWI begins"); tl.add_event(1939, "WWII begins")
        tl.add_era(1914, 1918, "WWI", get_theme().negative)
        self.show(tl, "main", animation=tl.build())
    """

    def __init__(self, start: float, end: float, width: float = 12.0, tick_step: float | None = None,
                 events=(), **kwargs):
        theme = get_theme()
        self.start, self.end, self.width = start, end, width
        self.tracker = ScaleTracker()
        span = end - start
        step = tick_step or _nice_years(span)
        self.axis = Line(LEFT * width / 2, RIGHT * width / 2, stroke_color=theme.muted, stroke_width=3)
        self.ticks = VGroup()
        first = np.ceil(start / step) * step
        for y in np.arange(first, end + 1e-9, step):
            x = self._x(y)
            tick = Line(np.array([x, -0.08, 0]), np.array([x, 0.08, 0]), stroke_color=theme.muted,
                        stroke_width=2)
            lab = Label(format_year(y), size="tiny", color=theme.muted).next_to(tick, DOWN, buff=0.12)
            self.ticks.add(VGroup(tick, lab))
        self.events: list[VGroup] = []
        self.eras = VGroup()
        self.event_group = VGroup()
        super().__init__(self.eras, self.axis, self.ticks, self.event_group, *self.tracker.mobjects,
                         **kwargs)
        for e in events:
            self.add_event(*e)

    def _x(self, year):
        return (year - self.start) / (self.end - self.start) * self.width - self.width / 2

    def point(self, year: float) -> np.ndarray:
        return self.tracker.to_scene(RIGHT * self._x(year))

    def add_event(self, year: float, label: str, color=None, above: bool = True) -> VGroup:
        """Add a dated event (above the axis by default; stems alternate in length)."""
        theme = get_theme()
        c = color or palette_color(len(self.events))
        s = self.tracker.scale()
        up = above
        d = UP if up else DOWN
        stem_len = (0.5 if len(self.events) % 2 == 0 else 1.45) if up else 1.3
        base = self.point(year)
        dot = Dot(base, radius=0.09 * s, fill_color=c)
        stem = Line(base, base + d * stem_len * s, stroke_color=c, stroke_width=2)
        tag = VGroup(Label(label, size="small", color=theme.text, max_width=3.2),
                     Label(format_year(year), size="tiny", color=theme.muted if theme.visual_style == "bubble" else c,
                           bold=True)).arrange(DOWN, buff=0.06)
        tag.scale(s).next_to(stem.get_end(), d, buff=0.06)
        others = [e[2] for e in self.events]
        resolve_overlaps(tag, fixed=tuple(others) + (self.axis,), buff=0.12)
        stem.put_start_and_end_on(base, tag.get_edge_center(-d) if up else tag.get_top())
        event = VGroup(dot, stem, tag)
        event.year = year
        self.events.append(event)
        self.event_group.add(event)
        return event

    def add_era(self, start: float, end: float, label: str, color=None) -> VGroup:
        c = color or palette_color(len(self.eras) + 3)
        s = self.tracker.scale()
        a, b = self.point(start), self.point(end)
        lane = DOWN * 0.85 * s  # Below the tick labels
        band = RoundedRectangle(width=max(b[0] - a[0], 0.05), height=0.3 * s, corner_radius=0.08 * s,
                                fill_color=c, fill_opacity=1 if get_theme().visual_style == "bubble" else 0.35,
                                stroke_color=c, stroke_width=0 if get_theme().visual_style == "bubble" else 1.5)
        band.move_to((a + b) / 2 + lane)
        tag = Label(label, size="tiny", color=get_theme().text if get_theme().visual_style == "bubble" else c,
                    bold=True).scale(s)
        if tag.get_width() > band.get_width() * 0.95:
            tag.next_to(band, DOWN, buff=0.1 * s)
            resolve_overlaps(tag, fixed=tuple(e[1] for e in self.eras if len(e) > 1), buff=0.1)
        else:
            tag.move_to(band)
            tag.set_color(get_theme().text)
        era = VGroup(band, tag)
        self.eras.add(era)
        return era

    def build(self, lag_ratio: float = 0.25, **kwargs) -> Animation:
        return Succession(
            AnimationGroup(ShowCreation(self.axis), FadeIn(self.ticks), FadeIn(self.eras)),
            LaggedStart(*(_grow_event(e) for e in self.events), lag_ratio=lag_ratio),
            **kwargs,
        )

    def cursor(self, year: float, color=None) -> VGroup:
        c = color or get_theme().accent
        s = self.tracker.scale()
        tri = Triangle(fill_color=c, fill_opacity=1, stroke_width=0).scale(0.12 * s).rotate(PI)
        tri.next_to(self.point(year), UP, buff=0.12 * s)
        return VGroup(tri)

    def move_cursor(self, cursor: VGroup, year: float, **kwargs) -> Animation:
        target = self.point(year) + UP * (cursor.get_height() / 2 + 0.12 * self.tracker.scale())
        return cursor.animate(**kwargs).move_to(target)


def _grow_event(event: VGroup) -> Animation:
    dot, stem, tag = event
    return Succession(FadeIn(dot, scale=0.5, run_time=0.3), ShowCreation(stem, run_time=0.3),
                      FadeIn(tag, shift=(stem.get_end() - stem.get_start()) * 0.2, run_time=0.5))


def _nice_years(span: float) -> float:
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000):
        if span / step <= 10:
            return step
    return 10000
