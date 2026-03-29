"""Tests for Agent Skill API registration and authentication."""

import pytest
from fastapi.testclient import TestClient

from app.db.models import AgentApiKeyRecord, AgentRecord
from app.services.agent_skill.auth import generate_api_key, hash_api_key


class TestAgentRegistration:
    """Test agent registration flow."""

    def test_register_agent_success(self, client: TestClient):
        """Test successful agent registration."""
        response = client.post(
            "/api/v1/agents/register",
            json={"name": "test-agent", "description": "A test agent"},
        )
        assert response.status_code == 201
        data = response.json()
        
        assert "agent" in data
        assert data["agent"]["name"] == "test-agent"
        assert data["agent"]["status"] == "pending_claim"
        assert "api_key" in data
        assert data["api_key"].startswith("rsk_live_")
        assert "claim_code" in data
        assert "claim_url" in data
        assert "important" in data

    def test_register_agent_duplicate_name(self, client: TestClient):
        """Test registration fails with duplicate name."""
        # First registration
        client.post(
            "/api/v1/agents/register",
            json={"name": "duplicate-agent"},
        )
        
        # Second registration with same name
        response = client.post(
            "/api/v1/agents/register",
            json={"name": "duplicate-agent"},
        )
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    def test_register_agent_invalid_name(self, client: TestClient):
        """Test registration fails with invalid name format."""
        response = client.post(
            "/api/v1/agents/register",
            json={"name": "Invalid Name!"},
        )
        assert response.status_code == 422  # Validation error


class TestAgentClaim:
    """Test agent claim flow."""

    def test_claim_agent_success(self, client: TestClient):
        """Test successful agent claim."""
        # Register first
        reg_response = client.post(
            "/api/v1/agents/register",
            json={"name": "claim-test-agent"},
        )
        reg_data = reg_response.json()
        agent_id = reg_data["agent"]["id"]
        claim_code = reg_data["claim_code"]
        
        # Claim
        response = client.post(
            f"/api/v1/agents/claim?agent_id={agent_id}",
            json={"claim_code": claim_code},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent"]["status"] == "active"

    def test_claim_agent_invalid_code(self, client: TestClient):
        """Test claim fails with wrong code."""
        # Register first
        reg_response = client.post(
            "/api/v1/agents/register",
            json={"name": "claim-invalid-agent"},
        )
        agent_id = reg_response.json()["agent"]["id"]
        
        # Claim with wrong code
        response = client.post(
            f"/api/v1/agents/claim?agent_id={agent_id}",
            json={"claim_code": "WRONG-CODE"},
        )
        assert response.status_code == 400
        assert "Invalid claim code" in response.json()["detail"]


class TestAgentAuthentication:
    """Test API key authentication."""

    def test_get_me_authenticated(self, client: TestClient):
        """Test /me endpoint with valid auth."""
        # Register and claim
        reg_response = client.post(
            "/api/v1/agents/register",
            json={"name": "auth-test-agent"},
        )
        reg_data = reg_response.json()
        api_key = reg_data["api_key"]
        agent_id = reg_data["agent"]["id"]
        claim_code = reg_data["claim_code"]
        
        client.post(
            f"/api/v1/agents/claim?agent_id={agent_id}",
            json={"claim_code": claim_code},
        )
        
        # Get me
        response = client.get(
            "/api/v1/agents/me",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        assert response.json()["agent"]["name"] == "auth-test-agent"

    def test_get_me_no_auth(self, client: TestClient):
        """Test /me endpoint without auth fails."""
        response = client.get("/api/v1/agents/me")
        assert response.status_code == 401  # Unauthorized

    def test_get_me_invalid_key(self, client: TestClient):
        """Test /me endpoint with invalid key fails."""
        response = client.get(
            "/api/v1/agents/me",
            headers={"Authorization": "Bearer rsk_live_invalid"},
        )
        assert response.status_code == 401

    def test_get_me_unclaimed_agent(self, client: TestClient):
        """Test /me endpoint with unclaimed agent fails."""
        # Register but don't claim
        reg_response = client.post(
            "/api/v1/agents/register",
            json={"name": "unclaimed-agent"},
        )
        api_key = reg_response.json()["api_key"]
        
        response = client.get(
            "/api/v1/agents/me",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 403
        assert "not yet claimed" in response.json()["detail"]


class TestApiKeyManagement:
    """Test API key rotation and revocation."""

    def _register_and_claim(self, client: TestClient, name: str) -> tuple[str, str]:
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
        return api_key, agent_id

    def test_rotate_api_key(self, client: TestClient):
        """Test API key rotation."""
        old_key, _ = self._register_and_claim(client, "rotate-test-agent")
        
        # Rotate
        response = client.post(
            "/api/v1/agents/keys/rotate",
            headers={"Authorization": f"Bearer {old_key}"},
        )
        assert response.status_code == 200
        new_key = response.json()["new_api_key"]
        assert new_key.startswith("rsk_live_")
        assert new_key != old_key
        
        # Old key should no longer work
        response = client.get(
            "/api/v1/agents/me",
            headers={"Authorization": f"Bearer {old_key}"},
        )
        assert response.status_code == 401
        
        # New key should work
        response = client.get(
            "/api/v1/agents/me",
            headers={"Authorization": f"Bearer {new_key}"},
        )
        assert response.status_code == 200

    def test_revoke_api_key(self, client: TestClient):
        """Test API key revocation."""
        api_key, _ = self._register_and_claim(client, "revoke-test-agent")
        
        # Revoke
        response = client.post(
            "/api/v1/agents/keys/revoke",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        
        # Key should no longer work
        response = client.get(
            "/api/v1/agents/me",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 401


class TestApiKeyGeneration:
    """Test API key generation utilities."""

    def test_generate_api_key_format(self):
        """Test generated key has correct format."""
        full_key, key_hash, prefix = generate_api_key()
        
        assert full_key.startswith("rsk_live_")
        assert len(full_key) == 9 + 32  # "rsk_live_" (9 chars) + 32 hex chars
        assert len(key_hash) == 64  # SHA-256 hex
        assert prefix == full_key[:12]

    def test_hash_api_key_consistent(self):
        """Test hashing is consistent."""
        key = "rsk_live_test1234567890abcdef"
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)
        assert hash1 == hash2

    def test_hash_api_key_different_keys(self):
        """Test different keys produce different hashes."""
        key1, hash1, _ = generate_api_key()
        key2, hash2, _ = generate_api_key()
        assert hash1 != hash2
