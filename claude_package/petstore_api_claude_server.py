#!/usr/bin/env python3
"""
Standalone MCP Server for petstore_api_claude
Generated from REST API YAML specification

This server follows the Model Context Protocol (MCP) specification
and can be used with Claude Desktop and other MCP clients.
"""

import asyncio
import json
import sys
import yaml
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

# Import FastMCP for easier MCP server development
try:
    from mcp.server.fastmcp import FastMCP
    import httpx
except ImportError:
    print("Error: mcp package not installed. Run: pip install mcp httpx pyyaml", file=sys.stderr)
    sys.exit(1)

logger = logging.getLogger(__name__)

# YAML file path (relative to this script)
YAML_FILE_PATH = r"C:\Users\HR\OneDrive\GitHub Projects\MCP Servers\rest_api_mcp_tools_generator\claude_package\petstore_api_claude.yaml"
SERVER_NAME = "petstore_api_claude"


class RestApiMCPServer:
    """MCP Server for REST API tools"""
    
    def __init__(self, yaml_file_path: str, server_name: str):
        self.yaml_file_path = yaml_file_path
        self.server_name = server_name
        self.yaml_data = None
        self.config = None
        self.mcp = FastMCP(server_name)
        
    async def load_configuration(self):
        """Load YAML configuration"""
        try:
            with open(self.yaml_file_path, 'r', encoding='utf-8') as f:
                self.yaml_data = yaml.safe_load(f)
            
            api_info = self.yaml_data.get('api_info', {})
            self.config = {
                'base_url': api_info.get('base_url', ''),
                'auth_type': api_info.get('auth_type', 'none'),
                'auth_config': api_info.get('auth_config', {}),
                'name': api_info.get('name', 'Generated API Tools')
            }
            
            logger.info(f"Loaded configuration for {self.config['name']}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            raise
    
    def register_tools(self):
        """Register all tools from YAML data"""
        for tool_data in self.yaml_data.get('tools', []):
            self._register_single_tool(tool_data)
    
    def _register_single_tool(self, tool_data: Dict[str, Any]):
        """Register a single tool"""
        tool_name = tool_data['name']
        description = tool_data.get('description', '')
        method = tool_data.get('method', 'GET')
        path = tool_data.get('path', '')
        parameters = tool_data.get('parameters', {})
        
        async def tool_function(**kwargs) -> str:
            """Tool execution function"""
            return await self._execute_tool(tool_data, kwargs)
        
        tool_function.__doc__ = description
        tool_function.__annotations__ = self._create_annotations(parameters)
        
        self.mcp.tool(name=tool_name)(tool_function)
        logger.info(f"Registered tool: {tool_name} ({method} {path})")
    
    def _create_annotations(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Create type annotations"""
        annotations = {'return': str}
        
        properties = parameters.get('properties', {})
        required = parameters.get('required', [])
        
        for param_name, param_info in properties.items():
            if param_name not in ['client_key', 'entity_key', 'user_key']:
                param_type = param_info.get('type', 'string')
                
                if param_type == 'string':
                    python_type = str
                elif param_type == 'integer':
                    python_type = int
                elif param_type == 'number':
                    python_type = float
                elif param_type == 'boolean':
                    python_type = bool
                elif param_type == 'array':
                    python_type = List[str]
                else:
                    python_type = str
                
                if param_name not in required:
                    python_type = Optional[python_type]
                
                annotations[param_name] = python_type
        
        return annotations
    
    async def _execute_tool(self, tool_data: Dict[str, Any], arguments: Dict[str, Any]) -> str:
        """Execute a tool"""
        method = tool_data.get('method', 'GET')
        path = tool_data.get('path', '')
        
        base_url = self.config['base_url'].rstrip('/')
        url = f"{base_url}{path}"
        
        request_data = {
            'client_key': arguments.get('client_key'),
            'entity_key': arguments.get('entity_key'),
            'user_key': arguments.get('user_key'),
        }
        
        for key, value in arguments.items():
            if key not in ['client_key', 'entity_key', 'user_key'] and value is not None:
                request_data[key] = value
        
        request_data = {k: v for k, v in request_data.items() if v is not None}
        
        try:
            async with httpx.AsyncClient() as client:
                if method.upper() in ['POST', 'PUT', 'PATCH']:
                    response = await client.request(
                        method.upper(), url, json=request_data, timeout=30.0
                    )
                else:
                    response = await client.request(
                        method.upper(), url, params=request_data, timeout=30.0
                    )
                
                response.raise_for_status()
                
                try:
                    result = response.json()
                except:
                    result = response.text
                
                json_rpc_result = {
                    'jsonrpc': '2.0',
                    'result': {
                        'status': response.status_code,
                        'data': result,
                        'message': 'Request successful'
                    },
                    'id': 1
                }
                
                return json.dumps(json_rpc_result, indent=2)
                
        except Exception as e:
            error_result = {
                'jsonrpc': '2.0',
                'error': {
                    'code': 500,
                    'message': f"Request failed: {str(e)}",
                    'data': {
                        'url': url,
                        'method': method,
                        'parameters': request_data
                    }
                },
                'id': 1
            }
            
            return json.dumps(error_result, indent=2)


def main():
    """Main entry point"""
    # Resolve YAML file path relative to this script
    script_dir = Path(__file__).parent
    yaml_path = script_dir / Path(YAML_FILE_PATH).name
    
    if not yaml_path.exists():
        print(f"Error: YAML file not found: {yaml_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        server = RestApiMCPServer(str(yaml_path), SERVER_NAME)
        # Load configuration synchronously
        import asyncio
        asyncio.get_event_loop().run_until_complete(server.load_configuration())
        server.register_tools()
        # Run the server
        server.mcp.run(transport='stdio')
        
    except KeyboardInterrupt:
        print("Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"Error starting MCP server: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
