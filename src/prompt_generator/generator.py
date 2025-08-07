"""Dynamic prompt generator using LLM"""

import logging
import hashlib
from typing import Dict, Any, Optional

from ..utils.llm_client import LLMClient
from .cache import PromptCache

logger = logging.getLogger(__name__)


class PromptGenerator:
    """Generates dynamic prompts based on intent and context"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm_client = LLMClient(config)
        self.cache = PromptCache()
        
        # Meta-prompt for generating focused prompts
        self.meta_prompt_template = """Generate a concise, focused system prompt for the following task:

Intent: {intent}
Complexity: {complexity}
Available Services: {services}
Context: {context}

Requirements:
1. Keep the prompt under 500 tokens
2. Be specific and actionable
3. Include relevant constraints and guidelines
4. Focus on the {intent} operation
5. Optimize for {complexity} complexity level
6. Reference available services when relevant

Generate ONLY the system prompt, no explanations or metadata."""
    
    async def initialize(self):
        """Initialize the generator"""
        await self.llm_client.initialize()
        await self.cache.initialize()
        logger.info("Prompt generator initialized")
    
    async def generate(
        self,
        intent: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Generate a dynamic prompt for the given intent and context
        
        Args:
            intent: The classified intent
            context: Context including complexity, services, etc.
            
        Returns:
            Generated system prompt
        """
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(intent, context)
            
            # Check cache first
            cached_prompt = await self.cache.get(cache_key)
            if cached_prompt:
                logger.info(f"Using cached prompt for key: {cache_key}")
                return cached_prompt
            
            # Build meta-prompt
            meta_prompt = self.meta_prompt_template.format(
                intent=intent,
                complexity=context.get("complexity", "moderate"),
                services=", ".join(context.get("services", [])),
                context=self._format_context(context.get("user_context", {}))
            )
            
            # Use prompt generator model
            model = self.config.get("prompt_generator", {}).get("default", "gemini-2.0-flash")
            temperature = self.config.get("prompt_generator", {}).get("temperature", 0.3)
            max_tokens = self.config.get("prompt_generator", {}).get("max_tokens", 500)
            
            # Generate prompt
            generated_prompt = await self.llm_client.complete(
                prompt=meta_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Clean and validate
            generated_prompt = self._clean_prompt(generated_prompt)
            
            # Add base instructions
            final_prompt = self._add_base_instructions(generated_prompt, intent, context)
            
            # Cache the result
            await self.cache.set(cache_key, final_prompt)
            
            logger.info(f"Generated prompt of {len(final_prompt)} characters for intent: {intent}")
            
            return final_prompt
            
        except Exception as e:
            logger.error(f"Prompt generation failed: {e}")
            # Return fallback prompt
            return self._get_fallback_prompt(intent, context)
    
    def _generate_cache_key(self, intent: str, context: Dict[str, Any]) -> str:
        """Generate a cache key for the prompt"""
        key_data = {
            "intent": intent,
            "complexity": context.get("complexity"),
            "services": sorted(context.get("services", [])),
            "user_context_keys": sorted(context.get("user_context", {}).keys())
        }
        
        key_str = str(key_data)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _format_context(self, user_context: Dict[str, Any]) -> str:
        """Format user context for inclusion in meta-prompt"""
        if not user_context:
            return "No specific context provided"
        
        formatted = []
        for key, value in user_context.items():
            if isinstance(value, dict):
                value = str(value)[:100]  # Limit nested dict size
            formatted.append(f"- {key}: {value}")
        
        return "\n".join(formatted)
    
    def _clean_prompt(self, prompt: str) -> str:
        """Clean and validate generated prompt"""
        # Remove any meta-instructions that might have leaked
        lines = prompt.strip().split("\n")
        cleaned_lines = []
        
        for line in lines:
            # Skip lines that look like meta-instructions
            if any(keyword in line.lower() for keyword in 
                   ["generate", "create a prompt", "requirements:", "keep under"]):
                continue
            cleaned_lines.append(line)
        
        return "\n".join(cleaned_lines).strip()
    
    def _add_base_instructions(
        self,
        prompt: str,
        intent: str,
        context: Dict[str, Any]
    ) -> str:
        """Add base instructions to the generated prompt"""
        base_instructions = []
        
        # Add intent-specific base instructions
        if intent == "write":
            base_instructions.append("Ensure all generated content is accurate and well-formatted.")
        elif intent == "search":
            base_instructions.append("Be thorough but concise in presenting search results.")
        elif intent == "analyze":
            base_instructions.append("Provide clear insights and actionable recommendations.")
        
        # Add complexity-specific instructions
        complexity = context.get("complexity", "moderate")
        if complexity == "simple":
            base_instructions.append("Keep the response brief and to the point.")
        elif complexity == "complex":
            base_instructions.append("Provide detailed analysis with step-by-step reasoning.")
        
        # Add service-specific instructions
        services = context.get("services", [])
        if services:
            base_instructions.append(f"You have access to these services: {', '.join(services)}")
        
        # Combine with generated prompt
        if base_instructions:
            return prompt + "\n\n" + "\n".join(base_instructions)
        
        return prompt
    
    def _get_fallback_prompt(self, intent: str, context: Dict[str, Any]) -> str:
        """Get a fallback prompt if generation fails"""
        fallback_prompts = {
            "read": "Help the user retrieve and understand the requested information. Be accurate and comprehensive.",
            "write": "Help the user create or modify content as requested. Ensure quality and correctness.",
            "search": "Help the user find the information they're looking for. Be thorough and relevant.",
            "analyze": "Analyze the provided data or situation and provide clear insights and recommendations.",
            "manage": "Help the user organize, configure, or administer the requested resources effectively."
        }
        
        base = fallback_prompts.get(intent, "Help the user with their request.")
        
        # Add context if available
        if context.get("services"):
            base += f"\n\nAvailable services: {', '.join(context['services'])}"
        
        return base