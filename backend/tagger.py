"""Search tags for a finished video, from its topic, title and narration.

New videos get tags from the TAGS line Claude writes into the scene; this is the
fallback when that line is missing.
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
