"""
Rendering a scene file with the local engine.

Command line:
    python -m animai path/to/scene.py SceneName [-q low|medium|high] [--theme NAME]
                     [--out DIR] [--dry-run] [--no-narration]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from animai import fonts, tools
from animai.themes import THEMES

ROOT = Path(__file__).resolve().parent.parent  # Folder holding animai/ and manimlib/
QUALITY_FLAGS = {"low": "-l", "medium": "-m", "high": "--hd", "4k": "--uhd"}
THEME_RE = re.compile(r'^THEME\s*=\s*["\'](\w+)["\']', re.MULTILINE)
CACHE_DIR = Path(os.getenv("ANIMAI_CACHE", Path.home() / ".animai"))


def detect_theme(scene_path: Path) -> str:
    match = THEME_RE.search(scene_path.read_text(encoding="utf-8"))
    return match.group(1) if match and match.group(1) in THEMES else "bubble"


def write_engine_config(path: Path, theme_name: str) -> Path:
    """ManimGL reads default colors and fonts at import time, so they go in its config file."""
    t = THEMES[theme_name]
    light = t.light
    config = {
        "directories": {"latex_cache": str(CACHE_DIR / "latex")},
        "camera": {"background_color": t.background},
        "mobject": {"default_mobject_color": t.text, "default_light_color": t.muted},
        "vmobject": {"default_stroke_color": t.text if light else "#DDDDDD",
                     "default_fill_color": t.muted},
        "file_writer": {"ffmpeg_bin": tools.ffmpeg_bin()},
        "text": {"font": t.font, "alignment": "CENTER", "weight": t.text_weight},
    }
    # JSON is valid YAML, which spares a dependency on a YAML writer
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


def render_command(scene_path: Path, scene_name: str, out_dir: Path, *, quality: str = "medium",
                   dry_run: bool = False, file_name: str | None = None,
                   theme: str | None = None) -> tuple[list[str], dict[str, str]]:
    """The command and environment that render `scene_name` from `scene_path` into `out_dir`."""
    scene_path, out_dir = scene_path.resolve(), out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    fonts.ensure_installed()
    theme = theme or detect_theme(scene_path)
    cfg = write_engine_config(out_dir / "engine_config.yml", theme)

    cmd = [sys.executable, "-m", "manimlib", str(scene_path), scene_name,
           "-w", QUALITY_FLAGS.get(quality, "-m"), "--video_dir", str(out_dir),
           "--config_file", str(cfg)]
    if file_name:
        cmd += ["--file_name", file_name]
    if dry_run:
        cmd.append("-s")

    env = tools.tool_env()
    env.update({
        "PYTHONPATH": os.pathsep.join([str(ROOT), env.get("PYTHONPATH", "")]),
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONWARNINGS": "ignore",
        "ANIMAI_THEME": theme,
        "ANIMAI_AUDIO_CACHE": env.get("ANIMAI_AUDIO_CACHE", str(CACHE_DIR / "audio")),
    })
    if dry_run:
        env["ANIMAI_NARRATION"] = "0"
    return cmd, env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m animai", description="Render an Animai scene")
    parser.add_argument("file", type=Path)
    parser.add_argument("scene")
    parser.add_argument("-q", "--quality", default="medium", choices=list(QUALITY_FLAGS))
    parser.add_argument("--theme", choices=list(THEMES))
    parser.add_argument("--out", type=Path, default=Path("renders"))
    parser.add_argument("--dry-run", action="store_true", help="Run the code, save only the last frame")
    parser.add_argument("--no-narration", action="store_true")
    parser.add_argument("--file-name", help="Output file name without extension (default: scene name)")
    args = parser.parse_args(argv)

    cmd, env = render_command(args.file, args.scene, args.out, quality=args.quality,
                              dry_run=args.dry_run, theme=args.theme, file_name=args.file_name)
    if args.no_narration:
        env["ANIMAI_NARRATION"] = "0"
    return subprocess.call(cmd, env=env, cwd=args.out.resolve())


if __name__ == "__main__":
    sys.exit(main())
