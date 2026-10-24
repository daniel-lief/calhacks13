# Animai — animated explanations of anything

Animai is an educational animation library built on top of 3Blue1Brown's rendering
engine, plus a web app where you type a topic and Claude turns it into a narrated video.

ManimGL is a general animation engine, but its building blocks are math-specific (`Tex`,
`Axes`, `NumberPlane`). Animai adds building blocks for every subject, and the plumbing
that makes AI-written scenes come out clean: themes, layout regions, narration with
captions, and components that keep working after they're resized.

| Subject | Components |
|---|---|
| Any | `Label`, `Title`, `BulletList`, `Card`, `Badge`, `QuoteCard`, `Callout`, `CodeBlock`, `Icon` (2,000+ Lucide icons), `Flowchart`, `CycleDiagram`, `VennDiagram`, `ComparisonTable`, `Hierarchy` |
| Data / economics | `BarPlot` (with bar-chart races), `LinePlot`, `PieChart` |
| Computer science | `ArrayViz` (with `run_sort`), `StackViz`, `QueueViz`, `LinkedListViz`, `BinaryTree`, `GraphViz` (with `run_bfs`, `run_dfs`, `run_dijkstra`), `BinaryNumber` |
| Chemistry | `Molecule` (structure from SMILES or a common name), `Molecule3D`, `ChemEquation`, `EnergyDiagram`, `PeriodicTable`, `BohrAtom` |
| Physics | `PhysicsWorld` (real rigid-body simulation), `Pendulum`, `MassSpring`, `Spring`, `ForceArrow`, `FreeBodyDiagram`, `Projectile`, `Wave`, `LensDiagram`, `SimpleCircuit`, `FieldLines` |
| History / geography | `WorldMap` (countries, cities, routes, territories, zoom), `Timeline` (events, eras, cursor) |

Everything from ManimGL (`Tex`, `Axes`, `Transform`, ...) is still available.

## Writing a scene

```python
from animai import *

THEME = "paper"  # classic | chalkboard | paper | blueprint


class SilkRoad(AnimaiScene):
    def construct(self):
        with self.voiceover("For over a thousand years, goods and ideas moved along the Silk Road."):
            self.set_title("The Silk Road")
            world = WorldMap("world")
            self.show(world, "main", animation=world.build())
        with self.voiceover("Silk went west from China, through Persia, all the way to Rome."):
            route = world.route(["Beijing", "Tehran", "Istanbul", "Rome"])
            self.play(ShowCreation(route), run_time=3)
```

```powershell
.venv\Scripts\python -m animai gallery\history_demo.py HistoryDemo -q medium --out renders
```

- **Narration:** `with self.voiceover(text):` synthesizes speech (edge-tts), plays it from
  the start of the block, and waits out whatever remains when the block ends. The timings
  become captions.
- **Layout:** `self.show(mob, "left")` scales a mobject into a named region and fades out
  whatever was shown there before. The regions are `main`, `left`, `right`, `top`,
  `bottom`, `stage`, `sidebar`, the four quadrants, and `full`.
- **Themes:** set `THEME` in the scene file. Components take their colors from
  `get_theme()` (`primary`, `secondary`, `accent`, `positive`, `negative`, `palette_color(i)`).
- **Gallery:** `gallery/` has one demo scene per subject. They double as visual tests.

## The engine

`manimlib/` is a local copy of [3b1b/manim](https://github.com/3b1b/manim) (master,
WebGPU renderer), used as-is. `animai/engine.py` and `animai/core/patches.py` work
around three problems found while building:

- On some Windows laptops with both AMD and NVIDIA graphics, `wgpu` crashes when it
  initializes every graphics backend at once. Animai selects Vulkan
  (`ANIMAI_GPU_BACKEND=auto|Vulkan|DX12|GL`).
- `color=` is silently ignored by `Dot`, `Circle`, `Text`, `Tex`, `Arrow` and others.
- The Tex parser breaks on `\;`, `\:` and `\!` followed by braces.

## Web app

```
topic ──▶ Claude (Sonnet 5.5) writes an Animai scene
            │
            ▼
      static checks ──▶ dry run ──▶ full render
            ▲                │ error      │ error
            └──── Claude repairs the file ◀┘   (up to 4 times)
                                          │ ok
                                          ▼
      frames at the end of each beat ──▶ Claude reviews the layout ──▶ polished re-render
```

The AI's API reference is generated from Animai's docstrings (`python -m animai.docs`),
so the prompt always matches the code.

### Setup (Windows)

```powershell
winget install Gyan.FFmpeg
winget install MiKTeX.MiKTeX
initexmf --set-config-value=[MPM]AutoInstall=1
miktex packages update
miktex packages install cm-super      # vector fonts; without it LaTeX renders blank

py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env                # add ANTHROPIC_API_KEY
.venv\Scripts\python -m backend       # http://127.0.0.1:8000
```

On macOS or Linux, install `ffmpeg` and a TeX distribution with your package manager.

### Cost

On Sonnet 5.5 at medium effort, a ~2-minute video costs about $0.40–0.80. The header
shows the running total. Set `CLAUDE_MODEL=claude-haiku-5-5` in `.env` for roughly 20×
cheaper (simpler) videos, or turn off the review pass under Options.

### Security note

The server runs Python generated by an AI model. `backend/validate.py` rejects imports
and builtins outside an allowlist, but that is a guardrail, not a sandbox. Keep the server
on localhost (the default), or run renders in a container before exposing it.

## Layout

```
animai/            the library
  core/            scene, themes, layout regions, narration, text/cards, icons, scaling
  subjects/        diagrams, data, cs, chemistry, physics, geography
  assets/          Natural Earth maps (public domain), Lucide icons (ISC)
  render.py        `python -m animai` render CLI
  docs.py          API reference generator
manimlib/          the engine (local copy of 3b1b/manim)
gallery/           demo scenes per subject
backend/           FastAPI app: Claude conversation, job pipeline, renderer
frontend/          single-page UI
```
