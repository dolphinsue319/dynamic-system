"""MCP service registry for managing available services"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """Types of MCP service connections"""
    STDIO = "stdio"
    HTTP = "http"
    WEBSOCKET = "websocket"


@dataclass
class MCPService:
    """MCP service definition"""
    name: str
    type: ServiceType
    command: Optional[List[str]] = None
    url: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    supported_intents: List[str] = None
    description: str = ""
    enabled: bool = True
    priority: int = 0  # Higher priority services are preferred


class MCPServiceRegistry:
    """Registry for managing MCP services"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.services: Dict[str, MCPService] = {}
        self.intent_map: Dict[str, List[str]] = {}
        self._load_services()
    
    def _load_services(self):
        """Load services from configuration"""
        services_config = self.config.get("services", {})
        
        for service_name, service_config in services_config.items():
            try:
                # Create service instance
                service = MCPService(
                    name=service_name,
                    type=ServiceType(service_config.get("type", "stdio")),
                    command=service_config.get("command"),
                    url=service_config.get("url"),
                    args=service_config.get("args"),
                    env=service_config.get("env"),
                    supported_intents=service_config.get("supported_intents", []),
                    description=service_config.get("description", ""),
                    enabled=service_config.get("enabled", True),
                    priority=service_config.get("priority", 0)
                )
                
                self.services[service_name] = service
                
                # Build intent mapping
                for intent in service.supported_intents:
                    if intent not in self.intent_map:
                        self.intent_map[intent] = []
                    self.intent_map[intent].append(service_name)
                
                logger.info(f"Registered MCP service: {service_name}")
                
            except Exception as e:
                logger.error(f"Failed to load service {service_name}: {e}")
    
    def get_service(self, name: str) -> Optional[MCPService]:
        """
        Get a specific service by name
        
        Args:
            name: Service name
            
        Returns:
            MCPService instance or None
        """
        return self.services.get(name)
    
    def get_services_for_intent(self, intent: str) -> List[MCPService]:
        """
        Get all services that support a specific intent
        
        Args:
            intent: The intent type
            
        Returns:
            List of MCPService instances
        """
        service_names = self.intent_map.get(intent, [])
        services = []
        
        for name in service_names:
            service = self.services.get(name)
            if service and service.enabled:
                services.append(service)
        
        # Sort by priority (higher first)
        services.sort(key=lambda s: s.priority, reverse=True)
        
        return services
    
    def get_all_services(self) -> List[MCPService]:
        """
        Get all registered services
        
        Returns:
            List of all MCPService instances
        """
        return list(self.services.values())
    
    def enable_service(self, name: str):
        """Enable a service"""
        if name in self.services:
            self.services[name].enabled = True
            logger.info(f"Enabled service: {name}")
    
    def disable_service(self, name: str):
        """Disable a service"""
        if name in self.services:
            self.services[name].enabled = False
            logger.info(f"Disabled service: {name}")
    
    def register_service(self, service: MCPService):
        """
        Register a new service dynamically
        
        Args:
            service: MCPService instance to register
        """
        self.services[service.name] = service
        
        # Update intent mapping
        for intent in service.supported_intents:
            if intent not in self.intent_map:
                self.intent_map[intent] = []
            if service.name not in self.intent_map[intent]:
                self.intent_map[intent].append(service.name)
        
        logger.info(f"Dynamically registered service: {service.name}")
    
    def unregister_service(self, name: str):
        """
        Unregister a service
        
        Args:
            name: Service name to unregister
        """
        if name in self.services:
            service = self.services[name]
            
            # Remove from intent mapping
            for intent in service.supported_intents:
                if intent in self.intent_map:
                    self.intent_map[intent] = [
                        s for s in self.intent_map[intent] if s != name
                    ]
            
            del self.services[name]
            logger.info(f"Unregistered service: {name}")
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get statistics about registered services"""
        total = len(self.services)
        enabled = sum(1 for s in self.services.values() if s.enabled)
        
        by_type = {}
        for service in self.services.values():
            type_name = service.type.value
            if type_name not in by_type:
                by_type[type_name] = 0
            by_type[type_name] += 1
        
        by_intent = {}
        for intent, services in self.intent_map.items():
            by_intent[intent] = len(services)
        
        return {
            "total_services": total,
            "enabled_services": enabled,
            "disabled_services": total - enabled,
            "by_type": by_type,
            "by_intent": by_intent,
            "services": [s.name for s in self.services.values()]
        }