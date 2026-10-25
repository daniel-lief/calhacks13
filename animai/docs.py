"""
Generates the compact API reference given to the AI that writes scenes, straight from the
docstrings and signatures in this package, so the prompt never drifts from the code.

    python -m animai.docs            # print the reference
"""
from __future__ import annotations

import inspect
import re

SECTIONS = [
    ("Core: scene, layout, theme", "animai.core.scene", ["AnimaiScene"]),
    ("Core: scene, layout, theme", "animai.core.layout", ["fit", "resolve_overlaps"]),
    ("Core: scene, layout, theme", "animai.core.theme", ["get_theme", "palette_color"]),
    ("Text, cards and icons", "animai.core.media",
     ["Label", "Title", "BulletList", "Card", "Badge", "QuoteCard", "Callout", "CodeBlock"]),
    ("Text, cards and icons", "animai.core.icons", ["Icon", "IconLabel"]),
    ("Diagrams (any subject)", "animai.subjects.diagrams",
     ["Node", "Connector", "Flowchart", "CycleDiagram", "VennDiagram", "ComparisonTable", "Hierarchy"]),
    ("Charts and data", "animai.subjects.data", ["BarPlot", "LinePlot", "PieChart"]),
    ("Computer science", "animai.subjects.cs",
     ["ArrayViz", "Pointer", "StackViz", "QueueViz", "LinkedListViz", "BinaryTree", "GraphViz",
      "BinaryNumber"]),
    ("Chemistry", "animai.subjects.chemistry",
     ["Molecule", "Molecule3D", "ChemEquation", "EnergyDiagram", "PeriodicTable", "BohrAtom"]),
    ("Physics", "animai.subjects.physics",
     ["PhysicsWorld", "Pendulum", "MassSpring", "Spring", "ForceArrow", "FreeBodyDiagram",
      "Projectile", "Wave", "LensDiagram", "SimpleCircuit", "FieldLines"]),
    ("History and geography", "animai.subjects.geography", ["WorldMap", "Timeline"]),
]

# Scene methods worth documenting individually
SCENE_METHODS = ["voiceover", "show", "place", "hide", "set_title", "title_card", "fade_out_all"]


def _signature(obj, skip_self=True) -> str:
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return "(...)"
    parts = []
    for name, p in sig.parameters.items():
        if skip_self and name == "self":
            continue
        if p.kind is p.VAR_KEYWORD:
            continue
        if p.kind is p.VAR_POSITIONAL:
            parts.append(f"*{name}")
            continue
        if p.default is p.empty:
            parts.append(name)
        else:
            parts.append(f"{name}={_short(p.default)}")
    return "(" + ", ".join(parts) + ")"


def _short(value) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if hasattr(value, "shape"):  # numpy direction constants
        for const in ("UP", "DOWN", "LEFT", "RIGHT", "ORIGIN", "UR", "UL", "DR", "DL"):
            import animlib
            if hasattr(animlib, const) and (getattr(animlib, const) == value).all():
                return const
        return "array"
    text = repr(value)
    return text if len(text) <= 24 else text[:21] + "..."


def _doc(obj) -> str:
    doc = inspect.getdoc(obj) or ""
    return re.sub(r"\n{3,}", "\n\n", doc).strip()


def build_reference() -> str:
    import importlib
    out, current = [], None
    for title, module_name, names in SECTIONS:
        module = importlib.import_module(module_name)
        if title != current:
            out.append(f"\n## {title}\n")
            current = title
        for name in names:
            obj = getattr(module, name)
            if name == "AnimaiScene":
                out.append("### class AnimaiScene(Scene)")
                out.append(_doc(obj))
                for m in SCENE_METHODS:
                    method = getattr(obj, m)
                    out.append(f"- `self.{m}{_signature(method)}`: {_doc(method)}")
                out.append("")
                continue
            kind = "class" if inspect.isclass(obj) else "def"
            sig = _signature(obj.__init__ if kind == "class" else obj, skip_self=True)
            out.append(f"### {name}{sig}")
            doc = _doc(obj)
            if doc:
                out.append(doc)
            out.append("")
    return "\n".join(out).strip() + "\n"


if __name__ == "__main__":
    import animai  # noqa: F401  (bootstraps the engine and patches)
    print(build_reference())
