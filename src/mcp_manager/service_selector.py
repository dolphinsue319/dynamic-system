"""Intelligent MCP service selector"""

import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass

from .service_registry import MCPServiceRegistry, MCPService

logger = logging.getLogger(__name__)


@dataclass
class ServiceSelection:
    """Result of service selection"""
    primary: List[str]  # Primary services to use
    secondary: List[str]  # Fallback services
    excluded: List[str]  # Services explicitly excluded
    reasoning: str  # Explanation of selection


class MCPServiceSelector:
    """Intelligently selects MCP services based on context"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.registry = MCPServiceRegistry(config)
        self.intent_mapping = config.get("intent_mapping", {})
        
    async def initialize(self):
        """Initialize the service selector"""
        logger.info("MCP service selector initialized")
    
    async def select_services(
        self,
        intent: str,
        complexity: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Select appropriate MCP services for a request
        
        Args:
            intent: The classified intent
            complexity: The complexity level
            context: Additional context
            
        Returns:
            List of selected service names
        """
        context = context or {}
        
        # Get base services for intent
        services = self._get_services_for_intent(intent)
        
        # Filter based on complexity
        services = self._filter_by_complexity(services, complexity)
        
        # Apply context-based filtering
        services = self._apply_context_filters(services, context)
        
        # Apply user preferences
        services = self._apply_user_preferences(services, context)
        
        # Limit number of services based on complexity
        services = self._limit_services(services, complexity)
        
        logger.info(f"Selected services for {intent}/{complexity}: {services}")
        
        return services
    
    def _get_services_for_intent(self, intent: str) -> List[str]:
        """Get base services for an intent"""
        # Check configured mapping first
        if intent in self.intent_mapping:
            primary = self.intent_mapping[intent].get("primary", [])
            # Get services from registry
            registered_services = self.registry.get_services_for_intent(intent)
            registered_names = [s.name for s in registered_services]
            
            # Combine configured and registered services
            all_services = []
            for service in primary:
                if service in registered_names or self.registry.get_service(service):
                    all_services.append(service)
            
            # Add registered services not in config
            for name in registered_names:
                if name not in all_services:
                    all_services.append(name)
            
            return all_services
        
        # Fallback to registry
        services = self.registry.get_services_for_intent(intent)
        return [s.name for s in services]
    
    def _filter_by_complexity(self, services: List[str], complexity: str) -> List[str]:
        """Filter services based on complexity"""
        if complexity == "simple":
            # For simple tasks, prefer lightweight services
            lightweight = ["filesystem", "memory"]
            return [s for s in services if any(l in s.lower() for l in lightweight)] or services[:2]
        
        elif complexity == "complex":
            # For complex tasks, include all relevant services
            return services
        
        else:  # moderate
            # For moderate tasks, use primary services only
            return services[:3] if len(services) > 3 else services
    
    def _apply_context_filters(
        self,
        services: List[str],
        context: Dict[str, Any]
    ) -> List[str]:
        """Apply context-based filtering"""
        filtered = services.copy()
        
        # Project type filtering
        project_type = context.get("project_type")
        if project_type:
            if project_type == "local":
                # Prefer local services
                filtered = [s for s in filtered if "cloud" not in s.lower()] or filtered
            elif project_type == "cloud":
                # Prefer cloud services
                filtered = [s for s in filtered if "local" not in s.lower()] or filtered
        
        # Security constraints
        if context.get("secure_only"):
            # Exclude potentially insecure services
            filtered = [s for s in filtered if "public" not in s.lower()]
        
        # Performance requirements
        if context.get("high_performance"):
            # Exclude slow services
            slow_services = ["web-search"]
            filtered = [s for s in filtered if s not in slow_services] or filtered
        
        return filtered
    
    def _apply_user_preferences(
        self,
        services: List[str],
        context: Dict[str, Any]
    ) -> List[str]:
        """Apply user preferences"""
        preferences = context.get("user_preferences", {})
        
        # Preferred services
        preferred = preferences.get("preferred_services", [])
        if preferred:
            # Move preferred services to front
            reordered = []
            for service in preferred:
                if service in services:
                    reordered.append(service)
            for service in services:
                if service not in reordered:
                    reordered.append(service)
            services = reordered
        
        # Excluded services
        excluded = preferences.get("excluded_services", [])
        if excluded:
            services = [s for s in services if s not in excluded]
        
        return services
    
    def _limit_services(self, services: List[str], complexity: str) -> List[str]:
        """Limit number of services based on complexity"""
        limits = {
            "simple": 2,
            "moderate": 3,
            "complex": 5
        }
        
        limit = limits.get(complexity, 3)
        return services[:limit]
    
    def get_service_details(self, service_names: List[str]) -> List[Dict[str, Any]]:
        """
        Get detailed information about selected services
        
        Args:
            service_names: List of service names
            
        Returns:
            List of service details
        """
        details = []
        
        for name in service_names:
            service = self.registry.get_service(name)
            if service:
                details.append({
                    "name": service.name,
                    "type": service.type.value,
                    "description": service.description,
                    "supported_intents": service.supported_intents,
                    "priority": service.priority,
                    "enabled": service.enabled
                })
        
        return details
    
    def estimate_latency(self, services: List[str]) -> int:
        """
        Estimate total latency for selected services
        
        Args:
            services: List of service names
            
        Returns:
            Estimated latency in milliseconds
        """
        # Base latency estimates per service type
        latency_map = {
            "filesystem": 10,
            "memory": 5,
            "database": 50,
            "github": 200,
            "web-search": 500,
        }
        
        total_latency = 0
        for service in services:
            # Find matching latency
            for key, latency in latency_map.items():
                if key in service.lower():
                    total_latency += latency
                    break
            else:
                # Default latency
                total_latency += 100
        
        # Add overhead
        total_latency += 50
        
        return total_latency
    
    async def validate_services(self, services: List[str]) -> Dict[str, bool]:
        """
        Validate that services are available and responsive
        
        Args:
            services: List of service names
            
        Returns:
            Dictionary of service availability
        """
        availability = {}
        
        for service_name in services:
            service = self.registry.get_service(service_name)
            if service and service.enabled:
                # TODO: Implement actual connectivity check
                availability[service_name] = True
            else:
                availability[service_name] = False
        
        return availability