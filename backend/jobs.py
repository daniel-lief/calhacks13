"""The topic -> video pipeline. Each job comes from Convex (claimed by backend/worker.py);
progress, logs and the finished files go back to Convex. Scratch files live under
DATA_DIR/work/<id> and are deleted when the job ends."""
from __future__ import annotations

import shutil
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from . import attachments, config
from .chapters import narration_segments, suggest_chapters
from .generator import GenerationError, SceneAuthor
from .research import ResearchResult, research_topic
from .renderer import extract_frames, make_thumbnail, render_scene, write_vtt
from .tagger import narration_text, suggest_tags
from .themes import theme_name
from .validate import apply_scene_theme, check_scene, count_voiceovers, extract_tags, extract_title

LOST_PDF = "The attached PDF was lost when the server restarted. Please try again."

# Field names the pipeline uses -> names in the Convex videos table
CONVEX_FIELDS = {"cost_usd": "costUsd", "finished_at": "finishedAt"}
UPLOADS = {
    "video": ("video.mp4", "video/mp4"),
    "thumbnail": ("thumbnail.jpg", "image/jpeg"),
    "captions": ("captions.vtt", "text/vtt"),
    "timings": ("timings.json", "application/json"),
    "code": ("scene.py", "text/x-python"),
}


@dataclass
class JobOptions:
    length: str = "medium"      # short | medium | long
    quality: str = "medium"     # low | medium | high
    narration: bool = True
    voice: str = ""             # edge-tts voice name; "" means the server default (TTS_VOICE)
    review: bool = True
    extra: str = ""
    theme: str = "bubble"
    research: bool = True


@dataclass
class Job:
    id: str
    topic: str
    options: JobOptions
    attempts: int = 0
    title: str | None = None
    tags: list[str] = field(default_factory=list)
    started: float = field(default_factory=time.time)
    pdf: bytes | None = None    # private context; only ever in memory, and never logged
    research: dict = field(default_factory=dict)

    @property
    def dir(self) -> Path:
        return config.DATA_DIR / "work" / self.id


class PipelineFailure(Exception):
    pass


class JobManager:
    """Runs one claimed job at a time, reporting to Convex through `convex`."""

    def __init__(self, convex):
        self.convex = convex

    def run(self, claimed: dict) -> None:
        opts = {k: v for k, v in claimed.get("options", {}).items() if k in JobOptions.__dataclass_fields__}
        job = Job(id=claimed["id"], topic=claimed["topic"], options=JobOptions(**opts),
                  attempts=int(claimed.get("attempts") or 0))
        job.dir.mkdir(parents=True, exist_ok=True)
        try:
            if claimed.get("attachment"):
                job.pdf = attachments.take(claimed["attachment"])
                if job.pdf is None:
                    raise PipelineFailure(LOST_PDF)
            self._pipeline(job)
        except (PipelineFailure, GenerationError) as exc:
            self._report_failure(job, str(exc), str(exc))
        except Exception as exc:  # Unexpected bug (or Convex unreachable): record it if we can
            traceback.print_exc()
            self._report_failure(job, f"Internal error: {exc}", traceback.format_exc(limit=3))
        finally:
            shutil.rmtree(job.dir, ignore_errors=True)

    def _report_failure(self, job: Job, error: str, log: str):
        """Best effort: if Convex can't be reached either, the worker's next startup marks it failed."""
        try:
            self._update(job, status="failed", stage="Failed", error=error,
                         finished_at=time.time(), log=log, kind="error")
        except Exception:
            traceback.print_exc()

    # --- reporting -------------------------------------------------------------

    def _update(self, job: Job, *, log: str | None = None, kind: str = "info", **fields):
        for key in ("title", "tags", "attempts"):
            if key in fields:
                setattr(job, key, fields[key])
        sent = {}
        for key, value in fields.items():
            if value is None:
                continue
            if key == "finished_at":
                value = value * 1000  # Convex timestamps are milliseconds
            sent[CONVEX_FIELDS.get(key, key)] = value
        args = {"id": job.id, "fields": sent}
        if log:
            args["log"] = {"t": round(time.time() - job.started, 1), "kind": kind, "msg": log}
        self.convex.mutation("worker:update", args)

    # --- pipeline --------------------------------------------------------------

    def _pipeline(self, job: Job):
        opts = job.options
        research = self._research(job)

        def on_event(kind: str, text: str):
            if kind == "thinking":
                self._update(job, log=text, kind="thinking")
            elif kind == "usage":
                self._update(job, log=text, cost_usd=round(author.cost_usd + research.cost_usd, 4))
            else:
                self._update(job, stage=text)

        author = SceneAuthor(on_event)
        self._update(job, model=config.CLAUDE_MODEL)
        self._update(job, status="writing", stage="Planning the video script…", progress=0.08,
                     log=f"Planning an explanation of “{job.topic}”")
        self._update(job, log=f"Color theme: {theme_name(opts.theme)}")
        code = author.write(job.topic, opts.length, opts.extra, theme=opts.theme,
                            research=research.context(), pdf=job.pdf)
        self._update(job, title=extract_title(code), tags=extract_tags(code), progress=0.25,
                     log=f"Scene written: {count_voiceovers(code)} narrated beats")

        code, render = self._build(job, author, code, budget=config.MAX_REPAIR_ATTEMPTS,
                                   progress_span=(0.25, 0.85 if opts.review else 0.97))
        self._publish(job, code, render)

        if opts.review:
            self._review(job, author, code)

        self._update(job, status="done", stage="Done", progress=1.0, finished_at=time.time(),
                     log="Video ready")

    def _research(self, job: Job) -> ResearchResult:
        if not job.options.research:
            result = ResearchResult("skipped", "Video research was turned off for this video.")
        else:
            self._update(job, status="researching", stage="Finding relevant video explanations…", progress=.01,
                         research={"status": "researching", "message": "Looking for useful explanations on YouTube.", "sources": []},
                         log="Researching existing YouTube explanations before writing the script")

            def progress(message: str):
                self._update(job, stage=message, log=message,
                             research={"status": "researching", "message": message, "sources": []})

            try:
                result = research_topic(job.topic, job.options.length, job.options.extra, on_progress=progress)
            except Exception:
                # Optional research must not strand a job. No raw third-party exceptions
                # are sent to clients or persisted, since they may include credentials.
                result = ResearchResult("unavailable", "Video research was unavailable. Continuing from your topic.")
        self._update(job, research=result.public(), cost_usd=round(result.cost_usd, 4),
                     log=result.message, kind="warning" if result.status == "unavailable" else "info")
        return result

    def _build(self, job: Job, author: SceneAuthor, code: str, *, budget: int,
               progress_span: tuple[float, float]):
        """Validate, dry-run and render, asking Claude to repair failures. Returns (code, render)."""
        lo, hi = progress_span
        for attempt in range(budget + 1):
            code = apply_scene_theme(code, job.options.theme)
            n = job.attempts + 1
            self._update(job, attempts=n)
            scene_path = job.dir / f"scene_v{n}.py"
            scene_path.write_text(code, encoding="utf-8")

            stage, problem = "static checks", check_scene(code)
            if not problem:
                self._update(job, status="checking", stage="Test-running the scene code…",
                             log=f"Attempt {n}: dry run")
                dry = render_scene(scene_path, job.dir / f"dry_v{n}", dry_run=True,
                                   theme=job.options.theme)
                stage, problem = "a dry run of the scene", (None if dry.ok else dry.error)
            if not problem:
                total = max(count_voiceovers(code), 1)

                def on_segment(i: int):
                    frac = min((i + 1) / total, 1.0)
                    self._update(job, progress=lo + (hi - lo) * frac,
                                 stage=f"Rendering beat {i + 1}" + (f" of {total}" if i < total else ""))

                self._update(job, status="rendering", stage="Rendering animation…", progress=lo,
                             log=f"Attempt {n}: rendering at {job.options.quality} quality")
                render = render_scene(scene_path, job.dir / f"render_v{n}",
                                      quality=job.options.quality, narration=job.options.narration,
                                      voice=job.options.voice, theme=job.options.theme,
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
        """Writes this cut's files locally (the review step reads them), then uploads them to Convex."""
        shutil.copyfile(render.output_path, job.dir / "video.mp4")
        (job.dir / "scene.py").write_text(code, encoding="utf-8")
        (job.dir / "captions.vtt").unlink(missing_ok=True)
        if render.timings_path:
            shutil.copyfile(render.timings_path, job.dir / "timings.json")
            if job.options.narration:
                write_vtt(render.timings_path, job.dir / "captions.vtt")
        make_thumbnail(job.dir / "video.mp4", render.timings_path, job.dir / "thumbnail.jpg")

        files = {}
        for key, (name, content_type) in UPLOADS.items():
            path = job.dir / name
            if path.exists():
                files[key] = self.convex.upload(path, content_type)
        self.convex.mutation("worker:attachFiles", {"id": job.id, "files": files})

        title = extract_title(code)
        tags = job.tags or extract_tags(code) or suggest_tags(job.topic, title, narration_text(job.dir))
        # Rebuilt on every cut, since a re-render after review changes the timings
        chapters = suggest_chapters(job.topic, title, narration_segments(job.dir))
        self._update(job, title=title, tags=tags, chapters=chapters)

    def _review(self, job: Job, author: SceneAuthor, code: str):
        self._update(job, status="reviewing", stage="Claude is reviewing the frames…", progress=0.86,
                     log="First cut ready — reviewing frames for layout problems")
        frames = extract_frames(job.dir / "video.mp4", job.dir / "timings.json",
                                job.dir / f"frames_v{job.attempts}")
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
