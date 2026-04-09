"""LLM client for profile helper: round-robin multi-key rotation.

Supports multiple API keys to distribute load and survive rate limits (HTTP 429).

Configuration (in .env):
    # Single key (original, still supported):
    AI_GENERATION_API_KEY=sk-xxx

    # Multiple keys — comma-separated (takes precedence over single key):
    AI_GENERATION_API_KEYS=sk-key1,sk-key2,sk-key3

    AI_GENERATION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
    AI_GENERATION_MODEL=qwen-plus

Rotation strategy:
  - Normal: round-robin across all keys
  - On 429: mark key as rate-limited (60s cooldown), immediately use next key
  - If ALL keys are rate-limited: fall back to waiting on the least-recently-limited key
"""

from __future__ import annotations

import logging
import os
import threading
import time
from openai import OpenAI

from app.core.config import (
    get_ai_generation_api_key,
    get_ai_generation_base_url,
    get_ai_generation_model,
)

logger = logging.getLogger(__name__)

_RATE_LIMIT_COOLDOWN = int(os.getenv("LLM_RATE_LIMIT_COOLDOWN_SECONDS", "60"))


def _load_api_keys() -> list[str]:
    """Load API keys from env. Supports comma-separated multi-key list."""
    multi = os.getenv("AI_GENERATION_API_KEYS", "").strip()
    if multi:
        keys = [k.strip() for k in multi.split(",") if k.strip()]
        if keys:
            return keys
    # Fall back to single-key config
    try:
        single = get_ai_generation_api_key()
        return [single] if single else []
    except ValueError:
        return []


# ── Module-level key pool (shared across all requests in the process) ──────────

class _KeyPool:
    """Thread-safe round-robin key pool with per-key rate-limit tracking."""

    def __init__(self, keys: list[str]) -> None:
        self._keys = keys
        self._idx = 0           # next key to try (round-robin pointer)
        self._limited: dict[int, float] = {}  # key_index → rate-limited-until timestamp
        self._lock = threading.Lock()

    def reload(self) -> None:
        """Reload keys from env (call after .env change without restart)."""
        with self._lock:
            self._keys = _load_api_keys()
            self._idx = 0
            self._limited = {}

    def get_next_key(self) -> str | None:
        """Return the next available key (skipping rate-limited ones)."""
        with self._lock:
            if not self._keys:
                return None
            n = len(self._keys)
            now = time.monotonic()
            # Try each key starting from current idx
            for _ in range(n):
                idx = self._idx % n
                self._idx += 1
                limited_until = self._limited.get(idx)
                if limited_until is None or now >= limited_until:
                    # Clear stale cooldown
                    self._limited.pop(idx, None)
                    return self._keys[idx]
            # All keys are rate-limited — pick the one whose cooldown expires soonest
            best_idx = min(self._limited, key=lambda i: self._limited[i])
            wait = max(0.0, self._limited[best_idx] - now)
            logger.warning("All LLM keys rate-limited. Waiting %.1fs for key #%d.", wait, best_idx)
            time.sleep(wait)
            self._limited.pop(best_idx, None)
            return self._keys[best_idx]

    def mark_rate_limited(self, key: str) -> None:
        """Mark a key as rate-limited for _RATE_LIMIT_COOLDOWN seconds."""
        with self._lock:
            try:
                idx = self._keys.index(key)
                self._limited[idx] = time.monotonic() + _RATE_LIMIT_COOLDOWN
                logger.warning(
                    "Key #%d marked rate-limited for %ds. Pool size: %d, limited: %d",
                    idx, _RATE_LIMIT_COOLDOWN, len(self._keys), len(self._limited),
                )
            except ValueError:
                pass  # key not in pool (shouldn't happen)

    @property
    def size(self) -> int:
        return len(self._keys)

    @property
    def available(self) -> int:
        now = time.monotonic()
        with self._lock:
            return sum(1 for i in range(len(self._keys))
                       if i not in self._limited or now >= self._limited[i])


_pool = _KeyPool(_load_api_keys())


# ── Public API ──────────────────────────────────────────────────────────────────

def create_client(base_url: str | None = None, api_key: str | None = None) -> OpenAI | None:
    """Create an OpenAI-compatible client.

    If api_key is explicitly provided, uses that key directly (single-key mode).
    Otherwise, picks the next available key from the round-robin pool.
    """
    url = base_url or get_ai_generation_base_url()
    if not url:
        return None

    key = api_key
    if not key:
        key = _pool.get_next_key()
    if not key:
        return None

    return OpenAI(api_key=key, base_url=url)


def get_client_with_rotation(base_url: str | None = None) -> tuple[OpenAI, str] | tuple[None, None]:
    """Return (client, api_key) pair for use with mark_rate_limited().

    Use this instead of create_client() when you want to report 429 errors back
    so the pool can rotate away from the offending key.

    Example:
        client, key = get_client_with_rotation()
        try:
            resp = client.chat.completions.create(...)
        except Exception as e:
            if "429" in str(e):
                mark_key_rate_limited(key)
    """
    url = base_url or get_ai_generation_base_url()
    if not url:
        return None, None
    key = _pool.get_next_key()
    if not key:
        return None, None
    return OpenAI(api_key=key, base_url=url), key


def mark_key_rate_limited(api_key: str) -> None:
    """Mark an API key as rate-limited. Call this when you receive HTTP 429."""
    _pool.mark_rate_limited(api_key)


def get_pool_status() -> dict:
    """Return current pool status (for health checks / logging)."""
    return {
        "total_keys": _pool.size,
        "available_keys": _pool.available,
    }


def get_default_model() -> str:
    """Get default model from config."""
    return get_ai_generation_model()
