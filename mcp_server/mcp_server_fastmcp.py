"""
FastMCP-based MCP Server implementation for Claude Desktop
This follows the recommended pattern from the MCP documentation
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
    print("Error: mcp package not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

from core.tools_base import RestApiTool, Property, RestApiParameters

logger = logging.getLogger(__name__)


class FastMCPRestApiServer:
    """
    FastMCP-based server for REST API tools generated from YAML
    """
    
    def __init__(self, yaml_file_path: str, server_name: str = "rest-api-tools"):
        self.yaml_file_path = yaml_file_path
        self.server_name = server_name
        self.yaml_data = None
        self.config = None
        
        # Initialize FastMCP server
        self.mcp = FastMCP(server_name)
        
    async def load_configuration(self):
        """Load YAML configuration"""
        try:
            with open(self.yaml_file_path, 'r', encoding='utf-8') as f:
                self.yaml_data = yaml.safe_load(f)
            
            # Extract API configuration
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
        """Register all tools from YAML data with FastMCP"""
        
        for tool_data in self.yaml_data.get('tools', []):
            self._register_single_tool(tool_data)
    
    def _register_single_tool(self, tool_data: Dict[str, Any]):
        """Register a single tool with FastMCP"""
        tool_name = tool_data['name']
        description = tool_data.get('description', '')
        method = tool_data.get('method', 'GET')
        path = tool_data.get('path', '')
        parameters = tool_data.get('parameters', {})
        
        # Create the tool function dynamically
        async def tool_function(**kwargs) -> str:
            """Dynamically generated tool function"""
            return await self._execute_tool(tool_data, kwargs)
        
        # Set the docstring
        tool_function.__doc__ = description
        
        # Add type annotations for parameters
        tool_function.__annotations__ = self._create_annotations(parameters)
        
        # Register the tool with FastMCP
        self.mcp.tool(name=tool_name)(tool_function)
        
        logger.info(f"Registered tool: {tool_name} ({method} {path})")
    
    def _create_annotations(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Create type annotations for the tool function"""
        annotations = {'return': str}
        
        properties = parameters.get('properties', {})
        required = parameters.get('required', [])
        
        for param_name, param_info in properties.items():
            if param_name not in ['client_key', 'entity_key', 'user_key']:
                param_type = param_info.get('type', 'string')
                
                # Map parameter types to Python types
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
                
                # Make optional if not required
                if param_name not in required:
                    python_type = Optional[python_type]
                
                annotations[param_name] = python_type
        
        return annotations
    
    async def _execute_tool(self, tool_data: Dict[str, Any], arguments: Dict[str, Any]) -> str:
        """Execute a tool with given arguments"""
        method = tool_data.get('method', 'GET')
        path = tool_data.get('path', '')
        
        # Build the full URL
        base_url = self.config['base_url'].rstrip('/')
        url = f"{base_url}{path}"
        
        # Prepare request data
        request_data = {
            'client_key': arguments.get('client_key'),
            'entity_key': arguments.get('entity_key'),
            'user_key': arguments.get('user_key'),
        }
        
        # Add other parameters
        for key, value in arguments.items():
            if key not in ['client_key', 'entity_key', 'user_key'] and value is not None:
                request_data[key] = value
        
        # Remove None values
        request_data = {k: v for k, v in request_data.items() if v is not None}
        
        try:
            async with httpx.AsyncClient() as client:
                # Make request based on method
                if method.upper() in ['POST', 'PUT', 'PATCH']:
                    response = await client.request(
                        method.upper(), 
                        url, 
                        json=request_data,
                        timeout=30.0
                    )
                else:
                    response = await client.request(
                        method.upper(), 
                        url, 
                        params=request_data,
                        timeout=30.0
                    )
                
                response.raise_for_status()
                
                # Try to parse as JSON, fallback to text
                try:
                    result = response.json()
                except:
                    result = response.text
                
                # Format as JSON-RPC response
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
            # Format error as JSON-RPC response
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


async def create_and_run_server(yaml_file_path: str, server_name: str = "rest-api-tools"):
    """
    Create and run FastMCP server for Claude Desktop
    """
    # Create server instance
    server = FastMCPRestApiServer(yaml_file_path, server_name)
    
    # Load configuration
    await server.load_configuration()
    
    # Register tools
    server.register_tools()
    
    # Run the server with stdio transport
    server.mcp.run(transport='stdio')


def main():
    """Main entry point for MCP server"""
    if len(sys.argv) < 2:
        print("Usage: python mcp_server_fastmcp.py <yaml_file_path> [server_name]", file=sys.stderr)
        sys.exit(1)
    
    yaml_file_path = sys.argv[1]
    server_name = sys.argv[2] if len(sys.argv) > 2 else "rest-api-tools"
    
    if not Path(yaml_file_path).exists():
        print(f"Error: YAML file not found: {yaml_file_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Run the server
        asyncio.run(create_and_run_server(yaml_file_path, server_name))
        
    except KeyboardInterrupt:
        print("Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"Error starting MCP server: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
