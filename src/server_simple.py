#!/usr/bin/env python3
"""Simple MCP Server for Dynamic Orchestrator"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from mcp import stdio_server
from mcp.server import Server
from mcp.types import Tool, TextContent

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

# Create server instance
server = Server("dynamic-orchestrator")

# Global instances
orchestrator: Optional[Orchestrator] = None
metrics: Optional[MetricsCollector] = None
config: Optional[Dict] = None


async def initialize_server():
    """Initialize the server components"""
    global orchestrator, metrics, config
    
    try:
        # Load configuration
        config_loader = ConfigLoader()
        config = config_loader.load_all()
        
        # Initialize orchestrator
        orchestrator = Orchestrator(config)
        await orchestrator.initialize()
        
        # Initialize metrics collector
        metrics = MetricsCollector(config.get("monitoring", {}))
        await metrics.initialize()
        
        logger.info("Dynamic Orchestrator MCP Server initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize server: {e}")
        raise


@server.list_tools()
async def handle_list_tools() -> List[Tool]:
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


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""
    try:
        if not orchestrator:
            await initialize_server()
        
        if name == "orchestrate":
            result = await handle_orchestrate(arguments)
        elif name == "analyze_request":
            result = await handle_analyze(arguments)
        elif name == "get_metrics":
            result = await handle_get_metrics(arguments)
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


async def handle_orchestrate(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle orchestrate tool call with input validation"""
    # Validate input
    try:
        validated = OrchestrateRequest(**arguments)
        request_data = validated.model_dump()
    except Exception as e:
        logger.error(f"Input validation failed: {e}")
        return {"error": f"Invalid input: {str(e)}"}
    
    # Start metrics tracking
    request_id = metrics.start_request() if metrics else None
    
    try:
        # Execute orchestration with validated data
        result = await orchestrator.orchestrate(
            request=request_data['request'],
            context=request_data.get('context'),
            options=request_data.get('options')
        )
        
        # Track metrics
        if metrics and request_id:
            await metrics.end_request(request_id, result)
        
        return result
        
    except Exception as e:
        if metrics and request_id:
            await metrics.record_error(request_id, str(e))
        raise


async def handle_analyze(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle analyze_request tool call with input validation"""
    # Validate input
    try:
        validated = AnalyzeRequest(**arguments)
        request = validated.request
    except Exception as e:
        logger.error(f"Input validation failed: {e}")
        return {"error": f"Invalid input: {str(e)}"}
    
    # Analyze without executing
    analysis = await orchestrator.analyze(request)
    
    return {
        "request": request,
        "analysis": analysis,
        "estimated_cost": analysis.get("estimated_cost"),
        "estimated_latency_ms": analysis.get("estimated_latency_ms"),
        "recommended_configuration": analysis.get("configuration")
    }


async def handle_get_metrics(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_metrics tool call with input validation"""
    # Validate input
    try:
        validated = MetricsRequest(**arguments)
        period = validated.period
    except Exception as e:
        logger.error(f"Input validation failed: {e}")
        return {"error": f"Invalid input: {str(e)}"}
    
    if not metrics:
        return {"error": "Metrics not initialized"}
    
    metrics_data = await metrics.get_metrics(period)
    
    return {
        "period": period,
        "metrics": metrics_data,
        "summary": {
            "total_requests": metrics_data.get("total_requests", 0),
            "success_rate": metrics_data.get("success_rate", 0),
            "avg_latency_ms": metrics_data.get("avg_latency_ms", 0),
            "total_cost_usd": metrics_data.get("total_cost_usd", 0),
            "tokens_saved": metrics_data.get("tokens_saved", 0)
        }
    }


async def main():
    """Main entry point"""
    try:
        # Initialize server components
        await initialize_server()
        
        # Run the server with stdio transport
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
            
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())