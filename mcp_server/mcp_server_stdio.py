"""
MCP Server implementation that follows the proper MCP protocol for Claude Desktop
"""
import asyncio
import json
import sys
from typing import Any, Dict, List, Optional, Sequence
import yaml
import importlib.util
import logging
from pathlib import Path

# MCP protocol implementation
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
import mcp.server.stdio
import mcp.types

from core.tools_base import RestApiTool

logger = logging.getLogger(__name__)


class MCPRestApiServer:
    """
    MCP Server that serves dynamically generated REST API tools following MCP protocol
    """
    
    def __init__(self, yaml_file_path: str, server_name: str = "rest-api-tools"):
        self.yaml_file_path = yaml_file_path
        self.server_name = server_name
        self.yaml_data = None
        self.tools_instances = {}
        self.config = None
        
        # Initialize MCP server
        self.server = Server(server_name)
        
    async def load_configuration(self):
        """Load YAML configuration and create tool instances"""
        try:
            with open(self.yaml_file_path, 'r', encoding='utf-8') as f:
                self.yaml_data = yaml.safe_load(f)
            
            # Extract API configuration
            api_info = self.yaml_data.get('api_info', {})
            self.config = MCPConfig(
                base_url=api_info.get('base_url', ''),
                auth_type=api_info.get('auth_type', 'none'),
                auth_config=api_info.get('auth_config', {}),
                name=api_info.get('name', 'Generated API Tools')
            )
            
            # Create tool instances from YAML
            await self._create_tool_instances()
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            raise
    
    async def _create_tool_instances(self):
        """Create tool instances from YAML data"""
        self.tools_instances = {}
        
        for tool_data in self.yaml_data.get('tools', []):
            tool_instance = self._create_dynamic_tool_instance(tool_data)
            self.tools_instances[tool_data['name']] = {
                'instance': tool_instance,
                'metadata': tool_data
            }
    
    def _create_dynamic_tool_instance(self, tool_data: Dict[str, Any]) -> RestApiTool:
        """Create a dynamic tool instance from YAML tool data"""
        class_name = tool_data['name']
        description = tool_data.get('description', '')
        method = tool_data.get('method', 'GET')
        path = tool_data.get('path', '')
        parameters = tool_data.get('parameters', {})
        
        # Create dynamic class
        class DynamicTool(RestApiTool):
            def __init__(self, config=None, **kwargs):
                super().__init__(config=config, **kwargs)
                self.api_path = path
                self.method = method
                self.tool_description = description
                self.tool_parameters = parameters
            
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
                    "client_key": getattr(self, 'client_key', None),
                    "entity_key": getattr(self, 'entity_key', None),
                    "user_key": getattr(self, 'user_key', None),
                }
                
                # Add other parameters
                for key, value in kwargs.items():
                    if key not in ['id'] and value is not None:
                        data[key] = value
                
                # Make request based on method
                try:
                    if method.upper() in ['POST', 'PUT', 'PATCH']:
                        res = requests.request(method.lower(), url, json=data, timeout=30)
                    else:
                        res = requests.request(method.lower(), url, params=data, timeout=30)
                    
                    response = res.json() if res.content else {}
                    return self.to_jsonrpc(response, id=kwargs.get('id'))
                    
                except Exception as e:
                    return {
                        'jsonrpc': '2.0',
                        'error': {
                            'code': 500,
                            'message': f"Request failed: {str(e)}",
                            'data': {}
                        },
                        'id': kwargs.get('id', -1)
                    }
        
        # Set the class name dynamically
        DynamicTool.__name__ = class_name
        DynamicTool.__qualname__ = class_name
        
        # Create and return instance
        return DynamicTool(config=self.config)
    
    def setup_handlers(self):
        """Setup MCP protocol handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools"""
            tools = []
            
            for tool_name, tool_info in self.tools_instances.items():
                tool_instance = tool_info['instance']
                tool_metadata = tool_info['metadata']
                
                # Get parameters from the tool instance
                params = tool_instance.get_parameters()
                
                # Convert to MCP Tool format
                mcp_tool = Tool(
                    name=tool_name,
                    description=tool_metadata.get('description', ''),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            name: {
                                "type": prop.type,
                                "description": prop.description
                            }
                            for name, prop in params.properties.items()
                        },
                        "required": params.required or []
                    }
                )
                tools.append(mcp_tool)
            
            return tools
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent]:
            """Call a tool with given arguments"""
            if name not in self.tools_instances:
                raise ValueError(f"Tool '{name}' not found")
            
            tool_instance = self.tools_instances[name]['instance']
            
            try:
                # Execute the tool
                result = await tool_instance.invoke(**arguments)
                
                # Return result as TextContent
                result_text = json.dumps(result, indent=2)
                return [TextContent(type="text", text=result_text)]
                
            except Exception as e:
                error_result = {
                    'jsonrpc': '2.0',
                    'error': {
                        'code': 500,
                        'message': f"Tool execution failed: {str(e)}",
                        'data': {}
                    },
                    'id': -1
                }
                return [TextContent(type="text", text=json.dumps(error_result, indent=2))]


class MCPConfig:
    """Configuration class for MCP Server"""
    
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


async def create_mcp_server(yaml_file_path: str, server_name: str = "rest-api-tools"):
    """
    Create and configure MCP server for Claude Desktop
    """
    # Create server instance
    mcp_server = MCPRestApiServer(yaml_file_path, server_name)
    
    # Load configuration
    await mcp_server.load_configuration()
    
    # Setup handlers
    mcp_server.setup_handlers()
    
    return mcp_server.server


async def main():
    """Main entry point for MCP server"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python mcp_server_stdio.py <yaml_file_path> [server_name]", file=sys.stderr)
        sys.exit(1)
    
    yaml_file_path = sys.argv[1]
    server_name = sys.argv[2] if len(sys.argv) > 2 else "rest-api-tools"
    
    if not Path(yaml_file_path).exists():
        print(f"Error: YAML file not found: {yaml_file_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Create MCP server
        server = await create_mcp_server(yaml_file_path, server_name)
        
        # Run with stdio transport for Claude Desktop
        async with stdio_server() as streams:
            await server.run(
                streams[0], streams[1],
                {
                    "name": server_name,
                    "version": "1.0.0"
                }
            )
            
    except Exception as e:
        print(f"Error starting MCP server: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
