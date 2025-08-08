#!/usr/bin/env python3
"""Direct test of orchestration without MCP server"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.orchestrator.coordinator import Orchestrator
from src.utils.config_loader import ConfigLoader
from src.monitoring.metrics_collector import MetricsCollector

async def test_orchestration():
    """Test orchestration directly"""
    
    # Load configuration
    config_loader = ConfigLoader()
    config = config_loader.load_all()
    
    # Initialize metrics collector
    metrics = MetricsCollector(config.get("monitoring", {}))
    await metrics.initialize()
    
    # Initialize orchestrator without MCP session
    orchestrator = Orchestrator(config, mcp_session=None, metrics=metrics)
    await orchestrator.initialize()
    
    # Test orchestration
    print("Testing orchestration...")
    result = await orchestrator.orchestrate(
        request="什麼是 Python？",
        context={},
        options={"verbose": True}
    )
    
    print(f"Success: {result.get('success')}")
    print(f"Model: {result.get('selected_model')}")
    print(f"Response length: {len(result.get('response', ''))}")
    print(f"Error: {result.get('error')}")
    
    # Print execution steps with errors
    for step in result.get('metrics', {}).get('steps', []):
        if step['step'] == 'execution' and 'error' in step:
            print(f"Execution error: {step.get('error')}")
            print(f"Attempts: {step.get('attempts', [])}")
    
    return result

if __name__ == "__main__":
    asyncio.run(test_orchestration())