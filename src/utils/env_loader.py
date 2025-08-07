"""Secure environment variable loader for API keys"""

import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class EnvLoader:
    """Securely load and manage API keys from environment"""
    
    def __init__(self):
        # Load from .env file if exists
        env_path = Path(__file__).parent.parent.parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            logger.info("Loaded environment variables from .env file")
    
    @staticmethod
    def get_api_key(provider: str) -> Optional[str]:
        """
        Get API key for a provider
        
        Args:
            provider: Provider name (openai, google, anthropic)
            
        Returns:
            API key or None if not found
        """
        key_mapping = {
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY", 
            "anthropic": "ANTHROPIC_API_KEY"
        }
        
        env_var = key_mapping.get(provider.lower())
        if not env_var:
            logger.warning(f"Unknown provider: {provider}")
            return None
        
        api_key = os.environ.get(env_var)
        
        if not api_key:
            logger.warning(f"API key not found for {provider} (env var: {env_var})")
            return None
        
        # Never log the actual key
        logger.debug(f"API key loaded for {provider} (length: {len(api_key)})")
        return api_key
    
    @staticmethod
    def mask_api_key(api_key: str) -> str:
        """
        Mask API key for safe logging
        
        Args:
            api_key: The API key to mask
            
        Returns:
            Masked version showing only first 4 and last 4 characters
        """
        if not api_key or len(api_key) < 12:
            return "***"
        
        return f"{api_key[:4]}...{api_key[-4:]}"
    
    @staticmethod
    def validate_api_keys() -> Dict[str, bool]:
        """
        Check which API keys are configured
        
        Returns:
            Dictionary of provider -> availability
        """
        providers = ["openai", "google", "anthropic"]
        status = {}
        
        for provider in providers:
            key = EnvLoader.get_api_key(provider)
            status[provider] = bool(key)
            
            if key:
                masked = EnvLoader.mask_api_key(key)
                logger.info(f"{provider} API key configured: {masked}")
            else:
                logger.info(f"{provider} API key not configured")
        
        return status
    
    @staticmethod
    def get_redis_config() -> Dict[str, Any]:
        """Get Redis configuration from environment"""
        return {
            "url": os.environ.get("REDIS_URL", "redis://localhost:6379"),
            "password": os.environ.get("REDIS_PASSWORD"),
            "ssl": os.environ.get("REDIS_SSL", "false").lower() == "true"
        }
    
    @staticmethod
    def get_monitoring_config() -> Dict[str, Any]:
        """Get monitoring configuration from environment"""
        return {
            "prometheus_port": int(os.environ.get("PROMETHEUS_PORT", "9090")),
            "metrics_enabled": os.environ.get("METRICS_ENABLED", "true").lower() == "true"
        }