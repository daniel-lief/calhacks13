"""Layout algorithms shared by flowcharts, trees, graphs and hierarchies."""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from manimlib import DOWN, RIGHT

__all__ = ["layered_positions", "tree_positions"]


def _acyclic_edges(nodes, edges):
    """Drop back edges (found by DFS) so the rest form a DAG."""
    out = defaultdict(list)
    for a, b in edges:
        out[a].append(b)
    state, keep = {}, []
    order = list(nodes)

    def visit(n):
        state[n] = 1
        for m in out[n]:
            if state.get(m) == 1:
                continue  # Back edge: skip
            keep.append((n, m))
            if m not in state:
                visit(m)
        state[n] = 2

    for n in order:
        if n not in state:
            visit(n)
    return keep


def layered_positions(nodes, edges, direction=RIGHT, layer_gap: float = 2.5,
                      node_gap: float = 1.4) -> dict:
    """
    Sugiyama-style layout: each node's layer is its longest distance from a source, and
    nodes within a layer are ordered to reduce crossings. Returns {node: point}, centered.
    """
    nodes = list(nodes)
    dag = _acyclic_edges(nodes, edges)
    preds = defaultdict(list)
    for a, b in dag:
        preds[b].append(a)

    layer = {}

    def depth(n):
        if n in layer:
            return layer[n]
        layer[n] = 0 if not preds[n] else 1 + max(depth(p) for p in preds[n])
        return layer[n]

    for n in nodes:
        depth(n)
    layers = defaultdict(list)
    for n in nodes:
        layers[layer[n]].append(n)

    # Barycenter ordering, a few sweeps
    index = {n: i for L in layers.values() for i, n in enumerate(L)}
    for _ in range(4):
        for k in sorted(layers)[1:]:
            layers[k].sort(key=lambda n: np.mean([index[p] for p in preds[n]]) if preds[n] else index[n])
            for i, n in enumerate(layers[k]):
                index[n] = i

    d, across = _axes(direction)
    pos = {}
    for k, L in layers.items():
        for i, n in enumerate(L):
            offset = (i - (len(L) - 1) / 2) * node_gap
            pos[n] = d * k * layer_gap + across * offset
    return _center(pos)


def _axes(direction):
    """Unit flow direction, and the direction siblings are listed in (top-down or left-right)."""
    d = np.array(direction, dtype=float)
    d /= np.linalg.norm(d)
    across = DOWN.astype(float) if abs(d[0]) >= abs(d[1]) else RIGHT.astype(float)
    return d, across


def tree_positions(root, children: dict, direction=DOWN, level_gap: float = 1.4,
                   sibling_gap: float = 1.2) -> dict:
    """Tidy tree layout: leaves spaced evenly, parents centered over their children."""
    pos_along, depth = {}, {}
    next_x = [0.0]

    def walk(n, dpt):
        depth[n] = dpt
        kids = [c for c in children.get(n, []) if c is not None]
        if not kids:
            pos_along[n] = next_x[0]
            next_x[0] += sibling_gap
        else:
            for c in kids:
                walk(c, dpt + 1)
            pos_along[n] = (pos_along[kids[0]] + pos_along[kids[-1]]) / 2

    walk(root, 0)
    d, across = _axes(direction)
    pos = {n: d * depth[n] * level_gap + across * pos_along[n] for n in pos_along}
    return _center(pos)


def _center(pos: dict) -> dict:
    if not pos:
        return pos
    pts = np.array(list(pos.values()))
    mid = (pts.min(axis=0) + pts.max(axis=0)) / 2
    return {n: p - mid for n, p in pos.items()}
