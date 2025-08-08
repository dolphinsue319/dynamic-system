"""Cache system for document summaries"""

import json
import hashlib
import time
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import aiofiles
import pickle

logger = logging.getLogger(__name__)


class SummaryCache:
    """
    Cache for preprocessed document summaries.
    Supports both in-memory and file-based caching.
    """
    
    def __init__(
        self,
        cache_dir: str = "/tmp/document_cache",
        ttl_seconds: int = 3600 * 24,  # 24 hours default
        max_memory_items: int = 100
    ):
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.max_memory_items = max_memory_items
        
        # In-memory cache for fast access
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, float] = {}
        
    async def initialize(self):
        """Initialize cache system"""
        # Create cache directory if it doesn't exist with secure permissions
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as e:
            # Fallback for systems that don't support mode in mkdir
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # Try to set permissions after creation
            try:
                import os
                os.chmod(self.cache_dir, 0o700)
            except:
                pass  # Best effort, continue if permission setting fails
        
        # Clean expired cache files
        await self._cleanup_expired()
        
        logger.info(f"Summary cache initialized at {self.cache_dir}")
    
    def generate_key(self, content: str, context: str) -> str:
        """Generate a unique cache key for content + context"""
        # Use first 1000 chars of content + full context for key
        key_content = content[:1000] + context
        return hashlib.sha256(key_content.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get cached summary
        
        Args:
            key: Cache key
            
        Returns:
            Cached DocumentSummary or None
        """
        # Check memory cache first
        if key in self.memory_cache:
            cache_entry = self.memory_cache[key]
            if self._is_valid(cache_entry):
                self.access_times[key] = time.time()
                logger.debug(f"Cache hit (memory): {key}")
                return cache_entry['data']
            else:
                # Expired, remove from memory
                del self.memory_cache[key]
        
        # Check file cache
        cache_file = self.cache_dir / f"{key}.cache"
        if cache_file.exists():
            try:
                async with aiofiles.open(cache_file, 'rb') as f:
                    content = await f.read()
                    cache_entry = pickle.loads(content)
                
                if self._is_valid(cache_entry):
                    # Load into memory cache
                    await self._add_to_memory(key, cache_entry)
                    logger.debug(f"Cache hit (file): {key}")
                    return cache_entry['data']
                else:
                    # Expired, delete file
                    cache_file.unlink()
                    
            except Exception as e:
                logger.error(f"Failed to load cache file {cache_file}: {e}")
        
        logger.debug(f"Cache miss: {key}")
        return None
    
    async def set(self, key: str, data: Any) -> None:
        """
        Set cached summary
        
        Args:
            key: Cache key
            data: DocumentSummary to cache
        """
        cache_entry = {
            'data': data,
            'timestamp': time.time(),
            'ttl': self.ttl_seconds
        }
        
        # Add to memory cache
        await self._add_to_memory(key, cache_entry)
        
        # Save to file
        cache_file = self.cache_dir / f"{key}.cache"
        try:
            async with aiofiles.open(cache_file, 'wb') as f:
                await f.write(pickle.dumps(cache_entry))
            logger.debug(f"Cached summary: {key}")
        except Exception as e:
            logger.error(f"Failed to save cache file {cache_file}: {e}")
    
    async def invalidate(self, key: str) -> None:
        """Invalidate a specific cache entry"""
        # Remove from memory
        if key in self.memory_cache:
            del self.memory_cache[key]
        if key in self.access_times:
            del self.access_times[key]
        
        # Remove file
        cache_file = self.cache_dir / f"{key}.cache"
        if cache_file.exists():
            cache_file.unlink()
        
        logger.debug(f"Invalidated cache: {key}")
    
    async def clear(self) -> None:
        """Clear all cache entries"""
        # Clear memory
        self.memory_cache.clear()
        self.access_times.clear()
        
        # Clear files
        for cache_file in self.cache_dir.glob("*.cache"):
            cache_file.unlink()
        
        logger.info("Cache cleared")
    
    def _is_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid"""
        if 'timestamp' not in cache_entry or 'ttl' not in cache_entry:
            return False
        
        age = time.time() - cache_entry['timestamp']
        return age < cache_entry['ttl']
    
    async def _add_to_memory(self, key: str, cache_entry: Dict[str, Any]) -> None:
        """Add entry to memory cache with LRU eviction"""
        # Check if we need to evict
        if len(self.memory_cache) >= self.max_memory_items:
            # Find least recently used
            if self.access_times:
                lru_key = min(self.access_times, key=self.access_times.get)
                del self.memory_cache[lru_key]
                del self.access_times[lru_key]
                logger.debug(f"Evicted from memory cache: {lru_key}")
        
        self.memory_cache[key] = cache_entry
        self.access_times[key] = time.time()
    
    async def _cleanup_expired(self) -> None:
        """Remove expired cache files"""
        try:
            current_time = time.time()
            expired_count = 0
            
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    # Check file age
                    file_age = current_time - cache_file.stat().st_mtime
                    if file_age > self.ttl_seconds:
                        cache_file.unlink()
                        expired_count += 1
                except Exception as e:
                    logger.error(f"Failed to check/remove cache file {cache_file}: {e}")
            
            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired cache files")
                
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        file_count = len(list(self.cache_dir.glob("*.cache")))
        
        # Calculate total size
        total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.cache"))
        
        return {
            "memory_items": len(self.memory_cache),
            "file_items": file_count,
            "total_size_mb": total_size / (1024 * 1024),
            "cache_dir": str(self.cache_dir),
            "ttl_seconds": self.ttl_seconds,
            "max_memory_items": self.max_memory_items
        }