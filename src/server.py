#!/usr/bin/env python3
"""MCP Server for Dynamic Orchestrator"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp

from orchestrator.coordinator import Orchestrator
from utils.config_loader import ConfigLoader
from utils.logger import setup_logger
from monitoring.metrics_collector import MetricsCollector

# Setup logging
logger = setup_logger(__name__)


class DynamicOrchestratorServer:
    """Dynamic Orchestrator MCP Server"""
    
    def __init__(self):
        self.server = Server("dynamic-orchestrator")
        self.orchestrator: Optional[Orchestrator] = None
        self.metrics: Optional[MetricsCollector] = None
        self.config: Optional[Dict] = None
        
        # Register handlers
        self.server.list_tools(self.handle_list_tools)
        self.server.call_tool(self.handle_call_tool)
        
    async def initialize(self):
        """Initialize the server components"""
        try:
            # Load configuration
            config_loader = ConfigLoader()
            self.config = config_loader.load_all()
            
            # Initialize orchestrator
            self.orchestrator = Orchestrator(self.config)
            await self.orchestrator.initialize()
            
            # Initialize metrics collector
            self.metrics = MetricsCollector(self.config.get("monitoring", {}))
            await self.metrics.initialize()
            
            logger.info("Dynamic Orchestrator MCP Server initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize server: {e}")
            raise
    
    async def handle_list_tools(self) -> List[Tool]:
        """List available tools"""
        return [
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
        """Handle orchestrate tool call"""
        request = arguments.get("request")
        context = arguments.get("context", {})
        options = arguments.get("options", {})
        
        # Start metrics tracking
        request_id = self.metrics.start_request() if self.metrics else None
        
        try:
            # Execute orchestration
            result = await self.orchestrator.orchestrate(
                request=request,
                context=context,
                options=options
            )
            
            # Track metrics
            if self.metrics and request_id:
                await self.metrics.end_request(request_id, result)
            
            return result
            
        except Exception as e:
            if self.metrics and request_id:
                await self.metrics.record_error(request_id, str(e))
            raise
    
    async def _handle_analyze(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle analyze_request tool call"""
        request = arguments.get("request")
        
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
        """Handle get_metrics tool call"""
        period = arguments.get("period", "5m")
        
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