"""
Computer science visuals: arrays, stacks, queues, linked lists, binary search trees,
graphs, binary numbers, with operations that animate (swap, push, insert, traverse...)
and built-in walkthroughs of classic algorithms (sorting, BFS, DFS, Dijkstra).
"""
from __future__ import annotations

import heapq

import numpy as np

from manimlib import (
    Animation, AnimationGroup, Arrow, Circle, FadeIn, FadeOut, GrowFromCenter, Indicate,
    LaggedStart, Line, Mobject, RoundedRectangle, ShowCreation, Square, Succession, Text,
    Transform, VectorizedPoint, VGroup, Write, UP, DOWN, LEFT, RIGHT, ORIGIN, PI,
)

from animai.core.graphs import tree_positions
from animai.core.layout import SAFE_BOTTOM, SAFE_X
from animai.core.media import Label
from animai.core.scaling import ScaleTracker
from animai.core.style import soft_shadow
from animai.core.theme import get_theme

__all__ = [
    "Pointer", "ArrayViz", "StackViz", "QueueViz", "LinkedListViz", "BinaryTree",
    "GraphViz", "BinaryNumber",
]


def _value_text(v, size=34, color=None) -> Text:
    theme = get_theme()
    return Text(str(v), font=theme.font if theme.visual_style == "bubble" else theme.mono_font,
                font_size=size, weight=theme.text_weight if theme.visual_style == "bubble" else "MEDIUM",
                fill_color=color or theme.text)


def _cell(size: float, color=None) -> RoundedRectangle:
    theme = get_theme()
    return RoundedRectangle(width=size, height=size, corner_radius=size * 0.22,
                            fill_color=color or (theme.pill if theme.visual_style == "bubble" else theme.surface),
                            fill_opacity=1, stroke_color=theme.outline,
                            stroke_width=0 if theme.visual_style == "bubble" else 2.5)


def _node_circle(radius: float, color=None) -> VGroup:
    """A raised circular node: shadow, surface disc with colored ring. `.circle` is the ring."""
    theme = get_theme()
    circle = Circle(radius=radius,
                    fill_color=(color or theme.primary) if theme.visual_style == "bubble" else theme.surface,
                    fill_opacity=1, stroke_color=color or theme.primary,
                    stroke_width=0 if theme.visual_style == "bubble" else 3.5)
    group = VGroup(soft_shadow(circle), circle)
    group.circle = circle
    return group


class Pointer(VGroup):
    """An arrow with a small label (e.g. "i", "low", "head") pointing down at a mobject."""

    def __init__(self, target: Mobject, label: str = "", color=None, direction=UP, **kwargs):
        theme = get_theme()
        c = color or theme.accent
        self.direction = np.array(direction, dtype=float)
        self.arrow = Arrow(self.direction * 0.9, ORIGIN, buff=0, thickness=3, fill_color=c)
        self.label = Label(label, size="small", color=c, bold=True)
        self.label.next_to(self.arrow, self.direction, buff=0.08)
        super().__init__(self.arrow, self.label, **kwargs)
        self.point_at(target)

    def point_at(self, target: Mobject):
        tip = target.get_boundary_point(self.direction) + self.direction * 0.08
        self.shift(tip - self.arrow.get_end())
        return self


class ArrayViz(VGroup):
    """
    A row of cells holding values, with indices underneath.

    Animations (pass to self.play): `swap(i, j)`, `set_value(i, v)`, `highlight(i, color)`,
    `unhighlight(i)`, `compare(i, j)`, `mark_sorted(i)`, `move_pointer(ptr, i)`.
    `pointer(i, "low")` creates a Pointer above cell i (add it with FadeIn).
    `run_sort(scene, "bubble" | "insertion" | "selection")` plays a full sort step by step.
    `arr.values` is the current list; `arr.cells[i]`, `arr.items[i]` (the value glyphs).

    Example:
        arr = ArrayViz([5, 2, 9, 1, 7])
        self.show(arr, "main")
        self.play(arr.compare(0, 1)); self.play(arr.swap(0, 1))
    """

    def __init__(self, values, cell_size: float = 0.9, show_indices: bool = True,
                 font_size: int = 34, **kwargs):
        theme = get_theme()
        self.values = list(values)
        self.cell_size = cell_size
        self.cells = VGroup(*(_cell(cell_size) for _ in self.values)).arrange(RIGHT, buff=cell_size * 0.12)
        self.shadows = VGroup(*(soft_shadow(c) for c in self.cells))
        self.items = [_value_text(v, font_size).move_to(c) for v, c in zip(self.values, self.cells)]
        self.indices = VGroup()
        if show_indices:
            for i, c in enumerate(self.cells):
                idx = Label(str(i), size="tiny", color=theme.muted)
                idx.next_to(c, DOWN, buff=0.12)
                self.indices.add(idx)
        self.font_size = font_size
        self._sorted: set[int] = set()
        self.tracker = ScaleTracker()
        # Invisible marker above the cells reserves room for pointers, so fitting the array
        # into a region leaves space for them instead of pushing them into the title
        self.headroom = VectorizedPoint(self.cells.get_top() + UP * 1.35)
        super().__init__(self.shadows, self.cells, *self.items, self.indices, self.headroom,
                         *self.tracker.mobjects, **kwargs)

    def cell(self, i: int) -> Mobject:
        return self.cells[i]

    def highlight(self, i: int, color=None) -> Animation:
        return self.cells[i].animate.set_fill(color or get_theme().accent,
                                             opacity=1 if get_theme().visual_style == "bubble" else 0.45)

    def unhighlight(self, *indices: int) -> Animation:
        """Reset cells to normal (cells marked sorted keep their color)."""
        theme = get_theme()
        idx = [i for i in (indices or range(len(self.cells))) if i not in self._sorted]
        return AnimationGroup(*(self.cells[i].animate.set_fill(
            theme.pill if theme.visual_style == "bubble" else theme.surface, opacity=1) for i in idx))

    def compare(self, i: int, j: int, color=None) -> Animation:
        c = color or get_theme().secondary
        return AnimationGroup(self.highlight(i, c), self.highlight(j, c))

    def mark_sorted(self, *indices: int) -> Animation:
        self._sorted.update(indices)
        return AnimationGroup(*(self.highlight(i, get_theme().positive) for i in indices))

    def swap(self, i: int, j: int) -> Animation:
        if i == j:
            return Indicate(self.items[i])
        a, b = self.items[i], self.items[j]
        anim = AnimationGroup(
            a.animate(path_arc=-PI * 0.8).move_to(self.cells[j]),
            b.animate(path_arc=-PI * 0.8).move_to(self.cells[i]),
        )
        self.items[i], self.items[j] = b, a
        self.values[i], self.values[j] = self.values[j], self.values[i]
        return anim

    def set_value(self, i: int, value) -> Animation:
        new = _value_text(value, self.font_size).scale(self.tracker.scale()).move_to(self.cells[i])
        old = self.items[i]
        self.items[i] = new
        self.values[i] = value
        self.remove(old)
        self.add(new)
        return AnimationGroup(FadeOut(old, shift=UP * 0.3), FadeIn(new, shift=UP * 0.3))

    def pointer(self, i: int, label: str = "", color=None) -> Pointer:
        ptr = Pointer(self.cells[i], label, color)
        ptr.scale(self.tracker.scale())
        return ptr.point_at(self.cells[i])

    def move_pointer(self, ptr: Pointer, i: int) -> Animation:
        target = ptr.copy().point_at(self.cells[i])
        return ptr.animate.move_to(target)

    def run_sort(self, scene, algorithm: str = "bubble", step_time: float = 0.45):
        """Play every compare/swap of a sorting algorithm on this array."""
        steps = {"bubble": _bubble_steps, "insertion": _insertion_steps,
                 "selection": _selection_steps}[algorithm](list(self.values))
        for kind, *args in steps:
            if kind == "compare":
                scene.play(self.compare(*args), run_time=step_time * 0.6)
            elif kind == "swap":
                scene.play(self.swap(*args), run_time=step_time)
            elif kind == "sorted":
                scene.play(self.mark_sorted(*args), run_time=step_time * 0.5)
                continue
            scene.play(self.unhighlight(*args), run_time=step_time * 0.3)


def _bubble_steps(v):
    n = len(v)
    for end in range(n - 1, 0, -1):
        for i in range(end):
            yield ("compare", i, i + 1)
            if v[i] > v[i + 1]:
                v[i], v[i + 1] = v[i + 1], v[i]
                yield ("swap", i, i + 1)
        yield ("sorted", end)
    yield ("sorted", 0)


def _insertion_steps(v):
    for i in range(1, len(v)):
        j = i
        while j > 0:
            yield ("compare", j - 1, j)
            if v[j - 1] <= v[j]:
                break
            v[j - 1], v[j] = v[j], v[j - 1]
            yield ("swap", j - 1, j)
            j -= 1
    yield ("sorted", *range(len(v)))


def _selection_steps(v):
    n = len(v)
    for i in range(n - 1):
        m = i
        for j in range(i + 1, n):
            yield ("compare", m, j)
            if v[j] < v[m]:
                m = j
        if m != i:
            v[i], v[m] = v[m], v[i]
            yield ("swap", i, m)
        yield ("sorted", i)
    yield ("sorted", n - 1)


class StackViz(VGroup):
    """
    A vertical stack (LIFO). `push(v)` and `pop()` return animations; `stack.values`.

    Example: s = StackViz([1, 2]); self.show(s, "left"); self.play(s.push(3)); self.play(s.pop())
    """

    def __init__(self, values=(), cell_width: float = 1.6, cell_height: float = 0.7,
                 capacity: int = 6, **kwargs):
        theme = get_theme()
        self.cw, self.ch = cell_width, cell_height
        self.values = list(values)
        self.tracker = ScaleTracker()
        half = cell_width / 2 + 0.1
        self.frame_lines = VGroup(
            Line(LEFT * half, RIGHT * half),
            Line(LEFT * half, LEFT * half + UP * capacity * cell_height),
            Line(RIGHT * half, RIGHT * half + UP * capacity * cell_height),
        ).set_stroke(theme.muted, 3)
        self.boxes = [self._box(v, i) for i, v in enumerate(self.values)]
        super().__init__(self.frame_lines, *self.boxes, *self.tracker.mobjects, **kwargs)

    def _box(self, v, i):
        theme = get_theme()
        rect = RoundedRectangle(width=self.cw, height=self.ch * 0.9, corner_radius=0.16,
                                fill_color=theme.primary, fill_opacity=1 if theme.visual_style == "bubble" else 0.25,
                                stroke_color=theme.primary, stroke_width=0 if theme.visual_style == "bubble" else 2.5)
        box = VGroup(rect, _value_text(v, 30).move_to(rect))
        box.move_to(UP * (self.ch * (i + 0.5) + 0.04))  # Design-space slot
        return self.tracker.adopt(box)

    def push(self, value) -> Animation:
        box = self._box(value, len(self.values))
        self.values.append(value)
        self.boxes.append(box)
        self.add(box)
        return FadeIn(box, shift=DOWN * 1.2 * self.tracker.scale())

    def pop(self) -> Animation:
        box = self.boxes.pop()
        self.values.pop()
        self.remove(box)
        return FadeOut(box, shift=UP * 1.2 * self.tracker.scale())


class QueueViz(VGroup):
    """
    A horizontal queue (FIFO): `enqueue(v)` adds at the back (right), `dequeue()` removes
    from the front (left) and slides the rest forward. `queue.values`.

    Example: q = QueueViz(["A", "B"]); self.play(q.enqueue("C")); self.play(q.dequeue())
    """

    def __init__(self, values=(), cell_size: float = 0.9, **kwargs):
        theme = get_theme()
        self.cs = cell_size
        self.values = list(values)
        self.tracker = ScaleTracker()
        self.front_label = Label("front", size="tiny", color=theme.muted)
        self.front_label.move_to(DOWN * (cell_size / 2 + 0.3))
        self.boxes = [self._box(v, i) for i, v in enumerate(self.values)]
        super().__init__(self.front_label, *self.boxes, *self.tracker.mobjects, **kwargs)

    def _slot(self, i):
        return self.tracker.to_scene(RIGHT * self.cs * 1.1 * i)

    def _box(self, v, i):
        theme = get_theme()
        sq = RoundedRectangle(width=self.cs, height=self.cs, corner_radius=0.18,
                              fill_color=theme.secondary, fill_opacity=1 if theme.visual_style == "bubble" else 0.25,
                              stroke_color=theme.secondary, stroke_width=0 if theme.visual_style == "bubble" else 2.5)
        box = VGroup(sq, _value_text(v, 30).move_to(sq)).move_to(RIGHT * self.cs * 1.1 * i)
        return self.tracker.adopt(box)

    def enqueue(self, value) -> Animation:
        box = self._box(value, len(self.values))
        self.values.append(value)
        self.boxes.append(box)
        self.add(box)
        return FadeIn(box, shift=LEFT * self.tracker.scale())

    def dequeue(self) -> Animation:
        box = self.boxes.pop(0)
        self.values.pop(0)
        self.remove(box)
        moves = [b.animate.move_to(self._slot(i)) for i, b in enumerate(self.boxes)]
        return AnimationGroup(FadeOut(box, shift=LEFT * self.tracker.scale()), *moves)


class LinkedListViz(VGroup):
    """
    Singly linked list: value boxes joined by arrows, ending in "null".
    `insert(index, value)` and `remove_at(index)` return animations that relink the
    arrows; `traverse()` walks a highlight from head to tail; `highlight(i)`; `nodes[i]`.

    Example: ll = LinkedListViz([3, 7, 1]); self.show(ll, "main"); self.play(ll.insert(1, 5))
    """
    BOX_W, NEXT_W, HEIGHT = 1.1, 0.35, 0.8

    def __init__(self, values, gap: float = 0.9, **kwargs):
        theme = get_theme()
        self.values = list(values)
        self.gap = gap
        self.tracker = ScaleTracker()
        self.nodes = [self._node(v) for v in self.values]
        self.null = Label("null", size="small", color=theme.muted)
        self._null_width = self.null.get_width()
        self._design_center = (len(self.values) * (self.node_width + gap) + self._null_width) / 2
        positions, null_pos = self._targets(len(self.nodes))
        for n, pos in zip(self.nodes, positions):
            n.move_to(pos)
        self.null.move_to(null_pos)
        self.arrows = self._arrows(len(self.nodes))
        super().__init__(*self.nodes, self.null, *self.arrows, *self.tracker.mobjects, **kwargs)

    @property
    def node_width(self):
        return self.BOX_W + self.NEXT_W

    def _node(self, v):
        theme = get_theme()
        box = RoundedRectangle(width=self.BOX_W, height=self.HEIGHT, corner_radius=0.1,
                               fill_color=theme.surface, fill_opacity=1,
                               stroke_color=theme.primary, stroke_width=0 if theme.visual_style == "bubble" else 2.5)
        nxt = RoundedRectangle(width=self.NEXT_W, height=self.HEIGHT, corner_radius=0.06,
                               fill_color=theme.primary, fill_opacity=1 if theme.visual_style == "bubble" else 0.3,
                               stroke_color=theme.primary, stroke_width=0 if theme.visual_style == "bubble" else 2.5)
        nxt.next_to(box, RIGHT, buff=0)
        node = VGroup(box, nxt, _value_text(v, 30).move_to(box))
        return self.tracker.adopt(node.move_to(ORIGIN))

    def _design_targets(self, count):
        """Layout for `count` nodes, centered where the original list was (grows both ways)."""
        step = self.node_width + self.gap
        total = count * step + self._null_width
        shift = self._design_center - total / 2
        positions = [RIGHT * (shift + self.node_width / 2 + i * step) for i in range(count)]
        null_pos = RIGHT * (shift + count * step + self._null_width / 2)
        return positions, null_pos

    def _targets(self, count):
        """Scene centers for `count` nodes, plus the null label's."""
        positions, null_pos = self._design_targets(count)
        return [self.tracker.to_scene(p) for p in positions], self.tracker.to_scene(null_pos)

    def _arrows(self, count):
        theme = get_theme()
        positions, null_pos = self._design_targets(count)
        ends = [p + LEFT * self.node_width / 2 for p in positions[1:]]
        ends.append(null_pos + LEFT * self._null_width / 2)
        arrows = []
        for p, end in zip(positions, ends):
            start = p + RIGHT * (self.node_width / 2 - self.NEXT_W / 2)
            arrow = Arrow(start, end, buff=0.05, thickness=2.5, fill_color=theme.muted)
            arrows.append(self.tracker.adopt(arrow))
        return arrows

    def _relink(self, nodes, entering=None, leaving=None) -> Animation:
        positions, null_pos = self._targets(len(nodes))
        new_arrows = self._arrows(len(nodes))
        lift = UP * 1.2 * self.tracker.scale()
        old_arrows = self.arrows
        self.remove(*old_arrows)
        moves = [n.animate.move_to(p) for n, p in zip(nodes, positions) if n is not entering]
        moves.append(self.null.animate.move_to(null_pos))
        first = [FadeOut(a) for a in old_arrows]
        if leaving is not None:
            first.append(FadeOut(leaving, shift=-lift))
            self.remove(leaving)
        last = [LaggedStart(*(GrowFromCenter(a) for a in new_arrows), lag_ratio=0.1)]
        if entering is not None:
            entering.move_to(positions[nodes.index(entering)] + lift)
            self.add(entering)
            last.append(entering.animate.shift(-lift))
        self.nodes, self.arrows = nodes, new_arrows
        self.add(*new_arrows)
        return Succession(AnimationGroup(*first, *moves), AnimationGroup(*last))

    def insert(self, index: int, value) -> Animation:
        node = self._node(value)
        self.values.insert(index, value)
        return self._relink(self.nodes[:index] + [node] + self.nodes[index:], entering=node)

    def remove_at(self, index: int) -> Animation:
        node = self.nodes[index]
        self.values.pop(index)
        return self._relink(self.nodes[:index] + self.nodes[index + 1:], leaving=node)

    def highlight(self, i: int, color=None) -> Animation:
        return self.nodes[i][0].animate.set_fill(color or get_theme().accent, opacity=0.4)

    def traverse(self, color=None, **kwargs) -> Animation:
        c = color or get_theme().accent
        anims = []
        for i, n in enumerate(self.nodes):
            anims.append(Indicate(n, color=c, scale_factor=1.1))
            if i < len(self.arrows):
                anims.append(Indicate(self.arrows[i], color=c))
        return Succession(*anims, **kwargs)


class BinaryTree(VGroup):
    """
    A binary search tree built from insertion order. Circles with values joined by lines.
    `insert(v)` animates the search path then the new node growing in (the tree re-lays
    itself out smoothly); `search(v)` highlights the comparison path; `node(v)` returns a
    node; `highlight_path([v1, v2, ...])`; `inorder()` returns the sorted values.

    Example:
        bst = BinaryTree([8, 3, 10, 1, 6]); self.show(bst, "main")
        self.play(bst.insert(7)); self.play(bst.search(6))
    """

    def __init__(self, values=(), node_radius: float = 0.38, level_gap: float = 1.1,
                 sibling_gap: float = 0.95, **kwargs):
        self.r, self.level_gap, self.sibling_gap = node_radius, level_gap, sibling_gap
        self.left, self.right = {}, {}
        self.root = None
        self.nodes: dict = {}
        self.links: dict = {}
        self.tracker = ScaleTracker()
        for v in values:
            self._insert_value(v)
        for v in self.nodes:
            self.nodes[v] = self._make_node(v)
        super().__init__(**kwargs)
        self._apply_layout(animate=False)
        for (a, b) in self._edges():
            self.links[(a, b)] = self._make_link(a, b)
        self.add(*self.links.values(), *self.nodes.values(), *self.tracker.mobjects)

    def _insert_value(self, v):
        if self.root is None:
            self.root = v
            self.nodes[v] = None
            return []
        cur, path = self.root, []
        while True:
            path.append(cur)
            side = self.left if v < cur else self.right
            if cur in side:
                cur = side[cur]
            else:
                side[cur] = v
                self.nodes[v] = None
                return path

    def _edges(self):
        return [(p, c) for p, c in self.left.items()] + [(p, c) for p, c in self.right.items()]

    def _positions(self):
        # Give missing children placeholders so a lone right child still leans right
        children = {}
        counter = [0]

        def kids(v):
            out = []
            for side in (self.left, self.right):
                if v in side:
                    out.append(side[v])
                elif v in self.left or v in self.right:
                    counter[0] += 1
                    ph = ("_ph", counter[0])
                    children[ph] = []
                    out.append(ph)
            return out

        stack = [self.root]
        while stack:
            v = stack.pop()
            children[v] = kids(v)
            stack += [c for c in children[v] if not (isinstance(c, tuple) and c and c[0] == "_ph")]
        pos = tree_positions(self.root, children, DOWN, self.level_gap, self.sibling_gap)
        return {v: p for v, p in pos.items() if v in self.nodes}

    def _make_node(self, v):
        theme = get_theme()
        disc = _node_circle(self.r)
        node = VGroup(disc, _value_text(v, 28).move_to(disc.circle))
        node.circle = disc.circle
        return self.tracker.adopt(node)

    def _make_link(self, a, b):
        return self._link_between(self.nodes[a].get_center(), self.nodes[b].get_center())

    def _apply_layout(self, animate: bool = False):
        for v, p in self._positions().items():
            self.nodes[v].move_to(self.tracker.to_scene(p))

    def node(self, v) -> Mobject:
        return self.nodes[v]

    def search(self, value, color=None) -> Animation:
        c = color or get_theme().accent
        path, cur = [], self.root
        while cur is not None:
            path.append(cur)
            if value == cur:
                break
            cur = (self.left if value < cur else self.right).get(cur)
        return self.highlight_path(path, c)

    def highlight_path(self, values, color=None) -> Animation:
        c = color or get_theme().accent
        return Succession(*(Indicate(self.nodes[v], color=c, scale_factor=1.15) for v in values))

    def insert(self, value, color=None) -> Animation:
        if value in self.nodes:
            return self.search(value, color)
        c = color or get_theme().accent
        path = self._insert_value(value)
        new = self._make_node(value)
        self.nodes[value] = new
        # Keep the root where it is; the tree grows downward and sideways
        pos = self._positions()
        root_now = self.nodes[self.root].get_center()
        k = self.tracker.scale()
        offsets = {v: (p - pos[self.root]) * k for v, p in pos.items()}
        # If the grown tree would leave the safe area, tighten its spacing (node size stays)
        r = self.r * k
        lowest = min(o[1] for o in offsets.values())
        widest = max(abs(o[0]) for o in offsets.values())
        room_down = root_now[1] - (SAFE_BOTTOM + r + 0.1)
        room_side = SAFE_X - r - abs(root_now[0])
        squeeze = min(1.0, room_down / -lowest if lowest < 0 else 1.0,
                      room_side / widest if widest > 0 else 1.0)
        targets = {v: root_now + o * squeeze for v, o in offsets.items()}
        new.move_to(targets[value])
        moves = [m.animate.move_to(targets[v]) for v, m in self.nodes.items() if v != value]
        old_links = list(self.links.values())
        self.remove(*old_links)
        self.links = {(a, b): self._link_between(targets[a], targets[b]) for a, b in self._edges()}
        new_link = next(l for (a, b), l in self.links.items() if b == value)
        self.add(*self.links.values(), *self.nodes.values())
        return Succession(
            self.highlight_path(path, c),
            AnimationGroup(*moves, *(FadeOut(l) for l in old_links),
                           *(FadeIn(l) for l in self.links.values() if l is not new_link)),
            AnimationGroup(GrowFromCenter(new), ShowCreation(new_link)),
        )

    def _link_between(self, pa, pb):
        d = (pb - pa) / np.linalg.norm(pb - pa)
        r = self.r * self.tracker.scale()
        return Line(pa + d * r, pb - d * r, stroke_color=get_theme().muted, stroke_width=3.5)

    def inorder(self):
        out = []

        def walk(v):
            if v is None:
                return
            walk(self.left.get(v))
            out.append(v)
            walk(self.right.get(v))

        walk(self.root)
        return out


class GraphViz(VGroup):
    """
    A graph of labeled nodes and edges, laid out automatically (networkx).

    edges: [("A", "B"), ...] or weighted [("A", "B", 4), ...]
    layout: "spring" (default), "circular", "kamada_kawai", "shell", or {node: (x, y)}
    `graph.nodes[n]`, `graph.edges[(u, v)]`; animations: `highlight_node(n)`,
    `highlight_edge(u, v)`, `visit(n)`; `set_note(n, text)` puts a small annotation
    (e.g. a distance) beside a node.
    Built-in walkthroughs: `run_bfs(scene, start)`, `run_dfs(scene, start)`,
    `run_dijkstra(scene, start, target=None)`.

    Example:
        g = GraphViz([("A", "B", 4), ("A", "C", 2), ("C", "B", 1), ("B", "D", 5)], weighted=True)
        self.show(g, "main"); g.run_dijkstra(self, "A", target="D")
    """

    def __init__(self, edges, nodes=None, directed: bool = False, weighted: bool | None = None,
                 layout="spring", width: float = 9.0, height: float = 5.0,
                 node_radius: float = 0.38, seed: int = 3, **kwargs):
        import networkx as nx
        theme = get_theme()
        self.directed = directed
        self.weighted = weighted if weighted is not None else any(len(e) > 2 for e in edges)
        self.G = nx.DiGraph() if directed else nx.Graph()
        if nodes:
            self.G.add_nodes_from(nodes)
        for e in edges:
            self.G.add_edge(e[0], e[1], weight=(e[2] if len(e) > 2 else 1))
        if isinstance(layout, dict):
            raw = {n: np.array(p, dtype=float) for n, p in layout.items()}
        elif layout == "circular":
            raw = nx.circular_layout(self.G)
        elif layout == "shell":
            raw = nx.shell_layout(self.G)
        elif layout == "kamada_kawai":
            raw = nx.kamada_kawai_layout(self.G)
        else:
            raw = nx.spring_layout(self.G, seed=seed)
        pts = np.array([raw[n] for n in self.G.nodes])
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        span = np.where(hi - lo < 1e-9, 1, hi - lo)
        self.r = node_radius
        self.nodes = {}
        for n in self.G.nodes:
            x, y = (np.array(raw[n]) - lo) / span - 0.5
            disc = _node_circle(node_radius)
            label = _value_text(n, 28)
            if label.get_width() > node_radius * 1.6:
                label.set_width(node_radius * 1.6)
            self.nodes[n] = VGroup(disc, label.move_to(disc.circle)).move_to(
                np.array([x * width, y * height, 0]))
        self.edges, self.weight_labels = {}, {}
        for u, v, data in self.G.edges(data=True):
            pu, pv = self.nodes[u].get_center(), self.nodes[v].get_center()
            d = (pv - pu) / np.linalg.norm(pv - pu)
            if directed:
                line = Arrow(pu + d * node_radius, pv - d * node_radius, buff=0.02, thickness=2.5,
                             fill_color=theme.muted)
            else:
                line = Line(pu + d * node_radius, pv - d * node_radius, stroke_color=theme.muted,
                            stroke_width=3.5)
            self.edges[(u, v)] = line
            if self.weighted:
                w = Label(str(data["weight"]), size="small",
                          color=theme.muted if theme.visual_style == "bubble" else theme.secondary)
                normal = np.array([-d[1], d[0], 0])
                w.move_to((pu + pv) / 2 + normal * 0.25)
                w.set_backstroke(theme.background, 6)
                self.weight_labels[(u, v)] = w
        self.notes = {}
        self.tracker = ScaleTracker()
        super().__init__(*self.edges.values(), *self.weight_labels.values(), *self.nodes.values(),
                         *self.tracker.mobjects, **kwargs)

    def edge(self, u, v) -> Mobject:
        return self.edges[(u, v)] if (u, v) in self.edges else self.edges[(v, u)]

    def highlight_node(self, n, color=None) -> Animation:
        c = color or get_theme().accent
        return self.nodes[n][0].circle.animate.set_stroke(
            c, width=0 if get_theme().visual_style == "bubble" else 5.5).set_fill(
                c, opacity=1 if get_theme().visual_style == "bubble" else 0.4)

    def visit(self, n, color=None) -> Animation:
        return self.highlight_node(n, color or get_theme().positive)

    def highlight_edge(self, u, v, color=None) -> Animation:
        c = color or get_theme().accent
        e = self.edge(u, v)
        if isinstance(e, Arrow):
            return e.animate.set_fill(c)
        return e.animate.set_stroke(c, width=6)

    def set_note(self, n, text: str, color=None) -> Animation:
        """Show (or update) a small annotation above-right of node n, e.g. a distance."""
        theme = get_theme()
        note = Label(text, size="small", color=color or (theme.accent if theme.visual_style == "bubble"
                                                        else theme.secondary), bold=True)
        note.scale(self.tracker.scale())
        note.next_to(self.nodes[n], UP + RIGHT * 0.6, buff=0.02)
        note.set_backstroke(theme.background, 5)
        old = self.notes.get(n)
        self.notes[n] = note
        self.add(note)
        if old is None:
            return FadeIn(note, scale=0.8)
        self.remove(old)
        return AnimationGroup(FadeOut(old, shift=UP * 0.2), FadeIn(note, shift=UP * 0.2))

    def _neighbors(self, n):
        return sorted(self.G.successors(n) if self.directed else self.G.neighbors(n), key=str)

    def run_bfs(self, scene, start, step_time: float = 0.6):
        """Breadth-first search from `start`, numbering nodes in visit order."""
        seen, queue, order = {start}, [start], 0
        scene.play(self.highlight_node(start), run_time=step_time)
        while queue:
            n = queue.pop(0)
            order += 1
            scene.play(self.visit(n), self.set_note(n, str(order)), run_time=step_time)
            for m in self._neighbors(n):
                if m not in seen:
                    seen.add(m)
                    queue.append(m)
                    scene.play(self.highlight_edge(n, m), self.highlight_node(m), run_time=step_time * 0.7)

    def run_dfs(self, scene, start, step_time: float = 0.6):
        """Depth-first search from `start`, numbering nodes in visit order."""
        seen, order = set(), [0]

        def go(n, parent=None):
            seen.add(n)
            order[0] += 1
            anims = [self.visit(n), self.set_note(n, str(order[0]))]
            if parent is not None:
                anims.append(self.highlight_edge(parent, n))
            scene.play(*anims, run_time=step_time)
            for m in self._neighbors(n):
                if m not in seen:
                    go(m, n)

        go(start)

    def run_dijkstra(self, scene, start, target=None, step_time: float = 0.6):
        """Dijkstra's shortest paths from `start`; shows tentative distances, then the path to `target`."""
        dist = {n: float("inf") for n in self.G.nodes}
        prev = {}
        dist[start] = 0
        scene.play(*(self.set_note(n, "∞") for n in self.G.nodes if n != start),
                   self.set_note(start, "0"), run_time=step_time)
        heap, done = [(0, str(start), start)], set()
        while heap:
            d, _, n = heapq.heappop(heap)
            if n in done:
                continue
            done.add(n)
            scene.play(self.visit(n), run_time=step_time)
            for m in self._neighbors(n):
                w = self.G[n][m]["weight"]
                if d + w < dist[m]:
                    dist[m] = d + w
                    prev[m] = n
                    heapq.heappush(heap, (dist[m], str(m), m))
                    scene.play(self.highlight_edge(n, m, get_theme().secondary),
                               self.set_note(m, f"{dist[m]:g}"), run_time=step_time)
        if target is not None and (target in prev or target == start):
            path = [target]
            while path[-1] != start:
                path.append(prev[path[-1]])
            path.reverse()
            on_path = {frozenset(e) for e in zip(path, path[1:])}
            scene.play(*(self.reset_edge(u, v) for (u, v) in self.edges
                         if frozenset((u, v)) not in on_path), run_time=step_time)
            scene.play(*(self.highlight_edge(a, b) for a, b in zip(path, path[1:])),
                       *(self.highlight_node(n) for n in path), run_time=step_time * 2)
        return dist

    def reset_edge(self, u, v) -> Animation:
        """Return an edge to its default muted look."""
        e, muted = self.edge(u, v), get_theme().muted
        if isinstance(e, Arrow):
            return e.animate.set_fill(muted)
        return e.animate.set_stroke(muted, width=3)


class BinaryNumber(VGroup):
    """
    A row of bits with place values (128 64 ... 1) above and the decimal value beside.
    `set_value(n)` flips the changed bits; `bits[i]` (0 = most significant).

    Example: b = BinaryNumber(5, n_bits=8); self.show(b, "main"); self.play(b.set_value(6))
    """

    def __init__(self, value: int = 0, n_bits: int = 8, cell_size: float = 0.8, **kwargs):
        theme = get_theme()
        self.n_bits, self.value = n_bits, value
        self.cells = VGroup(*(_cell(cell_size) for _ in range(n_bits))).arrange(RIGHT, buff=0.08)
        self.places = VGroup(*(Label(str(2 ** (n_bits - 1 - i)), size="tiny", color=theme.muted)
                               .next_to(c, UP, buff=0.12) for i, c in enumerate(self.cells)))
        self.bits = [self._bit(b, i) for i, b in enumerate(self._bits_of(value))]
        self.decimal = Label(f"= {value}", size="body", color=theme.accent)
        self.decimal.next_to(self.cells, RIGHT, buff=0.4)
        # Reserve the maximum decimal width before show() fits the component. Later
        # bit flips must not push the result outside its presentation card.
        reserve = Label(f"= {2 ** n_bits - 1}", size="body", color=theme.accent)
        reserve.move_to(self.decimal, aligned_edge=LEFT)
        self.decimal_bound = VectorizedPoint(reserve.get_right())
        self.tracker = ScaleTracker()
        super().__init__(self.cells, self.places, *self.bits, self.decimal, self.decimal_bound, *self.tracker.mobjects,
                         **kwargs)

    def _bits_of(self, value):
        return [(value >> (self.n_bits - 1 - i)) & 1 for i in range(self.n_bits)]

    def _bit(self, b, i):
        theme = get_theme()
        t = _value_text(b, 32, theme.accent if b else theme.muted)
        if hasattr(self, "tracker"):
            t.scale(self.tracker.scale())
        return t.move_to(self.cells[i])

    def set_value(self, value: int) -> Animation:
        anims = []
        for i, (old_b, new_b) in enumerate(zip(self._bits_of(self.value), self._bits_of(value))):
            if old_b != new_b:
                new = self._bit(new_b, i)
                anims += [FadeOut(self.bits[i], shift=UP * 0.3), FadeIn(new, shift=UP * 0.3)]
                self.remove(self.bits[i])
                self.bits[i] = new
                self.add(new)
        new_dec = Label(f"= {value}", size="body", color=get_theme().accent)
        new_dec.scale(self.tracker.scale()).move_to(self.decimal, aligned_edge=LEFT)
        anims.append(Transform(self.decimal, new_dec))
        self.value = value
        return AnimationGroup(*anims)
