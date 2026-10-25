"""The render worker's connection to Convex: calls worker:* functions over Convex's HTTP
API (with the shared secret) and uploads files to Convex storage."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx2 as httpx  # installed with the anthropic SDK; same API as httpx

RETRIES = 3


class ConvexError(RuntimeError):
    pass


class Convex:
    def __init__(self, url: str, secret: str, transport: httpx.BaseTransport | None = None):
        self.url = url.rstrip("/")
        self.secret = secret
        self._http = httpx.Client(timeout=30.0, transport=transport)

    def mutation(self, path: str, args: dict) -> Any:
        return self._call("mutation", path, args)

    def query(self, path: str, args: dict) -> Any:
        return self._call("query", path, args)

    def upload(self, path: Path, content_type: str) -> str:
        """Stores a file in Convex and returns its storage id."""
        upload_url = self.mutation("worker:generateUploadUrl", {})
        response = self._send(lambda: self._http.post(
            upload_url, content=path.read_bytes(), headers={"Content-Type": content_type}))
        response.raise_for_status()
        return response.json()["storageId"]

    def _call(self, kind: str, path: str, args: dict) -> Any:
        body = {"path": path, "args": {"secret": self.secret, **args}, "format": "json"}
        response = self._send(lambda: self._http.post(f"{self.url}/api/{kind}", json=body))
        data = response.json()
        if data.get("status") != "success":
            message = data.get("errorData") or data.get("errorMessage") or f"HTTP {response.status_code}"
            raise ConvexError(f"{path}: {message}")
        return data.get("value")

    def _send(self, request):
        for attempt in range(RETRIES):
            try:
                return request()
            except httpx.TransportError:
                if attempt == RETRIES - 1:
                    raise
                time.sleep(1.5 * (attempt + 1))


def user_for_token(url: str, token: str, transport: httpx.BaseTransport | None = None) -> dict | None:
    """Who a browser session token belongs to (Convex's users:me), or None if it isn't valid."""
    try:
        with httpx.Client(timeout=15.0, transport=transport) as http:
            response = http.post(
                f"{url.rstrip('/')}/api/query",
                json={"path": "users:me", "args": {}, "format": "json"},
                headers={"Authorization": f"Bearer {token}"},
            )
        data = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return data.get("value") if data.get("status") == "success" else None

