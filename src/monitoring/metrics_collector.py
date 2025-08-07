"""Metrics collection and aggregation"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from collections import defaultdict, deque
import statistics

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Metrics for a single request"""
    request_id: str
    start_time: float
    end_time: Optional[float] = None
    intent: Optional[str] = None
    complexity: Optional[str] = None
    model_used: Optional[str] = None
    services_used: List[str] = field(default_factory=list)
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_saved: int = 0
    cost_usd: float = 0.0
    success: bool = False
    error: Optional[str] = None
    fallback_attempts: int = 0
    cache_hits: int = 0
    
    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0
    
    @property
    def total_tokens(self) -> int:
        return self.tokens_input + self.tokens_output


class MetricsCollector:
    """Collects and aggregates metrics"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.metrics_config = config.get("metrics", {})
        
        # Storage
        self.active_requests: Dict[str, RequestMetrics] = {}
        self.completed_requests: deque = deque(maxlen=10000)
        
        # Aggregated metrics
        self.counters = defaultdict(int)
        self.histograms = defaultdict(list)
        self.gauges = defaultdict(float)
        
        # Time series data (for graphing)
        self.time_series = defaultdict(lambda: deque(maxlen=1000))
        
        # Prometheus metrics (if available)
        if PROMETHEUS_AVAILABLE:
            self._init_prometheus_metrics()
        
        self.request_counter = 0
        self.start_time = time.time()
    
    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics"""
        self.prom_request_count = Counter(
            'orchestrator_requests_total',
            'Total number of requests',
            ['intent', 'complexity', 'status']
        )
        
        self.prom_request_duration = Histogram(
            'orchestrator_request_duration_seconds',
            'Request duration in seconds',
            ['intent', 'complexity']
        )
        
        self.prom_tokens_used = Counter(
            'orchestrator_tokens_total',
            'Total tokens used',
            ['model', 'type']
        )
        
        self.prom_cost = Counter(
            'orchestrator_cost_usd_total',
            'Total cost in USD',
            ['model']
        )
        
        self.prom_active_requests = Gauge(
            'orchestrator_active_requests',
            'Number of active requests'
        )
        
        self.prom_cache_hit_rate = Gauge(
            'orchestrator_cache_hit_rate',
            'Cache hit rate'
        )
    
    async def initialize(self):
        """Initialize metrics collector"""
        logger.info("Metrics collector initialized")
        
        # Start background aggregation task
        asyncio.create_task(self._aggregate_metrics_loop())
    
    def start_request(self) -> str:
        """
        Start tracking a new request
        
        Returns:
            Request ID
        """
        self.request_counter += 1
        request_id = f"req_{self.request_counter}_{int(time.time())}"
        
        metrics = RequestMetrics(
            request_id=request_id,
            start_time=time.time()
        )
        
        self.active_requests[request_id] = metrics
        
        # Update gauges
        self.gauges["active_requests"] = len(self.active_requests)
        
        if PROMETHEUS_AVAILABLE:
            self.prom_active_requests.set(len(self.active_requests))
        
        return request_id
    
    async def end_request(self, request_id: str, result: Dict[str, Any]):
        """
        End tracking for a request
        
        Args:
            request_id: Request ID
            result: Orchestration result
        """
        if request_id not in self.active_requests:
            logger.warning(f"Unknown request ID: {request_id}")
            return
        
        metrics = self.active_requests[request_id]
        metrics.end_time = time.time()
        
        # Update metrics from result
        metrics.intent = result.get("intent")
        metrics.complexity = result.get("complexity")
        metrics.model_used = result.get("selected_model")
        metrics.services_used = result.get("selected_services", [])
        metrics.success = result.get("success", False)
        
        if "metrics" in result:
            result_metrics = result["metrics"]
            metrics.tokens_input = result_metrics.get("tokens_input", 0)
            metrics.tokens_output = result_metrics.get("tokens_output", 0)
            metrics.tokens_saved = result_metrics.get("tokens_saved", 0)
            metrics.cost_usd = result_metrics.get("cost_usd", 0.0)
        
        # Move to completed
        del self.active_requests[request_id]
        self.completed_requests.append(metrics)
        
        # Update counters
        self.counters["total_requests"] += 1
        if metrics.success:
            self.counters["successful_requests"] += 1
        else:
            self.counters["failed_requests"] += 1
        
        # Update histograms
        self.histograms["duration_ms"].append(metrics.duration_ms)
        self.histograms["tokens_used"].append(metrics.total_tokens)
        self.histograms["cost_usd"].append(metrics.cost_usd)
        
        # Update time series
        current_time = datetime.now()
        self.time_series["requests_per_minute"].append((current_time, 1))
        self.time_series["tokens_per_minute"].append((current_time, metrics.total_tokens))
        self.time_series["cost_per_minute"].append((current_time, metrics.cost_usd))
        
        # Update Prometheus metrics
        if PROMETHEUS_AVAILABLE:
            status = "success" if metrics.success else "failure"
            self.prom_request_count.labels(
                intent=metrics.intent or "unknown",
                complexity=metrics.complexity or "unknown",
                status=status
            ).inc()
            
            self.prom_request_duration.labels(
                intent=metrics.intent or "unknown",
                complexity=metrics.complexity or "unknown"
            ).observe(metrics.duration_ms / 1000)
            
            if metrics.model_used:
                self.prom_tokens_used.labels(
                    model=metrics.model_used,
                    type="input"
                ).inc(metrics.tokens_input)
                
                self.prom_tokens_used.labels(
                    model=metrics.model_used,
                    type="output"
                ).inc(metrics.tokens_output)
                
                self.prom_cost.labels(
                    model=metrics.model_used
                ).inc(metrics.cost_usd)
        
        # Update gauges
        self.gauges["active_requests"] = len(self.active_requests)
        self._update_rates()
    
    async def record_orchestration(
        self,
        request_id: str,
        intent: str,
        complexity: str,
        model: str,
        services: List[str],
        duration_ms: float,
        success: bool,
        tokens_used: int,
        cost: float
    ):
        """Record orchestration metrics"""
        if request_id in self.active_requests:
            metrics = self.active_requests[request_id]
            metrics.intent = intent
            metrics.complexity = complexity
            metrics.model_used = model
            metrics.services_used = services
            metrics.tokens_input = tokens_used // 2  # Estimate
            metrics.tokens_output = tokens_used // 2
            metrics.cost_usd = cost
            metrics.success = success
    
    async def record_error(self, request_id: str, error: str):
        """Record an error for a request"""
        if request_id in self.active_requests:
            metrics = self.active_requests[request_id]
            metrics.error = error
            metrics.success = False
    
    async def get_metrics(self, period: str = "5m") -> Dict[str, Any]:
        """
        Get aggregated metrics for a time period
        
        Args:
            period: Time period (1m, 5m, 1h, 1d)
            
        Returns:
            Aggregated metrics
        """
        # Parse period
        period_seconds = self._parse_period(period)
        cutoff_time = time.time() - period_seconds
        
        # Filter recent requests
        recent_requests = [
            r for r in self.completed_requests
            if r.start_time >= cutoff_time
        ]
        
        if not recent_requests:
            return self._empty_metrics()
        
        # Calculate aggregates
        total_requests = len(recent_requests)
        successful_requests = sum(1 for r in recent_requests if r.success)
        failed_requests = total_requests - successful_requests
        
        durations = [r.duration_ms for r in recent_requests]
        tokens = [r.total_tokens for r in recent_requests]
        costs = [r.cost_usd for r in recent_requests]
        tokens_saved = [r.tokens_saved for r in recent_requests]
        
        # Intent distribution
        intent_counts = defaultdict(int)
        for r in recent_requests:
            if r.intent:
                intent_counts[r.intent] += 1
        
        # Model distribution
        model_counts = defaultdict(int)
        for r in recent_requests:
            if r.model_used:
                model_counts[r.model_used] += 1
        
        # Service usage
        service_counts = defaultdict(int)
        for r in recent_requests:
            for service in r.services_used:
                service_counts[service] += 1
        
        return {
            "period": period,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": successful_requests / total_requests if total_requests > 0 else 0,
            "avg_duration_ms": statistics.mean(durations) if durations else 0,
            "p50_duration_ms": statistics.median(durations) if durations else 0,
            "p95_duration_ms": self._percentile(durations, 0.95) if durations else 0,
            "p99_duration_ms": self._percentile(durations, 0.99) if durations else 0,
            "total_tokens": sum(tokens),
            "avg_tokens": statistics.mean(tokens) if tokens else 0,
            "total_tokens_saved": sum(tokens_saved),
            "total_cost_usd": sum(costs),
            "avg_cost_usd": statistics.mean(costs) if costs else 0,
            "requests_per_minute": total_requests / (period_seconds / 60),
            "intent_distribution": dict(intent_counts),
            "model_distribution": dict(model_counts),
            "service_usage": dict(service_counts),
            "cache_hit_rate": self._calculate_cache_hit_rate(recent_requests),
            "active_requests": len(self.active_requests),
            "uptime_seconds": time.time() - self.start_time
        }
    
    def _parse_period(self, period: str) -> float:
        """Parse period string to seconds"""
        unit_map = {
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400
        }
        
        if period[-1] in unit_map:
            value = int(period[:-1])
            unit = period[-1]
            return value * unit_map[unit]
        
        return 300  # Default 5 minutes
    
    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile of data"""
        if not data:
            return 0
        
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def _calculate_cache_hit_rate(self, requests: List[RequestMetrics]) -> float:
        """Calculate cache hit rate"""
        total_cache_ops = sum(r.cache_hits for r in requests)
        total_requests = len(requests)
        
        if total_requests == 0:
            return 0.0
        
        return total_cache_ops / total_requests
    
    def _update_rates(self):
        """Update rate metrics"""
        # Calculate rates over last minute
        current_time = time.time()
        one_minute_ago = current_time - 60
        
        recent_requests = [
            r for r in self.completed_requests
            if r.start_time >= one_minute_ago
        ]
        
        if recent_requests:
            self.gauges["requests_per_minute"] = len(recent_requests)
            self.gauges["tokens_per_minute"] = sum(r.total_tokens for r in recent_requests)
            self.gauges["cost_per_minute"] = sum(r.cost_usd for r in recent_requests)
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure"""
        return {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "success_rate": 0.0,
            "avg_duration_ms": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "active_requests": len(self.active_requests)
        }
    
    async def _aggregate_metrics_loop(self):
        """Background task to aggregate metrics"""
        while True:
            try:
                await asyncio.sleep(60)  # Aggregate every minute
                
                # Clean old time series data
                cutoff = datetime.now() - timedelta(hours=1)
                for key in self.time_series:
                    self.time_series[key] = deque(
                        [(t, v) for t, v in self.time_series[key] if t > cutoff],
                        maxlen=1000
                    )
                
                # Update cache hit rate gauge
                if PROMETHEUS_AVAILABLE and self.completed_requests:
                    recent = list(self.completed_requests)[-100:]
                    cache_hit_rate = self._calculate_cache_hit_rate(recent)
                    self.prom_cache_hit_rate.set(cache_hit_rate)
                
            except Exception as e:
                logger.error(f"Error in metrics aggregation: {e}")
    
    def export_prometheus(self) -> bytes:
        """Export metrics in Prometheus format"""
        if PROMETHEUS_AVAILABLE:
            return generate_latest()
        return b""