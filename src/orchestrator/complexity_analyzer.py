"""Complexity analyzer for request evaluation"""

import logging
from typing import Dict, Any

from ..utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ComplexityAnalyzer:
    """Analyzes the complexity of requests"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm_client = LLMClient(config)
        
        # Complexity analysis prompt template
        self.analysis_prompt = """Analyze the complexity of this {intent} task and classify it as: simple, moderate, or complex.

Task: {request}

Consider these factors:
- Number of steps required
- Need for reasoning or creativity
- Amount of data to process
- Dependencies and interactions
- Technical difficulty

Examples:
- Simple: Single clear action, straightforward result (e.g., "read a file", "get current time")
- Moderate: Multiple steps or some decision-making (e.g., "search and summarize", "refactor a function")
- Complex: Extensive processing, creativity, or multi-system coordination (e.g., "design a system", "analyze and optimize codebase")

Respond with ONLY one word: simple, moderate, or complex."""
    
    async def initialize(self):
        """Initialize the analyzer"""
        await self.llm_client.initialize()
        logger.info("Complexity analyzer initialized")
    
    async def analyze(self, request: str, intent: str) -> str:
        """
        Analyze the complexity of a request
        
        Args:
            request: The user request
            intent: The classified intent
            
        Returns:
            Complexity level: simple, moderate, or complex
        """
        try:
            # Build analysis prompt
            prompt = self.analysis_prompt.format(
                intent=intent,
                request=request
            )
            
            # Use lightweight model for analysis
            model = self.config.get("complexity_analyzer", {}).get("default", "gemini-2.0-flash")
            temperature = self.config.get("complexity_analyzer", {}).get("temperature", 0.1)
            max_tokens = self.config.get("complexity_analyzer", {}).get("max_tokens", 50)
            
            # Get complexity assessment
            response = await self.llm_client.complete(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Parse and validate response
            complexity = response.strip().lower()
            
            # Validate complexity level
            valid_levels = ["simple", "moderate", "complex"]
            if complexity not in valid_levels:
                complexity = self._infer_complexity(response, request)
            
            logger.info(f"Analyzed request complexity as: {complexity}")
            
            return complexity
            
        except Exception as e:
            logger.error(f"Complexity analysis failed: {e}")
            # Default to moderate complexity
            return "moderate"
    
    def _infer_complexity(self, response: str, request: str) -> str:
        """
        Infer complexity from unclear response or request characteristics
        
        Args:
            response: The LLM response
            request: The original request
            
        Returns:
            Inferred complexity level
        """
        response_lower = response.lower()
        
        # Check for complexity keywords in response
        if any(word in response_lower for word in ["simple", "easy", "basic", "straightforward"]):
            return "simple"
        
        if any(word in response_lower for word in ["complex", "difficult", "extensive", "advanced"]):
            return "complex"
        
        # Analyze request characteristics
        request_lower = request.lower()
        
        # Simple indicators
        simple_keywords = ["get", "read", "show", "list", "count", "check"]
        if any(keyword in request_lower for keyword in simple_keywords) and len(request.split()) < 10:
            return "simple"
        
        # Complex indicators
        complex_keywords = ["analyze", "optimize", "design", "architect", "refactor", "implement"]
        if any(keyword in request_lower for keyword in complex_keywords):
            return "complex"
        
        # Multiple operations indicate higher complexity
        if any(word in request_lower for word in ["and", "then", "also", "with"]):
            if request.count(",") > 2 or request.count("and") > 2:
                return "complex"
            return "moderate"
        
        # Long requests often indicate complexity
        if len(request.split()) > 30:
            return "complex"
        elif len(request.split()) > 15:
            return "moderate"
        
        # Default to moderate
        logger.warning(f"Could not clearly determine complexity from: {response}")
        return "moderate"
    
    def estimate_resources(self, complexity: str) -> Dict[str, Any]:
        """
        Estimate resource requirements based on complexity
        
        Args:
            complexity: The complexity level
            
        Returns:
            Resource estimates
        """
        estimates = {
            "simple": {
                "estimated_tokens": 500,
                "estimated_time_ms": 1000,
                "estimated_cost_usd": 0.001,
                "recommended_timeout_ms": 5000
            },
            "moderate": {
                "estimated_tokens": 2000,
                "estimated_time_ms": 3000,
                "estimated_cost_usd": 0.01,
                "recommended_timeout_ms": 15000
            },
            "complex": {
                "estimated_tokens": 5000,
                "estimated_time_ms": 10000,
                "estimated_cost_usd": 0.05,
                "recommended_timeout_ms": 60000
            }
        }
        
        return estimates.get(complexity, estimates["moderate"])