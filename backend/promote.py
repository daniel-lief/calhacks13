"""Copy finished videos into backend/samples/ so they ship with the repo as public feed posts.

    .venv\\Scripts\\python -m backend.promote <job_id> [<job_id> ...]

Restart the server afterwards to load them.
"""
from __future__ import annotations

import json
import shutil
import sys

from . import config

FILES = ("video.mp4", "thumbnail.jpg", "captions.vtt", "scene.py", "timings.json")


def promote(job_id: str) -> None:
    src = config.JOBS_DIR / job_id
    data = json.loads((src / "job.json").read_text(encoding="utf-8"))
    if data.get("status") != "done" or not data.get("has_video"):
        raise SystemExit(f"{job_id}: not a finished video (status: {data.get('status')})")
    dst = config.SAMPLES_DIR / job_id
    dst.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        if (src / name).exists():
            shutil.copyfile(src / name, dst / name)
    data.update(public=True, sample=True, logs=[])
    (dst / "job.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"{job_id}: {data.get('title') or data['topic']} -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for job_id in sys.argv[1:]:
        promote(job_id)
