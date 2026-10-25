"""The render worker: asks Convex for queued videos and makes them, one at a time."""
from __future__ import annotations

import threading
import traceback

from . import config
from .jobs import JobManager


def run_forever(convex, stop: threading.Event, poll_seconds: float | None = None) -> None:
    poll = config.WORKER_POLL_SECONDS if poll_seconds is None else poll_seconds
    try:
        stale = convex.mutation("worker:failStale", {})
        if stale:
            print(f"Worker: marked {int(stale)} interrupted video(s) as failed", flush=True)
    except Exception:
        traceback.print_exc()
    while not stop.is_set():
        try:
            job = convex.mutation("worker:claimNext", {})
        except Exception:  # Network hiccup or Convex unavailable: try again shortly
            traceback.print_exc()
            stop.wait(max(poll, 5))
            continue
        if job:
            print(f"Worker: making “{job['topic']}” ({job['id']})", flush=True)
            try:
                JobManager(convex).run(job)
            except Exception:  # Never let one job stop the worker; later videos still need making
                traceback.print_exc()
        else:
            stop.wait(poll)
