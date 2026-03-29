"""Tests for heartbeat, search, and webhooks."""

import pytest
from fastapi.testclient import TestClient


class TestHeartbeat:
    """Test heartbeat endpoint."""

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

    def test_heartbeat_success(self, client: TestClient):
        """Test successful heartbeat."""
        api_key = self._register_and_claim(client, "heartbeat-test-agent")
        
        response = client.post(
            "/api/v1/heartbeat",
            headers={"Authorization": f"Bearer {api_key}"},
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["acknowledged"] is True
        assert "next_heartbeat_seconds" in data
        assert data["next_heartbeat_seconds"] > 0
        assert "notifications" in data

    def test_heartbeat_no_auth(self, client: TestClient):
        """Test heartbeat without auth fails."""
        response = client.post("/api/v1/heartbeat", json={})
        assert response.status_code == 401  # Unauthorized


class TestSearch:
    """Test search endpoint."""

    def _create_agent_and_posts(self, client: TestClient, name: str) -> str:
        """Helper to create agent with posts."""
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
        
        # Create some posts
        client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"title": "Machine Learning", "body": "Deep learning and neural networks."},
        )
        client.post(
            "/api/v1/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"title": "Python Programming", "body": "Python is a great language."},
        )
        
        return api_key

    def test_search_posts(self, client: TestClient):
        """Test searching for posts."""
        self._create_agent_and_posts(client, "search-test-agent")
        
        response = client.get("/api/v1/search?q=learning")
        assert response.status_code == 200
        data = response.json()
        
        assert "results" in data
        # Should find the ML post
        ml_results = [r for r in data["results"] if "learning" in r["snippet"].lower()]
        assert len(ml_results) > 0

    def test_search_with_semantic(self, client: TestClient):
        """Test search returns similarity scores when semantic=true."""
        self._create_agent_and_posts(client, "search-semantic-agent")
        
        response = client.get("/api/v1/search?q=artificial+intelligence&semantic=true")
        assert response.status_code == 200
        data = response.json()
        
        # Results should have similarity scores
        if data["results"]:
            assert data["results"][0]["similarity"] is not None

    def test_search_type_filter(self, client: TestClient):
        """Test search with type filter."""
        self._create_agent_and_posts(client, "search-filter-agent")
        
        response = client.get("/api/v1/search?q=python&type=posts")
        assert response.status_code == 200
        data = response.json()
        
        # All results should be posts
        for result in data["results"]:
            assert result["type"] == "post"


class TestWebhooks:
    """Test webhook endpoints."""

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

    def test_create_webhook(self, client: TestClient):
        """Test creating a webhook subscription."""
        api_key = self._register_and_claim(client, "webhook-create-agent")
        
        response = client.post(
            "/api/v1/webhooks",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "url": "https://example.com/webhook",
                "events": ["mention", "reply"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        
        assert "webhook" in data
        assert data["webhook"]["url"] == "https://example.com/webhook"
        assert "mention" in data["webhook"]["events"]
        assert "secret" in data

    def test_list_webhooks(self, client: TestClient):
        """Test listing webhooks."""
        api_key = self._register_and_claim(client, "webhook-list-agent")
        
        # Create some webhooks
        for i in range(3):
            client.post(
                "/api/v1/webhooks",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "url": f"https://example.com/webhook{i}",
                    "events": ["mention"],
                },
            )
        
        response = client.get(
            "/api/v1/webhooks",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["webhooks"]) == 3

    def test_delete_webhook(self, client: TestClient):
        """Test deleting a webhook."""
        api_key = self._register_and_claim(client, "webhook-delete-agent")
        
        # Create webhook
        create_response = client.post(
            "/api/v1/webhooks",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "url": "https://example.com/to-delete",
                "events": ["upvote"],
            },
        )
        webhook_id = create_response.json()["webhook"]["id"]
        
        # Delete it
        response = client.delete(
            f"/api/v1/webhooks/{webhook_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 204
        
        # Should no longer be in list
        list_response = client.get(
            "/api/v1/webhooks",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        webhook_ids = [w["id"] for w in list_response.json()["webhooks"]]
        assert webhook_id not in webhook_ids

    def test_delete_other_agent_webhook_forbidden(self, client: TestClient):
        """Test cannot delete another agent's webhook."""
        api_key1 = self._register_and_claim(client, "webhook-owner-agent")
        api_key2 = self._register_and_claim(client, "webhook-other-agent")
        
        # Agent 1 creates webhook
        create_response = client.post(
            "/api/v1/webhooks",
            headers={"Authorization": f"Bearer {api_key1}"},
            json={
                "url": "https://example.com/owned",
                "events": ["mention"],
            },
        )
        webhook_id = create_response.json()["webhook"]["id"]
        
        # Agent 2 tries to delete
        response = client.delete(
            f"/api/v1/webhooks/{webhook_id}",
            headers={"Authorization": f"Bearer {api_key2}"},
        )
        assert response.status_code == 403


class TestSkillFiles:
    """Test skill documentation file endpoints."""

    def test_get_skill_md(self, client: TestClient):
        """Test getting SKILL.md."""
        response = client.get("/api/v1/skill.md")
        assert response.status_code == 200
        assert "Resonnet Agent Skill API" in response.text

    def test_get_heartbeat_md(self, client: TestClient):
        """Test getting HEARTBEAT.md."""
        response = client.get("/api/v1/heartbeat.md")
        assert response.status_code == 200
        assert "Heartbeat Protocol" in response.text

    def test_get_messaging_md(self, client: TestClient):
        """Test getting MESSAGING.md."""
        response = client.get("/api/v1/messaging.md")
        assert response.status_code == 200
        assert "Messaging" in response.text

    def test_get_rules_md(self, client: TestClient):
        """Test getting RULES.md."""
        response = client.get("/api/v1/rules.md")
        assert response.status_code == 200
        assert "Rules" in response.text
