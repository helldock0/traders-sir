"""Anthropic API wrapper for the three roles: structured JSON output, cached system prompt, refusal
fallback, spend accounting.

Models (first-party API prices per 1M tokens, 2026-10): Fable 5.1 $10/$50, Opus 5.5 $4/$20,
Sonnet 5.5 $2/$10, Haiku 5.5 $0.10/$0.50. Thinking is always on for these models; depth is set
with output_config.effort. Forced tool choice is not available, so the roles answer with
output_config.format (JSON schema) instead of tools.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from ..data import store
from ..research.state import ResearchState

log = logging.getLogger(__name__)

DIRECTOR_MODEL = "claude-fable-5-1"
CRITIC_MODEL = "claude-opus-5-5"
BUILDER_MODEL = "claude-sonnet-5-5"
HOUSEKEEPING_MODEL = "claude-haiku-5-5"

# USD per 1M tokens: input, cache write, cache read, output
PRICES: dict[str, tuple[float, float, float, float]] = {
    "claude-fable-5-1": (10.0, 12.5, 0.25, 50.0),
    "claude-opus-5-5": (4.0, 5.0, 0.20, 20.0),
    "claude-sonnet-5-5": (2.0, 2.5, 0.20, 10.0),
    "claude-haiku-5-5": (0.10, 0.125, 0.01, 0.50),
    "claude-opus-4-8": (5.0, 6.25, 0.50, 25.0),
}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class RefusalError(RuntimeError):
    pass


@dataclass
class LLMResult:
    data: dict
    text: str
    model: str
    stop_reason: str
    usage: dict
    usd: float
    seconds: float
    attempts: int = 1


def _usage_dict(usage) -> dict:
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "cache_read_input_tokens": int(getattr(usage, "cache_read_input_tokens", 0) or 0),
        "cache_creation_input_tokens": int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
    }


def cost_usd(model: str, usage: dict) -> float:
    base = next((v for k, v in PRICES.items() if model.startswith(k)), None)
    if base is None:
        base = PRICES["claude-opus-5-5"]
    p_in, p_cw, p_cr, p_out = base
    return (usage["input_tokens"] * p_in + usage["cache_creation_input_tokens"] * p_cw
            + usage["cache_read_input_tokens"] * p_cr + usage["output_tokens"] * p_out) / 1e6


def credentials_present() -> bool:
    load_dotenv(store.ROOT / ".env")
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


class LLM:
    """Thin client. One call = one structured JSON answer."""

    def __init__(self, state: ResearchState | None = None, timeout_s: float = 1500.0, max_retries: int = 4):
        load_dotenv(store.ROOT / ".env")
        if not credentials_present():
            raise RuntimeError("No Anthropic credentials. Put ANTHROPIC_API_KEY in D:\\Traders sir\\.env (see .env.example).")
        self.client = anthropic.Anthropic(timeout=timeout_s, max_retries=max_retries)
        self.state = state
        self.use_fallbacks = os.environ.get("EDGE_NO_FALLBACKS", "") == ""
        self.total_usd = 0.0

    def call(self, role: str, model: str, system: str, user: str, schema: dict, effort: str = "high",
             max_tokens: int = 16000, cycle: int | None = None, history: list[dict] | None = None) -> LLMResult:
        system_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral", "ttl": "1h"}}]
        messages = list(history or []) + [{"role": "user", "content": user}]
        t0 = time.time()
        text = ""
        for attempt in range(1, 4):
            kwargs = dict(model=model, max_tokens=max_tokens, system=system_blocks, messages=messages,
                          output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}})
            if self.use_fallbacks:
                kwargs.update(betas=[FALLBACK_BETA], fallbacks="default")
            try:
                resp = self.client.beta.messages.create(**kwargs)
            except anthropic.BadRequestError as exc:
                if self.use_fallbacks and "fallback" in str(exc).lower():
                    log.warning("fallbacks rejected by the API (%s); retrying without them", exc)
                    self.use_fallbacks = False
                    continue
                raise
            usage = _usage_dict(resp.usage)
            served = getattr(resp, "model", model) or model
            usd = cost_usd(served, usage)
            self.total_usd += usd
            if self.state is not None:
                self.state.record_spend(cycle, role, served, usage, usd)
            if resp.stop_reason == "refusal":
                details = getattr(resp, "stop_details", None)
                raise RefusalError(f"{role}: request declined ({getattr(details, 'category', None)}: {getattr(details, 'explanation', '')})")
            text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
            if resp.stop_reason == "max_tokens":
                log.warning("%s hit max_tokens=%d; retrying with more room", role, max_tokens)
                max_tokens = min(max_tokens * 2, 64000)
                continue
            try:
                data = json.loads(text)
                return LLMResult(data=data, text=text, model=served, stop_reason=resp.stop_reason, usage=usage, usd=usd,
                                 seconds=time.time() - t0, attempts=attempt)
            except json.JSONDecodeError:
                log.warning("%s returned invalid JSON (attempt %d); asking for a clean object", role, attempt)
                messages = messages + [{"role": "assistant", "content": text},
                                       {"role": "user", "content": "That was not a valid JSON object for the schema. Return only the JSON object."}]
        raise RuntimeError(f"{role}: no valid JSON after retries; last text: {text[:500]}")
