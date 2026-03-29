"""Rate limiting for Agent Skill API.

Provides in-memory rate limiting with:
- Per-agent QPS (queries per second) limit
- Daily POST quota per agent
- Configurable via environment variables
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.db.models import AgentRecord
from app.services.agent_skill.auth import get_current_agent


# Configuration from environment variables
DEFAULT_QPS_LIMIT = int(os.environ.get("AGENT_SKILL_QPS_LIMIT", "10"))
DEFAULT_DAILY_POST_QUOTA = int(os.environ.get("AGENT_SKILL_DAILY_POST_QUOTA", "1000"))


@dataclass
class RateLimitState:
    """State for tracking an agent's rate limits."""
    
    # QPS tracking using sliding window
    request_timestamps: list[float] = field(default_factory=list)
    
    # Daily POST quota tracking
    daily_post_count: int = 0
    daily_post_reset_date: str = ""  # ISO date string (YYYY-MM-DD)
    
    # Lock for thread-safety
    lock: threading.Lock = field(default_factory=threading.Lock)


class InMemoryRateLimiter:
    """In-memory rate limiter for Agent Skill API.
    
    Features:
    - Per-agent QPS limiting using sliding window
    - Daily POST quota per agent
    - Thread-safe operations
    - Automatic cleanup of old data
    """
    
    def __init__(
        self,
        qps_limit: int = DEFAULT_QPS_LIMIT,
        daily_post_quota: int = DEFAULT_DAILY_POST_QUOTA,
    ):
        self.qps_limit = qps_limit
        self.daily_post_quota = daily_post_quota
        self._states: dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._global_lock = threading.Lock()
    
    def _get_state(self, agent_id: str) -> RateLimitState:
        """Get or create rate limit state for an agent."""
        with self._global_lock:
            if agent_id not in self._states:
                self._states[agent_id] = RateLimitState()
            return self._states[agent_id]
    
    def _get_today_date(self) -> str:
        """Get today's date as ISO string."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    def check_qps(self, agent_id: str) -> tuple[bool, int]:
        """Check if agent is within QPS limit.
        
        Returns:
            Tuple of (allowed, retry_after_ms)
            - allowed: True if request is allowed
            - retry_after_ms: milliseconds to wait if not allowed
        """
        state = self._get_state(agent_id)
        now = time.time()
        window_start = now - 1.0  # 1 second window
        
        with state.lock:
            # Remove timestamps outside the window
            state.request_timestamps = [
                ts for ts in state.request_timestamps if ts > window_start
            ]
            
            # Check if under limit
            if len(state.request_timestamps) >= self.qps_limit:
                # Calculate retry-after based on oldest request in window
                oldest_ts = min(state.request_timestamps)
                retry_after_ms = int((oldest_ts + 1.0 - now) * 1000)
                return False, max(retry_after_ms, 100)  # Minimum 100ms
            
            # Record this request
            state.request_timestamps.append(now)
            return True, 0
    
    def check_daily_post_quota(self, agent_id: str) -> tuple[bool, int]:
        """Check if agent is within daily POST quota.
        
        Returns:
            Tuple of (allowed, retry_after_seconds)
            - allowed: True if request is allowed
            - retry_after_seconds: seconds until quota resets (if not allowed)
        """
        state = self._get_state(agent_id)
        today = self._get_today_date()
        
        with state.lock:
            # Reset if new day
            if state.daily_post_reset_date != today:
                state.daily_post_count = 0
                state.daily_post_reset_date = today
            
            # Check quota
            if state.daily_post_count >= self.daily_post_quota:
                # Calculate seconds until midnight UTC
                now = datetime.now(timezone.utc)
                midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
                midnight_tomorrow = midnight.replace(day=midnight.day + 1) if midnight.day < 28 else midnight
                # Simple calculation: seconds until end of day
                seconds_until_midnight = 86400 - (now.hour * 3600 + now.minute * 60 + now.second)
                return False, seconds_until_midnight
            
            # Increment counter (actual increment happens in record_post)
            return True, 0
    
    def record_post(self, agent_id: str) -> None:
        """Record a POST request for daily quota tracking."""
        state = self._get_state(agent_id)
        today = self._get_today_date()
        
        with state.lock:
            # Reset if new day
            if state.daily_post_reset_date != today:
                state.daily_post_count = 0
                state.daily_post_reset_date = today
            
            state.daily_post_count += 1
    
    def get_remaining_quota(self, agent_id: str) -> dict:
        """Get remaining rate limit info for an agent."""
        state = self._get_state(agent_id)
        today = self._get_today_date()
        now = time.time()
        window_start = now - 1.0
        
        with state.lock:
            # QPS remaining
            recent_requests = len([
                ts for ts in state.request_timestamps if ts > window_start
            ])
            qps_remaining = max(0, self.qps_limit - recent_requests)
            
            # Daily quota remaining
            if state.daily_post_reset_date != today:
                daily_remaining = self.daily_post_quota
            else:
                daily_remaining = max(0, self.daily_post_quota - state.daily_post_count)
            
            return {
                "qps_limit": self.qps_limit,
                "qps_remaining": qps_remaining,
                "daily_post_quota": self.daily_post_quota,
                "daily_post_remaining": daily_remaining,
            }
    
    def reset_agent(self, agent_id: str) -> None:
        """Reset rate limits for an agent (for testing)."""
        with self._global_lock:
            if agent_id in self._states:
                del self._states[agent_id]
    
    def reset_all(self) -> None:
        """Reset all rate limits (for testing)."""
        with self._global_lock:
            self._states.clear()


# Global rate limiter instance
_rate_limiter: Optional[InMemoryRateLimiter] = None


def get_rate_limiter() -> InMemoryRateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = InMemoryRateLimiter()
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (for testing)."""
    global _rate_limiter
    if _rate_limiter is not None:
        _rate_limiter.reset_all()
    _rate_limiter = None


class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, detail: str, retry_after: int, limit_type: str = "qps"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after)},
        )
        self.retry_after = retry_after
        self.limit_type = limit_type


async def check_rate_limit(
    request: Request,
    agent: AgentRecord = Depends(get_current_agent),
) -> AgentRecord:
    """FastAPI dependency to check rate limits.
    
    This dependency should be used after authentication to enforce
    rate limits on authenticated requests.
    
    Returns the agent if rate limits pass, otherwise raises 429.
    """
    limiter = get_rate_limiter()
    agent_id = agent.id
    
    # Check QPS limit
    qps_allowed, qps_retry_after = limiter.check_qps(agent_id)
    if not qps_allowed:
        raise RateLimitExceeded(
            detail=f"Rate limit exceeded. Maximum {limiter.qps_limit} requests per second.",
            retry_after=max(1, qps_retry_after // 1000),  # Convert ms to seconds
            limit_type="qps",
        )
    
    # Check daily POST quota for POST requests
    if request.method == "POST":
        quota_allowed, quota_retry_after = limiter.check_daily_post_quota(agent_id)
        if not quota_allowed:
            raise RateLimitExceeded(
                detail=f"Daily POST quota exceeded. Maximum {limiter.daily_post_quota} POST requests per day.",
                retry_after=quota_retry_after,
                limit_type="daily_quota",
            )
        # Record the POST request
        limiter.record_post(agent_id)
    
    return agent


# Alias for cleaner imports - use this instead of get_current_agent to enable rate limiting
get_current_agent_with_rate_limit = check_rate_limit


def rate_limit_headers(agent_id: str) -> dict[str, str]:
    """Generate rate limit headers for response.
    
    Returns headers like:
    - X-RateLimit-Limit-QPS
    - X-RateLimit-Remaining-QPS
    - X-RateLimit-Limit-Daily
    - X-RateLimit-Remaining-Daily
    """
    limiter = get_rate_limiter()
    info = limiter.get_remaining_quota(agent_id)
    
    return {
        "X-RateLimit-Limit-QPS": str(info["qps_limit"]),
        "X-RateLimit-Remaining-QPS": str(info["qps_remaining"]),
        "X-RateLimit-Limit-Daily": str(info["daily_post_quota"]),
        "X-RateLimit-Remaining-Daily": str(info["daily_post_remaining"]),
    }
