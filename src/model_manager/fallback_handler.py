"""Fallback handler for automatic degradation when models fail"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import time

from ..utils.llm_client import LLMClient
from ..mcp_manager.connectors import MCPConnector
from ..mcp_manager.service_registry import MCPServiceRegistry
from .model_selector import ModelSelector

logger = logging.getLogger(__name__)


@dataclass
class ExecutionAttempt:
    """Record of an execution attempt"""
    model: str
    service: Optional[str]
    success: bool
    error: Optional[str]
    duration_ms: float
    tokens_used: int
    cost: float


class FallbackHandler:
    """Handles automatic fallback when primary options fail"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm_client = LLMClient(config)
        self.model_selector = ModelSelector(config)
        self.mcp_connector = MCPConnector()
        self.service_registry = MCPServiceRegistry(config.get("mcp_services", {}))
        
        # Fallback configuration
        self.max_retries = 3
        self.retry_delay_ms = 1000
        self.backoff_multiplier = 2.0
        
        # Track failures for circuit breaker pattern
        self.failure_counts: Dict[str, int] = {}
        self.failure_windows: Dict[str, float] = {}
        self.circuit_breaker_threshold = 3
        self.circuit_breaker_timeout = 300  # 5 minutes
    
    async def execute_with_fallback(
        self,
        request: str,
        prompt: str,
        model: str,
        services: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute request with automatic fallback on failure
        
        Args:
            request: Original user request
            prompt: Generated system prompt
            model: Primary model to use
            services: MCP services to use
            context: Additional context
            
        Returns:
            Execution result with metrics
        """
        context = context or {}
        attempts = []
        start_time = time.time()
        
        # Build fallback chain
        fallback_models = self._build_fallback_chain(model)
        fallback_services = self._build_service_fallbacks(services)
        
        # Try primary configuration
        result = await self._try_execution(
            request=request,
            prompt=prompt,
            model=model,
            services=services,
            context=context,
            attempts=attempts
        )
        
        if result["success"]:
            return self._build_response(result, attempts, start_time)
        
        # Try fallback models
        for fallback_model in fallback_models:
            if self._is_circuit_open(fallback_model):
                logger.warning(f"Circuit breaker open for model: {fallback_model}")
                continue
            
            logger.info(f"Falling back to model: {fallback_model}")
            
            result = await self._try_execution(
                request=request,
                prompt=prompt,
                model=fallback_model,
                services=services,
                context=context,
                attempts=attempts
            )
            
            if result["success"]:
                return self._build_response(result, attempts, start_time)
        
        # Try with reduced services
        if len(services) > 1:
            logger.info("Trying with reduced services")
            
            for reduced_services in fallback_services:
                result = await self._try_execution(
                    request=request,
                    prompt=prompt,
                    model=fallback_models[0] if fallback_models else model,
                    services=reduced_services,
                    context=context,
                    attempts=attempts
                )
                
                if result["success"]:
                    return self._build_response(result, attempts, start_time)
        
        # All attempts failed
        return self._build_failure_response(attempts, start_time)
    
    async def _try_execution(
        self,
        request: str,
        prompt: str,
        model: str,
        services: List[str],
        context: Dict[str, Any],
        attempts: List[ExecutionAttempt]
    ) -> Dict[str, Any]:
        """
        Try a single execution
        
        Args:
            request: User request
            prompt: System prompt
            model: Model to use
            services: Services to use
            context: Context
            attempts: List to track attempts
            
        Returns:
            Execution result
        """
        attempt_start = time.time()
        
        try:
            # Connect to required services
            connected_services = []
            for service_name in services:
                try:
                    service = self.service_registry.get_service(service_name)
                    if service:
                        connector = await self.mcp_connector.connect(service)
                        connected_services.append(service_name)
                except Exception as e:
                    logger.warning(f"Failed to connect to service {service_name}: {e}")
            
            # Build messages for LLM
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": request}
            ]
            
            # Add service context
            if connected_services:
                service_context = f"Available services: {', '.join(connected_services)}"
                messages[0]["content"] += f"\n\n{service_context}"
            
            # Call LLM
            response = await self.llm_client.complete(
                prompt=messages[1]["content"],
                model=model,
                temperature=0.7,
                max_tokens=2000
            )
            
            # Calculate metrics
            duration_ms = (time.time() - attempt_start) * 1000
            tokens_used = self.llm_client.estimate_tokens(prompt + request + response)
            cost = self.model_selector.estimate_cost(model, len(prompt + request + response))
            
            # Record success
            attempt = ExecutionAttempt(
                model=model,
                service=connected_services[0] if connected_services else None,
                success=True,
                error=None,
                duration_ms=duration_ms,
                tokens_used=tokens_used,
                cost=cost
            )
            attempts.append(attempt)
            
            # Reset failure count on success
            self._reset_circuit(model)
            
            return {
                "success": True,
                "response": response,
                "model_used": model,
                "services_used": connected_services,
                "tokens_used": tokens_used,
                "cost": cost
            }
            
        except Exception as e:
            # Record failure
            duration_ms = (time.time() - attempt_start) * 1000
            
            attempt = ExecutionAttempt(
                model=model,
                service=None,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
                tokens_used=0,
                cost=0
            )
            attempts.append(attempt)
            
            # Update circuit breaker
            self._record_failure(model)
            
            logger.error(f"Execution failed with model {model}: {e}")
            
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_fallback_chain(self, primary_model: str) -> List[str]:
        """Build fallback model chain"""
        fallback_chain = []
        
        # Get configured fallbacks
        execution_config = self.config.get("execution", {})
        
        # Find complexity level for this model
        for complexity in ["simple", "moderate", "complex"]:
            level_config = execution_config.get(complexity, {})
            if level_config.get("preferred") == primary_model:
                fallbacks = level_config.get("fallback", [])
                fallback_chain.extend(fallbacks)
                break
        
        # Add generic fallbacks
        generic_fallbacks = [
            "gpt-3.5-turbo",
            "gemini-2.0-flash",
            "claude-3-haiku-20240307"
        ]
        
        for model in generic_fallbacks:
            if model != primary_model and model not in fallback_chain:
                fallback_chain.append(model)
        
        # Filter to available models
        available = self.model_selector.available_models
        fallback_chain = [m for m in fallback_chain if m in available]
        
        return fallback_chain
    
    def _build_service_fallbacks(self, services: List[str]) -> List[List[str]]:
        """Build service fallback combinations"""
        if len(services) <= 1:
            return []
        
        fallbacks = []
        
        # Try with just primary service
        if services:
            fallbacks.append([services[0]])
        
        # Try with half the services
        if len(services) > 2:
            half = len(services) // 2
            fallbacks.append(services[:half])
        
        # Try with no services
        fallbacks.append([])
        
        return fallbacks
    
    def _is_circuit_open(self, model: str) -> bool:
        """Check if circuit breaker is open for a model"""
        if model not in self.failure_counts:
            return False
        
        # Check if we're still in the timeout window
        if model in self.failure_windows:
            if time.time() - self.failure_windows[model] < self.circuit_breaker_timeout:
                return self.failure_counts[model] >= self.circuit_breaker_threshold
        
        # Reset if timeout has passed
        self._reset_circuit(model)
        return False
    
    def _record_failure(self, model: str):
        """Record a failure for circuit breaker"""
        if model not in self.failure_counts:
            self.failure_counts[model] = 0
            self.failure_windows[model] = time.time()
        
        self.failure_counts[model] += 1
        
        # Update window if this is first failure after reset
        if self.failure_counts[model] == 1:
            self.failure_windows[model] = time.time()
    
    def _reset_circuit(self, model: str):
        """Reset circuit breaker for a model"""
        if model in self.failure_counts:
            del self.failure_counts[model]
        if model in self.failure_windows:
            del self.failure_windows[model]
    
    def _build_response(
        self,
        result: Dict[str, Any],
        attempts: List[ExecutionAttempt],
        start_time: float
    ) -> Dict[str, Any]:
        """Build successful response with metrics"""
        total_duration = (time.time() - start_time) * 1000
        total_cost = sum(a.cost for a in attempts)
        total_tokens = sum(a.tokens_used for a in attempts)
        
        # Calculate tokens saved (estimate)
        baseline_tokens = total_tokens * 3  # Assume 3x tokens without optimization
        tokens_saved = baseline_tokens - total_tokens
        
        return {
            "success": True,
            "response": result["response"],
            "model_used": result["model_used"],
            "services_used": result.get("services_used", []),
            "tokens_used": total_tokens,
            "tokens_saved": tokens_saved,
            "cost": total_cost,
            "duration_ms": total_duration,
            "fallback_attempts": len(attempts) - 1,
            "attempts": [
                {
                    "model": a.model,
                    "success": a.success,
                    "error": a.error,
                    "duration_ms": a.duration_ms
                }
                for a in attempts
            ]
        }
    
    def _build_failure_response(
        self,
        attempts: List[ExecutionAttempt],
        start_time: float
    ) -> Dict[str, Any]:
        """Build failure response with details"""
        total_duration = (time.time() - start_time) * 1000
        
        return {
            "success": False,
            "response": None,
            "error": "All execution attempts failed",
            "duration_ms": total_duration,
            "attempts": [
                {
                    "model": a.model,
                    "success": a.success,
                    "error": a.error,
                    "duration_ms": a.duration_ms
                }
                for a in attempts
            ]
        }