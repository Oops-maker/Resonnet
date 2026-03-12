"""Tests for MCP environment variable replacement."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from app.agent.workspace import _replace_env_variables, copy_mcp_to_workspace


def test_replace_env_variables_basic():
    """Test basic environment variable replacement."""
    env_dict = {
        "API_KEY": "${MCP_API_KEY}",
        "BASE_URL": "https://api.example.com",
        "MODEL": "${MCP_MODEL}",
    }
    
    with patch.dict(os.environ, {"MCP_API_KEY": "sk-test123", "MCP_MODEL": "glm-5"}):
        result = _replace_env_variables(env_dict)
        assert result["API_KEY"] == "sk-test123"
        assert result["BASE_URL"] == "https://api.example.com"
        assert result["MODEL"] == "glm-5"


def test_replace_env_variables_headers():
    """Test environment variable replacement in HTTP headers."""
    headers = {
        "Authorization": "${DASHSCOPE_API_KEY}",
        "X-Custom-Header": "static-value",
    }
    
    with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-dashscope-123"}):
        result = _replace_env_variables(headers)
        assert result["Authorization"] == "sk-dashscope-123"
        assert result["X-Custom-Header"] == "static-value"


def test_replace_env_variables_missing():
    """Test that missing env vars keep original pattern."""
    env_dict = {"KEY": "${NONEXISTENT_VAR}"}
    result = _replace_env_variables(env_dict)
    assert result["KEY"] == "${NONEXISTENT_VAR}"


def test_replace_env_variables_empty():
    """Test empty/None env dicts."""
    assert _replace_env_variables(None) is None
    assert _replace_env_variables({}) is None


def test_replace_env_variables_multiple_patterns():
    """Test multiple patterns in single value."""
    env_dict = {"URL": "${HOST}:${PORT}/api"}
    with patch.dict(os.environ, {"HOST": "localhost", "PORT": "8080"}):
        result = _replace_env_variables(env_dict)
        assert result["URL"] == "localhost:8080/api"


def test_copy_mcp_to_workspace_with_env(tmp_path):
    """Test that copy_mcp_to_workspace resolves environment variables."""
    # Setup: create fake mcps meta
    mcps_dir = tmp_path / "mcps" / "default"
    mcps_dir.mkdir(parents=True)
    meta_file = mcps_dir / "meta.json"
    meta_file.write_text(json.dumps({
        "categories": {"tools": {"id": "tools", "name": "Tools"}},
        "mcps": {
            "test-mcp": {
                "id": "test-mcp",
                "source": "default",
                "name": "Test MCP",
                "category": "tools",
                "command": "uvx",
                "args": ["test-mcp"],
                "env": {
                    "API_KEY": "${MCP_API_KEY}",
                    "MODEL": "${MCP_MODEL}",
                }
            },
            "test-http-mcp": {
                "id": "test-http-mcp",
                "source": "default",
                "name": "Test HTTP MCP",
                "category": "remote",
                "type": "http",
                "url": "https://api.example.com/mcp",
                "headers": {
                    "Authorization": "${MCP_API_KEY}"
                },
                "description": "Test HTTP MCP server",
                "isActive": True
            }
        }
    }))
    
    ws_path = tmp_path / "workspace"
    ws_path.mkdir()
    
    with patch.dict(os.environ, {"MCP_API_KEY": "sk-123", "MCP_MODEL": "glm-5"}):
        with patch('app.core.config.get_mcps_dir', return_value=mcps_dir.parent):
            with patch('app.core.mcps_meta.load_aggregated_mcps_meta') as mock_load:
                # Mock the meta loading to return our test meta
                mock_load.return_value = (mcps_dir.parent, {
                    "test-mcp": {
                        "id": "test-mcp",
                        "source": "default",
                        "name": "Test MCP",
                        "category": "tools",
                        "command": "uvx",
                        "args": ["test-mcp"],
                        "env": {
                            "API_KEY": "${MCP_API_KEY}",
                            "MODEL": "${MCP_MODEL}",
                        }
                    },
                    "test-http-mcp": {
                        "id": "test-http-mcp",
                        "source": "default",
                        "name": "Test HTTP MCP",
                        "category": "remote",
                        "type": "http",
                        "url": "https://api.example.com/mcp",
                        "headers": {
                            "Authorization": "${MCP_API_KEY}"
                        },
                        "description": "Test HTTP MCP server",
                        "isActive": True
                    }
                })
                
                # Test stdio type
                result = copy_mcp_to_workspace(ws_path, ["test-mcp"])
                assert result == ["test-mcp"]
                
                config_file = ws_path / "config" / "mcp.json"
                assert config_file.exists()
                config_data = json.loads(config_file.read_text())
                assert config_data["mcpServers"]["test-mcp"]["env"]["API_KEY"] == "sk-123"
                
                # Test HTTP type
                result = copy_mcp_to_workspace(ws_path, ["test-http-mcp"])
                assert result == ["test-http-mcp"]
                
                config_data = json.loads(config_file.read_text())
                assert config_data["mcpServers"]["test-http-mcp"]["type"] == "http"
                assert config_data["mcpServers"]["test-http-mcp"]["url"] == "https://api.example.com/mcp"
                assert config_data["mcpServers"]["test-http-mcp"]["headers"]["Authorization"] == "sk-123"
                assert config_data["mcpServers"]["test-http-mcp"]["description"] == "Test HTTP MCP server"
                assert config_data["mcpServers"]["test-http-mcp"]["isActive"] == True
