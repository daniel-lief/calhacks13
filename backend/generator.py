"""Claude conversation that writes, repairs and reviews a scene file."""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Callable

import anthropic

from . import config, prompts
from .validate import extract_code

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class GenerationError(RuntimeError):
    pass


class SceneAuthor:
    """
    Holds one append-only conversation per video, so every repair and review turn
    sees the original request, Claude's earlier code (and its thinking), and what went wrong.
    """

    def __init__(self, on_event: Callable[[str, str], None]):
        self.client = anthropic.Anthropic()
        self.messages: list[dict] = []
        self.on_event = on_event  # (kind, text): kind is "thinking" | "progress" | "usage"
        self.cost_usd = 0.0

    def write(self, topic: str, length: str, extra: str = "") -> str:
        return self._turn(prompts.initial_request(topic, length, extra), require_code=True)

    def repair(self, error: str, stage: str) -> str:
        return self._turn(prompts.repair_request(error, stage), require_code=True)

    def review(self, frames: list[tuple[float, Path, str]]) -> str | None:
        """Show Claude stills from the render. Returns revised code, or None if it approves."""
        content: list[dict] = []
        for t, path, narration in frames:
            content.append({"type": "text", "text": f"Frame at {t:.1f}s — narration: \"{narration}\""})
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.standard_b64encode(path.read_bytes()).decode("ascii"),
                },
            })
        content.append({"type": "text", "text": prompts.REVIEW_REQUEST})
        return self._turn(content, require_code=False)

    def _turn(self, content, *, require_code: bool) -> str | None:
        self.messages.append({"role": "user", "content": content})
        try:
            message = self._stream()
        except anthropic.AuthenticationError as exc:
            raise GenerationError("Anthropic API authentication failed — set ANTHROPIC_API_KEY in .env.") from exc
        except anthropic.RateLimitError as exc:
            raise GenerationError("Rate limited by the Anthropic API; try again in a minute.") from exc
        except anthropic.APIConnectionError as exc:
            raise GenerationError("Could not reach the Anthropic API (network error).") from exc
        except anthropic.APIStatusError as exc:
            raise GenerationError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc

        if message.stop_reason == "refusal":
            raise GenerationError("Claude declined to make a video about this topic.")
        if message.stop_reason == "max_tokens":
            raise GenerationError("Claude's reply was cut off before the scene was complete.")

        self._record_usage(message)
        # Keep the full content (including thinking blocks) so the conversation stays append-only
        self.messages.append({"role": "assistant", "content": message.content})
        reply = "".join(b.text for b in message.content if b.type == "text")

        code = extract_code(reply)
        if code:
            return code
        if not require_code and "LGTM" in reply:
            return None
        if require_code:
            raise GenerationError("Claude's reply did not contain a Python code block.")
        return None

    def _record_usage(self, message):
        u = message.usage
        price_in, price_out = config.MODEL_PRICES.get(config.CLAUDE_MODEL, (0.0, 0.0))
        cache_write = u.cache_creation_input_tokens or 0
        cache_read = u.cache_read_input_tokens or 0
        cost = (u.input_tokens * price_in + cache_write * price_in * 1.25
                + cache_read * price_in * 0.1 + u.output_tokens * price_out) / 1_000_000
        self.cost_usd += cost
        total_in = u.input_tokens + cache_write + cache_read
        self.on_event("usage", f"Claude call: {total_in:,} input tokens ({cache_read:,} cached), "
                               f"{u.output_tokens:,} output tokens ≈ ${cost:.3f}")

    def _stream(self):
        chars = 0
        thinking_buf = ""
        extra = {}
        if config.CLAUDE_MODEL in config.FALLBACK_MODELS:
            extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        with self.client.beta.messages.stream(
            model=config.CLAUDE_MODEL,
            max_tokens=64000,
            system=prompts.system_prompt(),
            messages=self.messages,
            thinking={"type": "adaptive", "display": "summarized"},
            output_config={"effort": config.CLAUDE_EFFORT},
            cache_control={"type": "ephemeral"},
            **extra,
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "thinking_delta":
                        thinking_buf += event.delta.thinking
                        # Surface the summarized reasoning a paragraph at a time
                        while "\n\n" in thinking_buf:
                            para, thinking_buf = thinking_buf.split("\n\n", 1)
                            if para.strip():
                                self.on_event("thinking", para.strip())
                    elif event.delta.type == "text_delta":
                        before = chars // 1500
                        chars += len(event.delta.text)
                        if chars // 1500 > before:
                            self.on_event("progress", f"Writing scene code… {chars:,} characters")
                elif event.type == "content_block_stop" and thinking_buf.strip():
                    self.on_event("thinking", thinking_buf.strip())
                    thinking_buf = ""
            return stream.get_final_message()
