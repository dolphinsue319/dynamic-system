"""Intelligent model selector based on complexity and constraints"""

import logging
from typing import Dict, Any, List, Optional
import os

from .config import MODEL_CONFIGS, ModelConfig, ModelTier, ModelCostCalculator

logger = logging.getLogger(__name__)


class ModelSelector:
    """Selects appropriate models based on various factors"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_configs = MODEL_CONFIGS
        self.cost_calculator = ModelCostCalculator()
        self.available_models = self._get_available_models()
        
    async def initialize(self):
        """Initialize the model selector"""
        logger.info(f"Model selector initialized with {len(self.available_models)} available models")
    
    def _get_available_models(self) -> List[str]:
        """Get list of available models based on API keys"""
        available = []
        
        # Check OpenAI models
        if os.environ.get("OPENAI_API_KEY"):
            available.extend([
                "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo",
                "o3", "o3-mini"
            ])
        
        # Check Google models
        if os.environ.get("GOOGLE_API_KEY"):
            available.extend([
                "gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro"
            ])
        
        # Check Anthropic models
        if os.environ.get("ANTHROPIC_API_KEY"):
            available.extend([
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307"
            ])
        
        # Filter to only models we have configs for
        available = [m for m in available if m in self.model_configs]
        
        return available
    
    async def select_model(
        self,
        complexity: str,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Select the best model for the given complexity and options
        
        Args:
            complexity: Task complexity (simple/moderate/complex)
            options: Optional constraints and preferences
            
        Returns:
            Selected model name
        """
        options = options or {}
        
        # Get complexity-based recommendations
        recommended_models = self._get_models_for_complexity(complexity)
        
        # Apply user preferences
        if options.get("preferred_models"):
            preferred = options["preferred_models"]
            # Use preferred model if available
            for model in preferred:
                if model in self.available_models:
                    logger.info(f"Using preferred model: {model}")
                    return model
        
        # Apply cost constraints
        if options.get("max_cost"):
            recommended_models = self._filter_by_cost(
                recommended_models,
                options["max_cost"]
            )
        
        # Apply latency constraints
        if options.get("max_latency_ms"):
            recommended_models = self._filter_by_latency(
                recommended_models,
                options["max_latency_ms"]
            )
        
        # Select best available model
        for model in recommended_models:
            if model in self.available_models:
                logger.info(f"Selected model: {model} for complexity: {complexity}")
                return model
        
        # Fallback to any available model
        if self.available_models:
            fallback = self.available_models[0]
            logger.warning(f"Using fallback model: {fallback}")
            return fallback
        
        raise ValueError("No models available")
    
    def _get_models_for_complexity(self, complexity: str) -> List[str]:
        """Get recommended models for complexity level"""
        complexity_mapping = self.config.get("execution", {})
        
        if complexity == "simple":
            # Use budget tier models
            models = complexity_mapping.get("simple", {}).get("preferred", "gemini-2.0-flash")
            fallbacks = complexity_mapping.get("simple", {}).get("fallback", [])
        elif complexity == "complex":
            # Use premium tier models
            models = complexity_mapping.get("complex", {}).get("preferred", "gpt-4o")
            fallbacks = complexity_mapping.get("complex", {}).get("fallback", [])
        else:  # moderate
            # Use standard tier models
            models = complexity_mapping.get("moderate", {}).get("preferred", "gpt-4o-mini")
            fallbacks = complexity_mapping.get("moderate", {}).get("fallback", [])
        
        # Build ordered list
        recommended = []
        if isinstance(models, str):
            recommended.append(models)
        else:
            recommended.extend(models)
        
        recommended.extend(fallbacks)
        
        # Add tier-based recommendations if not enough
        if len(recommended) < 3:
            if complexity == "simple":
                tier_models = self._get_models_by_tier(ModelTier.BUDGET)
            elif complexity == "complex":
                tier_models = self._get_models_by_tier(ModelTier.PREMIUM)
            else:
                tier_models = self._get_models_by_tier(ModelTier.STANDARD)
            
            for model in tier_models:
                if model not in recommended:
                    recommended.append(model)
        
        return recommended
    
    def _get_models_by_tier(self, tier: ModelTier) -> List[str]:
        """Get all models of a specific tier"""
        models = []
        for name, config in self.model_configs.items():
            if config.tier == tier:
                models.append(name)
        
        # Sort by cost (cheapest first)
        models.sort(key=lambda m: self.model_configs[m].input_cost_per_1k)
        
        return models
    
    def _filter_by_cost(self, models: List[str], max_cost: float) -> List[str]:
        """Filter models by maximum cost"""
        filtered = []
        
        for model in models:
            if model in self.model_configs:
                config = self.model_configs[model]
                # Estimate cost for typical usage (1000 input, 500 output tokens)
                estimated_cost = self.cost_calculator.calculate_cost(
                    config, 1000, 500
                )
                if estimated_cost <= max_cost:
                    filtered.append(model)
        
        return filtered
    
    def _filter_by_latency(self, models: List[str], max_latency_ms: int) -> List[str]:
        """Filter models by maximum latency"""
        filtered = []
        
        for model in models:
            if model in self.model_configs:
                config = self.model_configs[model]
                if config.average_latency_ms <= max_latency_ms:
                    filtered.append(model)
        
        return filtered
    
    def estimate_cost(self, model: str, text_length: int) -> float:
        """
        Estimate cost for using a model
        
        Args:
            model: Model name
            text_length: Approximate text length
            
        Returns:
            Estimated cost in USD
        """
        if model not in self.model_configs:
            return 0.0
        
        config = self.model_configs[model]
        
        # Estimate tokens
        input_tokens = text_length // 4  # Rough estimate
        output_tokens = input_tokens // 2  # Assume output is half of input
        
        return self.cost_calculator.calculate_cost(
            config, input_tokens, output_tokens
        )
    
    def get_model_info(self, model: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a model"""
        if model not in self.model_configs:
            return None
        
        config = self.model_configs[model]
        
        return {
            "name": config.name,
            "provider": config.provider,
            "tier": config.tier.value,
            "input_cost_per_1k": config.input_cost_per_1k,
            "output_cost_per_1k": config.output_cost_per_1k,
            "max_context": config.max_context,
            "supports_functions": config.supports_functions,
            "supports_vision": config.supports_vision,
            "supports_streaming": config.supports_streaming,
            "average_latency_ms": config.average_latency_ms,
            "reliability_score": config.reliability_score,
            "available": model in self.available_models
        }
    
    def rank_models_by_value(
        self,
        models: List[str],
        weights: Optional[Dict[str, float]] = None
    ) -> List[str]:
        """
        Rank models by value (performance/cost ratio)
        
        Args:
            models: List of model names
            weights: Optional weights for different factors
            
        Returns:
            Ranked list of models
        """
        weights = weights or {
            "cost": 0.4,
            "latency": 0.3,
            "reliability": 0.3
        }
        
        scores = {}
        
        for model in models:
            if model not in self.model_configs:
                continue
            
            config = self.model_configs[model]
            
            # Calculate normalized scores (0-1, higher is better)
            cost_score = 1.0 - min((config.input_cost_per_1k + config.output_cost_per_1k) / 0.1, 1.0)
            latency_score = 1.0 - min(config.average_latency_ms / 10000, 1.0)
            reliability_score = config.reliability_score
            
            # Calculate weighted score
            total_score = (
                cost_score * weights.get("cost", 0.33) +
                latency_score * weights.get("latency", 0.33) +
                reliability_score * weights.get("reliability", 0.34)
            )
            
            scores[model] = total_score
        
        # Sort by score (highest first)
        ranked = sorted(scores.keys(), key=lambda m: scores[m], reverse=True)
        
        return ranked