"""Pytest configuration and fixtures"""

import pytest
import asyncio
import os
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any


# Set test environment variables
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["GOOGLE_API_KEY"] = "test-key"
os.environ["ANTHROPIC_API_KEY"] = "test-key"


@pytest.fixture
def event_loop():
    """Create an event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def base_config() -> Dict[str, Any]:
    """Base configuration for tests"""
    return {
        "classification": {
            "model": "gemini-2.0-flash",
            "temperature": 0.3,
            "confidence_threshold": 0.7,
            "cache_ttl": 300
        },
        "analysis": {
            "model": "gemini-2.0-flash",
            "temperature": 0.3,
            "cache_ttl": 300
        },
        "prompt_generation": {
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "max_length": 2000,
            "cache_ttl": 600
        },
        "execution": {
            "simple": {
                "preferred": "gemini-2.0-flash",
                "fallback": ["gpt-3.5-turbo", "claude-3-haiku-20240307"]
            },
            "moderate": {
                "preferred": "gpt-4o-mini",
                "fallback": ["gemini-2.5-pro", "claude-3-sonnet-20240229"]
            },
            "complex": {
                "preferred": "gpt-4o",
                "fallback": ["o3", "claude-3-opus-20240229"]
            }
        },
        "mcp_services": {
            "file_manager": {
                "type": "stdio",
                "command": ["node", "/path/to/file-manager.js"],
                "capabilities": ["read", "write", "search"],
                "timeout": 30000
            },
            "code_analyzer": {
                "type": "stdio",
                "command": ["python", "-m", "code_analyzer"],
                "capabilities": ["analyze", "metrics", "dependencies"],
                "timeout": 60000
            },
            "test_runner": {
                "type": "http",
                "url": "http://localhost:8001",
                "capabilities": ["test", "coverage"],
                "timeout": 120000
            }
        },
        "cache": {
            "redis_url": "redis://localhost:6379",
            "default_ttl": 300
        },
        "metrics": {
            "prometheus_port": 9090,
            "collect_interval": 60
        },
        "logging": {
            "level": "INFO",
            "format": "json"
        }
    }


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for tests"""
    client = Mock()
    client.complete = AsyncMock()
    client.estimate_tokens = Mock(return_value=100)
    return client


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for tests"""
    client = Mock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=False)
    return client


@pytest.fixture
def sample_requests():
    """Sample requests for testing"""
    return {
        "simple_read": "Show me the contents of config.json",
        "moderate_write": "Create a new API endpoint for user profiles",
        "complex_refactor": "Refactor the entire authentication system to use OAuth 2.0",
        "search_query": "Find all functions that handle database connections",
        "analysis_request": "Analyze the security vulnerabilities in this code"
    }


@pytest.fixture
def sample_responses():
    """Sample LLM responses for testing"""
    return {
        "classification": {
            "intent": "READ",
            "confidence": 0.95,
            "reasoning": "User wants to view file contents"
        },
        "complexity": {
            "complexity": "simple",
            "confidence": 0.90,
            "factors": {
                "scope": "single_file",
                "operations": 1,
                "risk": "low"
            }
        },
        "prompt": "You are a helpful assistant. Help the user with their request.",
        "execution": "File contents successfully retrieved."
    }


@pytest.fixture
def mock_mcp_connector():
    """Mock MCP connector for tests"""
    connector = Mock()
    connector.connect = AsyncMock()
    connector.call_tool = AsyncMock()
    connector.disconnect = AsyncMock()
    return connector


class AsyncContextManager:
    """Helper for async context manager mocking"""
    
    def __init__(self, return_value=None):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def async_context_manager():
    """Factory for async context managers"""
    return AsyncContextManager