"""Cache for generated prompts"""

import time
import logging
from typing import Optional, Dict, Any
import json

from ..utils.env_loader import EnvLoader

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    
logger = logging.getLogger(__name__)


class PromptCache:
    """Cache for storing generated prompts"""
    
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.redis_client = None
        self.use_redis = False
    
    async def initialize(self):
        """Initialize cache backend"""
        if REDIS_AVAILABLE:
            try:
                # Load Redis config from environment
                env_loader = EnvLoader()
                redis_config = env_loader.get_redis_config()
                
                # Parse Redis URL if provided
                if redis_config.get('url'):
                    self.redis_client = redis.from_url(
                        redis_config['url'],
                        password=redis_config.get('password'),
                        decode_responses=True
                    )
                else:
                    # Fallback to localhost if no URL provided
                    self.redis_client = redis.Redis(
                        host='localhost',
                        port=6379,
                        decode_responses=True
                    )
                
                # Test connection
                self.redis_client.ping()
                self.use_redis = True
                logger.info("Using Redis for prompt caching")
            except Exception as e:
                logger.warning(f"Redis not available, using memory cache: {e}")
                self.use_redis = False
        else:
            logger.info("Using in-memory cache for prompts")
    
    async def get(self, key: str) -> Optional[str]:
        """
        Get a cached prompt
        
        Args:
            key: Cache key
            
        Returns:
            Cached prompt or None
        """
        try:
            if self.use_redis and self.redis_client:
                value = self.redis_client.get(f"prompt:{key}")
                if value:
                    return value
            else:
                # Check memory cache
                if key in self.memory_cache:
                    entry = self.memory_cache[key]
                    # Check if expired
                    if time.time() < entry["expires_at"]:
                        return entry["value"]
                    else:
                        # Remove expired entry
                        del self.memory_cache[key]
            
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    async def set(self, key: str, value: str):
        """
        Cache a generated prompt
        
        Args:
            key: Cache key
            value: Prompt to cache
        """
        try:
            if self.use_redis and self.redis_client:
                self.redis_client.setex(
                    f"prompt:{key}",
                    self.ttl_seconds,
                    value
                )
            else:
                # Use memory cache
                self.memory_cache[key] = {
                    "value": value,
                    "expires_at": time.time() + self.ttl_seconds
                }
                
                # Clean old entries if cache gets too large
                if len(self.memory_cache) > 100:
                    self._cleanup_memory_cache()
            
            logger.debug(f"Cached prompt with key: {key}")
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    def _cleanup_memory_cache(self):
        """Remove expired entries from memory cache"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.memory_cache.items()
            if current_time >= entry["expires_at"]
        ]
        
        for key in expired_keys:
            del self.memory_cache[key]
        
        logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    async def clear(self):
        """Clear all cached prompts"""
        try:
            if self.use_redis and self.redis_client:
                # Clear all prompt keys
                keys = self.redis_client.keys("prompt:*")
                if keys:
                    self.redis_client.delete(*keys)
            else:
                self.memory_cache.clear()
            
            logger.info("Prompt cache cleared")
            
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            "backend": "redis" if self.use_redis else "memory",
            "ttl_seconds": self.ttl_seconds
        }
        
        if self.use_redis and self.redis_client:
            try:
                keys = self.redis_client.keys("prompt:*")
                stats["cached_prompts"] = len(keys)
            except:
                stats["cached_prompts"] = 0
        else:
            stats["cached_prompts"] = len(self.memory_cache)
            stats["memory_size_bytes"] = sum(
                len(str(entry)) for entry in self.memory_cache.values()
            )
        
        return stats