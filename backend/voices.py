"""The narration voices people can choose from, and short previews of each.

Voices are Microsoft neural voices served free through edge-tts (the same engine
Animai narrates with). Previews are synthesized once and cached on disk.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from . import config

# id is the edge-tts voice name; the rest is what the picker shows
VOICES = [
    {"id": "en-US-AndrewMultilingualNeural", "name": "Andrew", "accent": "American", "description": "Warm and confident"},
    {"id": "en-US-AvaMultilingualNeural", "name": "Ava", "accent": "American", "description": "Expressive and caring"},
    {"id": "en-US-EmmaMultilingualNeural", "name": "Emma", "accent": "American", "description": "Cheerful and clear"},
    {"id": "en-US-ChristopherNeural", "name": "Christopher", "accent": "American", "description": "Deep and authoritative"},
    {"id": "en-US-AnaNeural", "name": "Ana", "accent": "American", "description": "Young and cute"},
    {"id": "en-GB-RyanNeural", "name": "Ryan", "accent": "British", "description": "Calm and steady"},
    {"id": "en-GB-SoniaNeural", "name": "Sonia", "accent": "British", "description": "Bright and friendly"},
    {"id": "en-AU-NatashaNeural", "name": "Natasha", "accent": "Australian", "description": "Upbeat and friendly"},
    {"id": "en-IN-NeerjaExpressiveNeural", "name": "Neerja", "accent": "Indian", "description": "Lively and expressive"},
    {"id": "en-IE-ConnorNeural", "name": "Connor", "accent": "Irish", "description": "Easygoing and friendly"},
]
VOICE_IDS = {v["id"] for v in VOICES}
PREVIEW_TEXT = "Hi! I'll be narrating your video. Let's turn a big idea into something you can see."
PREVIEW_DIR = config.DATA_DIR / "voice_previews"

_preview_lock = threading.Lock()


def default_voice() -> str:
    return config.TTS_VOICE


def voice_name(voice_id: str) -> str:
    """The display name for a voice, falling back to the raw id for voices not in the list."""
    vid = voice_id or default_voice()
    return next((v["name"] for v in VOICES if v["id"] == vid), vid)


def preview_path(voice_id: str) -> Path:
    """An MP3 of `voice_id` reading the preview line, synthesized on first request."""
    path = PREVIEW_DIR / f"{voice_id}.mp3"
    with _preview_lock:
        if not path.exists() or path.stat().st_size == 0:
            import edge_tts
            PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".part")
            asyncio.run(edge_tts.Communicate(PREVIEW_TEXT, voice_id).save(str(tmp)))
            tmp.replace(path)
    return path
