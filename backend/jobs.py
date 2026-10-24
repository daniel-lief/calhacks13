"""Job store and the topic -> video pipeline."""
from __future__ import annotations

import json
import shutil
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import config
from .generator import GenerationError, SceneAuthor
from .renderer import extract_frames, make_thumbnail, render_scene, write_vtt
from .validate import check_scene, count_voiceovers, extract_title

ACTIVE_STATUSES = {"queued", "writing", "checking", "rendering", "reviewing"}
MAX_LOG_ENTRIES = 300


@dataclass
class JobOptions:
    length: str = "medium"      # short | medium | long
    quality: str = "medium"     # low | medium | high
    narration: bool = True
    review: bool = True
    extra: str = ""


@dataclass
class Job:
    id: str
    topic: str
    options: JobOptions
    status: str = "queued"
    stage: str = "Waiting in queue"
    progress: float = 0.0
    title: str | None = None
    attempts: int = 0
    error: str | None = None
    has_video: bool = False
    has_captions: bool = False
    has_thumbnail: bool = False
    model: str = ""
    cost_usd: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    logs: list[dict] = field(default_factory=list)
    public: bool = False        # shown in the feed once it's done
    sample: bool = False        # pre-made post from backend/samples (read-only)

    @property
    def dir(self) -> Path:
        return (config.SAMPLES_DIR if self.sample else config.JOBS_DIR) / self.id

    def to_dict(self, include_logs: bool = True) -> dict:
        data = asdict(self)
        if not include_logs:
            data.pop("logs")
        media = f"/{'samples' if self.sample else 'media'}/{self.id}"
        data["video_url"] = f"{media}/video.mp4?v={int(self.updated_at)}" if self.has_video else None
        data["captions_url"] = f"{media}/captions.vtt?v={int(self.updated_at)}" if self.has_captions else None
        data["thumbnail_url"] = f"{media}/thumbnail.jpg" if self.has_thumbnail else None
        data["code_url"] = f"{media}/scene.py" if (self.dir / "scene.py").exists() else None
        return data


class PipelineFailure(Exception):
    pass


class JobManager:
    def __init__(self):
        config.JOBS_DIR.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_JOBS,
                                        thread_name_prefix="job")
        self._stats: dict[str, dict] = {}
        self._load_existing()
        self._load_samples()
        self._load_stats()

    # --- store ---------------------------------------------------------------

    @staticmethod
    def _read(path: Path) -> Job | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["options"] = JobOptions(**data.get("options", {}))
            return Job(**data)
        except Exception:
            return None

    def _load_existing(self):
        for path in config.JOBS_DIR.glob("*/job.json"):
            job = self._read(path)
            if not job:
                continue
            if job.status in ACTIVE_STATUSES:
                job.status = "failed"
                job.error = "The server restarted while this video was being made."
            self._jobs[job.id] = job

    def _load_samples(self):
        for path in config.SAMPLES_DIR.glob("*/job.json"):
            job = self._read(path)
            if job and job.status == "done":
                job.sample = job.public = True
                self._jobs[job.id] = job

    def _load_stats(self):
        try:
            self._stats = json.loads(config.STATS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._stats = {}

    def _save_stats(self):
        tmp = config.STATS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._stats), encoding="utf-8")
        tmp.replace(config.STATS_PATH)

    def _save(self, job: Job):
        job.updated_at = time.time()
        job.dir.mkdir(parents=True, exist_ok=True)
        tmp = job.dir / "job.json.tmp"
        tmp.write_text(json.dumps(asdict(job), indent=2), encoding="utf-8")
        tmp.replace(job.dir / "job.json")

    def create(self, topic: str, options: JobOptions, public: bool = False) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], topic=topic, options=options, public=public)
        with self._lock:
            self._jobs[job.id] = job
            self._save(job)
        self._pool.submit(self._run, job)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        """The user's own videos, newest first (samples aren't theirs)."""
        return sorted((j for j in self._jobs.values() if not j.sample),
                      key=lambda j: j.created_at, reverse=True)

    def feed(self) -> list[Job]:
        """Finished public posts, newest first."""
        return sorted((j for j in self._jobs.values() if j.public and j.status == "done" and j.has_video),
                      key=lambda j: j.created_at, reverse=True)

    def serialize(self, job: Job, include_logs: bool = True) -> dict:
        data = job.to_dict(include_logs=include_logs)
        stats = self._stats.get(job.id, {})
        data["likes"] = stats.get("likes", 0)
        data["views"] = stats.get("views", 0)
        return data

    def set_public(self, job_id: str, public: bool) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.sample:
                return None
            job.public = public
            self._save(job)
        return job

    def like(self, job_id: str, liked: bool) -> bool:
        with self._lock:
            if job_id not in self._jobs:
                return False
            stats = self._stats.setdefault(job_id, {})
            stats["likes"] = max(0, stats.get("likes", 0) + (1 if liked else -1))
            self._save_stats()
        return True

    def view(self, job_id: str) -> bool:
        with self._lock:
            if job_id not in self._jobs:
                return False
            stats = self._stats.setdefault(job_id, {})
            stats["views"] = stats.get("views", 0) + 1
            self._save_stats()
        return True

    def queue_position(self, job: Job) -> int:
        queued = sorted((j for j in self._jobs.values() if j.status == "queued"),
                        key=lambda j: j.created_at)
        return next((i for i, j in enumerate(queued) if j.id == job.id), -1) + 1

    def delete(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.sample or job.status in ACTIVE_STATUSES:
                return False
            del self._jobs[job_id]
            if self._stats.pop(job_id, None) is not None:
                self._save_stats()
        shutil.rmtree(job.dir, ignore_errors=True)
        return True

    # --- pipeline ------------------------------------------------------------

    def _update(self, job: Job, *, log: str | None = None, kind: str = "info", **fields):
        with self._lock:
            for key, value in fields.items():
                setattr(job, key, value)
            if log:
                job.logs.append({"t": round(time.time() - job.created_at, 1), "kind": kind, "msg": log})
                del job.logs[:-MAX_LOG_ENTRIES]
            self._save(job)

    def _run(self, job: Job):
        try:
            self._pipeline(job)
        except (PipelineFailure, GenerationError) as exc:
            self._update(job, status="failed", stage="Failed", error=str(exc),
                         finished_at=time.time(), log=str(exc), kind="error")
        except Exception as exc:  # Unexpected bug: record it rather than leave the job hanging
            traceback.print_exc()
            self._update(job, status="failed", stage="Failed", error=f"Internal error: {exc}",
                         finished_at=time.time(), log=traceback.format_exc(limit=3), kind="error")

    def _pipeline(self, job: Job):
        opts = job.options

        def on_event(kind: str, text: str):
            if kind == "thinking":
                self._update(job, log=text, kind="thinking")
            elif kind == "usage":
                self._update(job, log=text, cost_usd=round(author.cost_usd, 4))
            else:
                self._update(job, stage=text)

        author = SceneAuthor(on_event)
        self._update(job, model=config.CLAUDE_MODEL)
        self._update(job, status="writing", stage="Claude is planning the video…", progress=0.03,
                     log=f"Planning an explanation of “{job.topic}”")
        code = author.write(job.topic, opts.length, opts.extra)
        self._update(job, title=extract_title(code), progress=0.25,
                     log=f"Scene written: {count_voiceovers(code)} narrated beats")

        code, render = self._build(job, author, code, budget=config.MAX_REPAIR_ATTEMPTS,
                                   progress_span=(0.25, 0.85 if opts.review else 0.97))
        self._publish(job, code, render)

        if opts.review:
            self._review(job, author, code)

        self._update(job, status="done", stage="Done", progress=1.0, finished_at=time.time(),
                     log="Video ready")

    def _build(self, job: Job, author: SceneAuthor, code: str, *, budget: int,
               progress_span: tuple[float, float]):
        """Validate, dry-run and render, asking Claude to repair failures. Returns (code, render)."""
        lo, hi = progress_span
        for attempt in range(budget + 1):
            n = job.attempts = job.attempts + 1
            scene_path = job.dir / "work" / f"scene_v{n}.py"
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            scene_path.write_text(code, encoding="utf-8")

            stage, problem = "static checks", check_scene(code)
            if not problem:
                self._update(job, status="checking", stage="Test-running the scene code…",
                             log=f"Attempt {n}: dry run")
                dry = render_scene(scene_path, job.dir / "work" / f"dry_v{n}", dry_run=True)
                stage, problem = "a dry run of the scene", (None if dry.ok else dry.error)
            if not problem:
                total = max(count_voiceovers(code), 1)

                def on_segment(i: int):
                    frac = min((i + 1) / total, 1.0)
                    self._update(job, progress=lo + (hi - lo) * frac,
                                 stage=f"Rendering beat {i + 1}" + (f" of {total}" if i < total else ""))

                self._update(job, status="rendering", stage="Rendering animation…", progress=lo,
                             log=f"Attempt {n}: rendering at {job.options.quality} quality")
                render = render_scene(scene_path, job.dir / "work" / f"render_v{n}",
                                      quality=job.options.quality, narration=job.options.narration,
                                      on_segment=on_segment)
                for w in render.warnings:
                    self._update(job, log=w, kind="warning")
                if render.ok:
                    return code, render
                stage, problem = "the full render", render.error

            first_line = problem.strip().splitlines()[-1] if problem.strip() else "unknown error"
            self._update(job, log=f"Attempt {n} failed in {stage}: {first_line}", kind="error")
            if attempt == budget:
                raise PipelineFailure(f"Couldn't produce a working scene after {n} attempts. "
                                      f"Last error ({stage}): {first_line}")
            self._update(job, status="writing", stage="Claude is fixing an error…",
                         log="Asking Claude to fix it")
            code = author.repair(problem, stage)
        raise AssertionError("unreachable")

    def _publish(self, job: Job, code: str, render):
        shutil.copyfile(render.output_path, job.dir / "video.mp4")
        (job.dir / "scene.py").write_text(code, encoding="utf-8")
        has_captions = False
        if render.timings_path:
            shutil.copyfile(render.timings_path, job.dir / "timings.json")
            if job.options.narration:
                write_vtt(render.timings_path, job.dir / "captions.vtt")
                has_captions = True
        make_thumbnail(job.dir / "video.mp4", render.timings_path, job.dir / "thumbnail.jpg")
        self._update(job, has_video=True, has_captions=has_captions,
                     has_thumbnail=(job.dir / "thumbnail.jpg").exists(), title=extract_title(code))

    def _review(self, job: Job, author: SceneAuthor, code: str):
        self._update(job, status="reviewing", stage="Claude is reviewing the frames…", progress=0.86,
                     log="First cut ready — reviewing frames for layout problems")
        frames = extract_frames(job.dir / "video.mp4", job.dir / "timings.json",
                                job.dir / "work" / f"frames_v{job.attempts}")
        if not frames:
            self._update(job, log="No frames to review; keeping the first cut", kind="warning")
            return
        revised = author.review(frames)
        if revised is None:
            self._update(job, log="Review passed with no changes")
            return
        self._update(job, log="Review found issues; re-rendering a polished cut")
        try:
            revised, render = self._build(job, author, revised, budget=2, progress_span=(0.88, 0.99))
        except PipelineFailure as exc:
            self._update(job, log=f"Polished cut failed ({exc}); keeping the first cut", kind="warning")
            return
        self._publish(job, revised, render)
        self._update(job, log="Polished cut published")
