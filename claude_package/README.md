# petstore_api_claude MCP Server

This is a Model Context Protocol (MCP) server generated from REST API specifications.
It can be used with Claude Desktop and other MCP-compatible clients.

## Files Generated

- `petstore_api_claude.yaml` - REST API tool definitions
- `petstore_api_claude_server.py` - MCP server implementation
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
   python petstore_api_claude_server.py
   ```

## Claude Desktop Configuration

To use this server with Claude Desktop:

1. **Locate your Claude Desktop config file:**
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

2. **Add the server configuration:**
   ```json
   {
     "mcpServers": {
       "petstore_api_claude": {
         "command": "python",
         "args": [
           "/absolute/path/to/petstore_api_claude_server.py"
         ]
       }
     }
   }
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

- Tool: [Tools will be listed here based on YAML]

Each tool corresponds to a REST API endpoint and will execute HTTP requests
according to the specifications in the YAML file.

## Support

For issues with:
- **MCP protocol:** [MCP Documentation](https://modelcontextprotocol.io/)
- **Claude Desktop:** [Claude Desktop Support](https://support.anthropic.com/)
- **This server:** Check the generated YAML file and server implementation
