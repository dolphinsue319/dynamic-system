"""Unified LLM client for multiple providers"""

import logging
from typing import Any, Dict, Optional, List
from enum import Enum

from .env_loader import EnvLoader
from .claude_code_client import ClaudeCodeLLMClient

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers"""
    CLAUDE_CODE = "claude_code"  # Priority provider
    OPENAI = "openai"
    GOOGLE = "google"
    ANTHROPIC = "anthropic"


class LLMClient:
    """Unified client for multiple LLM providers"""
    
    def __init__(self, config: Dict[str, Any], mcp_session=None):
        self.config = config
        self.clients = {}
        self.initialized = False
        self.mcp_session = mcp_session
        self.claude_code_client = None
    
    async def initialize(self, mcp_session=None):
        """Initialize LLM clients based on available API keys"""
        if self.initialized:
            return
        
        # Update MCP session if provided
        if mcp_session:
            self.mcp_session = mcp_session
        
        # Initialize Claude Code client first (priority)
        if self.config.get("use_claude_code", True):
            try:
                self.claude_code_client = ClaudeCodeLLMClient(self.mcp_session)
                await self.claude_code_client.initialize()
                
                if self.claude_code_client.is_available():
                    self.clients[LLMProvider.CLAUDE_CODE] = self.claude_code_client
                    logger.info("Claude Code LLM client initialized (priority provider)")
            except Exception as e:
                logger.warning(f"Failed to initialize Claude Code client: {e}")
        
        # Load environment variables securely
        env_loader = EnvLoader()
        
        # Check for OpenAI
        openai_key = env_loader.get_api_key("openai")
        if openai_key:
            try:
                import openai
                self.clients[LLMProvider.OPENAI] = openai.AsyncOpenAI(
                    api_key=openai_key
                )
                masked_key = env_loader.mask_api_key(openai_key)
                logger.info(f"OpenAI client initialized with key: {masked_key}")
            except ImportError:
                logger.warning("OpenAI library not installed")
        
        # Check for Google
        google_key = env_loader.get_api_key("google")
        if google_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_key)
                self.clients[LLMProvider.GOOGLE] = genai
                masked_key = env_loader.mask_api_key(google_key)
                logger.info(f"Google Gemini client initialized with key: {masked_key}")
            except ImportError:
                logger.warning("Google Generative AI library not installed")
        
        # Check for Anthropic
        anthropic_key = env_loader.get_api_key("anthropic")
        if anthropic_key:
            try:
                import anthropic
                self.clients[LLMProvider.ANTHROPIC] = anthropic.AsyncAnthropic(
                    api_key=anthropic_key
                )
                masked_key = env_loader.mask_api_key(anthropic_key)
                logger.info(f"Anthropic client initialized with key: {masked_key}")
            except ImportError:
                logger.warning("Anthropic library not installed")
        
        self.initialized = True
        
        if not self.clients:
            logger.warning("No LLM providers initialized. Please set API keys.")
    
    async def complete(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """
        Get completion from LLM
        
        Args:
            prompt: The prompt text
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Generated text
        """
        # First, try Claude Code if available and model is supported
        if (self.claude_code_client and 
            self.claude_code_client.is_available() and
            self.claude_code_client.supports_model(model)):
            try:
                logger.info(f"Using Claude Code for model {model}")
                return await self.claude_code_client.complete(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            except Exception as e:
                logger.warning(f"Claude Code completion failed, falling back: {e}")
        
        # Fall back to external APIs
        provider = self._get_provider_from_model(model)
        
        if provider == LLMProvider.OPENAI:
            return await self._complete_openai(prompt, model, temperature, max_tokens, **kwargs)
        elif provider == LLMProvider.GOOGLE:
            return await self._complete_google(prompt, model, temperature, max_tokens, **kwargs)
        elif provider == LLMProvider.ANTHROPIC:
            return await self._complete_anthropic(prompt, model, temperature, max_tokens, **kwargs)
        else:
            # Fallback to any available provider
            return await self._complete_fallback(prompt, temperature, max_tokens, **kwargs)
    
    def _get_provider_from_model(self, model: str) -> Optional[LLMProvider]:
        """Determine provider from model name"""
        model_lower = model.lower()
        
        if any(x in model_lower for x in ["gpt", "o3", "o4", "turbo"]):
            return LLMProvider.OPENAI
        elif any(x in model_lower for x in ["gemini", "palm", "bard"]):
            return LLMProvider.GOOGLE
        elif any(x in model_lower for x in ["claude", "anthropic"]):
            return LLMProvider.ANTHROPIC
        
        return None
    
    async def _complete_openai(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """OpenAI completion"""
        if LLMProvider.OPENAI not in self.clients:
            raise ValueError("OpenAI client not initialized")
        
        client = self.clients[LLMProvider.OPENAI]
        
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI completion failed: {e}")
            raise
    
    async def _complete_google(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """Google Gemini completion"""
        if LLMProvider.GOOGLE not in self.clients:
            raise ValueError("Google client not initialized")
        
        genai = self.clients[LLMProvider.GOOGLE]
        
        try:
            # Map model names
            if "flash" in model.lower():
                model_name = "gemini-2.0-flash-latest"
            elif "pro" in model.lower():
                model_name = "gemini-1.5-pro-latest"
            else:
                model_name = model
            
            model_instance = genai.GenerativeModel(model_name)
            
            # Use asyncio to run the synchronous method
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model_instance.generate_content(
                    prompt,
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                    }
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Google completion failed: {e}")
            raise
    
    async def _complete_anthropic(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """Anthropic Claude completion"""
        if LLMProvider.ANTHROPIC not in self.clients:
            raise ValueError("Anthropic client not initialized")
        
        client = self.clients[LLMProvider.ANTHROPIC]
        
        try:
            response = await client.messages.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic completion failed: {e}")
            raise
    
    async def _complete_fallback(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """Fallback to any available provider"""
        # Try each provider in order
        for provider, client in self.clients.items():
            try:
                if provider == LLMProvider.OPENAI:
                    return await self._complete_openai(
                        prompt, "gpt-3.5-turbo", temperature, max_tokens, **kwargs
                    )
                elif provider == LLMProvider.GOOGLE:
                    return await self._complete_google(
                        prompt, "gemini-2.0-flash", temperature, max_tokens, **kwargs
                    )
                elif provider == LLMProvider.ANTHROPIC:
                    return await self._complete_anthropic(
                        prompt, "claude-3-haiku-20240307", temperature, max_tokens, **kwargs
                    )
            except Exception as e:
                logger.warning(f"Fallback to {provider.value} failed: {e}")
                continue
        
        raise ValueError("No LLM providers available")
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        # Rough estimate: 1 token ≈ 4 characters
        return len(text) // 4
    
    def get_available_models(self) -> List[str]:
        """Get list of available models based on initialized clients"""
        models = []
        
        if LLMProvider.OPENAI in self.clients:
            models.extend([
                "gpt-4o", "gpt-4o-mini", "gpt-4-turbo",
                "gpt-3.5-turbo", "o3", "o3-mini"
            ])
        
        if LLMProvider.GOOGLE in self.clients:
            models.extend([
                "gemini-2.0-flash", "gemini-2.0-flash-lite",
                "gemini-2.5-flash", "gemini-2.5-pro",
                "gemini-pro"
            ])
        
        if LLMProvider.ANTHROPIC in self.clients:
            models.extend([
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307"
            ])
        
        return models