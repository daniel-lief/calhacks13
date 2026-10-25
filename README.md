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

THEME = "bubble"  # Default Figma identity; legacy themes remain opt-in


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
- `Succession` puts every later step's objects on screen, fully drawn, before those steps
  start. This shows up as a finished diagram flashing, disappearing, then animating in.
- Grouped animations split apart any component whose parts they animate, so parts added
  to it later never appear.

## Visual style

The default `bubble` theme follows the Figma **THE IMAGE** frame: Fredoka SemiBold
(600 weight, 100 width), JetBrains Mono Regular code, a vertical `#F5D9C8` → `#FEEAE0`
peach gradient, `#583F41` text, `#EF7D99` accents, cream `#FBF5F2` cards and the
reference's six pastel series colors. Panels are borderless with centered black 7%
shadows (the 7.9px blur is approximated with vector feather layers). Rounded bars have
square bases, counters use blush pills, and scientific figures share the same palette.
Math and chemical formulas retain TeX's notation font for correct typesetting.

`AnimaiScene.show()` gives diagrams a cream presentation card and removes it with the
diagram; components with their own panels are not double-framed. `StatPill(label, value)`
adds the reference's two-color counters and supports animated `set_value(value)`.
The backend prompt requires this identity for every subject. Existing MP4 files are
unchanged; regenerate them or render their saved source with `--theme bubble`.

Raw Figma floats, font axes, effects and radii are recorded in
`animai/assets/figma-style-reference.json`. Theme hex colors are the nearest 8-bit sRGB
representations. Fredoka and JetBrains Mono are bundled with their OFL licenses.

Preview and regression scenes:

```powershell
.venv\Scripts\python -m animai gallery\bubble_style_demo.py BubbleStyleDemo -q medium --no-narration --out renders
.venv\Scripts\python -m animai gallery\bubble_style_check.py BubbleStyleCheck --dry-run --out renders\checks
```

In **New video → Options → Color theme**, choose Peach (the default), Ocean, Meadow,
Lavender, Rose, or Sand. These palettes change backgrounds, text, panels, charts,
diagrams, scientific figures, and code highlighting while keeping the same fonts,
shapes, shadows, and layout. The choice is saved with the job and retained through
repairs and review. Palette tokens live in `animai/assets/video-themes.json`.
For hand-written scenes, set `THEME` to `bubble`, `ocean`, `meadow`, `lavender`,
`rose`, or `sand`, or pass e.g. `--theme ocean` to the render command.

Legacy CLI themes each pair a font with a palette and a subtle backdrop (a soft vignette, or a fine
grid for `blueprint`). Cards, nodes and cells are raised panels with soft shadows, and
`show()` enlarges diagrams and charts to fill their region. The fonts (Fira Sans, Fira
Mono, Crimson Text and Patrick Hand, all under the SIL Open Font License) ship in
`animai/assets/fonts`. The render launcher installs them for the current user the first
time it runs (`python -m animai.fonts` does it by hand). They are installed rather than
loaded in-process because Pango's in-process font registration makes every text render
about 10 seconds slower on Windows.

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
  assets/          Natural Earth maps (public domain), Lucide icons (ISC), fonts (OFL)
  render.py        `python -m animai` render CLI
  docs.py          API reference generator
manimlib/          the engine (local copy of 3b1b/manim)
gallery/           demo scenes per subject
backend/           FastAPI app: Claude conversation, job pipeline, renderer
frontend/          single-page UI
```
