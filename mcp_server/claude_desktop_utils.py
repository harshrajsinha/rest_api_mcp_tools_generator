"""
Utilities for generating Claude Desktop configuration files
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, List


def generate_claude_desktop_config(
    mcp_servers: List[Dict[str, Any]], 
    config_file_path: str = None
) -> str:
    """
    Generate Claude Desktop configuration file for MCP servers
    
    Args:
        mcp_servers: List of MCP server configurations
        config_file_path: Optional path to save the config file
    
    Returns:
        JSON configuration string
    """
    
    config = {
        "mcpServers": {}
    }
    
    for server in mcp_servers:
        server_name = server['name']
        yaml_file_path = server['yaml_file_path']
        python_executable = server.get('python_executable', 'python')
        server_script = server.get('server_script', 'mcp_server_fastmcp.py')
        
        config["mcpServers"][server_name] = {
            "command": python_executable,
            "args": [
                server_script,
                yaml_file_path,
                server_name
            ]
        }
    
    config_json = json.dumps(config, indent=2)
    
    # Save to file if path provided
    if config_file_path:
        with open(config_file_path, 'w', encoding='utf-8') as f:
            f.write(config_json)
    
    return config_json


def get_claude_desktop_config_path() -> str:
    """
    Get the default Claude Desktop configuration file path
    """
    if os.name == 'nt':  # Windows
        app_data = os.environ.get('APPDATA', '')
        return os.path.join(app_data, 'Claude', 'claude_desktop_config.json')
    else:  # macOS/Linux
        home = os.path.expanduser('~')
        return os.path.join(home, 'Library', 'Application Support', 'Claude', 'claude_desktop_config.json')


def create_mcp_server_package(
    yaml_file_path: str,
    server_name: str,
    output_dir: str,
    include_config: bool = True
) -> Dict[str, str]:
    """
    Create a complete MCP server package for Claude Desktop
    
    Args:
        yaml_file_path: Path to the YAML file
        server_name: Name of the MCP server
        output_dir: Directory to create the package
        include_config: Whether to include Claude Desktop config
    
    Returns:
        Dictionary with created file paths
    """
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    created_files = {}
    
    # Copy YAML file to package
    yaml_dest = output_path / f"{server_name}.yaml"
    import shutil
    shutil.copy2(yaml_file_path, yaml_dest)
    created_files['yaml_file'] = str(yaml_dest)
    
    # Create server script
    server_script_path = output_path / f"{server_name}_server.py"
    server_script_content = generate_standalone_server_script(
        str(yaml_dest),
        server_name
    )
    
    with open(server_script_path, 'w', encoding='utf-8') as f:
        f.write(server_script_content)
    created_files['server_script'] = str(server_script_path)
    
    # Create requirements.txt
    requirements_path = output_path / "requirements.txt"
    requirements_content = """mcp>=1.2.0
httpx
pyyaml
requests
"""
    
    with open(requirements_path, 'w', encoding='utf-8') as f:
        f.write(requirements_content)
    created_files['requirements'] = str(requirements_path)
    
    # Create setup script
    setup_script_path = output_path / "setup.py"
    setup_content = f"""#!/usr/bin/env python3
\"\"\"
Setup script for {server_name} MCP Server
\"\"\"

import subprocess
import sys
import os

def install_dependencies():
    \"\"\"Install required dependencies\"\"\"
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def main():
    print(f"Setting up {server_name} MCP Server...")
    
    # Install dependencies
    install_dependencies()
    
    print("Setup complete!")
    print(f"To run the server: python {server_name}_server.py")
    print("Configure Claude Desktop with the generated configuration.")

if __name__ == "__main__":
    main()
"""
    
    with open(setup_script_path, 'w', encoding='utf-8') as f:
        f.write(setup_content)
    created_files['setup_script'] = str(setup_script_path)
    
    # Create Claude Desktop configuration if requested
    if include_config:
        config_data = [{
            'name': server_name,
            'yaml_file_path': str(yaml_dest),
            'server_script': str(server_script_path)
        }]
        
        config_path = output_path / "claude_desktop_config.json"
        config_content = generate_claude_desktop_config(config_data)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
        created_files['claude_config'] = str(config_path)
    
    # Create README
    readme_path = output_path / "README.md"
    readme_content = generate_readme_content(server_name, created_files)
    
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    created_files['readme'] = str(readme_path)
    
    return created_files


def generate_standalone_server_script(yaml_file_path: str, server_name: str) -> str:
    """
    Generate a standalone MCP server script
    """
    
    return f"""#!/usr/bin/env python3
\"\"\"
Standalone MCP Server for {server_name}
Generated from REST API YAML specification

This server follows the Model Context Protocol (MCP) specification
and can be used with Claude Desktop and other MCP clients.
\"\"\"

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
YAML_FILE_PATH = r"{yaml_file_path}"
SERVER_NAME = "{server_name}"


class RestApiMCPServer:
    \"\"\"MCP Server for REST API tools\"\"\"
    
    def __init__(self, yaml_file_path: str, server_name: str):
        self.yaml_file_path = yaml_file_path
        self.server_name = server_name
        self.yaml_data = None
        self.config = None
        self.mcp = FastMCP(server_name)
        
    async def load_configuration(self):
        \"\"\"Load YAML configuration\"\"\"
        try:
            with open(self.yaml_file_path, 'r', encoding='utf-8') as f:
                self.yaml_data = yaml.safe_load(f)
            
            api_info = self.yaml_data.get('api_info', {{}})
            self.config = {{
                'base_url': api_info.get('base_url', ''),
                'auth_type': api_info.get('auth_type', 'none'),
                'auth_config': api_info.get('auth_config', {{}}),
                'name': api_info.get('name', 'Generated API Tools')
            }}
            
            logger.info(f"Loaded configuration for {{self.config['name']}}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {{str(e)}}")
            raise
    
    def register_tools(self):
        \"\"\"Register all tools from YAML data\"\"\"
        for tool_data in self.yaml_data.get('tools', []):
            self._register_single_tool(tool_data)
    
    def _register_single_tool(self, tool_data: Dict[str, Any]):
        \"\"\"Register a single tool\"\"\"
        tool_name = tool_data['name']
        description = tool_data.get('description', '')
        method = tool_data.get('method', 'GET')
        path = tool_data.get('path', '')
        parameters = tool_data.get('parameters', {{}})
        
        async def tool_function(**kwargs) -> str:
            \"\"\"Tool execution function\"\"\"
            return await self._execute_tool(tool_data, kwargs)
        
        tool_function.__doc__ = description
        tool_function.__annotations__ = self._create_annotations(parameters)
        
        self.mcp.tool(name=tool_name)(tool_function)
        logger.info(f"Registered tool: {{tool_name}} ({{method}} {{path}})")
    
    def _create_annotations(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"Create type annotations\"\"\"
        annotations = {{'return': str}}
        
        properties = parameters.get('properties', {{}})
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
        \"\"\"Execute a tool\"\"\"
        method = tool_data.get('method', 'GET')
        path = tool_data.get('path', '')
        
        base_url = self.config['base_url'].rstrip('/')
        url = f"{{base_url}}{{path}}"
        
        request_data = {{
            'client_key': arguments.get('client_key'),
            'entity_key': arguments.get('entity_key'),
            'user_key': arguments.get('user_key'),
        }}
        
        for key, value in arguments.items():
            if key not in ['client_key', 'entity_key', 'user_key'] and value is not None:
                request_data[key] = value
        
        request_data = {{k: v for k, v in request_data.items() if v is not None}}
        
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
                
                json_rpc_result = {{
                    'jsonrpc': '2.0',
                    'result': {{
                        'status': response.status_code,
                        'data': result,
                        'message': 'Request successful'
                    }},
                    'id': 1
                }}
                
                return json.dumps(json_rpc_result, indent=2)
                
        except Exception as e:
            error_result = {{
                'jsonrpc': '2.0',
                'error': {{
                    'code': 500,
                    'message': f"Request failed: {{str(e)}}",
                    'data': {{
                        'url': url,
                        'method': method,
                        'parameters': request_data
                    }}
                }},
                'id': 1
            }}
            
            return json.dumps(error_result, indent=2)


async def main():
    \"\"\"Main entry point\"\"\"
    # Resolve YAML file path relative to this script
    script_dir = Path(__file__).parent
    yaml_path = script_dir / Path(YAML_FILE_PATH).name
    
    if not yaml_path.exists():
        print(f"Error: YAML file not found: {{yaml_path}}", file=sys.stderr)
        sys.exit(1)
    
    try:
        server = RestApiMCPServer(str(yaml_path), SERVER_NAME)
        await server.load_configuration()
        server.register_tools()
        server.mcp.run(transport='stdio')
        
    except KeyboardInterrupt:
        print("Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"Error starting MCP server: {{str(e)}}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
"""


def generate_readme_content(server_name: str, created_files: Dict[str, str]) -> str:
    """Generate README content for the MCP server package"""
    
    return f"""# {server_name} MCP Server

This is a Model Context Protocol (MCP) server generated from REST API specifications.
It can be used with Claude Desktop and other MCP-compatible clients.

## Files Generated

- `{server_name}.yaml` - REST API tool definitions
- `{server_name}_server.py` - MCP server implementation
- `requirements.txt` - Python dependencies
- `setup.py` - Setup script
- `claude_desktop_config.json` - Claude Desktop configuration
- `README.md` - This file

## Installation

1. **Install dependencies:**
   ```bash
   python setup.py
   # OR manually:
   pip install -r requirements.txt
   ```

2. **Test the server:**
   ```bash
   python {server_name}_server.py
   ```

## Claude Desktop Configuration

To use this server with Claude Desktop:

1. **Locate your Claude Desktop config file:**
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\\Claude\\claude_desktop_config.json`

2. **Add the server configuration:**
   ```json
   {{
     "mcpServers": {{
       "{server_name}": {{
         "command": "python",
         "args": [
           "/absolute/path/to/{server_name}_server.py"
         ]
       }}
     }}
   }}
   ```

   **Important:** Use the absolute path to the server script!

3. **Restart Claude Desktop**

## Verification

After configuration:

1. Open Claude Desktop
2. Look for the MCP tools indicator (🔧) in the interface
3. You should see the tools from your REST API available

## Troubleshooting

### Server not appearing in Claude Desktop

1. **Check the config file path** - Make sure you're editing the correct file
2. **Use absolute paths** - Relative paths may not work
3. **Check Python path** - You might need to use the full path to Python
4. **Restart Claude Desktop** after making changes
5. **Check server logs** - Run the server manually to see error messages

### Tools not working

1. **API connectivity** - Ensure the REST API is accessible
2. **Authentication** - Check if API keys or credentials are needed
3. **Parameters** - Verify required parameters are being passed

## Generated Tools

This server exposes the following tools:

{chr(10).join(f'- Tool: {tool_name}' for tool_name in ['[Tools will be listed here based on YAML]'])}

Each tool corresponds to a REST API endpoint and will execute HTTP requests
according to the specifications in the YAML file.

## Support

For issues with:
- **MCP protocol:** [MCP Documentation](https://modelcontextprotocol.io/)
- **Claude Desktop:** [Claude Desktop Support](https://support.anthropic.com/)
- **This server:** Check the generated YAML file and server implementation
"""
