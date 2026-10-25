"""Private PDF context for new videos, held only in this process's memory.

A PDF is uploaded right before its video is created, kept here under a random one-time
token, handed to the render worker when it claims that video, and then forgotten. It is
never written to disk, never sent to Convex, and its filename never reaches the server.
"""
from __future__ import annotations

import re
import secrets
import threading
import time

MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 50
TTL_SECONDS = 30 * 60
LIMIT_MESSAGE = "PDFs can be up to 20 MB and 50 pages"

_store: dict[str, tuple[float, bytes]] = {}
_lock = threading.Lock()

_PAGE_RE = re.compile(rb"/Type\s*/Page(?![a-zA-Z])")
_COUNT_RE = re.compile(rb"/Count\s+(\d+)")


def page_count(data: bytes) -> int:
    """Pages in a PDF, from its page objects or its page-tree count (whichever is larger)."""
    objects = len(_PAGE_RE.findall(data))
    counts = [int(n) for n in _COUNT_RE.findall(data)]
    return max([objects, *counts])


def problem_with(data: bytes) -> str | None:
    """Why this upload can't be used, or None if it's a PDF within the limits."""
    if not data.startswith(b"%PDF-"):
        return "That file isn't a PDF"
    if len(data) > MAX_BYTES or page_count(data) > MAX_PAGES:
        return LIMIT_MESSAGE
    return None


def _expire(now: float) -> None:
    for token in [t for t, (at, _) in _store.items() if now - at > TTL_SECONDS]:
        del _store[token]


def put(data: bytes) -> str:
    token = secrets.token_urlsafe(24)
    with _lock:
        now = time.monotonic()
        _expire(now)
        _store[token] = (now, data)
    return token


def take(token: str) -> bytes | None:
    """The PDF for `token`, removed from memory; None if it's unknown or expired."""
    with _lock:
        _expire(time.monotonic())
        entry = _store.pop(token, None)
    return entry[1] if entry else None
