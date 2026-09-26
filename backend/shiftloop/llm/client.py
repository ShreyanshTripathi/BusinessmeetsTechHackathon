"""Claude client setup. Model ids are configurable; defaults follow the plan (Sonnet 5 chat, Haiku 4.5 summaries)."""
from __future__ import annotations

import os

import anthropic

CHAT_MODEL = os.getenv("SHIFTLOOP_CHAT_MODEL", "claude-sonnet-5")
SUMMARY_MODEL = os.getenv("SHIFTLOOP_SUMMARY_MODEL", "claude-haiku-4-5")

# errors that mean "Claude is not reachable from here": fall back to offline answers
UNAVAILABLE = (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.APIConnectionError)


def make_client() -> anthropic.Anthropic | None:
    """Resolve credentials the SDK way (API key, auth token or `ant auth login` profile). None if unavailable."""
    if os.getenv("SHIFTLOOP_OFFLINE") == "1":
        return None
    try:
        return anthropic.Anthropic()
    except Exception:  # the SDK raises when no credential source resolves
        return None
