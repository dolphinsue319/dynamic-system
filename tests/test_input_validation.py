"""Tests for input validation with Pydantic"""

import pytest
from src.models.requests import OrchestrateRequest, AnalyzeRequest, MetricsRequest, validate_request


class TestOrchestrateRequest:
    """Test orchestrate request validation"""
    
    def test_valid_request(self):
        """Test valid orchestration request"""
        data = {
            "request": "Create a REST API endpoint",
            "context": {"framework": "FastAPI"},
            "options": {"max_cost": 0.1}
        }
        
        validated = OrchestrateRequest(**data)
        assert validated.request == "Create a REST API endpoint"
        assert validated.context["framework"] == "FastAPI"
        assert validated.options["max_cost"] == 0.1
    
    def test_empty_request(self):
        """Test that empty request is rejected"""
        with pytest.raises(ValueError, match="Request cannot be empty"):
            OrchestrateRequest(request="")
    
    def test_whitespace_only_request(self):
        """Test that whitespace-only request is rejected"""
        with pytest.raises(ValueError, match="Request cannot be empty"):
            OrchestrateRequest(request="   \n\t  ")
    
    def test_request_too_long(self):
        """Test that overly long request is rejected"""
        with pytest.raises(ValueError, match="Request too long"):
            OrchestrateRequest(request="x" * 10001)
    
    def test_sql_injection_attempt(self):
        """Test that SQL injection patterns are rejected"""
        with pytest.raises(ValueError, match="Invalid pattern"):
            OrchestrateRequest(request="'; DROP TABLE users; --")
    
    def test_javascript_injection_attempt(self):
        """Test that JavaScript injection is rejected"""
        with pytest.raises(ValueError, match="Invalid pattern"):
            OrchestrateRequest(request="<script>alert('xss')</script>")
    
    def test_python_code_injection_attempt(self):
        """Test that Python code injection is rejected"""
        dangerous_requests = [
            "eval('malicious code')",
            "__import__('os').system('rm -rf /')",
            "exec('import os; os.system(\"ls\")')",
            "subprocess.call(['rm', '-rf', '/'])"
        ]
        
        for req in dangerous_requests:
            with pytest.raises(ValueError, match="Invalid pattern"):
                OrchestrateRequest(request=req)
    
    def test_context_too_large(self):
        """Test that overly large context is rejected"""
        large_context = {"data": "x" * 60000}
        
        with pytest.raises(ValueError, match="Context too large"):
            OrchestrateRequest(request="Test", context=large_context)
    
    def test_invalid_max_cost(self):
        """Test max_cost validation"""
        # Negative cost
        with pytest.raises(ValueError, match="max_cost cannot be negative"):
            OrchestrateRequest(
                request="Test",
                options={"max_cost": -1}
            )
        
        # Too high cost
        with pytest.raises(ValueError, match="max_cost too high"):
            OrchestrateRequest(
                request="Test",
                options={"max_cost": 150}
            )
        
        # Non-numeric cost
        with pytest.raises(ValueError, match="max_cost must be a number"):
            OrchestrateRequest(
                request="Test",
                options={"max_cost": "free"}
            )
    
    def test_invalid_max_latency(self):
        """Test max_latency_ms validation"""
        # Too low
        with pytest.raises(ValueError, match="max_latency_ms too low"):
            OrchestrateRequest(
                request="Test",
                options={"max_latency_ms": 50}
            )
        
        # Too high
        with pytest.raises(ValueError, match="max_latency_ms too high"):
            OrchestrateRequest(
                request="Test",
                options={"max_latency_ms": 400000}
            )
        
        # Non-integer
        with pytest.raises(ValueError, match="max_latency_ms must be an integer"):
            OrchestrateRequest(
                request="Test",
                options={"max_latency_ms": "fast"}
            )
    
    def test_invalid_preferred_models(self):
        """Test preferred_models validation"""
        # Not a list
        with pytest.raises(ValueError, match="preferred_models must be a list"):
            OrchestrateRequest(
                request="Test",
                options={"preferred_models": "gpt-4"}
            )
        
        # Too many models
        with pytest.raises(ValueError, match="Too many preferred models"):
            OrchestrateRequest(
                request="Test",
                options={"preferred_models": [f"model-{i}" for i in range(15)]}
            )


class TestAnalyzeRequest:
    """Test analyze request validation"""
    
    def test_valid_request(self):
        """Test valid analysis request"""
        validated = AnalyzeRequest(request="Analyze the codebase structure")
        assert validated.request == "Analyze the codebase structure"
    
    def test_empty_request(self):
        """Test that empty request is rejected"""
        with pytest.raises(ValueError, match="Request cannot be empty"):
            AnalyzeRequest(request="")
    
    def test_request_too_long(self):
        """Test that overly long request is rejected"""
        with pytest.raises(ValueError, match="Request too long"):
            AnalyzeRequest(request="x" * 10001)


class TestMetricsRequest:
    """Test metrics request validation"""
    
    def test_valid_periods(self):
        """Test valid time periods"""
        valid_periods = ["1s", "5m", "1h", "7d", "30d"]
        
        for period in valid_periods:
            validated = MetricsRequest(period=period)
            assert validated.period == period
    
    def test_default_period(self):
        """Test default period is 5m"""
        validated = MetricsRequest()
        assert validated.period == "5m"
    
    def test_invalid_period_format(self):
        """Test invalid period formats are rejected"""
        invalid_periods = ["5", "m5", "5 minutes", "1w", "abc"]
        
        for period in invalid_periods:
            with pytest.raises(ValueError, match="Invalid period"):
                MetricsRequest(period=period)
    
    def test_period_too_long(self):
        """Test that overly long periods are rejected"""
        with pytest.raises(ValueError, match="Period too long"):
            MetricsRequest(period="100d")
        
        with pytest.raises(ValueError, match="Period too long"):
            MetricsRequest(period="200h")


class TestValidateRequest:
    """Test the validate_request helper function"""
    
    def test_orchestrate_validation(self):
        """Test orchestrate request validation"""
        data = {"request": "Test request"}
        result = validate_request("orchestrate", data)
        assert result["request"] == "Test request"
        assert result["context"] == {}
        assert result["options"] == {}
    
    def test_analyze_validation(self):
        """Test analyze request validation"""
        data = {"request": "Analyze this"}
        result = validate_request("analyze", data)
        assert result["request"] == "Analyze this"
    
    def test_metrics_validation(self):
        """Test metrics request validation"""
        data = {"period": "1h"}
        result = validate_request("metrics", data)
        assert result["period"] == "1h"
    
    def test_unknown_request_type(self):
        """Test unknown request type is rejected"""
        with pytest.raises(ValueError, match="Unknown request type"):
            validate_request("unknown", {"request": "test"})
    
    def test_validation_error_propagation(self):
        """Test that validation errors are properly propagated"""
        with pytest.raises(ValueError, match="Validation failed"):
            validate_request("orchestrate", {"request": ""})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])