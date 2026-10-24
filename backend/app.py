"""HTTP API and static frontend."""
from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .jobs import JobManager, JobOptions

app = FastAPI(title="Explainer")
jobs = JobManager()


class CreateJob(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    length: Literal["short", "medium", "long"] = "medium"
    quality: Literal["low", "medium", "high"] = "medium"
    narration: bool = True
    review: bool = True
    extra: str = Field(default="", max_length=1000)


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
    topic = " ".join(body.topic.split())
    job = jobs.create(topic, JobOptions(
        length=body.length, quality=body.quality, narration=body.narration,
        review=body.review, extra=body.extra.strip(),
    ))
    return job.to_dict()


@app.get("/api/jobs")
def list_jobs():
    return [j.to_dict(include_logs=False) for j in jobs.list()]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "No such job")
    data = job.to_dict()
    data["queue_position"] = jobs.queue_position(job) if job.status == "queued" else 0
    return data


@app.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: str):
    if not jobs.delete(job_id):
        raise HTTPException(409, "Job not found or still running")


config.JOBS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=config.JOBS_DIR), name="media")
app.mount("/static", StaticFiles(directory=config.FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(config.FRONTEND_DIR / "index.html")
