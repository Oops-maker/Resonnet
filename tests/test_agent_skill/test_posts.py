"""Tests for Agent Skill API posts and comments."""

import pytest
from fastapi.testclient import TestClient


class TestPosts:
    """Test post creation and management."""

    def _register_and_claim(self, client: TestClient, name: str, trusted: bool = False) -> str:
        """Helper to register and claim an agent, return API key."""
        from sqlalchemy import update
        from app.db.models import AgentRecord
        
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
            # Manually set trusted flag via app dependency override
            from app.db.session import get_db
            db = next(get_db())
            agent = db.get(AgentRecord, agent_id)
            agent.trusted = True
            db.commit()
        
        return api_key

    def test_create_post_untrusted_requires_verification(self, client: TestClient):
        """Test creating post as untrusted agent requires verification."""
        api_key = self._register_and_claim(client, "post-test-agent-1")
        
        response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"title": "Test Post", "body": "This is a test post."},
        )
        assert response.status_code == 201
        data = response.json()
        
        assert data["post"]["status"] == "pending_verification"
        assert data["verification_required"] is True
        assert "verification" in data
        assert "challenge_id" in data["verification"]
        assert "question" in data["verification"]

    def test_create_post_trusted_no_verification(self, client: TestClient):
        """Test creating post as trusted agent skips verification."""
        api_key = self._register_and_claim(client, "post-test-agent-2", trusted=True)
        
        response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"title": "Trusted Post", "body": "This is a trusted post."},
        )
        assert response.status_code == 201
        data = response.json()
        
        assert data["post"]["status"] == "published"
        assert data["verification_required"] is False
        assert data["verification"] is None

    def test_list_posts(self, client: TestClient):
        """Test listing published posts."""
        # Create a trusted agent and post
        api_key = self._register_and_claim(client, "post-list-agent", trusted=True)
        client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"title": "Visible Post", "body": "Should be visible."},
        )
        
        # List posts (no auth required for public posts)
        response = client.get("/api/v1/posts")
        assert response.status_code == 200
        data = response.json()
        
        assert "posts" in data
        assert len(data["posts"]) >= 1

    def test_get_single_post(self, client: TestClient):
        """Test getting a single post."""
        api_key = self._register_and_claim(client, "post-get-agent", trusted=True)
        create_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"title": "Single Post", "body": "Get this post."},
        )
        post_id = create_response.json()["post"]["id"]
        
        response = client.get(f"/api/v1/posts/{post_id}")
        assert response.status_code == 200
        assert response.json()["id"] == post_id

    def test_delete_own_post(self, client: TestClient):
        """Test deleting own post."""
        api_key = self._register_and_claim(client, "post-delete-agent", trusted=True)
        create_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": "Delete me."},
        )
        post_id = create_response.json()["post"]["id"]
        
        response = client.delete(
            f"/api/v1/posts/{post_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 204
        
        # Post should no longer exist
        response = client.get(f"/api/v1/posts/{post_id}")
        assert response.status_code == 404

    def test_delete_other_agent_post_forbidden(self, client: TestClient):
        """Test cannot delete another agent's post."""
        api_key1 = self._register_and_claim(client, "post-owner-agent", trusted=True)
        api_key2 = self._register_and_claim(client, "post-other-agent", trusted=True)
        
        # Agent 1 creates post
        create_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key1}"},
            json={"body": "My post."},
        )
        post_id = create_response.json()["post"]["id"]
        
        # Agent 2 tries to delete
        response = client.delete(
            f"/api/v1/posts/{post_id}",
            headers={"Authorization": f"Bearer {api_key2}"},
        )
        assert response.status_code == 403


class TestComments:
    """Test comment creation and listing."""

    def _create_agent_and_post(self, client: TestClient, name: str) -> tuple[str, str]:
        """Helper to create an agent and a post."""
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
        
        # Make trusted
        db = next(get_db())
        agent = db.get(AgentRecord, agent_id)
        agent.trusted = True
        db.commit()
        
        # Create post
        post_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": "Test post for comments."},
        )
        post_id = post_response.json()["post"]["id"]
        
        return api_key, post_id

    def test_create_comment(self, client: TestClient):
        """Test creating a comment."""
        api_key, post_id = self._create_agent_and_post(client, "comment-test-agent")
        
        response = client.post(
            f"/api/v1/posts/{post_id}/comments",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": "This is a comment."},
        )
        assert response.status_code == 201
        data = response.json()
        
        assert data["body"] == "This is a comment."
        assert data["post_id"] == post_id

    def test_list_comments(self, client: TestClient):
        """Test listing comments on a post."""
        api_key, post_id = self._create_agent_and_post(client, "comment-list-agent")
        
        # Create some comments
        for i in range(3):
            client.post(
                f"/api/v1/posts/{post_id}/comments",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"body": f"Comment {i}"},
            )
        
        # List comments
        response = client.get(f"/api/v1/posts/{post_id}/comments")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["comments"]) == 3


class TestVoting:
    """Test upvote and downvote."""

    def _create_agent_and_post(self, client: TestClient, name: str) -> tuple[str, str]:
        """Helper to create an agent and a post."""
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
        
        # Make trusted
        db = next(get_db())
        agent = db.get(AgentRecord, agent_id)
        agent.trusted = True
        db.commit()
        
        # Create post
        post_response = client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"body": "Votable post."},
        )
        post_id = post_response.json()["post"]["id"]
        
        return api_key, post_id

    def test_upvote(self, client: TestClient):
        """Test upvoting a post."""
        api_key, post_id = self._create_agent_and_post(client, "vote-test-agent")
        
        response = client.post(
            f"/api/v1/posts/{post_id}/upvote",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        assert response.json()["upvotes"] == 1

    def test_downvote(self, client: TestClient):
        """Test downvoting a post."""
        api_key, post_id = self._create_agent_and_post(client, "vote-down-agent")
        
        response = client.post(
            f"/api/v1/posts/{post_id}/downvote",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        assert response.json()["downvotes"] == 1
