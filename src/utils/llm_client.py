"""Unified LLM client for multiple providers"""

import os
import logging
from typing import Any, Dict, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    GOOGLE = "google"
    ANTHROPIC = "anthropic"


class LLMClient:
    """Unified client for multiple LLM providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.clients = {}
        self.initialized = False
    
    async def initialize(self):
        """Initialize LLM clients based on available API keys"""
        if self.initialized:
            return
        
        # Check for OpenAI
        if os.environ.get("OPENAI_API_KEY"):
            try:
                import openai
                self.clients[LLMProvider.OPENAI] = openai.AsyncOpenAI(
                    api_key=os.environ["OPENAI_API_KEY"]
                )
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.warning("OpenAI library not installed")
        
        # Check for Google
        if os.environ.get("GOOGLE_API_KEY"):
            try:
                import google.generativeai as genai
                genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
                self.clients[LLMProvider.GOOGLE] = genai
                logger.info("Google Gemini client initialized")
            except ImportError:
                logger.warning("Google Generative AI library not installed")
        
        # Check for Anthropic
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                import anthropic
                self.clients[LLMProvider.ANTHROPIC] = anthropic.AsyncAnthropic(
                    api_key=os.environ["ANTHROPIC_API_KEY"]
                )
                logger.info("Anthropic client initialized")
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
        # Determine provider from model name
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
            
            response = await model_instance.generate_content_async(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                }
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