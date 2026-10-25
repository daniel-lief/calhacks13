"""Renders generated scene files with Animai (`python -m animai`) in a subprocess."""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import config

SEGMENT_RE = re.compile(r"@@SEGMENT (\d+)")
TTS_FAILED_RE = re.compile(r"@@TTS_FAILED (.*)")
WARNING_RE = re.compile(r"@@WARNING (.*)")
# Lines worth surfacing when a render fails without a Python traceback
ERROR_HINT_RE = re.compile(r"error|exception|failed", re.IGNORECASE)
# Traceback frames from the launcher and engine entry points, which bury the scene's own lines
LAUNCHER_FRAME_RE = re.compile(
    r'\n  File "(?:<frozen runpy>|[^"]*(?:animlib[\\/](?:__main__|scene[\\/]scene)|animai[\\/](?:__main__|render))\.py)"[^\n]*\n[^\n]*')
PROGRESS_LINE_RE = re.compile(r"\n(?:Writing|Rendering) [^\n]*")


@dataclass
class RenderResult:
    ok: bool
    output_path: Path | None = None
    timings_path: Path | None = None
    error: str = ""
    warnings: list[str] = field(default_factory=list)


def _extract_error(lines: list[str], scene_path: Path) -> str:
    text = "\n".join(lines)
    idx = text.rfind("Traceback (most recent call last)")
    if idx != -1:
        error = text[idx:]
    else:
        hints = [ln for ln in lines if ERROR_HINT_RE.search(ln)]
        error = "\n".join(hints[-15:] or lines[-30:])
    # Trim launcher frames and long paths so the scene's own lines stand out
    error = LAUNCHER_FRAME_RE.sub("", error)
    error = PROGRESS_LINE_RE.sub("", error)
    for path, short in ((scene_path, "scene.py"), (config.ROOT, "")):
        error = re.sub(re.escape(str(path)), lambda _: short, error, flags=re.IGNORECASE)
    return error[-6000:].strip()


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill the animai CLI and the engine process it started."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def render_scene(
    scene_path: Path,
    out_dir: Path,
    *,
    quality: str = "medium",
    dry_run: bool = False,
    narration: bool = True,
    voice: str = "",
    theme: str = "bubble",
    on_segment: Callable[[int], None] | None = None,
) -> RenderResult:
    """
    Render `Explainer` from `scene_path` into `out_dir`.

    A dry run skips animation frames and only saves the final frame; it executes all
    scene code, so it catches most errors in a fraction of the time.
    """
    scene_path, out_dir = scene_path.resolve(), out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    timings = out_dir / "timings.json"
    timings.unlink(missing_ok=True)

    cmd = [sys.executable, "-m", "animai", str(scene_path), "Explainer", "-q", quality,
           "--out", str(out_dir), "--file-name", "explainer", "--theme", theme]
    if dry_run:
        cmd.append("--dry-run")
    if not narration:
        cmd.append("--no-narration")

    env = config.tool_env()
    env.update({
        "PYTHONPATH": os.pathsep.join([str(config.ROOT), env.get("PYTHONPATH", "")]),
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONWARNINGS": "ignore",
        "ANIMAI_VOICE": voice or config.TTS_VOICE,
        "ANIMAI_AUDIO_CACHE": str(config.AUDIO_CACHE_DIR),
        "ANIMAI_TIMINGS": str(timings),
    })

    proc = subprocess.Popen(
        cmd, cwd=out_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        start_new_session=sys.platform != "win32",
    )
    timed_out = threading.Event()

    def _kill():
        timed_out.set()
        _kill_tree(proc)

    timer = threading.Timer(config.RENDER_TIMEOUT_SECONDS, _kill)
    timer.start()
    lines: deque[str] = deque(maxlen=400)
    warnings: list[str] = []
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip()
            if not line:
                continue
            if m := SEGMENT_RE.search(line):
                if on_segment:
                    on_segment(int(m.group(1)))
                continue
            if m := TTS_FAILED_RE.search(line):
                warnings.append(f"Narration unavailable, rendering silently: {m.group(1)}")
                continue
            if m := WARNING_RE.search(line):
                warnings.append(m.group(1))
                continue
            lines.append(line)
        proc.wait()
    finally:
        timer.cancel()

    if timed_out.is_set():
        return RenderResult(False, error=f"Render timed out after {config.RENDER_TIMEOUT_SECONDS}s. "
                                         "The scene is probably too long or too expensive to draw.",
                            warnings=warnings)

    output = out_dir / ("explainer.png" if dry_run else "explainer.mp4")
    if proc.returncode != 0 or not output.exists():
        return RenderResult(False, error=_extract_error(list(lines), scene_path) or
                            f"manimgl exited with code {proc.returncode}", warnings=warnings)
    return RenderResult(True, output_path=output,
                        timings_path=timings if timings.exists() else None, warnings=warnings)


def write_vtt(timings_path: Path, vtt_path: Path) -> None:
    """Convert segment timings from the scene runtime into WebVTT captions."""
    data = json.loads(timings_path.read_text(encoding="utf-8"))

    def ts(seconds: float) -> str:
        ms = int(round(seconds * 1000))
        h, ms = divmod(ms, 3_600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    cues = ["WEBVTT", ""]
    for seg in data.get("segments", []):
        for i, (start, end, text) in enumerate(_split_caption(seg)):
            cues += [f"{seg['index'] + 1}.{i + 1}", f"{ts(start)} --> {ts(end)}", text, ""]
    vtt_path.write_text("\n".join(cues), encoding="utf-8")


def _split_caption(seg: dict, max_chars: int = 90):
    """Split long narration into sentence-sized cues spread over the speech time."""
    text, start, end = seg["text"], seg["start"], seg.get("speech_end", seg["end"])
    parts = [p for p in re.split(r"(?<=[.!?])\s+", text) if p]
    chunks: list[str] = []
    for part in parts:
        if chunks and len(chunks[-1]) + len(part) + 1 <= max_chars:
            chunks[-1] += " " + part
        else:
            chunks.append(part)
    total = sum(len(c) for c in chunks) or 1
    t = start
    for chunk in chunks:
        dur = (end - start) * len(chunk) / total
        yield t, t + dur, chunk
        t += dur


def extract_frames(video: Path, timings_path: Path | None, out_dir: Path, max_frames: int = 10):
    """Grab a still at the end of each narrated beat. Returns [(seconds, path, narration)]."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if timings_path and timings_path.exists():
        segments = json.loads(timings_path.read_text(encoding="utf-8")).get("segments", [])
        points = [(max(s["end"] - 0.15, 0), s["text"]) for s in segments]
    else:
        points = []
    if len(points) > max_frames:
        step = len(points) / max_frames
        points = [points[int(i * step)] for i in range(max_frames - 1)] + [points[-1]]

    frames = []
    for i, (t, text) in enumerate(points):
        path = out_dir / f"frame_{i:02d}.jpg"
        subprocess.run(
            [config.ffmpeg_bin(), "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video),
             "-frames:v", "1", "-vf", "scale=960:-2", "-q:v", "4", str(path)],
            env=config.tool_env(), capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if path.exists():
            frames.append((t, path, text))
    return frames


def make_thumbnail(video: Path, timings_path: Path | None, out: Path) -> None:
    t = 1.0
    if timings_path and timings_path.exists():
        segments = json.loads(timings_path.read_text(encoding="utf-8")).get("segments", [])
        if len(segments) > 1:
            t = segments[min(2, len(segments) - 1)]["end"] - 0.2
    subprocess.run(
        [config.ffmpeg_bin(), "-loglevel", "error", "-y", "-ss", f"{max(t, 0):.2f}", "-i", str(video),
         "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "5", str(out)],
        env=config.tool_env(), capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
