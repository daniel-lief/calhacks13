"""Chapters for a finished video: its narration grouped into a few titled parts.

New videos get chapters when they're published; this also (re)builds them for
existing videos:

    .venv\\Scripts\\python -m backend.chapters            # videos that have none
    .venv\\Scripts\\python -m backend.chapters --all      # every video, samples included

Stop the server first and restart it afterwards, so it picks up the new chapters.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import anthropic
from pydantic import BaseModel

from . import config, prompts

MAX_TITLE_LENGTH = 40


class _Chapter(BaseModel):
    title: str
    first_line: int


class _Chapters(BaseModel):
    chapters: list[_Chapter]


def narration_segments(job_dir: Path) -> list[dict]:
    try:
        return json.loads((job_dir / "timings.json").read_text(encoding="utf-8")).get("segments", [])
    except (OSError, ValueError):
        return []


def clean_chapters(raw: list[_Chapter], segments: list[dict]) -> list[dict]:
    """[{start, title}] in order, starting at 0:00, one per distinct first line."""
    by_line: dict[int, str] = {}
    for ch in raw:
        title = " ".join(ch.title.split())[:MAX_TITLE_LENGTH].strip()
        if title and 0 <= ch.first_line < len(segments):
            by_line.setdefault(ch.first_line, title)
    if not by_line:
        return []
    if 0 not in by_line:   # the first chapter always starts the video
        first = min(by_line)
        by_line[0] = by_line.pop(first)
    return [{"start": round(float(segments[i]["start"]), 2), "title": by_line[i]} for i in sorted(by_line)]


def suggest_chapters(topic: str, title: str | None, segments: list[dict]) -> list[dict]:
    """A few titled chapters, or [] if there's too little narration or Claude can't be reached."""
    if len(segments) < 3:
        return []
    client = anthropic.Anthropic()
    try:
        response = client.messages.parse(
            model=config.CLAUDE_MODEL,
            max_tokens=2000,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompts.chapter_request(topic, title, [s["text"] for s in segments])}],
            output_format=_Chapters,
        )
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
        print(f"Chapters failed for “{topic}”: {exc}", file=sys.stderr)
        return []
    if response.stop_reason == "refusal" or response.parsed_output is None:
        return []
    return clean_chapters(response.parsed_output.chapters, segments)


def _rebuild(path: Path, force: bool) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "done" or (data.get("chapters") and not force):
        return
    chapters = suggest_chapters(data["topic"], data.get("title"), narration_segments(path.parent))
    if not chapters:
        print(f"{path.parent.name}: no chapters returned, left unchanged")
        return
    data["chapters"] = chapters
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)
    summary = ", ".join(f"{int(c['start']) // 60}:{int(c['start']) % 60:02d} {c['title']}" for c in chapters)
    print(f"{path.parent.name}: {data.get('title') or data['topic']} -> {summary}")


if __name__ == "__main__":
    force = "--all" in sys.argv[1:]
    samples = list(config.SAMPLES_DIR.glob("*/job.json"))
    sample_ids = {p.parent.name for p in samples}
    # A promoted video also has its original under data/jobs; the sample copy is the one shown
    own = [p for p in config.JOBS_DIR.glob("*/job.json") if p.parent.name not in sample_ids]
    for job_json in own + samples:
        _rebuild(job_json, force)
