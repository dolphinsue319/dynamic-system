"""Configuration loader"""

import os
from pathlib import Path
from typing import Any, Dict
import yaml
import logging

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Load and manage configuration"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_cache: Dict[str, Any] = {}
    
    def load_yaml(self, filename: str) -> Dict[str, Any]:
        """
        Load a YAML configuration file
        
        Args:
            filename: Name of the YAML file
            
        Returns:
            Configuration dictionary
        """
        if filename in self.config_cache:
            return self.config_cache[filename]
        
        file_path = self.config_dir / filename
        
        if not file_path.exists():
            logger.warning(f"Configuration file not found: {file_path}")
            return {}
        
        try:
            with open(file_path, 'r') as f:
                config = yaml.safe_load(f)
                
            # Replace environment variables
            config = self._replace_env_vars(config)
            
            self.config_cache[filename] = config
            return config
            
        except Exception as e:
            logger.error(f"Failed to load configuration from {file_path}: {e}")
            return {}
    
    def load_all(self) -> Dict[str, Any]:
        """
        Load all configuration files
        
        Returns:
            Combined configuration dictionary
        """
        config = {}
        
        # Load all YAML files in config directory
        if self.config_dir.exists():
            for yaml_file in self.config_dir.glob("*.yaml"):
                key = yaml_file.stem  # filename without extension
                config[key] = self.load_yaml(yaml_file.name)
        
        # Add environment variables
        config["env"] = self._load_env_vars()
        
        return config
    
    def _replace_env_vars(self, config: Any) -> Any:
        """
        Recursively replace environment variable references
        
        Args:
            config: Configuration data
            
        Returns:
            Configuration with env vars replaced
        """
        if isinstance(config, dict):
            return {k: self._replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
            env_var = config[2:-1]
            return os.environ.get(env_var, config)
        else:
            return config
    
    def _load_env_vars(self) -> Dict[str, str]:
        """
        Load relevant environment variables
        
        Returns:
            Dictionary of environment variables
        """
        env_vars = {}
        
        # API Keys
        for key in ["OPENAI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN"]:
            if key in os.environ:
                env_vars[key] = os.environ[key]
        
        # Service configuration
        env_vars["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "INFO")
        env_vars["MCP_PORT"] = os.environ.get("MCP_PORT", "8080")
        env_vars["CACHE_TTL"] = os.environ.get("CACHE_TTL", "3600")
        
        # Redis configuration
        env_vars["REDIS_HOST"] = os.environ.get("REDIS_HOST", "localhost")
        env_vars["REDIS_PORT"] = os.environ.get("REDIS_PORT", "6379")
        
        return env_vars
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value
        
        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self.config_cache
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value if value is not None else default