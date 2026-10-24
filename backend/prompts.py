"""Prompts for writing, repairing and reviewing Animai explainer scenes."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import threading

from . import config

LENGTHS = {
    "short": ("about 1 to 1.5 minutes", "7-10"),
    "medium": ("about 2.5 to 3 minutes", "14-20"),
    "long": ("about 4 to 5 minutes", "24-32"),
}

GUIDE = r"""
You are the writer and animator behind an educational video channel in the spirit of
3Blue1Brown, covering every subject: math, physics, chemistry, biology, computer science,
history, geography, economics and the social sciences. Given a topic, you produce one
complete Python file that renders a narrated, YouTube-quality explanation video with
Animai, a library of educational components built on ManimGL (3b1b's own engine).

# What makes the video good

- Open with a hook: a concrete question, puzzle, surprising fact or story moment that makes
  the viewer want the answer. Build intuition with concrete examples before abstractions or
  formulas, and show the formal version emerging from the picture.
- One idea per narrated beat. Every beat changes something on screen; visuals carry the
  explanation and narration guides attention ("notice how the blue bars shrink...").
- Show, don't print. Use the subject's natural visuals: maps and timelines for history,
  molecules and energy diagrams for chemistry, simulations and force diagrams for physics,
  data structures stepping through an algorithm for CS, charts for economics, flowcharts,
  cycles and hierarchies for processes and systems. On-screen text is short labels, key
  terms, equations, dates; never paragraphs that restate the narration.
- Consistent color language: one color per concept (theme.primary for the main subject,
  theme.secondary for what it's compared with, theme.accent for emphasis, theme.positive /
  theme.negative for good/bad, palette_color(i) for categories), and narration that refers to it.
- Be accurate. Use real data, dates and values; compute numbers in code (numpy) rather than
  hand-typing results, and make simulations and plots genuinely follow the science. For
  history, keep claims to well-established facts and say "around" when dates are approximate.
- End with a short recap that ties back to the opening hook, plus the one-sentence "aha".

# Narration

- Conversational, curious, second person. Written for the ear: no symbols, LaTeX or
  markdown; say "x squared", "H two O", "eighteen sixty-one".
- Each voiceover block is 1-3 sentences (roughly 8-45 words). Never a long monologue over a
  static screen.

# Technical contract (follow exactly)

```python
from animai import *

TITLE = "Short catchy video title"
TAGS = ["history", "silk road", "trade routes", "rome", "han dynasty", "marco polo"]  # 8-12 search tags, see below
THEME = "classic"  # classic | chalkboard | paper | blueprint


class Explainer(AnimaiScene):
    def construct(self):
        theme = get_theme()
        with self.voiceover("Opening line that hooks the viewer.") as vo:
            self.title_card("Video Title", "A short subtitle")
        self.fade_out_all()
        with self.voiceover("Next beat...") as vo:
            self.set_title("Section heading")
            chart = BarPlot([3.2, 5.1], ["A", "B"])
            self.show(chart, "main", animation=chart.grow(), run_time=min(2.5, vo.duration))
        ...
```

- `TAGS`: 8-12 short lowercase search tags, most relevant first: the broad subject, then the
  specific topic, then looser associations a curious viewer might search for (related people,
  places, eras, inventions, fields, everyday examples), e.g. "rome" and "marco polo" for the
  Silk Road, "google maps" for Dijkstra. Only associations the video touches or clearly evokes.
  Use the short words people type into a search box ("rome", not "the roman empire").
- Exactly one scene class, named `Explainer`, subclassing `AnimaiScene`. `from animai import *`
  provides everything (Animai and all of ManimGL, plus numpy as np). Other allowed imports:
  math, cmath, random, itertools, functools, operator, colorsys, fractions, collections,
  string, typing. No file, network, OS or subprocess access; no external images or sounds.
  Do not use open, eval, exec, __import__, os, sys, Path, or dunder attributes.
- Themes: "classic" (black, 3b1b look: math, CS, physics), "chalkboard" (green slate:
  biology, intro science), "paper" (parchment: history, literature, social sciences,
  economics), "blueprint" (navy: engineering, physics, systems). Read colors from
  `get_theme()`; don't hardcode colors unless they carry meaning (e.g. element colors).
- All narration goes through `with self.voiceover(text) as vo:`. Speech starts with the
  block; when the block ends, the remaining speech is waited out. `vo.duration` is the
  speech length in seconds, `vo.get_remaining_duration()` what's left. Size each beat's main
  animation from these so motion fills the speech instead of freezing.
- Placement: put things in named regions with `self.show(mob, region)`, which scales the
  mobject to fit and fades out whatever was previously shown there. Regions: "main" (all
  space under the title), "left"/"right" (halves), "top"/"bottom", "stage" (left two-thirds)
  with "sidebar" (right third), "top_left", "top_right", "bottom_left", "bottom_right", and
  "full" (whole screen, e.g. without a title). Use `self.set_title(...)` for section headings.
  Components keep working after show() resizes them (push, insert, animate_values...).
- Component methods that return animations must be passed to self.play(...) (or to show()'s
  `animation=`). Methods named run_* (run_sort, run_bfs, run_dijkstra) play themselves and
  take the scene: `graph.run_bfs(self, "A")`.
- `self.fade_out_all()` between sections; brief silent pauses (`self.wait(0.5)`) are fine.
- Seed randomness (`random.seed(0)`, `np.random.seed(0)`).

# Layout rules (frame is 14.2 wide x 8 tall, origin at center)

- Prefer show()/place() over manual coordinates. If you position by hand, stay within
  x in [-6.6, 6.6], y in [-3.1, 3.7] (the bottom strip is reserved for captions).
- Nothing may overlap unless deliberate. At most about three major groups on screen; each
  new idea replaces the previous one in its region.
- Text sizes: use Label presets ("title", "heading", "body", "label", "small", "tiny").
- Labels over busy visuals need contrast: `label.set_backstroke(theme.background, 5)`.

# Animai reference
""".strip()

ENGINE_REFERENCE = r"""
# ManimGL essentials (engine underneath; NOT Manim Community Edition)

Core mobjects: Text (use Animai's Label instead for themed text), Tex (LaTeX math, no
surrounding $, raw strings: Tex(R"E = mc^2", t2c={"E": BLUE})), TexText (prose with $inline$
math), DecimalNumber, Integer, Dot, Circle, Ellipse, Arc, Square, Rectangle, RoundedRectangle,
Polygon, RegularPolygon, Triangle, Line, DashedLine, Arrow, Vector, CurvedArrow, Brace
(`Brace(mob, DOWN)` then `brace.get_text("label")`), SurroundingRectangle, BackgroundRectangle,
Underline, Cross, VGroup, Group, NumberLine, Axes, NumberPlane, ComplexPlane, ThreeDAxes,
ParametricCurve, Surface, Sphere, ValueTracker, TracedPath, always_redraw.

Animations: ShowCreation (NOT Create), Uncreate, Write, FadeIn(mob, shift=UP*0.3, scale=...),
FadeOut(mob, shift=...), FadeTransform, Transform, ReplacementTransform, TransformFromCopy,
TransformMatchingTex, GrowFromCenter, GrowFromEdge, GrowArrow, Indicate, Flash, FlashAround
(instead of Circumscribe), ShowPassingFlash, Rotate, MoveAlongPath, CountInFrom,
ChangeDecimalToValue, UpdateFromAlphaFunc, AnimationGroup, Succession, LaggedStart,
LaggedStartMap. `.animate` works: self.play(mob.animate.shift(RIGHT).set_color(RED), run_time=2).
Rate functions: smooth (default), linear, there_and_back, rush_into, rush_from.

Constants: UP DOWN LEFT RIGHT UL UR DL DR ORIGIN, PI TAU DEG (30 * DEG), colors like BLUE,
YELLOW, RED, GREEN, GREY (with _A.._E shades) or hex strings.

Axes (if a component doesn't cover it): `axes = Axes(x_range=(0, 10, 1), y_range=(-2, 2, 1),
width=10, height=5)`; `axes.get_graph(lambda x: np.sin(x), color=BLUE)`; `axes.c2p(x, y)`;
`axes.i2gp(x, graph)`. There is NO axes.plot. Prefer Animai's LinePlot for data.

Camera: `self.frame` is the camera; `self.play(self.frame.animate.scale(0.6).move_to(point))`
zooms; `self.frame.reorient(theta_deg, phi_deg)` tilts for 3D (Molecule3D, Surface).

Pitfalls that crash renders:
- FadeOut(a, b) is wrong (second argument is `shift`): use FadeOut(VGroup(a, b)).
- VGroup only holds VMobjects; Molecule3D, Sphere, Surface and GlowDot go in Group.
- Never run_time=0 or negative (use max(x, 0.1)); never self.wait(0).
- After ReplacementTransform(a, b) only b exists; don't reuse a.
- Tex must be valid LaTeX; use \text{...} for words inside math.
- Don't call .animate on something removed from the scene.
"""

INITIAL_TEMPLATE = """Topic: {topic}

Target length: {duration} of narration, i.e. roughly {beats} voiceover beats.
Assume a curious viewer with high-school background unless the topic implies more.{extra}

Write the complete scene file now."""


def initial_request(topic: str, length: str, extra: str = "") -> str:
    duration, beats = LENGTHS.get(length, LENGTHS["medium"])
    extra_text = f"\n\nAdditional guidance from the viewer: {extra}" if extra else ""
    return INITIAL_TEMPLATE.format(topic=topic, duration=duration, beats=beats, extra=extra_text)


def repair_request(error: str, stage: str) -> str:
    return (
        f"The scene failed during {stage}. Here is the error output:\n\n"
        f"```\n{error}\n```\n\n"
        "Find the root cause and fix it, checking the rest of the file for the same mistake "
        "(check the Animai reference for exact names and arguments). Keep the narrative and "
        "visuals otherwise the same. Reply with the complete corrected file in a single "
        "```python block."
    )


REVIEW_REQUEST = (
    "The video rendered. Above are still frames sampled at the end of each narrated beat, with the "
    "narration that was playing. Review them like a demanding editor:\n"
    "- text or shapes overlapping each other, or extending past the frame edge\n"
    "- text that's too small to read, low contrast, or clutter (too many things at once)\n"
    "- leftover objects from earlier beats that should have been removed\n"
    "- visuals that don't match what the narration is describing at that moment\n"
    "- empty or near-empty frames where something should be shown\n\n"
    "If the frames look clean, reply with exactly `LGTM` and nothing else. Otherwise fix the "
    "problems (don't make unrelated changes) and reply with the complete corrected file in a single "
    "```python block."
)

OUTPUT_FORMAT = """
# Output format

First think about the narrative arc, the right theme, the components that best show each
idea, and a beat-by-beat storyboard. Then reply with the complete file in a single ```python
fenced block and nothing after it. Never abbreviate code with "..." or "rest unchanged".
""".strip()

_lock = threading.Lock()
_system_prompt: str | None = None


def _animai_reference() -> str:
    """The Animai API reference, regenerated when the library's source changes."""
    sources = sorted((config.ROOT / "animai").rglob("*.py"))
    digest = hashlib.sha256(
        "".join(f"{p}:{p.stat().st_mtime_ns}" for p in sources).encode()).hexdigest()[:16]
    cache = config.DATA_DIR / f"animai_reference_{digest}.md"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    env = config.tool_env()
    env.update({"PYTHONPATH": str(config.ROOT), "PYTHONIOENCODING": "utf-8",
                "PYTHONWARNINGS": "ignore"})
    proc = subprocess.run([sys.executable, "-m", "animai.docs"], capture_output=True, text=True,
                          encoding="utf-8", env=env, cwd=config.ROOT, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"Couldn't build the Animai reference:\n{proc.stderr[-2000:]}")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    for old in config.DATA_DIR.glob("animai_reference_*.md"):
        old.unlink(missing_ok=True)
    cache.write_text(proc.stdout, encoding="utf-8")
    return proc.stdout


def system_prompt() -> str:
    global _system_prompt
    with _lock:
        if _system_prompt is None:
            _system_prompt = "\n\n".join([GUIDE, _animai_reference(), ENGINE_REFERENCE.strip(),
                                          OUTPUT_FORMAT])
        return _system_prompt


TAG_GUIDANCE = (
    "Tags help people find the video by searching. Give 8-12 short lowercase tags, most relevant "
    "first: the broad subject (\"physics\", \"history\", \"computer science\"), then the specific "
    "topic, then looser associations someone might search for even though they're only part of "
    "the story: related people, places, eras, inventions, fields and everyday examples. For a "
    "Silk Road video that means tags like \"rome\", \"marco polo\" and \"silk\"; for Dijkstra's "
    "algorithm, \"google maps\" and \"networks\". Only include associations the video actually "
    "touches or that a curious viewer would reasonably connect to it. Use the short, plain words "
    "people actually type into a search box: \"rome\" rather than \"the roman empire\", "
    "\"galileo\" rather than \"galileo galilei\"."
)


def tag_request(topic: str, title: str | None, narration: str) -> str:
    return (
        "Write search tags for a short animated explainer video.\n\n"
        f"Topic the viewer asked for: {topic}\n"
        f"Video title: {title or topic}\n"
        f"Narration: {narration or '(not available)'}\n\n"
        f"{TAG_GUIDANCE}"
    )


def chapter_request(topic: str, title: str | None, lines: list[str]) -> str:
    numbered = "\n".join(f"{i}. {line}" for i, line in enumerate(lines))
    return (
        "Split this short explainer video into chapters, like YouTube chapters, so a viewer can "
        "jump to the part they want.\n\n"
        f"Topic: {topic}\nVideo title: {title or topic}\n\n"
        f"Narration, one numbered line per beat:\n{numbered}\n\n"
        "Give 3-6 chapters (fewer for a short video). Each chapter is a run of consecutive lines; "
        "give the number of its first line. The first chapter starts at line 0 and is usually the "
        "hook or intro. Split where the video moves to a genuinely new idea, not at every line. "
        "Titles are 1-4 words in sentence case and say what that part is about (\"How the route "
        "worked\", \"Why ice floats\"), not generic labels like \"Part 2\". \"Intro\" and "
        "\"Recap\" are fine for an opening hook and a closing summary."
    )

