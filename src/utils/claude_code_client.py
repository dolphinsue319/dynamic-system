"""Claude Code LLM client using zen MCP tools"""

import logging
from typing import Dict, Any, Optional, List
import json

try:
    from mcp.types import CallToolResult
except ImportError:
    # Fallback for when MCP types are not available
    CallToolResult = type("CallToolResult", (), {})

logger = logging.getLogger(__name__)


class ClaudeCodeLLMClient:
    """Client for using Claude Code's built-in models via zen MCP tools"""
    
    # Model mapping for Claude Code zen tools
    CLAUDE_CODE_MODELS = {
        # Budget tier - use these for simple tasks
        "gemini-2.0-flash": "gemini-2.0-flash",
        "gemini-2.5-flash": "gemini-2.5-flash", 
        "claude-3-5-haiku": "anthropic/claude-3.5-haiku",
        "claude-3-haiku": "anthropic/claude-3.5-haiku",
        "gpt-3.5-turbo": "flash",  # Map to fast model
        
        # Standard tier - for moderate complexity
        "gpt-4o-mini": "mini",
        "claude-3-5-sonnet": "anthropic/claude-sonnet-4",
        "gemini-2.5-pro": "gemini-2.5-pro",
        
        # Premium tier - for complex tasks
        "gpt-4o": "openai/o3",
        "claude-opus-4": "anthropic/claude-opus-4",
        "o1-preview": "openai/o3",
        "o1-mini": "openai/o3-mini",
    }
    
    def __init__(self, mcp_session: Optional[Any] = None):
        """
        Initialize Claude Code LLM client
        
        Args:
            mcp_session: Optional MCP session for calling zen tools
        """
        self.mcp_session = mcp_session
        self.available = False
        
    async def initialize(self, mcp_session: Optional[Any] = None):
        """Initialize the client with MCP session"""
        if mcp_session:
            self.mcp_session = mcp_session
            
        if self.mcp_session:
            try:
                # Test if zen tools are available
                tools = await self.mcp_session.list_tools()
                zen_tools = [t for t in tools if t.name.startswith("mcp__zen__")]
                
                if zen_tools:
                    self.available = True
                    logger.info(f"Claude Code LLM client initialized with {len(zen_tools)} zen tools")
                else:
                    logger.warning("No zen tools found in MCP session")
                    
            except Exception as e:
                logger.warning(f"Failed to initialize Claude Code client: {e}")
                self.available = False
        else:
            logger.info("No MCP session provided, Claude Code client not available")
            
    def is_available(self) -> bool:
        """Check if Claude Code models are available"""
        return self.available and self.mcp_session is not None
    
    def get_available_models(self) -> List[str]:
        """Get list of models available through Claude Code"""
        if not self.is_available():
            return []
        return list(self.CLAUDE_CODE_MODELS.keys())
    
    def supports_model(self, model: str) -> bool:
        """Check if a model is supported by Claude Code"""
        return model in self.CLAUDE_CODE_MODELS
    
    async def complete(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        thinking_mode: str = "medium",
        **kwargs
    ) -> str:
        """
        Get completion using Claude Code's zen tools
        
        Args:
            prompt: The prompt text
            model: Model identifier
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            thinking_mode: Thinking depth (minimal/low/medium/high/max)
            **kwargs: Additional parameters
            
        Returns:
            Generated text
            
        Raises:
            ValueError: If model not supported or session not available
        """
        if not self.is_available():
            raise ValueError("Claude Code MCP session not available")
            
        if not self.supports_model(model):
            raise ValueError(f"Model {model} not supported by Claude Code")
            
        # Map to Claude Code model name
        zen_model = self.CLAUDE_CODE_MODELS[model]
        
        try:
            # Use mcp__zen__chat for completion
            result = await self.mcp_session.call_tool(
                "mcp__zen__chat",
                {
                    "prompt": prompt,
                    "model": zen_model,
                    "temperature": temperature,
                    "thinking_mode": thinking_mode,
                    "use_websearch": False  # Disable web search for speed
                }
            )
            
            # Extract response from result
            if isinstance(result, CallToolResult):
                # Parse the response content
                for content in result.content:
                    if hasattr(content, 'text'):
                        return content.text
                        
            # Fallback to string conversion
            return str(result)
            
        except Exception as e:
            logger.error(f"Claude Code completion failed for model {model}: {e}")
            raise
    
    async def analyze(
        self,
        request: str,
        context: Dict[str, Any],
        model: str = "gemini-2.5-flash",
        thinking_mode: str = "low"
    ) -> Dict[str, Any]:
        """
        Use zen tools for analysis tasks
        
        Args:
            request: Analysis request
            context: Additional context
            model: Model to use
            thinking_mode: Thinking depth
            
        Returns:
            Analysis result
        """
        if not self.is_available():
            raise ValueError("Claude Code MCP session not available")
            
        prompt = f"""Analyze this request and provide structured output:
        
Request: {request}
Context: {json.dumps(context, indent=2)}

Provide your analysis as JSON with fields:
- intent: The primary intent (READ/WRITE/SEARCH/ANALYZE/MANAGE)
- complexity: Task complexity (simple/moderate/complex)
- confidence: Your confidence level (0-1)
- reasoning: Brief explanation
"""
        
        response = await self.complete(
            prompt=prompt,
            model=model,
            temperature=0.3,  # Lower temperature for analysis
            thinking_mode=thinking_mode
        )
        
        # Try to parse JSON from response
        try:
            # Extract JSON if wrapped in markdown
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                json_str = response
                
            return json.loads(json_str)
        except:
            # Return as structured dict if parsing fails
            return {
                "intent": "ANALYZE",
                "complexity": "moderate",
                "confidence": 0.5,
                "reasoning": response[:200]
            }
    
    def estimate_cost(self, model: str, tokens: int) -> float:
        """
        Estimate cost for Claude Code models
        
        Args:
            model: Model name
            tokens: Number of tokens
            
        Returns:
            Estimated cost (0 for Claude Code since it's included)
        """
        # Claude Code models are included in the subscription
        # No additional cost
        return 0.0
    
    def get_model_info(self, model: str) -> Dict[str, Any]:
        """
        Get information about a Claude Code model
        
        Args:
            model: Model name
            
        Returns:
            Model information
        """
        if not self.supports_model(model):
            return {}
            
        zen_model = self.CLAUDE_CODE_MODELS[model]
        
        return {
            "name": model,
            "zen_model": zen_model,
            "provider": "claude_code",
            "cost": 0.0,  # No additional cost
            "available": self.is_available(),
            "supports_thinking": True,
            "max_context": 200000,  # Most zen models support large context
            "average_latency_ms": 1000  # Faster than external API
        }