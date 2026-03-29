"""Tests for Agent Skill API rate limiter."""

import os
import time
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.services.agent_skill.rate_limiter import (
    InMemoryRateLimiter,
    RateLimitExceeded,
    RateLimitState,
    check_rate_limit,
    get_rate_limiter,
    rate_limit_headers,
    reset_rate_limiter,
)


class TestRateLimitState:
    """Test RateLimitState dataclass."""

    def test_default_state(self):
        """Test default state initialization."""
        state = RateLimitState()
        assert state.request_timestamps == []
        assert state.daily_post_count == 0
        assert state.daily_post_reset_date == ""


class TestInMemoryRateLimiter:
    """Test InMemoryRateLimiter class."""

    def test_default_limits(self):
        """Test default rate limits."""
        limiter = InMemoryRateLimiter()
        assert limiter.qps_limit == 10
        assert limiter.daily_post_quota == 1000

    def test_custom_limits(self):
        """Test custom rate limits."""
        limiter = InMemoryRateLimiter(qps_limit=5, daily_post_quota=100)
        assert limiter.qps_limit == 5
        assert limiter.daily_post_quota == 100

    def test_qps_limit_allowed(self):
        """Test QPS allows requests under limit."""
        limiter = InMemoryRateLimiter(qps_limit=5)
        agent_id = "test-agent-1"
        
        # 5 requests should be allowed
        for i in range(5):
            allowed, retry_after = limiter.check_qps(agent_id)
            assert allowed, f"Request {i+1} should be allowed"
            assert retry_after == 0

    def test_qps_limit_exceeded(self):
        """Test QPS blocks requests over limit."""
        limiter = InMemoryRateLimiter(qps_limit=3)
        agent_id = "test-agent-2"
        
        # 3 requests should be allowed
        for _ in range(3):
            allowed, _ = limiter.check_qps(agent_id)
            assert allowed
        
        # 4th request should be blocked
        allowed, retry_after = limiter.check_qps(agent_id)
        assert not allowed
        assert retry_after > 0

    def test_qps_limit_resets_after_window(self):
        """Test QPS limit resets after 1 second window."""
        limiter = InMemoryRateLimiter(qps_limit=2)
        agent_id = "test-agent-3"
        
        # Use up the limit
        limiter.check_qps(agent_id)
        limiter.check_qps(agent_id)
        
        # Should be blocked
        allowed, _ = limiter.check_qps(agent_id)
        assert not allowed
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Should be allowed again
        allowed, retry_after = limiter.check_qps(agent_id)
        assert allowed
        assert retry_after == 0

    def test_daily_post_quota_allowed(self):
        """Test daily POST quota allows requests under limit."""
        limiter = InMemoryRateLimiter(daily_post_quota=5)
        agent_id = "test-agent-4"
        
        for i in range(5):
            allowed, retry_after = limiter.check_daily_post_quota(agent_id)
            assert allowed, f"POST {i+1} should be allowed"
            limiter.record_post(agent_id)

    def test_daily_post_quota_exceeded(self):
        """Test daily POST quota blocks requests over limit."""
        limiter = InMemoryRateLimiter(daily_post_quota=3)
        agent_id = "test-agent-5"
        
        # Use up the quota
        for _ in range(3):
            allowed, _ = limiter.check_daily_post_quota(agent_id)
            assert allowed
            limiter.record_post(agent_id)
        
        # 4th POST should be blocked
        allowed, retry_after = limiter.check_daily_post_quota(agent_id)
        assert not allowed
        assert retry_after > 0  # Should return seconds until midnight

    def test_get_remaining_quota(self):
        """Test getting remaining quota info."""
        limiter = InMemoryRateLimiter(qps_limit=10, daily_post_quota=100)
        agent_id = "test-agent-6"
        
        info = limiter.get_remaining_quota(agent_id)
        assert info["qps_limit"] == 10
        assert info["qps_remaining"] == 10
        assert info["daily_post_quota"] == 100
        assert info["daily_post_remaining"] == 100
        
        # Use some quota
        limiter.check_qps(agent_id)
        limiter.check_qps(agent_id)
        limiter.record_post(agent_id)
        
        info = limiter.get_remaining_quota(agent_id)
        assert info["qps_remaining"] == 8
        assert info["daily_post_remaining"] == 99

    def test_reset_agent(self):
        """Test resetting rate limits for a specific agent."""
        limiter = InMemoryRateLimiter(qps_limit=2)
        agent_id = "test-agent-7"
        
        # Use up limit
        limiter.check_qps(agent_id)
        limiter.check_qps(agent_id)
        allowed, _ = limiter.check_qps(agent_id)
        assert not allowed
        
        # Reset
        limiter.reset_agent(agent_id)
        
        # Should be allowed again
        allowed, _ = limiter.check_qps(agent_id)
        assert allowed

    def test_reset_all(self):
        """Test resetting all rate limits."""
        limiter = InMemoryRateLimiter(qps_limit=1)
        
        # Use up limits for multiple agents
        for i in range(3):
            agent_id = f"test-agent-reset-{i}"
            limiter.check_qps(agent_id)
            allowed, _ = limiter.check_qps(agent_id)
            assert not allowed
        
        # Reset all
        limiter.reset_all()
        
        # All should be allowed again
        for i in range(3):
            agent_id = f"test-agent-reset-{i}"
            allowed, _ = limiter.check_qps(agent_id)
            assert allowed

    def test_per_agent_isolation(self):
        """Test rate limits are isolated per agent."""
        limiter = InMemoryRateLimiter(qps_limit=2)
        
        # Agent 1 uses up limit
        for _ in range(2):
            limiter.check_qps("agent-1")
        allowed, _ = limiter.check_qps("agent-1")
        assert not allowed
        
        # Agent 2 should still have quota
        allowed, _ = limiter.check_qps("agent-2")
        assert allowed


class TestGlobalRateLimiter:
    """Test global rate limiter functions."""

    def test_get_rate_limiter_singleton(self):
        """Test get_rate_limiter returns singleton."""
        reset_rate_limiter()
        
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2
        
        reset_rate_limiter()

    def test_reset_rate_limiter(self):
        """Test reset_rate_limiter clears global instance."""
        limiter1 = get_rate_limiter()
        reset_rate_limiter()
        limiter2 = get_rate_limiter()
        
        assert limiter1 is not limiter2
        reset_rate_limiter()


class TestRateLimitExceeded:
    """Test RateLimitExceeded exception."""

    def test_exception_properties(self):
        """Test exception has correct properties."""
        exc = RateLimitExceeded(
            detail="Too many requests",
            retry_after=30,
            limit_type="qps",
        )
        
        assert exc.status_code == 429
        assert exc.detail == "Too many requests"
        assert exc.headers["Retry-After"] == "30"
        assert exc.retry_after == 30
        assert exc.limit_type == "qps"


class TestRateLimitHeaders:
    """Test rate limit header generation."""

    def test_rate_limit_headers(self):
        """Test rate limit headers are generated correctly."""
        reset_rate_limiter()
        limiter = get_rate_limiter()
        agent_id = "test-agent-headers"
        
        headers = rate_limit_headers(agent_id)
        
        assert "X-RateLimit-Limit-QPS" in headers
        assert "X-RateLimit-Remaining-QPS" in headers
        assert "X-RateLimit-Limit-Daily" in headers
        assert "X-RateLimit-Remaining-Daily" in headers
        
        assert headers["X-RateLimit-Limit-QPS"] == "10"
        assert headers["X-RateLimit-Remaining-QPS"] == "10"
        
        reset_rate_limiter()


class TestEnvironmentConfiguration:
    """Test environment variable configuration."""

    def test_env_var_qps_limit(self):
        """Test QPS limit from environment variable."""
        with patch.dict(os.environ, {"AGENT_SKILL_QPS_LIMIT": "20"}):
            # Reimport to pick up new env var
            from importlib import reload
            import app.services.agent_skill.rate_limiter as rl_module
            reload(rl_module)
            
            assert rl_module.DEFAULT_QPS_LIMIT == 20
            
            # Restore
            reload(rl_module)

    def test_env_var_daily_quota(self):
        """Test daily quota from environment variable."""
        with patch.dict(os.environ, {"AGENT_SKILL_DAILY_POST_QUOTA": "500"}):
            from importlib import reload
            import app.services.agent_skill.rate_limiter as rl_module
            reload(rl_module)
            
            assert rl_module.DEFAULT_DAILY_POST_QUOTA == 500
            
            # Restore
            reload(rl_module)


class TestRateLimitIntegration:
    """Integration tests for rate limiting with FastAPI."""

    def test_rate_limit_with_authenticated_agent(self, client: TestClient):
        """Test rate limiting on authenticated endpoint."""
        reset_rate_limiter()
        
        # Register and claim an agent
        reg_response = client.post(
            "/api/v1/agents/register",
            json={"name": "rate-limit-test-agent"},
        )
        reg_data = reg_response.json()
        api_key = reg_data["api_key"]
        agent_id = reg_data["agent"]["id"]
        claim_code = reg_data["claim_code"]
        
        # Claim the agent
        client.post(
            f"/api/v1/agents/claim?agent_id={agent_id}",
            json={"claim_code": claim_code},
        )
        
        # Make requests within QPS limit (10 by default)
        for i in range(10):
            response = client.get(
                "/api/v1/agents/me",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            assert response.status_code == 200, f"Request {i+1} should succeed"
        
        # 11th request should be rate limited
        response = client.get(
            "/api/v1/agents/me",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        assert "Rate limit exceeded" in response.json()["detail"]
        
        reset_rate_limiter()

    def test_daily_post_quota_on_post_endpoints(self, client: TestClient):
        """Test daily POST quota on POST endpoints."""
        reset_rate_limiter()
        
        # Create rate limiter with low quota for testing
        from app.services.agent_skill import rate_limiter as rl_module
        rl_module._rate_limiter = InMemoryRateLimiter(qps_limit=100, daily_post_quota=3)
        
        # Register and claim an agent
        reg_response = client.post(
            "/api/v1/agents/register",
            json={"name": "quota-test-agent"},
        )
        reg_data = reg_response.json()
        api_key = reg_data["api_key"]
        agent_id = reg_data["agent"]["id"]
        claim_code = reg_data["claim_code"]
        
        client.post(
            f"/api/v1/agents/claim?agent_id={agent_id}",
            json={"claim_code": claim_code},
        )
        
        # Make POST requests up to quota
        # Note: Each POST to /heartbeat uses up quota
        for i in range(3):
            response = client.post(
                "/api/v1/heartbeat",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            assert response.status_code == 200, f"POST {i+1} should succeed"
        
        # Next POST should be rate limited
        response = client.post(
            "/api/v1/heartbeat",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 429
        assert "Daily POST quota exceeded" in response.json()["detail"]
        
        # GET requests should still work
        response = client.get(
            "/api/v1/agents/me",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        
        reset_rate_limiter()

    def test_rate_limit_different_agents(self, client: TestClient):
        """Test rate limits are per-agent."""
        reset_rate_limiter()
        
        # Create rate limiter with low limit for testing
        from app.services.agent_skill import rate_limiter as rl_module
        rl_module._rate_limiter = InMemoryRateLimiter(qps_limit=2, daily_post_quota=1000)
        
        # Register and claim first agent
        reg1 = client.post(
            "/api/v1/agents/register",
            json={"name": "agent-rate-1"},
        ).json()
        api_key1 = reg1["api_key"]
        client.post(
            f"/api/v1/agents/claim?agent_id={reg1['agent']['id']}",
            json={"claim_code": reg1["claim_code"]},
        )
        
        # Register and claim second agent
        reg2 = client.post(
            "/api/v1/agents/register",
            json={"name": "agent-rate-2"},
        ).json()
        api_key2 = reg2["api_key"]
        client.post(
            f"/api/v1/agents/claim?agent_id={reg2['agent']['id']}",
            json={"claim_code": reg2["claim_code"]},
        )
        
        # Agent 1: Use up QPS limit
        for _ in range(2):
            client.get(
                "/api/v1/agents/me",
                headers={"Authorization": f"Bearer {api_key1}"},
            )
        
        # Agent 1 should be limited
        response = client.get(
            "/api/v1/agents/me",
            headers={"Authorization": f"Bearer {api_key1}"},
        )
        assert response.status_code == 429
        
        # Agent 2 should still work
        response = client.get(
            "/api/v1/agents/me",
            headers={"Authorization": f"Bearer {api_key2}"},
        )
        assert response.status_code == 200
        
        reset_rate_limiter()


class TestThreadSafety:
    """Test thread safety of rate limiter."""

    def test_concurrent_requests(self):
        """Test rate limiter handles concurrent requests correctly."""
        import concurrent.futures
        
        limiter = InMemoryRateLimiter(qps_limit=100, daily_post_quota=1000)
        agent_id = "concurrent-test-agent"
        
        def make_request():
            allowed, _ = limiter.check_qps(agent_id)
            return allowed
        
        # Make 50 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should be allowed since limit is 100
        assert all(results)
        
        # Check remaining quota is correct
        info = limiter.get_remaining_quota(agent_id)
        assert info["qps_remaining"] == 50

    def test_concurrent_quota_tracking(self):
        """Test daily quota tracking under concurrent access."""
        import concurrent.futures
        
        limiter = InMemoryRateLimiter(qps_limit=1000, daily_post_quota=100)
        agent_id = "quota-concurrent-agent"
        
        def record_post():
            limiter.record_post(agent_id)
            return True
        
        # Record 50 POSTs concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(record_post) for _ in range(50)]
            [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # Check count is correct
        info = limiter.get_remaining_quota(agent_id)
        assert info["daily_post_remaining"] == 50
