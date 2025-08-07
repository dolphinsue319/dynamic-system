#!/usr/bin/env python3
"""
Simple test script to call the analyze_request function directly
This simulates what would happen when the MCP tool is called
"""

import asyncio
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.orchestrator.coordinator import Orchestrator
from src.utils.config_loader import ConfigLoader
from src.models.requests import AnalyzeRequest


async def test_analyze_request():
    """Test the analyze_request functionality"""
    
    print("Testing analyze_request tool with: 'What is 2+2?'")
    print("="*60)
    
    try:
        # Load configuration
        config_loader = ConfigLoader()
        config = config_loader.load_all()
        
        # Initialize orchestrator without MCP session (external APIs)
        orchestrator = Orchestrator(config, mcp_session=None, metrics=None)
        await orchestrator.initialize()
        
        # Test the specific request
        request = "What is 2+2?"
        print(f"Request: {request}")
        
        # Validate the request (this is what the MCP server does)
        try:
            validated = AnalyzeRequest(request=request)
            print(f"✅ Request validation: PASSED")
        except Exception as e:
            print(f"❌ Request validation: FAILED - {e}")
            return
        
        # Analyze the request (this is the core functionality)
        print("\nAnalyzing request...")
        analysis = await orchestrator.analyze(request)
        
        # Format the response (this is what the MCP server returns)
        result = {
            "request": request,
            "analysis": analysis,
            "estimated_cost": analysis.get("estimated_cost"),
            "estimated_latency_ms": analysis.get("estimated_latency_ms"),
            "recommended_configuration": analysis.get("configuration")
        }
        
        print("\n🎯 ANALYSIS RESULT:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        print(f"\n✅ analyze_request tool is working!")
        print(f"   - Request was classified as: {analysis.get('intent')} intent")
        print(f"   - Complexity level: {analysis.get('complexity')}")
        print(f"   - Recommended model: {analysis.get('configuration', {}).get('recommended_model')}")
        print(f"   - Recommended services: {', '.join(analysis.get('configuration', {}).get('recommended_services', []))}")
        
    except Exception as e:
        print(f"❌ Error testing analyze_request: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_analyze_request())