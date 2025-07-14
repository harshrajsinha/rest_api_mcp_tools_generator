"""
MCP Server implementation for serving generated tools
"""
import yaml
import json
import importlib.util
import sys
import asyncio
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

from core.tools_base import RestApiTool, get_rest_api_tools

logger = logging.getLogger(__name__)


class MCPServer:
    """
    MCP Server that serves dynamically generated REST API tools
    """
    
    def __init__(self, yaml_file_path: str, tools_file_path: Optional[str] = None):
        self.yaml_file_path = yaml_file_path
        self.tools_file_path = tools_file_path
        self.yaml_data = None
        self.tools = {}
        self.config = None
        
    def load_yaml_configuration(self) -> Dict[str, Any]:
        """
        Load YAML configuration file
        """
        try:
            with open(self.yaml_file_path, 'r', encoding='utf-8') as f:
                self.yaml_data = yaml.safe_load(f)
            
            # Extract API configuration
            api_info = self.yaml_data.get('api_info', {})
            self.config = MCPServerConfig(
                base_url=api_info.get('base_url', ''),
                auth_type=api_info.get('auth_type', 'none'),
                auth_config=api_info.get('auth_config', {}),
                name=api_info.get('name', 'Generated API Tools')
            )
            
            return self.yaml_data
        
        except Exception as e:
            logger.error(f"Failed to load YAML configuration: {str(e)}")
            raise
    
    def load_dynamic_tools(self) -> Dict[str, RestApiTool]:
        """
        Load dynamically generated tool classes
        """
        if not self.tools_file_path:
            # Generate tools from YAML if no tools file provided
            return self._generate_tools_from_yaml()
        
        try:
            # Load the Python module containing the tool classes
            spec = importlib.util.spec_from_file_location("generated_tools", self.tools_file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["generated_tools"] = module
            spec.loader.exec_module(module)
            
            # Extract tool classes from the module
            tools = {}
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, RestApiTool) and 
                    attr is not RestApiTool):
                    
                    # Instantiate the tool with configuration
                    tool_instance = attr(config=self.config)
                    tools[attr_name] = tool_instance
            
            self.tools = tools
            return tools
        
        except Exception as e:
            logger.error(f"Failed to load dynamic tools: {str(e)}")
            raise
    
    def _generate_tools_from_yaml(self) -> Dict[str, RestApiTool]:
        """
        Generate tool instances directly from YAML data
        """
        if not self.yaml_data:
            self.load_yaml_configuration()
        
        tools = {}
        
        for tool_data in self.yaml_data.get('tools', []):
            tool_class = self._create_dynamic_tool_class(tool_data)
            tool_instance = tool_class(config=self.config)
            tools[tool_data['name']] = tool_instance
        
        self.tools = tools
        return tools
    
    def _create_dynamic_tool_class(self, tool_data: Dict[str, Any]) -> type:
        """
        Create a dynamic tool class from YAML tool data
        """
        class_name = tool_data['name']
        description = tool_data.get('description', '')
        method = tool_data.get('method', 'GET')
        path = tool_data.get('path', '')
        parameters = tool_data.get('parameters', {})
        
        # Create dynamic class
        def __init__(self, config=None, **kwargs):
            super(DynamicTool, self).__init__(config=config, **kwargs)
            self.api_path = path
            self.method = method
            self.tool_description = description
        
        def get_parameters(self):
            from core.tools_base import RestApiParameters, Property
            
            properties = parameters.get('properties', {})
            required = parameters.get('required', [])
            
            if not properties:
                return RestApiParameters()
            
            extra_properties = {}
            extra_required = []
            
            for prop_name, prop_info in properties.items():
                if prop_name not in ['client_key', 'entity_key', 'user_key']:
                    extra_properties[prop_name] = Property(
                        type=prop_info.get('type', 'string'),
                        description=prop_info.get('description', '')
                    )
                    if prop_name in required:
                        extra_required.append(prop_name)
            
            return RestApiParameters(extra_properties, extra_required)
        
        async def invoke(self, **kwargs):
            import requests
            
            url = self.get_api_url(self.api_path)
            data = {
                "client_key": self.client_key,
                "entity_key": self.entity_key,
                "user_key": self.user_key,
            }
            
            # Add other parameters
            for key, value in kwargs.items():
                if key not in ['id'] and value is not None:
                    data[key] = value
            
            # Make request based on method
            if method.upper() in ['POST', 'PUT', 'PATCH']:
                res = requests.request(method.lower(), url, data=data)
            else:
                res = requests.request(method.lower(), url, params=data)
            
            response = res.json()
            return self.to_jsonrpc(response, id=kwargs.get('id'))
        
        # Set docstring for invoke method
        invoke.__doc__ = description
        
        # Create the dynamic class
        DynamicTool = type(class_name, (RestApiTool,), {
            '__init__': __init__,
            'get_parameters': get_parameters,
            'invoke': invoke,
        })
        
        return DynamicTool
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools with their metadata
        """
        if not self.tools:
            self.load_dynamic_tools()
        
        tools_list = []
        for tool_name, tool_instance in self.tools.items():
            tool_info = {
                'name': tool_name,
                'description': getattr(tool_instance, 'tool_description', tool_instance.invoke.__doc__ or ''),
                'parameters': tool_instance.get_parameters().__dict__,
                'method': getattr(tool_instance, 'method', 'GET'),
                'path': getattr(tool_instance, 'api_path', ''),
            }
            tools_list.append(tool_info)
        
        return tools_list
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a specific tool with given parameters
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        tool_instance = self.tools[tool_name]
        
        try:
            result = await tool_instance.invoke(**parameters)
            return result
        
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {str(e)}")
            return {
                'jsonrpc': '2.0',
                'error': {
                    'code': 500,
                    'message': f"Tool execution failed: {str(e)}",
                    'data': {}
                },
                'id': parameters.get('id', -1)
            }
    
    def start_server(self, host: str = 'localhost', port: int = 8080):
        """
        Start the MCP server
        """
        # This would be implemented with a proper MCP server framework
        # For now, this is a placeholder that shows the structure
        logger.info(f"Starting MCP server on {host}:{port}")
        logger.info(f"Loaded {len(self.tools)} tools from {self.yaml_file_path}")
        
        # In a real implementation, this would start an HTTP/WebSocket server
        # that implements the MCP protocol
        pass


class MCPServerConfig:
    """
    Configuration class for MCP Server
    """
    
    def __init__(self, base_url: str, auth_type: str = 'none', 
                 auth_config: Dict[str, Any] = None, name: str = 'MCP Server'):
        self.base_url = base_url
        self.auth_type = auth_type
        self.auth_config = auth_config or {}
        self.name = name
        
        # These would be set based on authentication configuration
        self.client_key = None
        self.entity_key = None
        self.user_key = None


class MCPToolRegistry:
    """
    Registry for managing multiple MCP servers and their tools
    """
    
    def __init__(self):
        self.servers = {}
    
    def register_server(self, server_name: str, yaml_file_path: str, 
                       tools_file_path: Optional[str] = None) -> MCPServer:
        """
        Register a new MCP server
        """
        server = MCPServer(yaml_file_path, tools_file_path)
        server.load_yaml_configuration()
        server.load_dynamic_tools()
        
        self.servers[server_name] = server
        return server
    
    def get_server(self, server_name: str) -> Optional[MCPServer]:
        """
        Get a registered MCP server
        """
        return self.servers.get(server_name)
    
    def list_servers(self) -> List[str]:
        """
        List all registered server names
        """
        return list(self.servers.keys())
    
    def get_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all tools from all registered servers
        """
        all_tools = {}
        
        for server_name, server in self.servers.items():
            all_tools[server_name] = server.get_available_tools()
        
        return all_tools
