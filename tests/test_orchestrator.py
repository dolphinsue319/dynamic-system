"""Integration tests for the main orchestrator"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.orchestrator.coordinator import Coordinator


class TestOrchestrator:
    """Integration tests for the coordinator"""
    
    @pytest.fixture
    def config(self):
        """Test configuration"""
        return {
            "classification": {
                "model": "gemini-2.0-flash",
                "temperature": 0.3
            },
            "analysis": {
                "model": "gemini-2.0-flash",
                "temperature": 0.3
            },
            "prompt_generation": {
                "model": "gpt-4o-mini",
                "temperature": 0.7
            },
            "execution": {
                "simple": {
                    "preferred": "gemini-2.0-flash",
                    "fallback": ["gpt-3.5-turbo"]
                },
                "moderate": {
                    "preferred": "gpt-4o-mini",
                    "fallback": ["gemini-2.5-pro", "claude-3-haiku-20240307"]
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
                    "capabilities": ["read", "write", "search"]
                }
            }
        }
    
    @pytest.fixture
    async def coordinator(self, config):
        """Create test coordinator instance"""
        coord = Coordinator(config)
        await coord.initialize()
        return coord
    
    @pytest.mark.asyncio
    async def test_orchestrate_simple_read(self, coordinator):
        """Test orchestration of a simple read request"""
        # Mock the components
        with patch.object(coordinator.intent_classifier, 'classify', new_callable=AsyncMock) as mock_classify, \
             patch.object(coordinator.complexity_analyzer, 'analyze', new_callable=AsyncMock) as mock_analyze, \
             patch.object(coordinator.service_selector, 'select_services', new_callable=AsyncMock) as mock_select_services, \
             patch.object(coordinator.prompt_generator, 'generate', new_callable=AsyncMock) as mock_generate, \
             patch.object(coordinator.model_selector, 'select_model', new_callable=AsyncMock) as mock_select_model, \
             patch.object(coordinator.fallback_handler, 'execute_with_fallback', new_callable=AsyncMock) as mock_execute:
            
            # Setup mock returns
            mock_classify.return_value = {
                "intent": "READ",
                "confidence": 0.95
            }
            
            mock_analyze.return_value = {
                "complexity": "simple",
                "confidence": 0.90
            }
            
            mock_select_services.return_value = ["file_manager"]
            
            mock_generate.return_value = "You are a helpful assistant. Read the requested file."
            
            mock_select_model.return_value = "gemini-2.0-flash"
            
            mock_execute.return_value = {
                "success": True,
                "response": "File contents: print('Hello, World!')",
                "model_used": "gemini-2.0-flash",
                "services_used": ["file_manager"],
                "tokens_used": 50,
                "tokens_saved": 100,
                "cost": 0.001,
                "duration_ms": 500
            }
            
            # Execute orchestration
            result = await coordinator.orchestrate("Show me the contents of main.py")
            
            # Verify the flow
            assert result["success"] == True
            assert result["intent"] == "READ"
            assert result["complexity"] == "simple"
            assert result["selected_model"] == "gemini-2.0-flash"
            assert result["selected_services"] == ["file_manager"]
            assert "response" in result
            assert "metrics" in result
    
    @pytest.mark.asyncio
    async def test_orchestrate_complex_refactor(self, coordinator):
        """Test orchestration of a complex refactoring request"""
        with patch.object(coordinator.intent_classifier, 'classify', new_callable=AsyncMock) as mock_classify, \
             patch.object(coordinator.complexity_analyzer, 'analyze', new_callable=AsyncMock) as mock_analyze, \
             patch.object(coordinator.service_selector, 'select_services', new_callable=AsyncMock) as mock_select_services, \
             patch.object(coordinator.prompt_generator, 'generate', new_callable=AsyncMock) as mock_generate, \
             patch.object(coordinator.model_selector, 'select_model', new_callable=AsyncMock) as mock_select_model, \
             patch.object(coordinator.fallback_handler, 'execute_with_fallback', new_callable=AsyncMock) as mock_execute:
            
            mock_classify.return_value = {
                "intent": "MANAGE",
                "confidence": 0.88
            }
            
            mock_analyze.return_value = {
                "complexity": "complex",
                "confidence": 0.85,
                "factors": {
                    "scope": "entire_codebase",
                    "risk": "high"
                }
            }
            
            mock_select_services.return_value = ["file_manager", "code_analyzer", "test_runner"]
            
            mock_generate.return_value = "You are an expert software architect..."
            
            mock_select_model.return_value = "gpt-4o"
            
            mock_execute.return_value = {
                "success": True,
                "response": "Refactoring plan: 1. Extract interfaces...",
                "model_used": "gpt-4o",
                "services_used": ["file_manager", "code_analyzer"],
                "tokens_used": 2000,
                "tokens_saved": 4000,
                "cost": 0.05,
                "duration_ms": 3000
            }
            
            result = await coordinator.orchestrate(
                "Refactor the authentication module to use dependency injection"
            )
            
            assert result["complexity"] == "complex"
            assert result["selected_model"] == "gpt-4o"
            assert len(result["selected_services"]) == 3
    
    @pytest.mark.asyncio
    async def test_orchestrate_with_context(self, coordinator):
        """Test orchestration with additional context"""
        context = {
            "project_type": "FastAPI",
            "language": "Python",
            "current_file": "api/endpoints.py"
        }
        
        with patch.object(coordinator.fallback_handler, 'execute_with_fallback', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {
                "success": True,
                "response": "Created new endpoint",
                "model_used": "gpt-4o-mini",
                "services_used": ["file_manager"],
                "tokens_used": 100,
                "cost": 0.002
            }
            
            result = await coordinator.orchestrate(
                "Add a new endpoint for user profiles",
                context=context
            )
            
            # Verify context was passed through
            call_args = mock_execute.call_args
            assert call_args[1]["context"] == context
    
    @pytest.mark.asyncio
    async def test_orchestrate_with_options(self, coordinator):
        """Test orchestration with user options"""
        options = {
            "preferred_models": ["gemini-2.5-pro"],
            "max_cost": 0.01,
            "max_latency_ms": 2000
        }
        
        with patch.object(coordinator.model_selector, 'select_model', new_callable=AsyncMock) as mock_select_model, \
             patch.object(coordinator.fallback_handler, 'execute_with_fallback', new_callable=AsyncMock) as mock_execute:
            
            mock_select_model.return_value = "gemini-2.5-pro"
            
            mock_execute.return_value = {
                "success": True,
                "response": "Analysis complete",
                "model_used": "gemini-2.5-pro",
                "services_used": [],
                "tokens_used": 200,
                "cost": 0.008
            }
            
            result = await coordinator.orchestrate(
                "Analyze code quality",
                options=options
            )
            
            # Verify options were considered
            mock_select_model.assert_called_with("moderate", options)
            assert result["selected_model"] == "gemini-2.5-pro"
    
    @pytest.mark.asyncio
    async def test_orchestrate_fallback_on_failure(self, coordinator):
        """Test that orchestration handles failures with fallback"""
        with patch.object(coordinator.fallback_handler, 'execute_with_fallback', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {
                "success": True,
                "response": "Completed with fallback",
                "model_used": "gpt-3.5-turbo",  # Fallback model
                "services_used": [],
                "tokens_used": 150,
                "cost": 0.003,
                "fallback_attempts": 2,
                "attempts": [
                    {"model": "gpt-4o", "success": False, "error": "Rate limit"},
                    {"model": "gemini-2.5-pro", "success": False, "error": "API error"},
                    {"model": "gpt-3.5-turbo", "success": True}
                ]
            }
            
            result = await coordinator.orchestrate("Generate unit tests")
            
            assert result["success"] == True
            assert "fallback_attempts" in result.get("metrics", {})
    
    @pytest.mark.asyncio
    async def test_orchestrate_metrics_tracking(self, coordinator):
        """Test that metrics are properly tracked"""
        with patch.object(coordinator.metrics_collector, 'start_request') as mock_start, \
             patch.object(coordinator.metrics_collector, 'end_request', new_callable=AsyncMock) as mock_end, \
             patch.object(coordinator.fallback_handler, 'execute_with_fallback', new_callable=AsyncMock) as mock_execute:
            
            mock_start.return_value = "req_123"
            
            mock_execute.return_value = {
                "success": True,
                "response": "Done",
                "model_used": "gpt-4o-mini",
                "services_used": ["file_manager"],
                "tokens_used": 100,
                "tokens_saved": 200,
                "cost": 0.002,
                "duration_ms": 1000
            }
            
            result = await coordinator.orchestrate("Update configuration")
            
            # Verify metrics were tracked
            mock_start.assert_called_once()
            mock_end.assert_called_once()
            
            # Check that request_id was passed to end_request
            end_call_args = mock_end.call_args
            assert end_call_args[0][0] == "req_123"
    
    @pytest.mark.asyncio
    async def test_orchestrate_error_handling(self, coordinator):
        """Test error handling in orchestration"""
        with patch.object(coordinator.intent_classifier, 'classify', new_callable=AsyncMock) as mock_classify:
            mock_classify.side_effect = Exception("Classification failed")
            
            result = await coordinator.orchestrate("Test request")
            
            assert result["success"] == False
            assert "error" in result
            assert "Classification failed" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])