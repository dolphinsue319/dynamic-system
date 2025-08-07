"""Tests for intent classifier"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from src.orchestrator.intent_classifier import IntentClassifier, Intent


class TestIntentClassifier:
    """Test cases for intent classifier"""
    
    @pytest.fixture
    def config(self):
        """Test configuration"""
        return {
            "classification": {
                "model": "gemini-2.0-flash",
                "temperature": 0.3,
                "confidence_threshold": 0.7
            }
        }
    
    @pytest.fixture
    def classifier(self, config):
        """Create test classifier instance"""
        return IntentClassifier(config)
    
    @pytest.mark.asyncio
    async def test_classify_read_intent(self, classifier):
        """Test classification of READ intent"""
        with patch.object(classifier.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = """
            {
                "intent": "READ",
                "confidence": 0.95,
                "reasoning": "User wants to view existing code"
            }
            """
            
            result = await classifier.classify("Show me the contents of main.py")
            
            assert result["intent"] == Intent.READ
            assert result["confidence"] == 0.95
            assert "reasoning" in result
    
    @pytest.mark.asyncio
    async def test_classify_write_intent(self, classifier):
        """Test classification of WRITE intent"""
        with patch.object(classifier.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = """
            {
                "intent": "WRITE",
                "confidence": 0.90,
                "reasoning": "User wants to create a new function"
            }
            """
            
            result = await classifier.classify("Create a new function called process_data")
            
            assert result["intent"] == Intent.WRITE
            assert result["confidence"] == 0.90
    
    @pytest.mark.asyncio
    async def test_classify_search_intent(self, classifier):
        """Test classification of SEARCH intent"""
        with patch.object(classifier.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = """
            {
                "intent": "SEARCH",
                "confidence": 0.88,
                "reasoning": "User wants to find specific code patterns"
            }
            """
            
            result = await classifier.classify("Find all functions that use async/await")
            
            assert result["intent"] == Intent.SEARCH
            assert result["confidence"] == 0.88
    
    @pytest.mark.asyncio
    async def test_classify_analyze_intent(self, classifier):
        """Test classification of ANALYZE intent"""
        with patch.object(classifier.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = """
            {
                "intent": "ANALYZE",
                "confidence": 0.92,
                "reasoning": "User wants code analysis and insights"
            }
            """
            
            result = await classifier.classify("Analyze the performance bottlenecks in this code")
            
            assert result["intent"] == Intent.ANALYZE
            assert result["confidence"] == 0.92
    
    @pytest.mark.asyncio
    async def test_classify_manage_intent(self, classifier):
        """Test classification of MANAGE intent"""
        with patch.object(classifier.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = """
            {
                "intent": "MANAGE",
                "confidence": 0.85,
                "reasoning": "User wants to refactor code structure"
            }
            """
            
            result = await classifier.classify("Refactor this module to use dependency injection")
            
            assert result["intent"] == Intent.MANAGE
            assert result["confidence"] == 0.85
    
    @pytest.mark.asyncio
    async def test_classify_with_cache(self, classifier):
        """Test that classification uses cache for repeated requests"""
        request = "Find all TODO comments"
        
        with patch.object(classifier.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = """
            {
                "intent": "SEARCH",
                "confidence": 0.90,
                "reasoning": "Searching for comments"
            }
            """
            
            # First call
            result1 = await classifier.classify(request)
            
            # Second call (should use cache)
            result2 = await classifier.classify(request)
            
            # LLM should only be called once
            assert mock_complete.call_count == 1
            assert result1 == result2
    
    @pytest.mark.asyncio
    async def test_classify_error_handling(self, classifier):
        """Test error handling in classification"""
        with patch.object(classifier.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.side_effect = Exception("LLM API error")
            
            result = await classifier.classify("Test request")
            
            # Should return default intent on error
            assert result["intent"] == Intent.ANALYZE
            assert result["confidence"] == 0.5
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_classify_invalid_json_response(self, classifier):
        """Test handling of invalid JSON from LLM"""
        with patch.object(classifier.llm_client, 'complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = "This is not valid JSON"
            
            result = await classifier.classify("Test request")
            
            # Should handle gracefully
            assert result["intent"] == Intent.ANALYZE
            assert result["confidence"] == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])