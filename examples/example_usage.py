#!/usr/bin/env python
"""Example usage of the Dynamic Orchestrator MCP Service"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    """Demonstrate usage of the orchestrator"""
    
    # Connect to the MCP server
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "src.server"],
        env={}
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()
            
            print("Connected to Dynamic Orchestrator MCP Service")
            print("=" * 50)
            
            # Example 1: Simple file reading
            print("\n1. Simple Read Request:")
            result = await session.call_tool(
                "orchestrate",
                {
                    "request": "Show me the contents of README.md"
                }
            )
            print(f"Intent: {result.get('intent')}")
            print(f"Complexity: {result.get('complexity')}")
            print(f"Model Used: {result.get('selected_model')}")
            print(f"Tokens Saved: {result.get('metrics', {}).get('tokens_saved')}")
            
            # Example 2: Code generation with preferences
            print("\n2. Code Generation with Preferences:")
            result = await session.call_tool(
                "orchestrate",
                {
                    "request": "Create a FastAPI endpoint for user authentication",
                    "context": {
                        "framework": "FastAPI",
                        "language": "Python",
                        "auth_type": "JWT"
                    },
                    "options": {
                        "preferred_models": ["gpt-4o-mini"],
                        "max_cost": 0.05
                    }
                }
            )
            print(f"Success: {result.get('success')}")
            print(f"Model Used: {result.get('selected_model')}")
            print(f"Services Used: {result.get('selected_services')}")
            print(f"Cost: ${result.get('metrics', {}).get('cost_usd', 0):.4f}")
            
            # Example 3: Complex refactoring
            print("\n3. Complex Refactoring Request:")
            result = await session.call_tool(
                "orchestrate",
                {
                    "request": "Refactor the database module to use async SQLAlchemy",
                    "context": {
                        "current_orm": "SQLAlchemy 1.4",
                        "target_orm": "SQLAlchemy 2.0 with async",
                        "database": "PostgreSQL"
                    }
                }
            )
            print(f"Complexity: {result.get('complexity')}")
            print(f"Model: {result.get('selected_model')}")
            print(f"Duration: {result.get('metrics', {}).get('duration_ms')}ms")
            
            # Example 4: Search operation
            print("\n4. Code Search:")
            result = await session.call_tool(
                "orchestrate",
                {
                    "request": "Find all API endpoints that don't have authentication"
                }
            )
            print(f"Intent: {result.get('intent')}")
            print(f"Services: {result.get('selected_services')}")
            
            # Example 5: Analysis request
            print("\n5. Code Analysis:")
            result = await session.call_tool(
                "analyze_request",
                {
                    "request": "Analyze the performance bottlenecks in the data processing pipeline"
                }
            )
            print(f"Intent: {result.get('intent')}")
            print(f"Complexity: {result.get('complexity')}")
            print(f"Factors: {json.dumps(result.get('analysis', {}).get('factors', {}), indent=2)}")
            
            # Example 6: Get metrics
            print("\n6. System Metrics:")
            metrics = await session.call_tool(
                "get_metrics",
                {
                    "period": "5m"
                }
            )
            print(f"Total Requests: {metrics.get('total_requests')}")
            print(f"Success Rate: {metrics.get('success_rate', 0):.2%}")
            print(f"Avg Duration: {metrics.get('avg_duration_ms', 0):.0f}ms")
            print(f"Total Tokens Saved: {metrics.get('total_tokens_saved')}")
            print(f"Total Cost: ${metrics.get('total_cost_usd', 0):.4f}")
            
            print("\n" + "=" * 50)
            print("Examples completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())