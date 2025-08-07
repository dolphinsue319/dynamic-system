"""Pydantic models for request validation"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
import re


class OrchestrateRequest(BaseModel):
    """Validated orchestration request"""
    
    request: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The user's request to orchestrate"
    )
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional context for the request"
    )
    options: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="User options and preferences"
    )
    
    @validator('request')
    def validate_request(cls, v):
        """Validate and sanitize the request"""
        # Strip whitespace
        v = v.strip()
        
        # Check for empty request
        if not v:
            raise ValueError('Request cannot be empty')
        
        # Check for excessive length
        if len(v) > 10000:
            raise ValueError('Request too long (max 10000 characters)')
        
        # Basic sanitization - remove potential injection patterns
        dangerous_patterns = [
            r'<script',
            r'javascript:',
            r'eval\(',
            r'exec\(',
            r'__import__',
            r'os\.system',
            r'subprocess\.',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError(f'Invalid pattern detected in request: {pattern}')
        
        return v
    
    @validator('context')
    def validate_context(cls, v):
        """Validate context dictionary"""
        if v and len(str(v)) > 50000:
            raise ValueError('Context too large (max 50KB)')
        return v
    
    @validator('options')
    def validate_options(cls, v):
        """Validate options dictionary"""
        if v:
            # Validate specific option constraints
            if 'max_cost' in v:
                if not isinstance(v['max_cost'], (int, float)):
                    raise ValueError('max_cost must be a number')
                if v['max_cost'] < 0:
                    raise ValueError('max_cost cannot be negative')
                if v['max_cost'] > 100:
                    raise ValueError('max_cost too high (max $100)')
            
            if 'max_latency_ms' in v:
                if not isinstance(v['max_latency_ms'], int):
                    raise ValueError('max_latency_ms must be an integer')
                if v['max_latency_ms'] < 100:
                    raise ValueError('max_latency_ms too low (min 100ms)')
                if v['max_latency_ms'] > 300000:
                    raise ValueError('max_latency_ms too high (max 5 minutes)')
            
            if 'preferred_models' in v:
                if not isinstance(v['preferred_models'], list):
                    raise ValueError('preferred_models must be a list')
                if len(v['preferred_models']) > 10:
                    raise ValueError('Too many preferred models (max 10)')
        
        return v


class AnalyzeRequest(BaseModel):
    """Validated analysis request"""
    
    request: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The request to analyze"
    )
    
    @validator('request')
    def validate_request(cls, v):
        """Validate the analysis request"""
        v = v.strip()
        if not v:
            raise ValueError('Request cannot be empty')
        if len(v) > 10000:
            raise ValueError('Request too long')
        return v


class MetricsRequest(BaseModel):
    """Validated metrics request"""
    
    period: str = Field(
        default="5m",
        regex="^[0-9]+[smhd]$",
        description="Time period for metrics (e.g., 5m, 1h, 1d)"
    )
    
    @validator('period')
    def validate_period(cls, v):
        """Validate the time period"""
        # Extract number and unit
        import re
        match = re.match(r'^(\d+)([smhd])$', v)
        if not match:
            raise ValueError('Invalid period format (use: 1s, 5m, 1h, 1d)')
        
        value = int(match.group(1))
        unit = match.group(2)
        
        # Validate reasonable ranges
        max_values = {'s': 3600, 'm': 1440, 'h': 168, 'd': 30}
        if value > max_values.get(unit, 30):
            raise ValueError(f'Period too long for unit {unit}')
        
        return v


def validate_request(request_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a request based on its type
    
    Args:
        request_type: Type of request (orchestrate, analyze, metrics)
        data: Request data to validate
        
    Returns:
        Validated data as dictionary
        
    Raises:
        ValueError: If validation fails
    """
    validators = {
        'orchestrate': OrchestrateRequest,
        'analyze': AnalyzeRequest,
        'metrics': MetricsRequest
    }
    
    validator_class = validators.get(request_type)
    if not validator_class:
        raise ValueError(f'Unknown request type: {request_type}')
    
    try:
        validated = validator_class(**data)
        return validated.dict()
    except Exception as e:
        raise ValueError(f'Validation failed: {str(e)}')