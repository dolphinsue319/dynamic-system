# Security Improvements Required

## Critical Security Issues to Address

### 1. Authentication & Authorization
- [ ] Add API key authentication for MCP endpoints
- [ ] Implement request signing/verification
- [ ] Add rate limiting middleware

### 2. Input Validation
- [ ] Add Pydantic models for all request payloads
- [ ] Implement input sanitization
- [ ] Add request size limits

### 3. Redis Security
- [ ] Use environment variables for Redis configuration
- [ ] Add Redis AUTH password
- [ ] Consider TLS for Redis connections

### 4. API Key Management
- [ ] Secure storage of API keys
- [ ] Rotate keys regularly
- [ ] Never log sensitive keys

### 5. Container Security
- [ ] Run as non-root user
- [ ] Remove unnecessary packages
- [ ] Add health checks
- [ ] Set resource limits

## Implementation Priority

1. **Immediate (Critical)**
   - Add authentication to MCP server
   - Secure Redis configuration
   - Input validation with Pydantic

2. **Short Term (High)**
   - Rate limiting
   - Async Redis with aioredis
   - Update model configurations

3. **Medium Term**
   - Comprehensive logging
   - Monitoring improvements
   - Test coverage increase

## Code Examples

### Authentication Middleware
```python
from functools import wraps
import os
import hashlib

def require_auth(f):
    @wraps(f)
    async def decorated_function(self, *args, **kwargs):
        # Get API key from request or environment
        provided_key = get_api_key_from_request()
        expected_key_hash = os.environ.get("MCP_API_KEY_HASH")
        
        if not provided_key or not expected_key_hash:
            raise ValueError("Authentication required")
        
        # Compare hashed keys
        provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()
        if provided_hash != expected_key_hash:
            raise ValueError("Invalid API key")
            
        return await f(self, *args, **kwargs)
    return decorated_function
```

### Input Validation
```python
from pydantic import BaseModel, Field, validator

class OrchestrateRequest(BaseModel):
    request: str = Field(..., min_length=1, max_length=10000)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('request')
    def sanitize_request(cls, v):
        # Remove any potential injection attempts
        v = v.strip()
        if any(char in v for char in ['<script', 'javascript:', 'eval(']):
            raise ValueError('Invalid characters in request')
        return v
```

### Secure Redis Configuration
```python
import os
import aioredis
from typing import Optional

async def create_redis_client() -> Optional[aioredis.Redis]:
    redis_url = os.environ.get('REDIS_URL')
    redis_password = os.environ.get('REDIS_PASSWORD')
    redis_ssl = os.environ.get('REDIS_SSL', 'false').lower() == 'true'
    
    if not redis_url:
        return None
    
    try:
        client = await aioredis.from_url(
            redis_url,
            password=redis_password,
            ssl=redis_ssl,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        await client.ping()
        return client
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        return None
```

## Testing Security

Add security-focused tests:

```python
import pytest
from unittest.mock import patch

@pytest.mark.asyncio
async def test_authentication_required():
    """Test that endpoints require authentication"""
    server = DynamicOrchestratorServer({})
    
    with pytest.raises(ValueError, match="Authentication required"):
        await server.handle_call_tool("orchestrate", {})

@pytest.mark.asyncio
async def test_input_validation():
    """Test input validation and sanitization"""
    from src.server import OrchestrateRequest
    
    # Test SQL injection attempt
    with pytest.raises(ValueError):
        OrchestrateRequest(request="'; DROP TABLE users; --")
    
    # Test XSS attempt
    with pytest.raises(ValueError):
        OrchestrateRequest(request="<script>alert('xss')</script>")
    
    # Test oversized request
    with pytest.raises(ValueError):
        OrchestrateRequest(request="x" * 10001)
```

## Monitoring & Alerting

Add security metrics:
- Failed authentication attempts
- Rate limit violations
- Input validation failures
- Unusual token usage patterns
- API error rates by endpoint

## References
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [MCP Security Best Practices](https://modelcontextprotocol.io/docs/security)
- [Redis Security Guidelines](https://redis.io/docs/management/security/)