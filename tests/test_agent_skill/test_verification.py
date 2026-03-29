"""Tests for verification challenge system."""

import pytest
from datetime import datetime, timedelta, timezone

from app.services.agent_skill.verification import (
    CHALLENGE_EXPIRATION_MINUTES,
    MAX_ATTEMPTS,
    _generate_comprehension_challenge,
    _generate_logic_challenge,
    _generate_math_challenge,
)


class TestChallengeGeneration:
    """Test challenge generation utilities."""

    def test_math_challenge_format(self):
        """Test math challenge has correct format."""
        question, options, answer = _generate_math_challenge()
        
        assert question
        assert options is not None
        assert len(options) == 4
        assert answer in options

    def test_logic_challenge_format(self):
        """Test logic challenge has correct format."""
        question, options, answer = _generate_logic_challenge()
        
        assert question
        assert options is not None
        assert len(options) == 4
        assert answer in options

    def test_comprehension_challenge_format(self):
        """Test comprehension challenge has correct format."""
        question, options, answer = _generate_comprehension_challenge()
        
        assert question
        assert "Read the following" in question
        assert options is not None
        assert len(options) == 4
        assert answer in options

    def test_math_answer_is_correct(self):
        """Test math challenge answers are mathematically correct."""
        # Run multiple times to test different operations
        for _ in range(10):
            question, options, answer = _generate_math_challenge()
            
            # Parse the question to verify the answer
            if "+" in question:
                parts = question.split()
                a = int(parts[2])
                b = int(parts[4].rstrip("?"))
                assert int(answer) == a + b
            elif "×" in question:
                parts = question.split()
                a = int(parts[2])
                b = int(parts[4].rstrip("?"))
                assert int(answer) == a * b


class TestVerificationFlow:
    """Test verification challenge submission flow."""

    def _register_and_claim(self, client, name: str) -> str:
        """Helper to register and claim an agent."""
        reg_response = client.post(
            "/api/v1/agents/register",
            json={"name": name},
        )
        reg_data = reg_response.json()
        api_key = reg_data["api_key"]
        agent_id = reg_data["agent"]["id"]
        claim_code = reg_data["claim_code"]
        
        client.post(
            f"/api/v1/agents/claim?agent_id={agent_id}",
            json={"claim_code": claim_code},
        )
        return api_key

    def test_submit_correct_answer(self, client):
        """Test submitting correct verification answer."""
        from app.db.models import VerificationChallengeRecord
        from app.db.session import get_db
        
        api_key = self._register_and_claim(client, "verify-correct-agent")
        
        # Create post (gets challenge)
        post_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": "Test post needing verification."},
        )
        post_data = post_response.json()
        challenge_id = post_data["verification"]["challenge_id"]
        
        # Get the correct answer from DB
        db = next(get_db())
        challenge = db.get(VerificationChallengeRecord, challenge_id)
        correct_answer = challenge.correct_answer
        
        # Submit correct answer
        response = client.post(
            f"/api/v1/verification/{challenge_id}/submit",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"answer": correct_answer},
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["passed"] is True
        assert data["post_status"] == "published"

    def test_submit_wrong_answer(self, client):
        """Test submitting wrong verification answer."""
        api_key = self._register_and_claim(client, "verify-wrong-agent")
        
        # Create post (gets challenge)
        post_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": "Test post needing verification."},
        )
        post_data = post_response.json()
        challenge_id = post_data["verification"]["challenge_id"]
        
        # Submit wrong answer
        response = client.post(
            f"/api/v1/verification/{challenge_id}/submit",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"answer": "definitely wrong answer"},
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["passed"] is False
        assert "remaining" in data["message"].lower()

    def test_max_attempts_exceeded(self, client):
        """Test verification fails after max attempts."""
        api_key = self._register_and_claim(client, "verify-maxattempts-agent")
        
        # Create post (gets challenge)
        post_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": "Test post."},
        )
        post_data = post_response.json()
        challenge_id = post_data["verification"]["challenge_id"]
        
        # Submit wrong answers until max
        for i in range(MAX_ATTEMPTS):
            response = client.post(
                f"/api/v1/verification/{challenge_id}/submit",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"answer": f"wrong{i}"},
            )
        
        # Check final response
        data = response.json()
        assert data["passed"] is False
        assert data["post_status"] == "rejected"

    def test_submit_to_expired_challenge(self, client):
        """Test submitting to expired challenge fails."""
        from app.db.models import VerificationChallengeRecord
        from app.db.session import get_db
        
        api_key = self._register_and_claim(client, "verify-expired-agent")
        
        # Create post (gets challenge)
        post_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": "Test post."},
        )
        post_data = post_response.json()
        challenge_id = post_data["verification"]["challenge_id"]
        
        # Manually expire the challenge
        db = next(get_db())
        challenge = db.get(VerificationChallengeRecord, challenge_id)
        challenge.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        
        # Try to submit
        response = client.post(
            f"/api/v1/verification/{challenge_id}/submit",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"answer": "any"},
        )
        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()
