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
nest_asyncio
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
        # Use placeholder paths that users need to update with absolute paths
        config_data = [{
            'name': server_name,
            'yaml_file_path': f"[UPDATE_PATH]/{server_name}.yaml",
            'server_script': f"[UPDATE_PATH]/{server_name}_server.py"
        }]
        
        config_path = output_path / "claude_desktop_config.json"
        config_content = generate_claude_desktop_config(config_data)
        
        # Add instructions as comments (JSON doesn't support comments, so add as a separate instruction file)
        instructions_content = f"""CLAUDE DESKTOP CONFIGURATION INSTRUCTIONS

1. Copy the contents of claude_desktop_config.json
2. Replace [UPDATE_PATH] with the absolute path to the extracted folder
3. Add the configuration to your Claude Desktop config file:
   - Windows: %APPDATA%\\Claude\\claude_desktop_config.json
   - macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
4. Restart Claude Desktop

Example (Windows):
Replace [UPDATE_PATH] with: C:\\path\\to\\extracted\\{server_name}_mcp_package

Example (macOS):
Replace [UPDATE_PATH] with: /Users/yourname/path/to/extracted/{server_name}_mcp_package
"""
        
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
        created_files['claude_config'] = str(config_path)
        
        # Create instructions file
        instructions_path = output_path / "CLAUDE_SETUP_INSTRUCTIONS.txt"
        with open(instructions_path, 'w', encoding='utf-8') as f:
            f.write(instructions_content)
        created_files['instructions'] = str(instructions_path)
    
    # Create README
    readme_path = output_path / "README.md"
    readme_content = generate_readme_content(server_name, created_files)
    
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    created_files['readme'] = str(readme_path)
    
    # Create detailed usage guide
    how_to_use_path = output_path / "HOW_TO_USE.md"
    how_to_use_content = generate_how_to_use_guide(server_name)
    
    with open(how_to_use_path, 'w', encoding='utf-8') as f:
        f.write(how_to_use_content)
    created_files['how_to_use'] = str(how_to_use_path)
    
    # Create API tools reference
    api_ref_path = output_path / "API_TOOLS_REFERENCE.md"
    api_ref_content = generate_api_tools_reference(yaml_file_path, server_name)
    
    with open(api_ref_path, 'w', encoding='utf-8') as f:
        f.write(api_ref_content)
    created_files['api_reference'] = str(api_ref_path)
    
    # Create verification script
    verify_script_path = output_path / "verify_setup.py"
    verify_script_content = generate_verification_script(server_name)
    
    with open(verify_script_path, 'w', encoding='utf-8') as f:
        f.write(verify_script_content)
    created_files['verify_script'] = str(verify_script_path)
    
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
    import nest_asyncio
    
    # Apply nest_asyncio immediately to prevent event loop conflicts
    try:
        nest_asyncio.apply()
        print("Applied nest_asyncio for event loop compatibility", file=sys.stderr)
        
        # Patch anyio to work with nest_asyncio
        import anyio
        original_run = anyio.run
        
        def patched_anyio_run(func, *args, **kwargs):
            \"\"\"Patched anyio.run that works with nest_asyncio\"\"\"
            try:
                loop = asyncio.get_running_loop()
                # If there's a running loop, use it
                return loop.run_until_complete(func(*args, **kwargs))
            except RuntimeError:
                # No running loop, use original anyio.run
                return original_run(func, *args, **kwargs)
        
        anyio.run = patched_anyio_run
        print("Patched anyio.run for event loop compatibility", file=sys.stderr)
        
    except Exception as e:
        print(f"Warning: Could not apply patches: {{str(e)}}", file=sys.stderr)
except ImportError:
    print("Error: Required packages not installed. Run: pip install mcp httpx pyyaml nest_asyncio", file=sys.stderr)
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
    
    def _create_input_schema(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"Create input schema for MCP tool\"\"\"
        properties = parameters.get('properties', {{}})
        required = parameters.get('required', [])
        
        schema_properties = {{}}
        
        for param_name, param_info in properties.items():
            if param_name not in ['client_key', 'entity_key', 'user_key']:
                schema_properties[param_name] = {{
                    'type': param_info.get('type', 'string'),
                    'description': param_info.get('description', '')
                }}
        
        return {{
            'type': 'object',
            'properties': schema_properties,
            'required': [r for r in required if r not in ['client_key', 'entity_key', 'user_key']]
        }}
    
    def _create_annotations(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"Create type annotations (legacy method)\"\"\"
        annotations = {{'return': str}}
        
        properties = parameters.get('properties', {{}})
        
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
        
        # Run the server with patched anyio
        print("Starting MCP server...", file=sys.stderr)
        server.mcp.run(transport='stdio')
        
    except KeyboardInterrupt:
        print("Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"Error starting MCP server: {{str(e)}}", file=sys.stderr)
        sys.exit(1)


def run_server():
    \"\"\"Run the MCP server with proper asyncio handling\"\"\"
    print("Initializing MCP server...", file=sys.stderr)
    
    try:
        # The anyio patch should handle event loop conflicts
        asyncio.run(main())
    except Exception as e:
        print(f"Server startup failed: {{str(e)}}", file=sys.stderr)
        print("Trying fallback method...", file=sys.stderr)
        
        # Fallback: create a new event loop
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(main())
        except Exception as e2:
            print(f"All methods failed: {{str(e2)}}", file=sys.stderr)
            sys.exit(1)
        finally:
            if 'loop' in locals():
                loop.close()


if __name__ == "__main__":
    run_server()
"""


def generate_readme_content(server_name: str, created_files: Dict[str, str]) -> str:
    """Generate README content for the MCP server package"""
    
    return f"""# {server_name} MCP Server

This is a Model Context Protocol (MCP) server generated from REST API specifications.
It can be used with Claude Desktop and other MCP-compatible clients.

## 📁 Package Contents

- `{server_name}.yaml` - REST API tool definitions and configuration
- `{server_name}_server.py` - Complete MCP server implementation  
- `requirements.txt` - Python dependencies (mcp, httpx, pyyaml, nest_asyncio)
- `setup.py` - Automated setup script
- `claude_desktop_config.json` - Claude Desktop configuration template
- `CLAUDE_SETUP_INSTRUCTIONS.txt` - Detailed Claude Desktop setup guide
- `HOW_TO_USE.md` - Complete usage instructions and examples
- `API_TOOLS_REFERENCE.md` - Generated API tools documentation
- `verify_setup.py` - Automated setup verification script
- `README.md` - This overview file

## 🚀 Quick Start

### 1. Install Dependencies
```bash
# Option A: Use the setup script (recommended)
python setup.py

# Option B: Manual installation
pip install -r requirements.txt
```

### 2. Test the Server
```bash
# Option A: Use the verification script (recommended)
python verify_setup.py

# Option B: Test server manually
python {server_name}_server.py

# You should see:
# ✅ "Loaded configuration for {server_name}"
# ✅ "Registered tool: ToolName (METHOD /path)" (for each API endpoint)  
# ✅ Server waiting for JSON-RPC messages
```

### 3. Configure Claude Desktop
1. **Find your Claude Desktop config:**
   - **Windows:** `%APPDATA%\\Claude\\claude_desktop_config.json`
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

2. **Update the configuration** (see `claude_desktop_config.json` template)
3. **Replace `[UPDATE_PATH]`** with the full path to this extracted folder
4. **Restart Claude Desktop**

### 4. Verify Integration
- Open Claude Desktop
- Look for the tools indicator (🔧) in the chat interface
- Your API tools should be available for use

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

### Common Issues

#### "Already running asyncio in this thread" Error
This is fixed in the generated server. The server now includes `nest_asyncio` to handle event loop conflicts.

#### Server not appearing in Claude Desktop

1. **Check the config file path** - Make sure you're editing the correct file
   - Windows: `%APPDATA%\\Claude\\claude_desktop_config.json`
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
2. **Use absolute paths** - Replace `[UPDATE_PATH]` with full paths
3. **Check Python path** - You might need to use the full path to Python
4. **Restart Claude Desktop** after making changes
5. **Check server logs** - Run the server manually to see error messages

#### Manual Testing
Test your server manually before adding to Claude Desktop:
```bash
# Run the server directly
python {server_name}_server.py

# Should show:
# - "Loaded configuration for..."
# - "Registered tool: ..." (for each tool)
# - Wait for JSON-RPC messages
```

#### Python Dependencies
If you get import errors:
```bash
pip install -r requirements.txt
# OR
pip install mcp httpx pyyaml nest_asyncio
```

### Tools not working

1. **API connectivity** - Ensure the REST API is accessible
2. **Authentication** - Check if API keys or credentials are needed
3. **Parameters** - Verify required parameters are being passed
4. **Network issues** - Check if the API server is running and accessible

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


def generate_how_to_use_guide(server_name: str) -> str:
    """Generate detailed HOW_TO_USE guide"""
    
    return f"""# How to Use {server_name} MCP Server

This guide provides comprehensive instructions for setting up and using your MCP server with Claude Desktop.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Testing the Server](#testing-the-server)
4. [Claude Desktop Integration](#claude-desktop-integration)
5. [Using the Tools](#using-the-tools)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Configuration](#advanced-configuration)

## Prerequisites

### System Requirements
- **Python 3.7+** (Python 3.9+ recommended)
- **Claude Desktop** application installed
- **Internet connection** for API calls

### Check Python Version
```bash
python --version
# Should show Python 3.7 or higher
```

### Install Python (if needed)
- **Windows:** Download from [python.org](https://python.org)
- **macOS:** `brew install python` or download from python.org
- **Linux:** `sudo apt install python3 python3-pip` (Ubuntu/Debian)

## Installation

### Step 1: Extract the Package
```bash
# Extract the downloaded ZIP file
unzip {server_name}_mcp_package.zip
cd {server_name}_mcp_package
```

### Step 2: Install Dependencies
```bash
# Option A: Use the automated setup (recommended)
python setup.py

# Option B: Manual installation
pip install -r requirements.txt

# Option C: Install individual packages
pip install mcp httpx pyyaml nest_asyncio
```

### Step 3: Verify Installation
```bash
# Test imports
python -c "import mcp, httpx, yaml, nest_asyncio; print('✅ All dependencies installed successfully!')"
```

## Testing the Server

### Basic Server Test
```bash
# Run the server directly
python {server_name}_server.py

# Expected output:
# [timestamp] INFO     Loaded configuration for [API_NAME]
# [timestamp] INFO     Registered tool: ToolName (METHOD /path)
# [timestamp] INFO     Registered tool: ... (for each API endpoint)
# Server ready and waiting for JSON-RPC messages...
```

### Verify Tools Loading
The server should show all registered tools. Each line should display:
- **Tool Name:** Generated from API endpoint
- **HTTP Method:** GET, POST, PUT, DELETE, etc.
- **API Path:** The REST API endpoint path

### Test JSON-RPC Communication
```bash
# Send a test message (optional advanced testing)
echo '{{"jsonrpc": "2.0", "method": "initialize", "params": {{"protocolVersion": "2025-06-18", "capabilities": {{}}}}, "id": 1}}' | python {server_name}_server.py
```

## Claude Desktop Integration

### Step 1: Locate Claude Desktop Config
Find your Claude Desktop configuration file:

**Windows:**
```
%APPDATA%\\Claude\\claude_desktop_config.json
```
Full path example: `C:\\Users\\YourName\\AppData\\Roaming\\Claude\\claude_desktop_config.json`

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```
Full path example: `/Users/YourName/Library/Application Support/Claude/claude_desktop_config.json`

### Step 2: Backup Existing Config
```bash
# Windows (in PowerShell)
copy "%APPDATA%\\Claude\\claude_desktop_config.json" "%APPDATA%\\Claude\\claude_desktop_config.json.backup"

# macOS/Linux
cp "~/Library/Application Support/Claude/claude_desktop_config.json" "~/Library/Application Support/Claude/claude_desktop_config.json.backup"
```

### Step 3: Update Configuration

1. **Open** the Claude Desktop config file in a text editor
2. **Find** the `"mcpServers"` section (create if it doesn't exist)
3. **Add** your server configuration:

```json
{{
  "mcpServers": {{
    "{server_name}": {{
      "command": "python",
      "args": [
        "C:\\\\full\\\\path\\\\to\\\\{server_name}_server.py"
      ]
    }}
  }}
}}
```

**⚠️ Important Notes:**
- Use **full absolute paths** (no relative paths)
- Use **double backslashes** (`\\\\`) in Windows paths
- Replace the example path with your actual extraction location

### Step 4: Example Configurations

**Windows Example:**
```json
{{
  "mcpServers": {{
    "{server_name}": {{
      "command": "C:\\\\Users\\\\YourName\\\\anaconda3\\\\python.exe",
      "args": [
        "C:\\\\Users\\\\YourName\\\\Desktop\\\\{server_name}_mcp_package\\\\{server_name}_server.py"
      ]
    }}
  }}
}}
```

**macOS Example:**
```json
{{
  "mcpServers": {{
    "{server_name}": {{
      "command": "/usr/bin/python3",
      "args": [
        "/Users/YourName/Desktop/{server_name}_mcp_package/{server_name}_server.py"
      ]
    }}
  }}
}}
```

### Step 5: Restart Claude Desktop
- **Completely close** Claude Desktop
- **Reopen** the application
- **Wait** for initialization (may take 30-60 seconds)

## Using the Tools

### Finding Your Tools
1. Open Claude Desktop
2. Look for the **tools indicator** (🔧) in the chat interface
3. Your API tools should be listed and available

### Tool Usage Patterns
Each API endpoint becomes a tool you can use in conversations:

**Example requests:**
- "Use the GetUserTool to fetch user with ID 123"
- "Create a new pet using the AddPetTool with name 'Fluffy'"
- "Get the inventory using GetInventoryTool"

### Tool Parameters
- **Required parameters:** Must be provided for the tool to work
- **Optional parameters:** Can be omitted (will use defaults)
- **Path parameters:** Automatically extracted from the API path (e.g., `{{petId}}`)

### Example Usage
```
You: "Can you get information about pet ID 12345?"

Claude will:
1. Identify this needs the GetPetByIdTool
2. Extract petId = 12345
3. Call the REST API: GET /pet/12345
4. Return the formatted results
```

## Troubleshooting

### Server Not Appearing in Claude Desktop

**Check 1: Verify Claude Desktop Config File Location**
```bash
# Windows - check if file exists
dir "%APPDATA%\\Claude\\claude_desktop_config.json"

# macOS - check if file exists
ls -la "~/Library/Application Support/Claude/claude_desktop_config.json"
```

**Check 2: Validate JSON Syntax**
```bash
# Test JSON syntax (Python method)
python -c "import json; print('✅ Valid JSON' if json.load(open('path/to/claude_desktop_config.json')) else '❌ Invalid JSON')"
```

**Check 3: Verify Python Path**
```bash
# Test the exact Python command from your config
C:\\full\\path\\to\\python.exe --version

# Or for macOS
/usr/bin/python3 --version
```

**Check 4: Test Server Manually**
```bash
# Run server with same command as Claude Desktop config
C:\\full\\path\\to\\python.exe C:\\full\\path\\to\\{server_name}_server.py
```

### Tools Not Working

**API Connection Issues:**
- Verify the REST API is running and accessible
- Check network connectivity
- Confirm API base URL in the YAML file

**Authentication Problems:**
- Check if API requires authentication (API keys, tokens)
- Update the YAML file with proper auth configuration
- Verify credentials are valid

**Parameter Errors:**
- Review required vs optional parameters
- Check parameter types and formats
- Validate API endpoint expectations

### Common Error Messages

**"ModuleNotFoundError: No module named 'mcp'"**
```bash
# Solution: Install dependencies
pip install -r requirements.txt
```

**"Already running asyncio in this thread"**
```bash
# This is handled automatically by nest_asyncio
# If still occurring, try:
pip install --upgrade nest_asyncio
```

**"Server disconnected"**
```bash
# Usually indicates Python path or script path issues
# Verify both paths in Claude Desktop config are correct and absolute
```

## Advanced Configuration

### Custom Python Environment
If using virtual environments or conda:

```json
{{
  "mcpServers": {{
    "{server_name}": {{
      "command": "C:\\\\path\\\\to\\\\venv\\\\Scripts\\\\python.exe",
      "args": [
        "C:\\\\full\\\\path\\\\to\\\\{server_name}_server.py"
      ]
    }}
  }}
}}
```

### Multiple Environments
```json
{{
  "mcpServers": {{
    "{server_name}_dev": {{
      "command": "python",
      "args": [
        "C:\\\\dev\\\\{server_name}_server.py"
      ]
    }},
    "{server_name}_prod": {{
      "command": "python",
      "args": [
        "C:\\\\prod\\\\{server_name}_server.py"
      ]
    }}
  }}
}}
```

### Environment Variables
Set environment variables for API configuration:

**Windows:**
```batch
set API_BASE_URL=https://api.example.com
set API_KEY=your_api_key
python {server_name}_server.py
```

**macOS/Linux:**
```bash
export API_BASE_URL=https://api.example.com
export API_KEY=your_api_key
python {server_name}_server.py
```

### Logging Configuration
Enable debug logging by modifying the server script:

```python
# Add to {server_name}_server.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Getting Help

### Check Server Logs
```bash
# Run server with verbose output
python {server_name}_server.py 2>&1 | tee server.log
```

### Community Resources
- **MCP Documentation:** [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)
- **Claude Desktop Support:** [https://support.anthropic.com/](https://support.anthropic.com/)
- **GitHub Issues:** Report issues with the generated server

### Debug Checklist
- [ ] Python 3.7+ installed and accessible
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] Server runs manually without errors
- [ ] Claude Desktop config file exists and has valid JSON
- [ ] Absolute paths used in configuration
- [ ] Claude Desktop restarted after config changes
- [ ] REST API is accessible and running

---

**Success Indicators:**
- ✅ Server starts without errors
- ✅ Tools appear in Claude Desktop
- ✅ API calls return expected results
- ✅ No error messages in Claude Desktop logs
"""


def generate_api_tools_reference(yaml_file_path: str, server_name: str) -> str:
    """Generate API tools reference documentation"""
    
    try:
        # Load YAML to extract tools information
        import yaml
        with open(yaml_file_path, 'r', encoding='utf-8') as f:
            yaml_data = yaml.safe_load(f)
        
        api_info = yaml_data.get('api_info', {{}})
        tools = yaml_data.get('tools', [])
        
        tools_doc = f"""# API Tools Reference - {server_name}

This document provides detailed information about all available tools generated from the REST API specification.

## API Information

- **Name:** {api_info.get('name', 'Unknown')}
- **Description:** {api_info.get('description', 'No description available')}
- **Base URL:** {api_info.get('base_url', 'Not specified')}
- **Authentication:** {api_info.get('auth_type', 'none')}

## Available Tools ({len(tools)} total)

"""

        for i, tool in enumerate(tools, 1):
            tool_name = tool.get('name', 'Unknown Tool')
            description = tool.get('description', 'No description available')
            method = tool.get('method', 'GET')
            path = tool.get('path', '/')
            parameters = tool.get('parameters', {{}})
            
            tools_doc += f"""### {i}. {tool_name}

**Description:** {description}

**HTTP Method:** `{method}`

**API Path:** `{path}`

**Full URL:** `{api_info.get('base_url', '')}{path}`

"""

            # Add parameters documentation
            properties = parameters.get('properties', {{}})
            required = parameters.get('required', [])
            
            if properties:
                tools_doc += "**Parameters:**\n\n"
                
                for param_name, param_info in properties.items():
                    param_type = param_info.get('type', 'string')
                    param_desc = param_info.get('description', 'No description')
                    is_required = param_name in required
                    
                    required_badge = "**Required**" if is_required else "*Optional*"
                    
                    tools_doc += f"""- **`{param_name}`** ({param_type}) - {required_badge}
  - {param_desc}

"""
            else:
                tools_doc += "**Parameters:** None\n\n"
            
            # Add usage examples
            tools_doc += f"""**Usage Example:**
```
You: "Use {tool_name} to {method.lower()} {path}"
Claude: [Executes the API call and returns results]
```

**Claude Desktop Usage:**
```
"Please call the {tool_name} to retrieve data"
```

---

"""

        # Add footer with additional information
        tools_doc += f"""
## Usage Notes

### Authentication
- **Type:** {api_info.get('auth_type', 'none')}
- **Configuration:** Check the YAML file for authentication details

### Error Handling
- All tools return JSON-RPC formatted responses
- HTTP errors are captured and returned with error details
- Network timeouts are set to 30 seconds

### Response Format
Each tool returns a structured response:
```json
{{
  "jsonrpc": "2.0",
  "result": {{
    "status": 200,
    "data": {{...}},
    "message": "Request successful"
  }},
  "id": 1
}}
```

### Tips for Using Tools
1. **Be specific** about which tool you want to use
2. **Provide required parameters** in your request
3. **Check responses** for errors or unexpected results
4. **Use natural language** - Claude will map your request to the appropriate tool

### Common Patterns

**Retrieving Data:**
- "Get user information for ID 12345"
- "Fetch the inventory data"
- "Show me details for order #67890"

**Creating Resources:**
- "Create a new user with name 'John Doe' and email 'john@example.com'"
- "Add a pet named 'Buddy' to the system"
- "Place an order for 3 items"

**Updating Data:**
- "Update user 12345 with new email address"
- "Modify pet information for ID 456"
- "Change the status of order #789"

**Deleting Resources:**
- "Delete user with ID 12345"
- "Remove pet #456 from the system"
- "Cancel order #789"

---

*Generated from {server_name} REST API specification*
*Total API endpoints: {len(tools)}*
"""

        return tools_doc
        
    except Exception as e:
        return f"""# API Tools Reference - {server_name}

## Error Loading Tools Information

Could not load tools information from YAML file: {str(e)}

## Basic Information

This MCP server was generated from a REST API specification and provides tools for interacting with the API endpoints.

### Usage
- Each API endpoint becomes a tool in Claude Desktop
- Tools can be invoked through natural language requests
- All tools return JSON-formatted responses

### Getting Tool Information
To see available tools:
1. Start the MCP server manually: `python {server_name}_server.py`
2. Check the console output for "Registered tool:" messages
3. Each message shows the tool name and corresponding API endpoint

### Support
If you cannot see this information, please check:
- YAML file exists and is valid
- Python dependencies are installed
- Server starts without errors

---

*Auto-generated documentation for {server_name} MCP Server*
"""


def generate_verification_script(server_name: str) -> str:
    """Generate verification script to test MCP server setup"""
    
    return f"""#!/usr/bin/env python3
\"\"\"
Setup Verification Script for {server_name} MCP Server

This script helps verify that your MCP server is properly configured
and ready to use with Claude Desktop.
\"\"\"

import sys
import os
import subprocess
import json
import platform
from pathlib import Path


def print_header(title):
    \"\"\"Print a formatted header\"\"\"
    print("\\n" + "="*60)
    print(f" {{title}}")
    print("="*60)


def print_status(message, status):
    \"\"\"Print a status message\"\"\"
    if status:
        print(f"✅ {{message}}")
    else:
        print(f"❌ {{message}}")
    return status


def check_python_version():
    \"\"\"Check if Python version is compatible\"\"\"
    print_header("Python Version Check")
    
    version = sys.version_info
    print(f"Python version: {{version.major}}.{{version.minor}}.{{version.micro}}")
    
    compatible = version >= (3, 7)
    print_status(f"Python 3.7+ required", compatible)
    
    if compatible:
        print(f"✅ Using: {{sys.executable}}")
    else:
        print("❌ Please upgrade Python to version 3.7 or higher")
    
    return compatible


def check_dependencies():
    \"\"\"Check if required dependencies are installed\"\"\"
    print_header("Dependencies Check")
    
    required_packages = ['mcp', 'httpx', 'yaml', 'nest_asyncio']
    all_installed = True
    
    for package in required_packages:
        try:
            if package == 'yaml':
                import yaml
            elif package == 'mcp':
                import mcp
            elif package == 'httpx':
                import httpx
            elif package == 'nest_asyncio':
                import nest_asyncio
            
            print_status(f"Package '{{package}}' installed", True)
        except ImportError:
            print_status(f"Package '{{package}}' missing", False)
            all_installed = False
    
    if not all_installed:
        print("\\n💡 To install missing packages:")
        print("   pip install -r requirements.txt")
        print("   OR run: python setup.py")
    
    return all_installed


def check_server_files():
    \"\"\"Check if server files exist\"\"\"
    print_header("Server Files Check")
    
    script_dir = Path(__file__).parent
    required_files = [
        f'{server_name}.yaml',
        f'{server_name}_server.py',
        'requirements.txt',
        'setup.py'
    ]
    
    all_files_exist = True
    
    for filename in required_files:
        file_path = script_dir / filename
        exists = file_path.exists()
        print_status(f"File '{{filename}}' exists", exists)
        all_files_exist = all_files_exist and exists
    
    return all_files_exist


def test_server_startup():
    \"\"\"Test if the MCP server starts without errors\"\"\"
    print_header("Server Startup Test")
    
    script_dir = Path(__file__).parent
    server_script = script_dir / f'{server_name}_server.py'
    
    if not server_script.exists():
        print_status("Server script not found", False)
        return False
    
    try:
        print("Testing server startup (this may take a few seconds)...")
        
        # Run server with timeout to test startup
        result = subprocess.run(
            [sys.executable, str(server_script)],
            timeout=10,  # 10 second timeout
            capture_output=True,
            text=True,
            input='\\n'  # Send newline to stop server
        )
        
        # Check if server started successfully (look for key messages)
        output = result.stderr + result.stdout
        
        startup_success = (
            "Loaded configuration" in output and 
            "Registered tool:" in output
        )
        
        print_status("Server starts without errors", startup_success)
        
        if startup_success:
            # Count registered tools
            tool_count = output.count("Registered tool:")
            print(f"✅ Found {{tool_count}} registered tools")
        else:
            print("❌ Server output:")
            print(output[:500] + "..." if len(output) > 500 else output)
        
        return startup_success
        
    except subprocess.TimeoutExpired:
        print_status("Server started (stopped after timeout)", True)
        return True
    except Exception as e:
        print_status(f"Server startup failed: {{str(e)}}", False)
        return False


def check_claude_desktop_config():
    \"\"\"Check Claude Desktop configuration\"\"\"
    print_header("Claude Desktop Configuration Check")
    
    # Determine config file path based on OS
    if platform.system() == "Windows":
        config_path = Path(os.environ.get('APPDATA', '')) / 'Claude' / 'claude_desktop_config.json'
    else:  # macOS/Linux
        config_path = Path.home() / 'Library' / 'Application Support' / 'Claude' / 'claude_desktop_config.json'
    
    print(f"Expected config location: {{config_path}}")
    
    if not config_path.exists():
        print_status("Claude Desktop config file found", False)
        print("💡 Create the config file and add your MCP server configuration")
        print("   See CLAUDE_SETUP_INSTRUCTIONS.txt for details")
        return False
    
    print_status("Claude Desktop config file found", True)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        mcp_servers = config.get('mcpServers', {{}})
        server_configured = server_name in mcp_servers
        
        print_status(f"Server '{{server_name}}' configured", server_configured)
        
        if server_configured:
            server_config = mcp_servers[server_name]
            command = server_config.get('command', '')
            args = server_config.get('args', [])
            
            print(f"✅ Command: {{command}}")
            print(f"✅ Args: {{args}}")
            
            # Check if paths are absolute
            if args and not os.path.isabs(args[0]):
                print_status("Using absolute paths", False)
                print("💡 Update paths to be absolute for better reliability")
            else:
                print_status("Using absolute paths", True)
        
        return True
        
    except json.JSONDecodeError:
        print_status("Config file has valid JSON", False)
        print("💡 Fix JSON syntax errors in claude_desktop_config.json")
        return False
    except Exception as e:
        print_status(f"Config file readable: {{str(e)}}", False)
        return False


def show_next_steps(all_checks_passed):
    \"\"\"Show next steps based on verification results\"\"\"
    print_header("Next Steps")
    
    if all_checks_passed:
        print("🎉 All checks passed! Your MCP server is ready to use.")
        print("\\n📋 To use with Claude Desktop:")
        print("1. Restart Claude Desktop completely")
        print("2. Open a new conversation")
        print("3. Look for the tools indicator (🔧) in the interface")
        print("4. Start using your API tools!")
        
        print("\\n📖 Documentation:")
        print("- README.md - Quick start guide")
        print("- HOW_TO_USE.md - Detailed usage instructions") 
        print("- API_TOOLS_REFERENCE.md - Complete tools reference")
    else:
        print("🔧 Some issues need to be resolved:")
        print("\\n1. Fix any ❌ items shown above")
        print("2. Run this script again: python verify_setup.py")
        print("3. Check the documentation files for detailed help")
        
        print("\\n📚 Helpful files:")
        print("- HOW_TO_USE.md - Complete setup instructions")
        print("- CLAUDE_SETUP_INSTRUCTIONS.txt - Claude Desktop setup")
        print("- requirements.txt - Dependencies list")


def main():
    \"\"\"Main verification function\"\"\"
    print("🔍 MCP Server Setup Verification")
    print(f"Server: {{server_name}}")
    
    checks = [
        ("Python Version", check_python_version()),
        ("Dependencies", check_dependencies()),
        ("Server Files", check_server_files()),
        ("Server Startup", test_server_startup()),
        ("Claude Desktop Config", check_claude_desktop_config())
    ]
    
    # Summary
    print_header("Verification Summary")
    
    passed = 0
    for name, status in checks:
        print_status(name, status)
        if status:
            passed += 1
    
    all_passed = passed == len(checks)
    
    print(f"\\nResult: {{passed}}/{{len(checks)}} checks passed")
    
    show_next_steps(all_passed)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
"""
