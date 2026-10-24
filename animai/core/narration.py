"""
Speech synthesis for voiceovers.

Configured by environment variables (the backend renderer sets them):
  ANIMAI_NARRATION    "1" to synthesize speech (default), "0" for silent timing only
  ANIMAI_VOICE        edge-tts voice name
  ANIMAI_AUDIO_CACHE  directory for cached clips
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import time
from dataclasses import dataclass
from pathlib import Path

WORDS_PER_SECOND = 2.6  # Used to time segments when speech is unavailable
DEFAULT_VOICE = "en-US-AndrewMultilingualNeural"
RETRIES = 4


@dataclass
class Clip:
    path: str | None
    duration: float


def estimate_duration(text: str) -> float:
    return max(1.5, len(text.split()) / WORDS_PER_SECOND)


def _audio_duration(path: Path) -> float:
    from pydub import AudioSegment
    return AudioSegment.from_file(str(path)).duration_seconds


def synthesize(text: str) -> Clip:
    if os.environ.get("ANIMAI_NARRATION", "1") != "1":
        return Clip(None, estimate_duration(text))

    voice = os.environ.get("ANIMAI_VOICE", DEFAULT_VOICE)
    cache_dir = Path(os.environ.get("ANIMAI_AUDIO_CACHE", Path.home() / ".animai" / "audio"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{voice}\n{text}".encode()).hexdigest()[:24]
    path = cache_dir / f"{key}.mp3"

    error = None
    for attempt in range(RETRIES):
        try:
            if not path.exists() or path.stat().st_size == 0:
                import edge_tts
                tmp = path.with_suffix(".part")
                asyncio.run(edge_tts.Communicate(text, voice).save(str(tmp)))
                tmp.replace(path)
            return Clip(str(path), _audio_duration(path))
        except Exception as exc:  # The free voice service fails intermittently: retry
            error = exc
            time.sleep(1.5 * (attempt + 1))
    print(f"@@TTS_FAILED {type(error).__name__}: {error}", flush=True)
    return Clip(None, estimate_duration(text))
