"""Serves the frontend, the voice list and previews, and runs the render worker.

Videos, users, likes and saves live in Convex: the browser talks to it directly, and the
worker (backend/worker.py) claims queued videos from it and renders them here."""
from __future__ import annotations

import hashlib
import re
import threading

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import attachments, config
from .convex_api import Convex
from .convex_api import user_for_token as _convex_user
from .voices import VOICE_IDS, VOICES, default_voice, preview_path
from .themes import DEFAULT_THEME, VIDEO_THEMES
from .worker import run_forever

app = FastAPI(title="Animai")
_worker_stop = threading.Event()


<<<<<<< HEAD
class CreateJob(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    length: Literal["short", "medium", "long"] = "medium"
    quality: Literal["low", "medium", "high"] = "medium"
    narration: bool = True
    review: bool = True
    research: bool = True
    extra: str = Field(default="", max_length=1000)
    public: bool = False
    voice: str = ""
    theme: str = Field(default=DEFAULT_THEME, max_length=32)

    @field_validator("theme")
    @classmethod
    def valid_theme(cls, value):
        if value not in THEME_IDS:
            raise ValueError("Unknown video color theme")
        return value
=======
def convex_configured() -> bool:
    return bool(config.CONVEX_URL and config.WORKER_SECRET)
>>>>>>> d3c55572a0f9208d969fcd767d476cd92c738b32


@app.on_event("startup")
def start_worker():
    if not convex_configured():
        print("Worker not started: set CONVEX_URL and WORKER_SECRET in backend/.env.local", flush=True)
        return
    convex = Convex(config.CONVEX_URL, config.WORKER_SECRET)
    threading.Thread(target=run_forever, args=(convex, _worker_stop), name="render-worker", daemon=True).start()


@app.on_event("shutdown")
def stop_worker():
    _worker_stop.set()


@app.get("/api/config")
def client_config():
    """What the browser needs to reach Convex."""
    return {"convexUrl": config.CONVEX_URL}


def user_for_token(token: str) -> dict | None:
    return _convex_user(config.CONVEX_URL, token) if config.CONVEX_URL else None


@app.post("/api/attachments", status_code=201)
async def upload_attachment(request: Request):
    """Private PDF context for a video about to be created. Held in memory only; see attachments.py."""
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    if not token or not user_for_token(token):
        raise HTTPException(401, "Sign in first")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > attachments.MAX_BYTES:
            raise HTTPException(422, attachments.LIMIT_MESSAGE)
    problem = attachments.problem_with(bytes(data))
    if problem:
        raise HTTPException(422, problem)
    return {"token": attachments.put(bytes(data))}


@app.get("/api/voices")
def voices():
    return {"default": default_voice(), "voices": VOICES}


@app.get("/api/themes")
def themes():
    return {"default": DEFAULT_THEME, "themes": VIDEO_THEMES}


@app.get("/api/voices/{voice_id}/preview")
def voice_preview(voice_id: str):
    if voice_id not in VOICE_IDS:
        raise HTTPException(404, "No such voice")
    try:
        return FileResponse(preview_path(voice_id), media_type="audio/mpeg")
    except Exception as exc:  # The free voice service fails now and then
        raise HTTPException(503, f"Couldn't make a preview right now: {exc}") from exc


@app.get("/api/health")
def health():
    return {
        "anthropic": config.has_anthropic_credentials(),
        "ffmpeg": config.FFMPEG_DIR is not None,
        "latex": config.LATEX_DIR is not None,
        "tts": config.tts_available(),
        "convex": convex_configured(),
        "model": config.CLAUDE_MODEL,
    }


<<<<<<< HEAD
@app.post("/api/jobs", status_code=201)
def create_job(body: CreateJob):
    if body.voice and body.voice not in VOICE_IDS:
        raise HTTPException(422, "Unknown voice")
    topic = " ".join(body.topic.split())
    job = jobs.create(topic, JobOptions(
        length=body.length, quality=body.quality, narration=body.narration,
        review=body.review, research=body.research, extra=body.extra.strip(), voice=body.voice, theme=body.theme,
    ), public=body.public)
    return jobs.serialize(job)


@app.get("/api/jobs")
def list_jobs():
    return [jobs.serialize(j, include_logs=False) for j in jobs.list()]


@app.get("/api/feed")
def feed():
    return [jobs.serialize(j, include_logs=False) for j in jobs.feed()]


@app.get("/api/saved")
def saved():
    return [jobs.serialize(j, include_logs=False) for j in jobs.saved()]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "No such job")
    data = jobs.serialize(job)
    data["queue_position"] = jobs.queue_position(job) if job.status == "queued" else 0
    return data


@app.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: str):
    if not jobs.delete(job_id):
        raise HTTPException(409, "Job not found, still running, or a sample")


@app.patch("/api/jobs/{job_id}")
def update_job(job_id: str, body: UpdateJob):
    job = jobs.update(job_id, public=body.public, tags=body.tags)
    if not job:
        raise HTTPException(404, "No such job, or it's a sample")
    return jobs.serialize(job, include_logs=False)


@app.post("/api/jobs/{job_id}/like")
def like_job(job_id: str, body: Like):
    if not jobs.like(job_id, body.liked):
        raise HTTPException(404, "No such job")
    return jobs.serialize(jobs.get(job_id), include_logs=False)


@app.post("/api/jobs/{job_id}/save")
def save_job(job_id: str, body: Save):
    if not jobs.save(job_id, body.saved):
        raise HTTPException(404, "No such post, or it's your own video")
    return jobs.serialize(jobs.get(job_id), include_logs=False)


@app.post("/api/jobs/{job_id}/view", status_code=204)
def view_job(job_id: str):
    if not jobs.view(job_id):
        raise HTTPException(404, "No such job")


config.JOBS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=config.JOBS_DIR), name="media")
config.SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/samples", StaticFiles(directory=config.SAMPLES_DIR), name="samples")
=======
>>>>>>> d3c55572a0f9208d969fcd767d476cd92c738b32
app.mount("/static", StaticFiles(directory=config.FRONTEND_DIR), name="static")


@app.get("/")
def index():
    # Keep the HTML and its scripts/styles from different pulls from mixing in a
    # long-lived browser tab. Unchanged assets retain the same cacheable URL.
    html = (config.FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    def version_asset(match):
        path = config.FRONTEND_DIR / match.group(1)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        return f"/static/{match.group(1)}?v={digest}"

    html = re.sub(r'/static/([\w.-]+\.(?:js|css))(?=["\'])', version_asset, html)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})
