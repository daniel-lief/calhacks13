"""
General diagrams that every subject uses: labeled nodes, connectors, flowcharts,
cycles, Venn diagrams, comparison tables and hierarchies (org charts, family trees,
taxonomies).
"""
from __future__ import annotations

import numpy as np

from manimlib import (
    Animation, AnimationGroup, Arrow, Circle, CurvedArrow, DashedLine, FadeIn, GrowArrow,
    Indicate, LaggedStart, Line, Mobject, Polygon, RoundedRectangle, ShowCreation, VGroup,
    Write, UP, DOWN, LEFT, RIGHT, ORIGIN, TAU, PI,
)

from animai.core.graphs import layered_positions, tree_positions
from animai.core.media import Label
from animai.core.scaling import ScaleTracker
from animai.core.style import Panel, soft_shadow
from animai.core.theme import get_theme, palette_color

__all__ = [
    "Node", "Connector", "Flowchart", "CycleDiagram", "VennDiagram", "ComparisonTable",
    "Hierarchy",
]


class Node(VGroup):
    """
    A raised shape with a centered text label. shape: "rounded" (default), "box", "circle",
    "pill", "diamond". `node.shape` (the bordered outline) and `node.label` are the parts.
    `node.highlight()` returns an animation that lights it up in the accent color.

    Example: Node("Photosynthesis", color=get_theme().positive)
    """

    def __init__(self, text: str, shape: str = "rounded", color=None, size="label",
                 width: float | None = None, height: float | None = None,
                 fill_opacity: float = 0.2, max_text_width: float = 3.6, shadow: bool = True,
                 **kwargs):
        theme = get_theme()
        self.color = color or theme.primary
        self.fill_opacity = 1 if theme.name == "bubble" else fill_opacity
        self.label = Label(text, size=size, max_width=max_text_width, bold=True)
        w = width or max(self.label.get_width() + 0.7, 1.3)
        h = height or max(self.label.get_height() + 0.55, 0.85)
        style = dict(fill_color=theme.surface, fill_opacity=1, stroke_color=self.color,
                     stroke_width=0 if theme.name == "bubble" else 3)
        if shape == "circle":
            self.shape = Circle(radius=max(w, h) / 2, **style)
        elif shape == "diamond":
            w, h = w * 1.35, h * 1.5
            self.shape = Polygon(UP * h / 2, RIGHT * w / 2, DOWN * h / 2, LEFT * w / 2, **style)
        elif shape == "box":
            self.shape = RoundedRectangle(width=w, height=h, corner_radius=0.06, **style)
        elif shape == "pill":
            self.shape = RoundedRectangle(width=w + 0.3, height=h, corner_radius=h / 2, **style)
        else:
            self.shape = RoundedRectangle(width=w, height=h, corner_radius=0.22, **style)
        self.tint = self.shape.copy().set_stroke(width=0).set_fill(self.color, opacity=self.fill_opacity)
        self.label.move_to(self.shape)
        parts = [self.shape, self.tint, self.label]
        if shadow:
            parts.insert(0, soft_shadow(self.shape))
        super().__init__(*parts, **kwargs)

    def highlight(self, color=None, run_time: float = 0.8) -> Animation:
        c = color or get_theme().accent
        return AnimationGroup(
            self.shape.animate.set_stroke(c, width=0 if get_theme().name == "bubble" else 5),
            self.tint.animate.set_fill(c, opacity=1 if get_theme().name == "bubble" else 0.38),
            Indicate(self.label, color=get_theme().text if get_theme().name == "bubble" else c,
                     scale_factor=1.08), run_time=run_time,
        )

    def unhighlight(self, run_time: float = 0.6) -> Animation:
        return AnimationGroup(self.shape.animate.set_stroke(
                                  self.color, width=0 if get_theme().name == "bubble" else 3),
                              self.tint.animate.set_fill(self.color, opacity=self.fill_opacity),
                              run_time=run_time)


class Connector(VGroup):
    """
    An arrow between two mobjects' borders, with an optional label (on a small pill) at
    its midpoint. `curve` bends it (radians, e.g. 0.4); `dashed=True` for weaker or
    implied links.

    Example: Connector(cause, effect, label="leads to")
    """

    def __init__(self, start: Mobject, end: Mobject, label: str | None = None, color=None,
                 curve: float = 0.0, dashed: bool = False, tip: bool = True,
                 buff: float = 0.14, label_size="tiny", **kwargs):
        theme = get_theme()
        c = color or theme.muted
        a, b = start.get_center(), end.get_center()
        d = (b - a) / (np.linalg.norm(b - a) or 1)
        p0 = _border_point(start, d) + d * buff
        p1 = _border_point(end, -d) - d * buff
        if dashed:
            self.line = DashedLine(p0, p1, stroke_color=c, stroke_width=3, dash_length=0.12)
        elif tip:
            self.line = Arrow(p0, p1, buff=0, path_arc=curve, thickness=3.5, fill_color=c,
                              tip_width_ratio=4)
        else:
            self.line = Line(p0, p1, path_arc=curve, stroke_color=c, stroke_width=3)
        parts = [self.line]
        self.label = None
        if label:
            text = Label(label, size=label_size, color=theme.text, bold=True)
            h = text.get_height() + 0.22
            pill = RoundedRectangle(width=text.get_width() + 0.36, height=h, corner_radius=h / 2,
                                    fill_color=theme.surface, fill_opacity=1, stroke_color=c,
                                    stroke_width=0 if theme.name == "bubble" else 1.5)
            self.label = VGroup(pill, text.move_to(pill))
            normal = np.array([-d[1], d[0], 0])
            self.label.move_to((p0 + p1) / 2 + normal * abs(curve) * 0.5)
            parts.append(self.label)
        super().__init__(*parts, **kwargs)

    def grow(self, **kwargs) -> Animation:
        anims = [ShowCreation(self.line) if isinstance(self.line, (DashedLine, Line))
                 and not isinstance(self.line, Arrow) else GrowArrow(self.line)]
        if self.label is not None:
            anims.append(FadeIn(self.label, scale=0.8))
        return AnimationGroup(*anims, **kwargs)


def _border_point(mob: Mobject, direction) -> np.ndarray:
    target = mob.shape if isinstance(mob, Node) else mob
    return target.get_boundary_point(direction)


class Flowchart(VGroup):
    """
    Nodes connected by arrows, laid out automatically in layers.

    nodes: {id: "text"} (or a list of texts, ids become the texts)
    edges: [(from_id, to_id)] or [(from_id, to_id, "label")]
    direction: RIGHT (left-to-right, default) or DOWN (top-to-bottom)
    shapes: optional {id: "diamond" | "pill" | ...}; colors: optional {id: color}

    `fc.nodes[id]`, `fc.edges[(a, b)]`; `fc.build()` animates it in layer by layer;
    `fc.highlight(id)` and `fc.trace([id1, id2, ...])` walk a path.

    Example:
        fc = Flowchart({"in": "Input", "check": "Valid?", "ok": "Save", "err": "Reject"},
                       [("in", "check"), ("check", "ok", "yes"), ("check", "err", "no")],
                       shapes={"check": "diamond"})
        self.show(fc, "main", animation=fc.build())
    """

    def __init__(self, nodes, edges, direction=RIGHT, shapes: dict | None = None,
                 colors: dict | None = None, layer_gap: float | None = None,
                 node_gap: float | None = None, size="label", **kwargs):
        if not isinstance(nodes, dict):
            nodes = {n: n for n in nodes}
        shapes, colors = shapes or {}, colors or {}
        self.nodes = {k: Node(v, shape=shapes.get(k, "rounded"), color=colors.get(k), size=size)
                      for k, v in nodes.items()}
        horizontal = abs(np.array(direction)[0]) > 0.5
        max_w = max(n.get_width() for n in self.nodes.values())
        max_h = max(n.get_height() for n in self.nodes.values())
        lg = layer_gap or ((max_w + 1.2) if horizontal else (max_h + 1.0))
        ng = node_gap or ((max_h + 0.6) if horizontal else (max_w + 0.5))
        pairs = [(e[0], e[1]) for e in edges]
        positions = layered_positions(list(self.nodes), pairs, direction, lg, ng)
        for k, n in self.nodes.items():
            n.move_to(positions[k])
        self.edges = {}
        for e in edges:
            label = e[2] if len(e) > 2 else None
            self.edges[(e[0], e[1])] = Connector(self.nodes[e[0]], self.nodes[e[1]], label=label)
        self._order = sorted(self.nodes, key=lambda k: tuple(np.round(positions[k] @ np.array(direction, float), 3).flat))
        super().__init__(*self.edges.values(), *self.nodes.values(), **kwargs)

    def build(self, lag_ratio: float = 0.3, **kwargs) -> Animation:
        anims = []
        for k in self._order:
            anims.append(FadeIn(self.nodes[k], scale=0.9))
            for (a, b), conn in self.edges.items():
                if b == k:
                    anims.append(conn.grow())
        return LaggedStart(*anims, lag_ratio=lag_ratio, **kwargs)

    def highlight(self, node_id, color=None) -> Animation:
        return self.nodes[node_id].highlight(color)

    def trace(self, path: list, color=None, **kwargs) -> Animation:
        c = color or get_theme().accent
        anims = []
        for i, k in enumerate(path):
            anims.append(self.nodes[k].highlight(c))
            if i + 1 < len(path) and (k, path[i + 1]) in self.edges:
                anims.append(self.edges[(k, path[i + 1])].line.animate.set_color(c))
        return LaggedStart(*anims, lag_ratio=0.6, **kwargs)


class CycleDiagram(VGroup):
    """
    Stages arranged in a circle with curved arrows between consecutive stages
    (water cycle, cell cycle, business cycle...). `cycle.stages[i]`, `cycle.arrows[i]`
    (from stage i to i+1). `cycle.build()` animates stage by stage; `cycle.highlight(i)`.

    Example: CycleDiagram(["Evaporation", "Condensation", "Precipitation", "Collection"])
    """

    def __init__(self, stages: list[str], radius: float = 2.4, colors=None, size="label",
                 **kwargs):
        n = len(stages)
        self.stages = []
        for i, text in enumerate(stages):
            node = Node(text, color=(colors[i] if colors else palette_color(i)), size=size,
                        max_text_width=2.6)
            angle = PI / 2 - i * TAU / n
            node.move_to(radius * np.array([np.cos(angle), np.sin(angle), 0]))
            self.stages.append(node)
        self.arrows = []
        for i in range(n):
            a, b = self.stages[i], self.stages[(i + 1) % n]
            self.arrows.append(Connector(a, b, curve=-TAU / n * 0.6, color=get_theme().muted))
        super().__init__(*self.arrows, *self.stages, **kwargs)

    def build(self, lag_ratio: float = 0.4, **kwargs) -> Animation:
        anims = []
        for s, a in zip(self.stages, self.arrows):
            anims += [FadeIn(s, scale=0.9), a.grow()]
        return LaggedStart(*anims, lag_ratio=lag_ratio, **kwargs)

    def highlight(self, i: int, color=None) -> Animation:
        return self.stages[i].highlight(color)


class VennDiagram(VGroup):
    """
    Two or three overlapping translucent circles with set labels. `venn.circles[i]`,
    `venn.labels[i]`; `venn.add_item(text, region)` places a small label in a region
    named by the sets it belongs to, e.g. (0,), (0, 1), (0, 1, 2).

    Example: venn = VennDiagram(["Mammals", "Can fly"]); venn.add_item("Bat", (0, 1))
    """

    def __init__(self, set_names: list[str], radius: float = 1.8, colors=None, **kwargs):
        theme = get_theme()
        n = len(set_names)
        if n not in (2, 3):
            raise ValueError("VennDiagram supports 2 or 3 sets")
        offset = radius * 0.62
        centers = ([LEFT * offset, RIGHT * offset] if n == 2 else
                   [offset * np.array([np.cos(a), np.sin(a), 0])
                    for a in (PI / 2 + TAU / 3, PI / 2 + 2 * TAU / 3, PI / 2)])
        self.circles, self.labels = [], []
        for i, (name, c) in enumerate(zip(set_names, centers)):
            c = np.array(c, dtype=float)
            col = colors[i] if colors else palette_color(i)
            circle = Circle(radius=radius, stroke_color=col,
                            stroke_width=0 if theme.name == "bubble" else 3,
                            fill_color=col, fill_opacity=0.55 if theme.name == "bubble" else 0.18).move_to(c)
            label = Label(name, size="label", color=theme.text if theme.name == "bubble" else col, bold=True)
            direction = c / (np.linalg.norm(c) or 1)
            if n == 2:
                direction = UP
                label.move_to(c + UP * (radius + 0.35))
            else:
                label.move_to(c + direction * (radius + 0.4))
            self.circles.append(circle)
            self.labels.append(label)
        self.items = VGroup()
        self.tracker = ScaleTracker()
        super().__init__(*self.circles, *self.labels, self.items, *self.tracker.mobjects, **kwargs)

    def region_point(self, sets: tuple) -> np.ndarray:
        """A point inside the region belonging to exactly the given sets (e.g. (0, 1))."""
        centers = [c.get_center() for c in self.circles]  # Live, in case the diagram moved
        middle = np.mean(centers, axis=0)
        inside = [centers[i] for i in sets]
        outside = [centers[i] for i in range(len(centers)) if i not in sets]
        p = np.mean(inside, axis=0)
        if len(sets) == 1:
            return p + (p - middle) * 0.6
        for o in outside:
            p = p + (p - o) * 0.35
        return p

    def add_item(self, text: str, sets: tuple, size="small") -> Mobject:
        s = self.tracker.scale()
        item = Label(text, size=size).scale(s)
        stacked = [m for m in self.items if getattr(m, "_sets", None) == tuple(sets)]
        item.move_to(self.region_point(tuple(sets)) + DOWN * 0.4 * s * len(stacked))
        item._sets = tuple(sets)
        self.items.add(item)
        return item

    def build(self, **kwargs) -> Animation:
        return LaggedStart(*(AnimationGroup(ShowCreation(c), FadeIn(l))
                             for c, l in zip(self.circles, self.labels)), lag_ratio=0.4, **kwargs)


class ComparisonTable(VGroup):
    """
    A grid of text with a highlighted header row (compare options, eras, properties).
    `table.cell(r, c)` (row 0 is the header), `table.row(r)`, `table.column(c)`;
    `table.build()` reveals header then rows; `table.highlight_row(r)`.

    Example:
        ComparisonTable(["", "Mitosis", "Meiosis"],
                        [["Daughter cells", "2", "4"], ["Identical?", "Yes", "No"]])
    """

    def __init__(self, header: list[str], rows: list[list[str]], size="small",
                 col_gap: float = 0.6, row_gap: float = 0.35, **kwargs):
        theme = get_theme()
        grid = [[Label(str(t), size=size, bold=True, color=theme.accent) for t in header]]
        grid += [[Label(str(t), size=size) for t in row] for row in rows]
        n_cols = len(header)
        col_w = [max(r[c].get_width() for r in grid if c < len(r)) for c in range(n_cols)]
        row_h = [max(m.get_height() for m in r) for r in grid]
        self._cells = []
        y = 0.0
        for r, row in enumerate(grid):
            x = 0.0
            cells = []
            for c, m in enumerate(row):
                m.move_to(np.array([x + col_w[c] / 2, y - row_h[r] / 2, 0]))
                if c == 0 and r > 0:
                    m.move_to(np.array([x + m.get_width() / 2, y - row_h[r] / 2, 0]))
                x += col_w[c] + col_gap
                cells.append(m)
            self._cells.append(VGroup(*cells))
            y -= row_h[r] + row_gap
        total_w = sum(col_w) + col_gap * (n_cols - 1)
        total_h = -y - row_gap
        pad = 0.45
        self.panel = Panel(total_w + 2 * pad, total_h + 2 * pad, color=theme.outline, tint=0.0,
                           corner_radius=0.22)
        self.panel.move_to(np.array([total_w / 2, -total_h / 2, 0]))
        # Header band and zebra stripes
        self.rules = VGroup()
        y = 0.0
        for r in range(len(grid)):
            band_h = row_h[r] + row_gap
            if r == 0 or r % 2 == 0:
                band = RoundedRectangle(
                    width=total_w + 2 * pad - 0.16, height=band_h, corner_radius=0.1,
                    fill_color=theme.accent if r == 0 else theme.outline,
                    fill_opacity=0.16 if r == 0 else 0.14, stroke_width=0)
                band.move_to(np.array([total_w / 2, y - row_h[r] / 2, 0]))
                self.rules.add(band)
            y -= band_h
        super().__init__(self.panel, self.rules, *self._cells, **kwargs)
        self.center()

    def cell(self, r: int, c: int) -> Mobject:
        return self._cells[r][c]

    def row(self, r: int) -> VGroup:
        return self._cells[r]

    def column(self, c: int) -> VGroup:
        return VGroup(*(row[c] for row in self._cells if c < len(row)))

    def build(self, lag_ratio: float = 0.25, **kwargs) -> Animation:
        return LaggedStart(FadeIn(VGroup(self.panel, self.rules), scale=0.97),
                           FadeIn(self._cells[0], shift=DOWN * 0.1),
                           *(FadeIn(r, shift=DOWN * 0.15) for r in self._cells[1:]),
                           lag_ratio=lag_ratio, **kwargs)

    def highlight_row(self, r: int, color=None) -> Animation:
        return self._cells[r].animate.set_color(color or get_theme().accent)


class Hierarchy(VGroup):
    """
    A tree of labeled nodes: org charts, family trees, taxonomies, outlines.
    `tree` is a nested dict {"Root": {"Child A": {...}, "Child B": {}}} or
    {"Root": ["Leaf 1", "Leaf 2"]}. `h.nodes["Child A"]`; `h.build()` reveals level by level.

    Example: Hierarchy({"Animals": {"Vertebrates": ["Mammals", "Birds"], "Invertebrates": ["Insects"]}})
    """

    def __init__(self, tree: dict, direction=DOWN, size="small", colors_by_level: bool = True,
                 **kwargs):
        children: dict[str, list[str]] = {}
        level: dict[str, int] = {}

        def walk(name, sub, depth):
            level[name] = depth
            if isinstance(sub, dict):
                kids = list(sub)
                children[name] = kids
                for k in kids:
                    walk(k, sub[k], depth + 1)
            elif isinstance(sub, (list, tuple)):
                children[name] = list(sub)
                for k in sub:
                    walk(k, None, depth + 1)
            else:
                children[name] = []

        (root, sub), = tree.items()
        walk(root, sub, 0)
        self.nodes = {n: Node(n, size=size, color=palette_color(level[n]) if colors_by_level else None,
                              max_text_width=2.4)
                      for n in level}
        max_w = max(n.get_width() for n in self.nodes.values())
        max_h = max(n.get_height() for n in self.nodes.values())
        vertical = abs(np.array(direction)[1]) > 0.5
        pos = tree_positions(root, children, direction,
                             level_gap=(max_h + 0.9) if vertical else (max_w + 0.9),
                             sibling_gap=(max_w + 0.3) if vertical else (max_h + 0.3))
        for n, node in self.nodes.items():
            node.move_to(pos[n])
        self.links = VGroup()
        self._levels = level
        for parent, kids in children.items():
            for k in kids:
                self.links.add(_elbow(self.nodes[parent], self.nodes[k], direction))
        super().__init__(self.links, *self.nodes.values(), **kwargs)

    def build(self, **kwargs) -> Animation:
        depth = max(self._levels.values())
        waves = []
        for d in range(depth + 1):
            nodes = [self.nodes[n] for n, l in self._levels.items() if l == d]
            waves.append(AnimationGroup(*(FadeIn(n, shift=DOWN * 0.15) for n in nodes)))
        return AnimationGroup(ShowCreation(self.links, lag_ratio=0.1),
                              LaggedStart(*waves, lag_ratio=0.7), **kwargs)


def _elbow(parent: Node, child: Node, direction) -> VGroup:
    theme = get_theme()
    d = np.array(direction, dtype=float)
    a = parent.shape.get_boundary_point(d)
    b = child.shape.get_boundary_point(-d)
    if abs(d[1]) > 0.5:
        mid_y = (a[1] + b[1]) / 2
        pts = [a, np.array([a[0], mid_y, 0]), np.array([b[0], mid_y, 0]), b]
    else:
        mid_x = (a[0] + b[0]) / 2
        pts = [a, np.array([mid_x, a[1], 0]), np.array([mid_x, b[1], 0]), b]
    from manimlib import VMobject
    path = VMobject(stroke_color=theme.muted, stroke_width=2.5)
    path.set_points_as_corners(pts)
    return path
