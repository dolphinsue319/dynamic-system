"""Model configuration and cost estimation"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum


class ModelTier(Enum):
    """Model pricing tiers"""
    BUDGET = "budget"      # Cheapest models
    STANDARD = "standard"  # Balanced cost/performance
    PREMIUM = "premium"    # High-end models


@dataclass
class ModelConfig:
    """Configuration for a specific model"""
    name: str
    provider: str
    tier: ModelTier
    input_cost_per_1k: float  # Cost per 1K input tokens in USD
    output_cost_per_1k: float  # Cost per 1K output tokens in USD
    max_context: int  # Maximum context length
    supports_functions: bool = True
    supports_vision: bool = False
    supports_streaming: bool = True
    average_latency_ms: int = 1000
    reliability_score: float = 0.95  # 0-1 score for reliability


# Predefined model configurations
MODEL_CONFIGS = {
    # OpenAI Models
    "gpt-4o": ModelConfig(
        name="gpt-4o",
        provider="openai",
        tier=ModelTier.PREMIUM,
        input_cost_per_1k=0.005,
        output_cost_per_1k=0.015,
        max_context=128000,
        supports_vision=True,
        average_latency_ms=3000,
        reliability_score=0.98
    ),
    "gpt-4o-mini": ModelConfig(
        name="gpt-4o-mini",
        provider="openai",
        tier=ModelTier.STANDARD,
        input_cost_per_1k=0.00015,
        output_cost_per_1k=0.0006,
        max_context=128000,
        supports_vision=True,
        average_latency_ms=2000,
        reliability_score=0.97
    ),
    "gpt-3.5-turbo": ModelConfig(
        name="gpt-3.5-turbo",
        provider="openai",
        tier=ModelTier.BUDGET,
        input_cost_per_1k=0.0005,
        output_cost_per_1k=0.0015,
        max_context=16385,
        average_latency_ms=1000,
        reliability_score=0.95
    ),
    "o3": ModelConfig(
        name="o3",
        provider="openai",
        tier=ModelTier.PREMIUM,
        input_cost_per_1k=0.015,
        output_cost_per_1k=0.06,
        max_context=200000,
        average_latency_ms=5000,
        reliability_score=0.99
    ),
    "o3-mini": ModelConfig(
        name="o3-mini",
        provider="openai",
        tier=ModelTier.STANDARD,
        input_cost_per_1k=0.003,
        output_cost_per_1k=0.012,
        max_context=200000,
        average_latency_ms=3000,
        reliability_score=0.97
    ),
    
    # Google Models
    "gemini-2.0-flash": ModelConfig(
        name="gemini-2.0-flash",
        provider="google",
        tier=ModelTier.BUDGET,
        input_cost_per_1k=0.00,  # Free tier available
        output_cost_per_1k=0.00,
        max_context=1000000,
        supports_vision=True,
        average_latency_ms=800,
        reliability_score=0.94
    ),
    "gemini-2.5-flash": ModelConfig(
        name="gemini-2.5-flash",
        provider="google",
        tier=ModelTier.BUDGET,
        input_cost_per_1k=0.0001,
        output_cost_per_1k=0.0003,
        max_context=1000000,
        supports_vision=True,
        average_latency_ms=700,
        reliability_score=0.95
    ),
    "gemini-2.5-pro": ModelConfig(
        name="gemini-2.5-pro",
        provider="google",
        tier=ModelTier.STANDARD,
        input_cost_per_1k=0.00125,
        output_cost_per_1k=0.005,
        max_context=1000000,
        supports_vision=True,
        average_latency_ms=2000,
        reliability_score=0.97
    ),
    
    # Anthropic Models
    "claude-3-opus-20240229": ModelConfig(
        name="claude-3-opus-20240229",
        provider="anthropic",
        tier=ModelTier.PREMIUM,
        input_cost_per_1k=0.015,
        output_cost_per_1k=0.075,
        max_context=200000,
        supports_vision=True,
        average_latency_ms=4000,
        reliability_score=0.98
    ),
    "claude-3-sonnet-20240229": ModelConfig(
        name="claude-3-sonnet-20240229",
        provider="anthropic",
        tier=ModelTier.STANDARD,
        input_cost_per_1k=0.003,
        output_cost_per_1k=0.015,
        max_context=200000,
        supports_vision=True,
        average_latency_ms=2500,
        reliability_score=0.97
    ),
    "claude-3-haiku-20240307": ModelConfig(
        name="claude-3-haiku-20240307",
        provider="anthropic",
        tier=ModelTier.BUDGET,
        input_cost_per_1k=0.00025,
        output_cost_per_1k=0.00125,
        max_context=200000,
        supports_vision=True,
        average_latency_ms=1200,
        reliability_score=0.95
    ),
}


class ModelCostCalculator:
    """Calculate costs for model usage"""
    
    @staticmethod
    def calculate_cost(
        model_config: ModelConfig,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Calculate the cost for a model usage
        
        Args:
            model_config: Model configuration
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Total cost in USD
        """
        input_cost = (input_tokens / 1000) * model_config.input_cost_per_1k
        output_cost = (output_tokens / 1000) * model_config.output_cost_per_1k
        return input_cost + output_cost
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate token count for text
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        # Rough estimate: 1 token ≈ 4 characters
        return len(text) // 4
    
    @staticmethod
    def compare_costs(
        models: List[str],
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, float]:
        """
        Compare costs across multiple models
        
        Args:
            models: List of model names
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Dictionary of model costs
        """
        costs = {}
        
        for model in models:
            if model in MODEL_CONFIGS:
                config = MODEL_CONFIGS[model]
                costs[model] = ModelCostCalculator.calculate_cost(
                    config, input_tokens, output_tokens
                )
        
        return costs