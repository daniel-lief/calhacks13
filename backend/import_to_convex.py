"""One-off import of the pre-Convex videos into Convex.

    .venv\\Scripts\\python -m backend.import_to_convex                  # the six samples, as @animai
    .venv\\Scripts\\python -m backend.import_to_convex --owner bryce    # ...plus data/jobs videos, as @bryce

The owner must have signed up on the site first. Safe to re-run: videos already
imported for that owner are skipped.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config
from .convex_api import Convex
from .jobs import UPLOADS


def _load(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if data.get("status") != "done" or not data.get("has_video"):
        return None
    return data


def _import(convex: Convex, owner: str, folder: Path, data: dict, views: int) -> str:
    files = {}
    for key, (name, content_type) in UPLOADS.items():
        if (folder / name).exists():
            files[key] = convex.upload(folder / name, content_type)
    options = data.get("options", {})
    video = {
        "topic": data["topic"],
        "options": {
            "length": options.get("length", "medium"),
            "quality": options.get("quality", "medium"),
            "narration": bool(options.get("narration", True)),
            "review": bool(options.get("review", True)),
            "extra": options.get("extra", ""),
            "voice": options.get("voice", ""),
        },
        "tags": data.get("tags", []),
        "chapters": [{"start": float(c["start"]), "title": c["title"]} for c in data.get("chapters", [])],
        "public": bool(data.get("public", False)),
        "views": int(views),
        "costUsd": float(data.get("cost_usd", 0.0)),
        "files": files,
    }
    if data.get("title"):
        video["title"] = data["title"]
    if data.get("model"):
        video["model"] = data["model"]
    result = convex.mutation("worker:importVideo", {"ownerUsername": owner, "video": video})
    return "skipped (already imported)" if result["skipped"] else "imported"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--owner", help="username to own the videos in data/jobs (sign up first)")
    args = parser.parse_args(argv)
    if not (config.CONVEX_URL and config.WORKER_SECRET):
        print("Set CONVEX_URL and WORKER_SECRET in backend/.env.local first.", file=sys.stderr)
        return 1
    convex = Convex(config.CONVEX_URL, config.WORKER_SECRET)
    try:
        stats = json.loads(config.STATS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stats = {}

    batches = [("animai", sorted(config.SAMPLES_DIR.glob("*/job.json")))]
    if args.owner:
        sample_ids = {p.parent.name for p in batches[0][1]}
        own = [p for p in config.JOBS_DIR.glob("*/job.json") if p.parent.name not in sample_ids]
        batches.append((args.owner, own))

    for owner, paths in batches:
        loaded = [(p.parent, d) for p in paths if (d := _load(p))]
        loaded.sort(key=lambda item: item[1].get("created_at", 0))  # oldest first, so the newest stays newest
        for folder, data in loaded:
            views = stats.get(folder.name, {}).get("views", 0)
            outcome = _import(convex, owner, folder, data, views)
            print(f"@{owner}: {data.get('title') or data['topic']} -> {outcome}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
