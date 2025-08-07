"""Intent classifier for request categorization"""

import logging
from typing import Dict, Any, List
from enum import Enum

from ..utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class Intent(Enum):
    """Supported intent types"""
    READ = "read"
    WRITE = "write"
    SEARCH = "search"
    ANALYZE = "analyze"
    MANAGE = "manage"


class IntentClassifier:
    """Classifies user requests into intent categories"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm_client = LLMClient(config)
        self.intents = [intent.value for intent in Intent]
        
        # Classification prompt template
        self.classification_prompt = """Classify the following request into EXACTLY ONE of these categories:
{intents}

Request: {request}

Rules:
- READ: Getting or viewing existing information
- WRITE: Creating, modifying, or generating new content
- SEARCH: Finding or locating specific information
- ANALYZE: Processing, evaluating, or extracting insights from data
- MANAGE: Organizing, configuring, or administering resources

Respond with ONLY the category name, nothing else."""
    
    async def initialize(self):
        """Initialize the classifier"""
        await self.llm_client.initialize()
        logger.info("Intent classifier initialized")
    
    async def classify(self, request: str) -> Dict[str, Any]:
        """
        Classify a request into an intent category
        
        Args:
            request: The user request to classify
            
        Returns:
            Dictionary with intent and confidence
        """
        try:
            # Build classification prompt
            prompt = self.classification_prompt.format(
                intents=", ".join(self.intents),
                request=request
            )
            
            # Use lightweight model for classification
            model = self.config.get("classifier", {}).get("default", "gemini-2.0-flash")
            temperature = self.config.get("classifier", {}).get("temperature", 0.1)
            max_tokens = self.config.get("classifier", {}).get("max_tokens", 100)
            
            # Get classification
            response = await self.llm_client.complete(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Parse and validate response
            intent = response.strip().lower()
            
            # Validate intent
            if intent not in self.intents:
                # Try to match partial or find closest
                intent = self._fuzzy_match_intent(intent)
            
            # Calculate confidence based on response clarity
            confidence = self._calculate_confidence(response, intent)
            
            logger.info(f"Classified request as '{intent}' with confidence {confidence}")
            
            return {
                "intent": intent,
                "confidence": confidence,
                "raw_response": response
            }
            
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            # Default to most general intent
            return {
                "intent": Intent.READ.value,
                "confidence": 0.0,
                "error": str(e)
            }
    
    def _fuzzy_match_intent(self, response: str) -> str:
        """
        Try to match intent from unclear response
        
        Args:
            response: The LLM response
            
        Returns:
            Best matching intent
        """
        response_lower = response.lower()
        
        # Check if any intent keyword is in response
        for intent in self.intents:
            if intent in response_lower:
                return intent
        
        # Check for common synonyms
        synonym_map = {
            "get": Intent.READ.value,
            "fetch": Intent.READ.value,
            "retrieve": Intent.READ.value,
            "create": Intent.WRITE.value,
            "generate": Intent.WRITE.value,
            "make": Intent.WRITE.value,
            "find": Intent.SEARCH.value,
            "locate": Intent.SEARCH.value,
            "look": Intent.SEARCH.value,
            "examine": Intent.ANALYZE.value,
            "evaluate": Intent.ANALYZE.value,
            "process": Intent.ANALYZE.value,
            "organize": Intent.MANAGE.value,
            "configure": Intent.MANAGE.value,
            "admin": Intent.MANAGE.value
        }
        
        for keyword, intent in synonym_map.items():
            if keyword in response_lower:
                return intent
        
        # Default to READ if unclear
        logger.warning(f"Could not match intent from response: {response}")
        return Intent.READ.value
    
    def _calculate_confidence(self, response: str, intent: str) -> float:
        """
        Calculate confidence score for classification
        
        Args:
            response: The LLM response
            intent: The classified intent
            
        Returns:
            Confidence score between 0 and 1
        """
        # Clean response
        clean_response = response.strip().lower()
        
        # Perfect match
        if clean_response == intent:
            return 1.0
        
        # Intent is in response
        if intent in clean_response:
            return 0.9
        
        # Response contains multiple words (uncertain)
        if len(clean_response.split()) > 2:
            return 0.6
        
        # Fuzzy matched
        return 0.7
    
    def get_intent_description(self, intent: str) -> str:
        """Get human-readable description of intent"""
        descriptions = {
            Intent.READ.value: "Reading or retrieving existing information",
            Intent.WRITE.value: "Creating or modifying content",
            Intent.SEARCH.value: "Searching for specific information",
            Intent.ANALYZE.value: "Analyzing or processing data",
            Intent.MANAGE.value: "Managing or configuring resources"
        }
        return descriptions.get(intent, "Unknown intent")