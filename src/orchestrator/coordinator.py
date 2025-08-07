"""Central orchestrator for dynamic request handling"""

import asyncio
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import logging

from .intent_classifier import IntentClassifier
from .complexity_analyzer import ComplexityAnalyzer
from ..prompt_generator.generator import PromptGenerator
from ..mcp_manager.service_selector import MCPServiceSelector
from ..model_manager.model_selector import ModelSelector
from ..model_manager.fallback_handler import FallbackHandler
from ..monitoring.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationResult:
    """Result of orchestration"""
    request: str
    intent: str
    complexity: str
    selected_model: str
    selected_services: List[str]
    generated_prompt: str
    response: Any
    metrics: Dict[str, Any]
    success: bool
    error: Optional[str] = None


class Orchestrator:
    """Main orchestrator for dynamic system"""
    
    def __init__(self, config: Dict[str, Any], mcp_session=None):
        self.config = config
        self.mcp_session = mcp_session
        
        # Initialize components
        self.intent_classifier = IntentClassifier(config.get("models", {}), mcp_session=mcp_session)
        self.complexity_analyzer = ComplexityAnalyzer(config.get("models", {}), mcp_session=mcp_session)
        self.prompt_generator = PromptGenerator(config.get("models", {}), mcp_session=mcp_session)
        self.service_selector = MCPServiceSelector(config.get("mcp_services", {}))
        
        # Initialize model selector with Claude Code support
        from ..utils.claude_code_client import ClaudeCodeLLMClient
        claude_code_client = ClaudeCodeLLMClient(mcp_session) if mcp_session else None
        self.model_selector = ModelSelector(config.get("models", {}), claude_code_client=claude_code_client)
        
        self.fallback_handler = FallbackHandler(config.get("models", {}))
        self.metrics = MetricsCollector(config.get("monitoring", {}))
        
        self.initialized = False
    
    async def initialize(self):
        """Initialize all components"""
        if self.initialized:
            return
        
        try:
            # Initialize all async components
            await asyncio.gather(
                self.intent_classifier.initialize(),
                self.complexity_analyzer.initialize(),
                self.prompt_generator.initialize(),
                self.service_selector.initialize(),
                self.model_selector.initialize(),
                self.metrics.initialize()
            )
            
            self.initialized = True
            logger.info("Orchestrator initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {e}")
            raise
    
    async def orchestrate(
        self,
        request: str,
        context: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main orchestration function
        
        Args:
            request: The user request to process
            context: Optional context information
            options: Optional orchestration options
            
        Returns:
            Orchestration result with response and metrics
        """
        start_time = time.time()
        context = context or {}
        options = options or {}
        
        # Initialize tracking
        request_id = await self.metrics.start_request()
        orchestration_steps = []
        
        try:
            # Step 1: Classify intent
            logger.info(f"Classifying intent for request: {request[:100]}...")
            intent_result = await self.intent_classifier.classify(request)
            intent = intent_result["intent"]
            intent_confidence = intent_result["confidence"]
            
            orchestration_steps.append({
                "step": "intent_classification",
                "result": intent,
                "confidence": intent_confidence,
                "duration_ms": (time.time() - start_time) * 1000
            })
            
            # Step 2: Analyze complexity
            logger.info(f"Analyzing complexity for intent: {intent}")
            complexity = await self.complexity_analyzer.analyze(request, intent)
            
            orchestration_steps.append({
                "step": "complexity_analysis",
                "result": complexity,
                "duration_ms": (time.time() - start_time) * 1000
            })
            
            # Step 3: Select MCP services
            logger.info(f"Selecting MCP services for intent: {intent}")
            selected_services = await self.service_selector.select_services(
                intent=intent,
                complexity=complexity,
                context=context
            )
            
            orchestration_steps.append({
                "step": "service_selection",
                "result": selected_services,
                "duration_ms": (time.time() - start_time) * 1000
            })
            
            # Step 4: Generate dynamic prompt
            logger.info("Generating dynamic prompt")
            prompt_context = {
                "intent": intent,
                "complexity": complexity,
                "services": selected_services,
                "user_context": context
            }
            generated_prompt = await self.prompt_generator.generate(
                intent=intent,
                context=prompt_context
            )
            
            orchestration_steps.append({
                "step": "prompt_generation",
                "result": f"{len(generated_prompt)} chars",
                "duration_ms": (time.time() - start_time) * 1000
            })
            
            # Step 5: Select model
            logger.info(f"Selecting model for complexity: {complexity}")
            selected_model = await self.model_selector.select_model(
                complexity=complexity,
                options=options
            )
            
            orchestration_steps.append({
                "step": "model_selection",
                "result": selected_model,
                "duration_ms": (time.time() - start_time) * 1000
            })
            
            # Step 6: Execute with fallback handling
            logger.info(f"Executing with model: {selected_model}")
            execution_result = await self.fallback_handler.execute_with_fallback(
                request=request,
                prompt=generated_prompt,
                model=selected_model,
                services=selected_services,
                context=context
            )
            
            orchestration_steps.append({
                "step": "execution",
                "result": "success" if execution_result.get("success") else "failed",
                "model_used": execution_result.get("model_used"),
                "duration_ms": (time.time() - start_time) * 1000
            })
            
            # Calculate metrics
            total_duration = (time.time() - start_time) * 1000
            
            # Record metrics
            await self.metrics.record_orchestration(
                request_id=request_id,
                intent=intent,
                complexity=complexity,
                model=execution_result.get("model_used", selected_model),
                services=selected_services,
                duration_ms=total_duration,
                success=execution_result.get("success", False),
                tokens_used=execution_result.get("tokens_used", 0),
                cost=execution_result.get("cost", 0)
            )
            
            # Build result
            result = {
                "request": request,
                "intent": intent,
                "complexity": complexity,
                "selected_model": execution_result.get("model_used", selected_model),
                "selected_services": selected_services,
                "response": execution_result.get("response"),
                "success": execution_result.get("success", False),
                "metrics": {
                    "total_duration_ms": total_duration,
                    "tokens_used": execution_result.get("tokens_used", 0),
                    "tokens_saved": execution_result.get("tokens_saved", 0),
                    "cost_usd": execution_result.get("cost", 0),
                    "steps": orchestration_steps
                }
            }
            
            if options.get("verbose"):
                result["debug"] = {
                    "generated_prompt": generated_prompt[:500],
                    "intent_confidence": intent_confidence,
                    "fallback_attempts": execution_result.get("fallback_attempts", 0)
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            
            # Record error
            await self.metrics.record_error(request_id, str(e))
            
            return {
                "request": request,
                "success": False,
                "error": str(e),
                "metrics": {
                    "total_duration_ms": (time.time() - start_time) * 1000,
                    "steps": orchestration_steps
                }
            }
    
    async def analyze(self, request: str) -> Dict[str, Any]:
        """
        Analyze a request without executing it
        
        Args:
            request: The request to analyze
            
        Returns:
            Analysis result with recommendations
        """
        try:
            # Classify intent
            intent_result = await self.intent_classifier.classify(request)
            intent = intent_result["intent"]
            
            # Analyze complexity
            complexity = await self.complexity_analyzer.analyze(request, intent)
            
            # Get recommended services
            services = await self.service_selector.select_services(
                intent=intent,
                complexity=complexity,
                context={}
            )
            
            # Get recommended model
            model = await self.model_selector.select_model(complexity=complexity)
            
            # Estimate cost and latency
            estimated_cost = self.model_selector.estimate_cost(model, len(request))
            estimated_latency = self.service_selector.estimate_latency(services)
            
            return {
                "intent": intent,
                "intent_confidence": intent_result["confidence"],
                "complexity": complexity,
                "configuration": {
                    "recommended_model": model,
                    "recommended_services": services,
                    "estimated_prompt_tokens": len(request) // 4,  # Rough estimate
                },
                "estimated_cost": estimated_cost,
                "estimated_latency_ms": estimated_latency,
                "optimization_tips": self._get_optimization_tips(intent, complexity)
            }
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return {"error": str(e)}
    
    def _get_optimization_tips(self, intent: str, complexity: str) -> List[str]:
        """Get optimization tips based on analysis"""
        tips = []
        
        if complexity == "complex":
            tips.append("Consider breaking down the request into smaller sub-tasks")
            tips.append("Use caching for repeated similar requests")
        
        if intent == "search":
            tips.append("Provide more specific search criteria to reduce scope")
            tips.append("Consider using filters to narrow results")
        
        if intent == "write":
            tips.append("Provide examples or templates for better results")
            tips.append("Specify the desired output format clearly")
        
        return tips