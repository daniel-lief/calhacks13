"""HTTP API and static frontend."""
from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .jobs import JobManager, JobOptions
from .voices import VOICE_IDS, VOICES, default_voice, preview_path

app = FastAPI(title="Explainer")
jobs = JobManager()


class CreateJob(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    length: Literal["short", "medium", "long"] = "medium"
    quality: Literal["low", "medium", "high"] = "medium"
    narration: bool = True
    review: bool = True
    extra: str = Field(default="", max_length=1000)
    public: bool = True
    voice: str = ""


class UpdateJob(BaseModel):
    public: bool | None = None
    tags: list[str] | None = Field(default=None, max_length=50)


class Like(BaseModel):
    liked: bool


class Save(BaseModel):
    saved: bool


@app.get("/api/voices")
def voices():
    return {"default": default_voice(), "voices": VOICES}


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
        "model": config.CLAUDE_MODEL,
        "total_cost_usd": round(sum(j.cost_usd for j in jobs.list()), 2),
    }


@app.post("/api/jobs", status_code=201)
def create_job(body: CreateJob):
    if body.voice and body.voice not in VOICE_IDS:
        raise HTTPException(422, "Unknown voice")
    topic = " ".join(body.topic.split())
    job = jobs.create(topic, JobOptions(
        length=body.length, quality=body.quality, narration=body.narration,
        review=body.review, extra=body.extra.strip(), voice=body.voice,
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
app.mount("/static", StaticFiles(directory=config.FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(config.FRONTEND_DIR / "index.html")
