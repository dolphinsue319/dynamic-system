"""Tests for complexity analyzer"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from src.orchestrator.complexity_analyzer import ComplexityAnalyzer


class TestComplexityAnalyzer:
    """Test cases for complexity analyzer"""
    
    @pytest.fixture
    def config(self):
        """Test configuration"""
        return {
            "analysis": {
                "model": "gemini-2.0-flash",
                "temperature": 0.3
            }
        }
    
    @pytest.fixture
    def analyzer(self, config):
        """Create test analyzer instance"""
        return ComplexityAnalyzer(config)
    
    @pytest.mark.asyncio
    async def test_analyze_simple_complexity(self, analyzer):
        """Test analysis of simple complexity task"""
        with patch.object(analyzer.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = """
            {
                "complexity": "simple",
                "confidence": 0.95,
                "factors": {
                    "scope": "single_file",
                    "operations": 1,
                    "dependencies": 0,
                    "risk": "low"
                },
                "reasoning": "Basic file read operation"
            }
            """
            
            result = await analyzer.analyze(
                "Read the contents of config.json",
                {"intent": "READ"}
            )
            
            assert result["complexity"] == "simple"
            assert result["confidence"] == 0.95
            assert result["factors"]["risk"] == "low"
    
    @pytest.mark.asyncio
    async def test_analyze_moderate_complexity(self, analyzer):
        """Test analysis of moderate complexity task"""
        with patch.object(analyzer.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = """
            {
                "complexity": "moderate",
                "confidence": 0.85,
                "factors": {
                    "scope": "multiple_files",
                    "operations": 5,
                    "dependencies": 2,
                    "risk": "medium"
                },
                "reasoning": "Requires analysis across multiple modules"
            }
            """
            
            result = await analyzer.analyze(
                "Find all API endpoints and their dependencies",
                {"intent": "SEARCH"}
            )
            
            assert result["complexity"] == "moderate"
            assert result["confidence"] == 0.85
            assert result["factors"]["scope"] == "multiple_files"
    
    @pytest.mark.asyncio
    async def test_analyze_complex_task(self, analyzer):
        """Test analysis of complex task"""
        with patch.object(analyzer.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = """
            {
                "complexity": "complex",
                "confidence": 0.90,
                "factors": {
                    "scope": "entire_codebase",
                    "operations": 20,
                    "dependencies": 10,
                    "risk": "high"
                },
                "reasoning": "Major refactoring with multiple system impacts"
            }
            """
            
            result = await analyzer.analyze(
                "Refactor the entire authentication system to use OAuth 2.0",
                {"intent": "MANAGE"}
            )
            
            assert result["complexity"] == "complex"
            assert result["confidence"] == 0.90
            assert result["factors"]["risk"] == "high"
    
    @pytest.mark.asyncio
    async def test_analyze_with_existing_classification(self, analyzer):
        """Test that existing classification affects complexity analysis"""
        classification = {
            "intent": "WRITE",
            "confidence": 0.9,
            "sub_intent": "create_module"
        }
        
        with patch.object(analyzer.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = """
            {
                "complexity": "moderate",
                "confidence": 0.88,
                "factors": {
                    "scope": "new_module",
                    "operations": 8,
                    "dependencies": 3,
                    "risk": "medium"
                }
            }
            """
            
            result = await analyzer.analyze(
                "Create a new payment processing module",
                classification
            )
            
            # Verify that classification was passed to LLM
            call_args = mock_complete.call_args
            assert "WRITE" in call_args[1]["prompt"]
    
    @pytest.mark.asyncio
    async def test_analyze_with_cache(self, analyzer):
        """Test that complexity analysis uses cache"""
        request = "Update the user profile endpoint"
        classification = {"intent": "WRITE"}
        
        with patch.object(analyzer.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = """
            {
                "complexity": "simple",
                "confidence": 0.92
            }
            """
            
            # First call
            result1 = await analyzer.analyze(request, classification)
            
            # Second call (should use cache)
            result2 = await analyzer.analyze(request, classification)
            
            # LLM should only be called once
            assert mock_complete.call_count == 1
            assert result1 == result2
    
    @pytest.mark.asyncio
    async def test_analyze_error_handling(self, analyzer):
        """Test error handling in complexity analysis"""
        with patch.object(analyzer.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.side_effect = Exception("LLM API error")
            
            result = await analyzer.analyze(
                "Test request",
                {"intent": "READ"}
            )
            
            # Should return default complexity on error
            assert result["complexity"] == "moderate"
            assert result["confidence"] == 0.5
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_analyze_factors_extraction(self, analyzer):
        """Test extraction of complexity factors"""
        with patch.object(analyzer.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = """
            {
                "complexity": "moderate",
                "confidence": 0.87,
                "factors": {
                    "scope": "module",
                    "operations": 6,
                    "dependencies": 4,
                    "risk": "medium",
                    "time_estimate": "2-3 hours",
                    "skills_required": ["Python", "FastAPI", "SQL"]
                }
            }
            """
            
            result = await analyzer.analyze(
                "Add caching to the database queries",
                {"intent": "WRITE"}
            )
            
            assert "factors" in result
            assert result["factors"]["time_estimate"] == "2-3 hours"
            assert "Python" in result["factors"]["skills_required"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])