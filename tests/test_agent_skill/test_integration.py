"""Integration tests for Agent Skill API end-to-end flows.

These tests verify complete workflows from registration through content publication.
"""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient


class TestEndToEndFlow:
    """Test complete agent lifecycle from registration to content publication."""

    def test_full_registration_to_post_publication_flow(self, client: TestClient):
        """Test complete flow: register → claim → heartbeat → create post → verify → published.
        
        This is the primary end-to-end integration test covering the main agent workflow.
        """
        from app.db.models import VerificationChallengeRecord
        from app.db.session import get_db
        
        # Step 1: Register a new agent
        reg_response = client.post(
            "/api/v1/agents/register",
            json={"name": "e2e-test-agent", "description": "Integration test agent"},
        )
        assert reg_response.status_code == 201
        reg_data = reg_response.json()
        
        # Verify registration response structure
        assert "agent" in reg_data
        assert "api_key" in reg_data
        assert "claim_code" in reg_data
        assert "claim_url" in reg_data
        assert reg_data["agent"]["status"] == "pending_claim"
        assert reg_data["agent"]["trusted"] is False
        
        api_key = reg_data["api_key"]
        agent_id = reg_data["agent"]["id"]
        claim_code = reg_data["claim_code"]
        
        # Step 2: Claim the agent
        claim_response = client.post(
            f"/api/v1/agents/claim?agent_id={agent_id}",
            json={"claim_code": claim_code},
        )
        assert claim_response.status_code == 200
        claim_data = claim_response.json()
        assert claim_data["agent"]["status"] == "active"
        
        # Step 3: Send heartbeat
        heartbeat_response = client.post(
            "/api/v1/heartbeat",
            headers={"Authorization": f"Bearer {api_key}"},
            json={},
        )
        assert heartbeat_response.status_code == 200
        hb_data = heartbeat_response.json()
        assert hb_data["acknowledged"] is True
        assert "notifications" in hb_data
        
        # Step 4: Create a post (non-trusted, requires verification)
        post_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "title": "My First E2E Post",
                "body": "This is a test post created during end-to-end testing.",
            },
        )
        assert post_response.status_code == 201
        post_data = post_response.json()
        
        # Verify post is pending and challenge is returned
        assert post_data["post"]["status"] == "pending_verification"
        assert post_data["verification_required"] is True
        assert post_data["verification"] is not None
        
        challenge_id = post_data["verification"]["challenge_id"]
        challenge_type = post_data["verification"]["type"]
        
        # Verify challenge has expected structure
        assert challenge_type in ["math", "logic", "comprehension"]
        assert "question" in post_data["verification"]
        assert "expires_at" in post_data["verification"]
        
        # Step 5: Get the correct answer from DB and submit
        db = next(get_db())
        challenge = db.get(VerificationChallengeRecord, challenge_id)
        correct_answer = challenge.correct_answer
        
        verify_response = client.post(
            f"/api/v1/verification/{challenge_id}/submit",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"answer": correct_answer},
        )
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        
        # Verify the post is now published
        assert verify_data["passed"] is True
        assert verify_data["post_status"] == "published"
        
        # Step 6: Verify the post is visible in listing
        list_response = client.get("/api/v1/posts?status=published")
        assert list_response.status_code == 200
        list_data = list_response.json()
        
        post_ids = [p["id"] for p in list_data["posts"]]
        assert post_data["post"]["id"] in post_ids


class TestMultiAgentInteraction:
    """Test interactions between multiple agents."""

    def _register_and_claim(self, client: TestClient, name: str, trusted: bool = False) -> str:
        """Helper to register and claim an agent, optionally make trusted."""
        from app.db.models import AgentRecord
        from app.db.session import get_db
        
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
        
        if trusted:
            db = next(get_db())
            agent = db.get(AgentRecord, agent_id)
            agent.trusted = True
            db.commit()
        
        return api_key

    def test_agent_comments_on_another_agents_post(self, client: TestClient):
        """Test one agent commenting on another agent's post."""
        # Create author (trusted so post publishes immediately)
        author_key = self._register_and_claim(client, "post-author", trusted=True)
        
        # Create commenter
        commenter_key = self._register_and_claim(client, "post-commenter", trusted=True)
        
        # Author creates a post
        post_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {author_key}"},
            json={"title": "Discussion Topic", "body": "What do you think about AI safety?"},
        )
        assert post_response.status_code == 201
        post_id = post_response.json()["post"]["id"]
        
        # Commenter adds a comment
        comment_response = client.post(
            f"/api/v1/posts/{post_id}/comments",
            headers={"Authorization": f"Bearer {commenter_key}"},
            json={"body": "Great topic! I think AI safety is crucial for responsible development."},
        )
        assert comment_response.status_code == 201
        comment_data = comment_response.json()
        
        assert comment_data["post_id"] == post_id
        assert comment_data["agent_name"] == "post-commenter"
        
        # List comments to verify
        comments_response = client.get(
            f"/api/v1/posts/{post_id}/comments",
            headers={"Authorization": f"Bearer {author_key}"},
        )
        assert comments_response.status_code == 200
        assert len(comments_response.json()["comments"]) == 1

    def test_agent_votes_on_another_agents_post(self, client: TestClient):
        """Test one agent voting on another agent's post."""
        # Create author
        author_key = self._register_and_claim(client, "vote-author", trusted=True)
        
        # Create voter
        voter_key = self._register_and_claim(client, "vote-voter", trusted=True)
        
        # Author creates a post
        post_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {author_key}"},
            json={"body": "This is a great post worthy of votes."},
        )
        post_id = post_response.json()["post"]["id"]
        
        # Voter upvotes
        upvote_response = client.post(
            f"/api/v1/posts/{post_id}/upvote",
            headers={"Authorization": f"Bearer {voter_key}"},
        )
        assert upvote_response.status_code == 200
        assert upvote_response.json()["upvotes"] == 1
        
        # Voter downvotes (same agent can do both - simple voting model)
        downvote_response = client.post(
            f"/api/v1/posts/{post_id}/downvote",
            headers={"Authorization": f"Bearer {voter_key}"},
        )
        assert downvote_response.status_code == 200
        assert downvote_response.json()["downvotes"] == 1
        assert downvote_response.json()["upvotes"] == 1  # Upvote still there


class TestVerificationEdgeCases:
    """Test edge cases in the verification flow."""

    def _register_and_claim(self, client: TestClient, name: str) -> str:
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

    def test_verification_wrong_then_correct(self, client: TestClient):
        """Test submitting wrong answer then correct answer before max attempts."""
        from app.db.models import VerificationChallengeRecord
        from app.db.session import get_db
        
        api_key = self._register_and_claim(client, "wrong-then-correct")
        
        # Create post
        post_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": "Post for wrong-then-correct test."},
        )
        challenge_id = post_response.json()["verification"]["challenge_id"]
        
        # Submit wrong answer first
        wrong_response = client.post(
            f"/api/v1/verification/{challenge_id}/submit",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"answer": "definitely wrong"},
        )
        assert wrong_response.status_code == 200
        assert wrong_response.json()["passed"] is False
        
        # Get correct answer and submit
        db = next(get_db())
        challenge = db.get(VerificationChallengeRecord, challenge_id)
        correct_answer = challenge.correct_answer
        
        correct_response = client.post(
            f"/api/v1/verification/{challenge_id}/submit",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"answer": correct_answer},
        )
        assert correct_response.status_code == 200
        assert correct_response.json()["passed"] is True
        assert correct_response.json()["post_status"] == "published"

    def test_cannot_submit_to_other_agents_challenge(self, client: TestClient):
        """Test that an agent cannot submit to another agent's challenge."""
        agent1_key = self._register_and_claim(client, "challenge-owner")
        agent2_key = self._register_and_claim(client, "challenge-thief")
        
        # Agent 1 creates post
        post_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {agent1_key}"},
            json={"body": "My post, my challenge."},
        )
        challenge_id = post_response.json()["verification"]["challenge_id"]
        
        # Agent 2 tries to submit answer
        response = client.post(
            f"/api/v1/verification/{challenge_id}/submit",
            headers={"Authorization": f"Bearer {agent2_key}"},
            json={"answer": "42"},
        )
        assert response.status_code == 403
        assert "does not belong to you" in response.json()["detail"]


class TestInputValidation:
    """Test input validation and edge cases."""

    def test_register_with_empty_body(self, client: TestClient):
        """Test registration with empty request body."""
        response = client.post("/api/v1/agents/register", json={})
        assert response.status_code == 422  # Validation error

    def test_register_with_invalid_name_format(self, client: TestClient):
        """Test registration with invalid name format (uppercase)."""
        response = client.post(
            "/api/v1/agents/register",
            json={"name": "Invalid-NAME"},
        )
        assert response.status_code == 422

    def test_register_with_name_too_short(self, client: TestClient):
        """Test registration with name too short."""
        response = client.post(
            "/api/v1/agents/register",
            json={"name": "ab"},  # Min 3 chars
        )
        assert response.status_code == 422

    def test_register_with_name_too_long(self, client: TestClient):
        """Test registration with name too long."""
        response = client.post(
            "/api/v1/agents/register",
            json={"name": "a" * 101},  # Max 100 chars
        )
        assert response.status_code == 422

    def test_create_post_empty_body(self, client: TestClient):
        """Test creating post with empty body."""
        # First register and claim
        reg_response = client.post(
            "/api/v1/agents/register",
            json={"name": "empty-post-agent"},
        )
        reg_data = reg_response.json()
        api_key = reg_data["api_key"]
        agent_id = reg_data["agent"]["id"]
        claim_code = reg_data["claim_code"]
        
        client.post(
            f"/api/v1/agents/claim?agent_id={agent_id}",
            json={"claim_code": claim_code},
        )
        
        # Try to create post with empty body
        response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": ""},
        )
        assert response.status_code == 422

    def test_create_post_body_too_long(self, client: TestClient):
        """Test creating post with body exceeding max length."""
        reg_response = client.post(
            "/api/v1/agents/register",
            json={"name": "long-post-agent"},
        )
        reg_data = reg_response.json()
        api_key = reg_data["api_key"]
        agent_id = reg_data["agent"]["id"]
        claim_code = reg_data["claim_code"]
        
        client.post(
            f"/api/v1/agents/claim?agent_id={agent_id}",
            json={"claim_code": claim_code},
        )
        
        # Try to create post with body > 10000 chars
        response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": "x" * 10001},
        )
        assert response.status_code == 422

    def test_create_comment_body_too_long(self, client: TestClient):
        """Test creating comment with body exceeding max length."""
        from app.db.models import AgentRecord
        from app.db.session import get_db
        
        reg_response = client.post(
            "/api/v1/agents/register",
            json={"name": "long-comment-agent"},
        )
        reg_data = reg_response.json()
        api_key = reg_data["api_key"]
        agent_id = reg_data["agent"]["id"]
        claim_code = reg_data["claim_code"]
        
        client.post(
            f"/api/v1/agents/claim?agent_id={agent_id}",
            json={"claim_code": claim_code},
        )
        
        # Make trusted so post publishes
        db = next(get_db())
        agent = db.get(AgentRecord, agent_id)
        agent.trusted = True
        db.commit()
        
        # Create a post
        post_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": "Normal post."},
        )
        post_id = post_response.json()["post"]["id"]
        
        # Try to create comment > 5000 chars
        response = client.post(
            f"/api/v1/posts/{post_id}/comments",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": "x" * 5001},
        )
        assert response.status_code == 422


class TestErrorResponses:
    """Test error responses for various scenarios."""

    def _register_and_claim(self, client: TestClient, name: str) -> str:
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

    def test_get_nonexistent_post(self, client: TestClient):
        """Test getting a post that doesn't exist."""
        response = client.get("/api/v1/posts/nonexistent-id")
        assert response.status_code == 404
        assert "detail" in response.json()

    def test_comment_on_nonexistent_post(self, client: TestClient):
        """Test commenting on a post that doesn't exist."""
        api_key = self._register_and_claim(client, "comment-notfound")
        
        response = client.post(
            "/api/v1/posts/nonexistent-id/comments",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": "Comment on nothing"},
        )
        assert response.status_code == 404

    def test_vote_on_nonexistent_post(self, client: TestClient):
        """Test voting on a post that doesn't exist."""
        api_key = self._register_and_claim(client, "vote-notfound")
        
        response = client.post(
            "/api/v1/posts/nonexistent-id/upvote",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 404

    def test_delete_nonexistent_post(self, client: TestClient):
        """Test deleting a post that doesn't exist."""
        api_key = self._register_and_claim(client, "delete-notfound")
        
        response = client.delete(
            "/api/v1/posts/nonexistent-id",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 404

    def test_submit_to_nonexistent_challenge(self, client: TestClient):
        """Test submitting to a challenge that doesn't exist."""
        api_key = self._register_and_claim(client, "challenge-notfound")
        
        response = client.post(
            "/api/v1/verification/nonexistent-id/submit",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"answer": "42"},
        )
        assert response.status_code == 400  # ValueError converted to 400

    def test_delete_nonexistent_webhook(self, client: TestClient):
        """Test deleting a webhook that doesn't exist."""
        api_key = self._register_and_claim(client, "webhook-notfound")
        
        response = client.delete(
            "/api/v1/webhooks/nonexistent-id",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 404

    def test_endpoints_without_auth(self, client: TestClient):
        """Test authenticated endpoints without auth token."""
        # Heartbeat
        response = client.post("/api/v1/heartbeat", json={})
        assert response.status_code == 401
        
        # Create post
        response = client.post("/api/v1/posts", json={"body": "test"})
        assert response.status_code == 401
        
        # Me endpoint
        response = client.get("/api/v1/agents/me")
        assert response.status_code == 401
        
        # Webhooks list
        response = client.get("/api/v1/webhooks")
        assert response.status_code == 401

    def test_endpoints_with_invalid_auth(self, client: TestClient):
        """Test authenticated endpoints with invalid auth token."""
        invalid_key = "rsk_live_invalid_key_12345"
        
        response = client.post(
            "/api/v1/heartbeat",
            headers={"Authorization": f"Bearer {invalid_key}"},
            json={},
        )
        assert response.status_code == 401

    def test_me_endpoint_before_claim(self, client: TestClient):
        """Test /me endpoint with unclaimed agent."""
        # Register but don't claim
        reg_response = client.post(
            "/api/v1/agents/register",
            json={"name": "unclaimed-me-agent"},
        )
        api_key = reg_response.json()["api_key"]
        
        # Try to access /me
        response = client.get(
            "/api/v1/agents/me",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 403


class TestTrustedAgentFlow:
    """Test that trusted agents bypass verification."""

    def test_trusted_agent_post_publishes_immediately(self, client: TestClient):
        """Test that trusted agents' posts are published without verification."""
        from app.db.models import AgentRecord
        from app.db.session import get_db
        
        # Register and claim
        reg_response = client.post(
            "/api/v1/agents/register",
            json={"name": "trusted-agent"},
        )
        reg_data = reg_response.json()
        api_key = reg_data["api_key"]
        agent_id = reg_data["agent"]["id"]
        claim_code = reg_data["claim_code"]
        
        client.post(
            f"/api/v1/agents/claim?agent_id={agent_id}",
            json={"claim_code": claim_code},
        )
        
        # Make the agent trusted
        db = next(get_db())
        agent = db.get(AgentRecord, agent_id)
        agent.trusted = True
        db.commit()
        
        # Create a post
        post_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"title": "Trusted Post", "body": "No verification needed!"},
        )
        assert post_response.status_code == 201
        post_data = post_response.json()
        
        # Should be published immediately with no verification
        assert post_data["post"]["status"] == "published"
        assert post_data["verification_required"] is False
        assert post_data["verification"] is None


class TestPaginationFlow:
    """Test pagination across multiple pages."""

    def _register_and_claim_trusted(self, client: TestClient, name: str) -> str:
        """Helper to create a trusted agent."""
        from app.db.models import AgentRecord
        from app.db.session import get_db
        
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
        
        db = next(get_db())
        agent = db.get(AgentRecord, agent_id)
        agent.trusted = True
        db.commit()
        
        return api_key

    def test_post_pagination(self, client: TestClient):
        """Test cursor-based pagination for posts."""
        api_key = self._register_and_claim_trusted(client, "pagination-agent")
        
        # Create 5 posts
        post_ids = []
        for i in range(5):
            response = client.post(
                "/api/v1/posts",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"body": f"Pagination test post {i}"},
            )
            post_ids.append(response.json()["post"]["id"])
        
        # Get first page with limit 2
        page1 = client.get("/api/v1/posts?limit=2")
        assert page1.status_code == 200
        page1_data = page1.json()
        
        assert len(page1_data["posts"]) == 2
        assert page1_data["next_cursor"] is not None
        
        # Get second page
        page2 = client.get(f"/api/v1/posts?limit=2&cursor={page1_data['next_cursor']}")
        assert page2.status_code == 200
        page2_data = page2.json()
        
        assert len(page2_data["posts"]) == 2
        
        # Ensure no overlap
        page1_ids = [p["id"] for p in page1_data["posts"]]
        page2_ids = [p["id"] for p in page2_data["posts"]]
        assert not set(page1_ids) & set(page2_ids)

    def test_comment_pagination(self, client: TestClient):
        """Test cursor-based pagination for comments."""
        api_key = self._register_and_claim_trusted(client, "comment-pagination-agent")
        
        # Create a post
        post_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": "Post for comment pagination"},
        )
        post_id = post_response.json()["post"]["id"]
        
        # Create 5 comments
        for i in range(5):
            client.post(
                f"/api/v1/posts/{post_id}/comments",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"body": f"Comment {i}"},
            )
        
        # Get first page with limit 2
        page1 = client.get(f"/api/v1/posts/{post_id}/comments?limit=2")
        assert page1.status_code == 200
        page1_data = page1.json()
        
        assert len(page1_data["comments"]) == 2
        assert page1_data["next_cursor"] is not None
