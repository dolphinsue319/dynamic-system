"""MCP service connectors for different connection types"""

import asyncio
import json
import logging
import subprocess
from typing import Any, Dict, Optional, List
from abc import ABC, abstractmethod

import aiohttp

from .service_registry import MCPService, ServiceType

logger = logging.getLogger(__name__)


class MCPConnectorBase(ABC):
    """Base class for MCP connectors"""
    
    @abstractmethod
    async def connect(self, service: MCPService) -> bool:
        """Connect to the MCP service"""
        pass
    
    @abstractmethod
    async def call_tool(self, tool: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the MCP service"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the MCP service"""
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected to the service"""
        pass


class StdioMCPConnector(MCPConnectorBase):
    """Connector for stdio-based MCP services"""
    
    def __init__(self):
        self.process: Optional[asyncio.subprocess.Process] = None
        self.service: Optional[MCPService] = None
    
    async def connect(self, service: MCPService) -> bool:
        """Connect to stdio MCP service"""
        try:
            if not service.command:
                logger.error(f"No command specified for service {service.name}")
                return False
            
            # Build command with args
            cmd = service.command.copy()
            if service.args:
                cmd.extend(service.args)
            
            # Set environment variables
            env = None
            if service.env:
                import os
                env = os.environ.copy()
                env.update(service.env)
            
            # Start the process
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            self.service = service
            
            # Send initialization
            await self._send_message({
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": "dynamic-orchestrator",
                        "version": "0.1.0"
                    }
                },
                "id": 1
            })
            
            # Read initialization response
            response = await self._read_message()
            
            if response and "result" in response:
                logger.info(f"Connected to stdio MCP service: {service.name}")
                return True
            else:
                logger.error(f"Failed to initialize service {service.name}: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to stdio service {service.name}: {e}")
            return False
    
    async def call_tool(self, tool: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the stdio MCP service"""
        if not self.process or not self.service:
            raise RuntimeError("Not connected to service")
        
        try:
            # Send tool call
            await self._send_message({
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool,
                    "arguments": arguments
                },
                "id": 2
            })
            
            # Read response
            response = await self._read_message()
            
            if response and "result" in response:
                return response["result"]
            elif response and "error" in response:
                raise RuntimeError(f"Tool call error: {response['error']}")
            else:
                raise RuntimeError(f"Invalid response: {response}")
                
        except Exception as e:
            logger.error(f"Failed to call tool {tool}: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from the stdio MCP service"""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
            
            self.process = None
            self.service = None
            logger.info("Disconnected from stdio MCP service")
    
    async def is_connected(self) -> bool:
        """Check if connected to the service"""
        return self.process is not None and self.process.returncode is None
    
    async def _send_message(self, message: Dict[str, Any]):
        """Send a JSON-RPC message to the process"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not connected")
        
        data = json.dumps(message) + "\n"
        self.process.stdin.write(data.encode())
        await self.process.stdin.drain()
    
    async def _read_message(self) -> Optional[Dict[str, Any]]:
        """Read a JSON-RPC message from the process"""
        if not self.process or not self.process.stdout:
            raise RuntimeError("Process not connected")
        
        try:
            line = await asyncio.wait_for(
                self.process.stdout.readline(),
                timeout=10.0
            )
            
            if line:
                return json.loads(line.decode())
            
            return None
            
        except asyncio.TimeoutError:
            logger.error("Timeout reading from process")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")
            return None


class HttpMCPConnector(MCPConnectorBase):
    """Connector for HTTP-based MCP services"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.service: Optional[MCPService] = None
        self.base_url: Optional[str] = None
    
    async def connect(self, service: MCPService) -> bool:
        """Connect to HTTP MCP service"""
        try:
            if not service.url:
                logger.error(f"No URL specified for service {service.name}")
                return False
            
            self.base_url = service.url.rstrip("/")
            self.service = service
            
            # Create HTTP session
            headers = {}
            if service.env and "API_KEY" in service.env:
                headers["Authorization"] = f"Bearer {service.env['API_KEY']}"
            
            self.session = aiohttp.ClientSession(headers=headers)
            
            # Test connection
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    logger.info(f"Connected to HTTP MCP service: {service.name}")
                    return True
                else:
                    logger.error(f"Health check failed for {service.name}: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to connect to HTTP service {service.name}: {e}")
            return False
    
    async def call_tool(self, tool: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the HTTP MCP service"""
        if not self.session or not self.service:
            raise RuntimeError("Not connected to service")
        
        try:
            url = f"{self.base_url}/tools/{tool}"
            
            async with self.session.post(url, json=arguments) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error = await response.text()
                    raise RuntimeError(f"Tool call failed: {error}")
                    
        except Exception as e:
            logger.error(f"Failed to call tool {tool}: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from the HTTP MCP service"""
        if self.session:
            await self.session.close()
            self.session = None
            self.service = None
            logger.info("Disconnected from HTTP MCP service")
    
    async def is_connected(self) -> bool:
        """Check if connected to the service"""
        if not self.session:
            return False
        
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                return response.status == 200
        except:
            return False


class MCPConnector:
    """Main connector that manages multiple connection types"""
    
    def __init__(self):
        self.connectors: Dict[str, MCPConnectorBase] = {}
    
    async def connect(self, service: MCPService) -> MCPConnectorBase:
        """
        Connect to an MCP service
        
        Args:
            service: MCPService to connect to
            
        Returns:
            Connected MCPConnectorBase instance
        """
        # Check if already connected
        if service.name in self.connectors:
            connector = self.connectors[service.name]
            if await connector.is_connected():
                return connector
        
        # Create appropriate connector
        if service.type == ServiceType.STDIO:
            connector = StdioMCPConnector()
        elif service.type == ServiceType.HTTP:
            connector = HttpMCPConnector()
        else:
            raise ValueError(f"Unsupported service type: {service.type}")
        
        # Connect
        success = await connector.connect(service)
        if success:
            self.connectors[service.name] = connector
            return connector
        else:
            raise RuntimeError(f"Failed to connect to service {service.name}")
    
    async def disconnect(self, service_name: str):
        """Disconnect from a service"""
        if service_name in self.connectors:
            await self.connectors[service_name].disconnect()
            del self.connectors[service_name]
    
    async def disconnect_all(self):
        """Disconnect from all services"""
        for connector in self.connectors.values():
            await connector.disconnect()
        self.connectors.clear()
    
    async def call_tool(
        self,
        service_name: str,
        tool: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        Call a tool on a service
        
        Args:
            service_name: Name of the service
            tool: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool result
        """
        if service_name not in self.connectors:
            raise RuntimeError(f"Not connected to service {service_name}")
        
        return await self.connectors[service_name].call_tool(tool, arguments)