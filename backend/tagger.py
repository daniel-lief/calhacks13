"""Search tags for a finished video, from its topic, title and narration.

New videos get tags from the TAGS line Claude writes into the scene; this is the
fallback when that line is missing, and the way to (re)tag existing videos:

    .venv\\Scripts\\python -m backend.tagger            # tag videos that have none
    .venv\\Scripts\\python -m backend.tagger --all      # retag every video, samples included

Restart the server afterwards to pick up the new tags.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import anthropic
from pydantic import BaseModel

from . import config, prompts
from .validate import clean_tags


class _Tags(BaseModel):
    tags: list[str]


def narration_text(job_dir: Path) -> str:
    try:
        data = json.loads((job_dir / "timings.json").read_text(encoding="utf-8"))
        return " ".join(s["text"] for s in data.get("segments", []))
    except (OSError, ValueError, KeyError):
        return ""


def suggest_tags(topic: str, title: str | None, narration: str) -> list[str]:
    """Ranked tags (most relevant first), or [] if Claude can't be reached."""
    client = anthropic.Anthropic()
    try:
        response = client.messages.parse(
            model=config.CLAUDE_MODEL,
            max_tokens=2000,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompts.tag_request(topic, title, narration)}],
            output_format=_Tags,
        )
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
        print(f"Tagging failed for “{topic}”: {exc}", file=sys.stderr)
        return []
    if response.stop_reason == "refusal" or response.parsed_output is None:
        return []
    return clean_tags(response.parsed_output.tags)


def _retag(path: Path, force: bool) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "done" or (data.get("tags") and not force):
        return
    tags = suggest_tags(data["topic"], data.get("title"), narration_text(path.parent))
    if not tags:
        print(f"{path.parent.name}: no tags returned, left unchanged")
        return
    data["tags"] = tags
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)
    print(f"{path.parent.name}: {data.get('title') or data['topic']} -> {', '.join(tags)}")


if __name__ == "__main__":
    force = "--all" in sys.argv[1:]
    samples = list(config.SAMPLES_DIR.glob("*/job.json"))
    sample_ids = {p.parent.name for p in samples}
    # A promoted video also has its original under data/jobs; the sample copy is the one shown
    own = [p for p in config.JOBS_DIR.glob("*/job.json") if p.parent.name not in sample_ids]
    for job_json in own + samples:
        _retag(job_json, force)
