#!/usr/bin/env python3
"""MCP Server for Dynamic Orchestrator"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp

# Try relative imports first (for local execution), fall back to absolute (for container)
try:
    from orchestrator.coordinator import Orchestrator
    from utils.config_loader import ConfigLoader
    from utils.logger import setup_logger
    from monitoring.metrics_collector import MetricsCollector
    from models.requests import OrchestrateRequest, AnalyzeRequest, MetricsRequest
except ImportError:
    from src.orchestrator.coordinator import Orchestrator
    from src.utils.config_loader import ConfigLoader
    from src.utils.logger import setup_logger
    from src.monitoring.metrics_collector import MetricsCollector
    from src.models.requests import OrchestrateRequest, AnalyzeRequest, MetricsRequest

# Setup logging
logger = setup_logger(__name__)
logger.info("MCP Server starting with logging initialized")


class DynamicOrchestratorServer:
    """Dynamic Orchestrator MCP Server"""
    
    def __init__(self, mcp_session=None):
        self.server = Server("dynamic-orchestrator")
        self.orchestrator: Optional[Orchestrator] = None
        self.metrics: Optional[MetricsCollector] = None
        self.config: Optional[Dict] = None
        # In MCP server context, we don't have access to external MCP sessions
        # The server IS the MCP interface, not a client
        self.mcp_session = None
        
        # Handlers will be registered with decorators
        
    async def initialize(self):
        """Initialize the server components"""
        try:
            # Load configuration
            config_loader = ConfigLoader()
            self.config = config_loader.load_all()
            
            # Initialize metrics collector first
            self.metrics = MetricsCollector(self.config.get("monitoring", {}))
            await self.metrics.initialize()
            
            # Initialize orchestrator without MCP session (server context doesn't need Claude Code client)
            # The MCP server uses external providers instead of trying to call back to Claude Code
            self.orchestrator = Orchestrator(self.config, mcp_session=None, metrics=self.metrics)
            await self.orchestrator.initialize()
            
            logger.info("Dynamic Orchestrator MCP Server initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize server: {e}")
            raise
    
    async def handle_list_tools(self) -> List[Tool]:
        """List available tools"""
        import os
        tools = [
            Tool(
                name="orchestrate",
                description=(
                    "Intelligently orchestrate a request by analyzing intent, "
                    "selecting appropriate MCP services and models, generating "
                    "dynamic prompts, and executing with optimal configuration."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "request": {
                            "type": "string",
                            "description": "The user request to orchestrate"
                        },
                        "context": {
                            "type": "object",
                            "description": "Optional context for the request",
                            "properties": {
                                "project_type": {"type": "string"},
                                "user_preferences": {"type": "object"},
                                "constraints": {"type": "object"}
                            }
                        },
                        "options": {
                            "type": "object",
                            "description": "Orchestration options",
                            "properties": {
                                "max_cost": {"type": "number"},
                                "max_latency_ms": {"type": "number"},
                                "preferred_models": {"type": "array", "items": {"type": "string"}},
                                "verbose": {"type": "boolean"}
                            }
                        }
                    },
                    "required": ["request"]
                }
            ),
            Tool(
                name="analyze_request",
                description="Analyze a request without executing it",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "request": {
                            "type": "string",
                            "description": "The request to analyze"
                        }
                    },
                    "required": ["request"]
                }
            ),
            Tool(
                name="get_metrics",
                description="Get current metrics and statistics",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "description": "Time period (1m, 5m, 1h, 1d)",
                            "default": "5m"
                        }
                    }
                }
            )
        ]
        
        # Only include debug tools if explicitly enabled
        if os.environ.get("ENABLE_DEBUG_TOOLS") == "true":
            tools.append(
                Tool(
                    name="test_llm",
                    description="Test LLM client directly",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "prompt": {
                                "type": "string",
                                "description": "Test prompt"
                            },
                            "model": {
                                "type": "string",
                                "description": "Model to test",
                                "default": "gemini-2.0-flash"
                            }
                        },
                        "required": ["prompt"]
                    }
                )
            )
        
        return tools
    
    async def handle_call_tool(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle tool calls"""
        try:
            if not self.orchestrator:
                await self.initialize()
            
            if name == "orchestrate":
                result = await self._handle_orchestrate(arguments)
            elif name == "analyze_request":
                result = await self._handle_analyze(arguments)
            elif name == "get_metrics":
                result = await self._handle_get_metrics(arguments)
            elif name == "test_llm":
                result = await self._handle_test_llm(arguments)
            else:
                result = {"error": f"Unknown tool: {name}"}
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, ensure_ascii=False)
            )]
            
        except Exception as e:
            logger.error(f"Error handling tool call {name}: {e}")
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]
    
    async def _handle_orchestrate(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle orchestrate tool call with input validation"""
        logger.info(f"_handle_orchestrate called with arguments: {arguments}")
        
        # Validate input
        try:
            validated = OrchestrateRequest(**arguments)
            request_data = validated.model_dump()
            logger.info(f"Input validated successfully: {request_data}")
        except Exception as e:
            logger.error(f"Input validation failed: {e}")
            return {"error": f"Invalid input: {str(e)}"}
        
        # Start metrics tracking
        request_id = self.metrics.start_request() if self.metrics else None
        logger.info(f"Started metrics tracking with request_id: {request_id}")
        
        try:
            # Execute orchestration with validated data
            logger.info("About to call orchestrator.orchestrate")
            result = await self.orchestrator.orchestrate(
                request=request_data['request'],
                context=request_data['context'],
                options=request_data['options']
            )
            logger.info(f"Orchestration result: success={result.get('success')}, model={result.get('selected_model')}")
            
            # Track metrics
            if self.metrics and request_id:
                await self.metrics.end_request(request_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Orchestration exception: {e}")
            if self.metrics and request_id:
                await self.metrics.record_error(request_id, str(e))
            raise
    
    async def _handle_analyze(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle analyze_request tool call with input validation"""
        # Validate input
        try:
            validated = AnalyzeRequest(**arguments)
            request = validated.request
        except Exception as e:
            logger.error(f"Input validation failed: {e}")
            return {"error": f"Invalid input: {str(e)}"}
        
        # Analyze without executing
        analysis = await self.orchestrator.analyze(request)
        
        return {
            "request": request,
            "analysis": analysis,
            "estimated_cost": analysis.get("estimated_cost"),
            "estimated_latency_ms": analysis.get("estimated_latency_ms"),
            "recommended_configuration": analysis.get("configuration")
        }
    
    async def _handle_get_metrics(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_metrics tool call with input validation"""
        # Validate input
        try:
            validated = MetricsRequest(**arguments)
            period = validated.period
        except Exception as e:
            logger.error(f"Input validation failed: {e}")
            return {"error": f"Invalid input: {str(e)}"}
        
        if not self.metrics:
            return {"error": "Metrics not initialized"}
        
        metrics = await self.metrics.get_metrics(period)
        
        return {
            "period": period,
            "metrics": metrics,
            "summary": {
                "total_requests": metrics.get("total_requests", 0),
                "success_rate": metrics.get("success_rate", 0),
                "avg_latency_ms": metrics.get("avg_latency_ms", 0),
                "total_cost_usd": metrics.get("total_cost_usd", 0),
                "tokens_saved": metrics.get("tokens_saved", 0)
            }
        }
    
    async def _handle_test_llm(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle direct LLM test for debugging"""
        prompt = arguments.get("prompt", "Hello")
        model = arguments.get("model", "gemini-2.0-flash")
        
        if not self.orchestrator:
            return {"error": "Orchestrator not initialized"}
        
        try:
            # Test LLM client directly
            llm_client = self.orchestrator.fallback_handler.llm_client
            
            # Check initialization status
            if not llm_client.initialized:
                await llm_client.initialize()
            
            # Test completion
            response = await llm_client.complete(
                prompt=prompt,
                model=model,
                temperature=0.7,
                max_tokens=100
            )
            
            return {
                "success": True,
                "prompt": prompt,
                "model": model,
                "response": response,
                "llm_initialized": llm_client.initialized,
                "available_clients": list(llm_client.clients.keys())
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "prompt": prompt,
                "model": model,
                "llm_initialized": getattr(self.orchestrator.fallback_handler.llm_client, 'initialized', False),
                "available_clients": list(getattr(self.orchestrator.fallback_handler.llm_client, 'clients', {}).keys())
            }
    
    async def run(self):
        """Run the MCP server"""
        try:
            await self.initialize()
            
            # Run the server
            async with mcp.stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options()
                )
                
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise


async def main():
    """Main entry point"""
    server = DynamicOrchestratorServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())