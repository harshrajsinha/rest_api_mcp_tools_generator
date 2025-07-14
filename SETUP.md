# REST API MCP Tools Generator - Setup Instructions

## Overview

This Django application implements the REST API MCP Tools Generator as described in the README.md. It consists of two main components:

1. **Tools Generator**: Processes Swagger/OpenAPI specifications and generates YAML tool definitions
2. **MCP Server**: Creates and manages MCP servers from the generated YAML files

## Architecture

### Core Components

- **Core App**: Contains base models and the `RestApiTool` class structure
- **Tools Generator App**: Handles Swagger parsing and YAML generation
- **MCP Server App**: Manages MCP server instances and tool execution

### Key Features

1. **Swagger Interface Processing**:
   - Fetch and validate Swagger/OpenAPI specifications
   - Parse API endpoints, parameters, and responses
   - Support for multiple authentication mechanisms

2. **YAML Generation**:
   - Generate structured YAML files with tool definitions
   - Allow enhancement of API descriptions and parameters
   - Support for custom tool naming conventions

3. **Dynamic Tool Creation**:
   - Classes like `CreateUserTool` are dynamically generated from YAML
   - All generated tools inherit from `RestApiTool`
   - Support for different tool types and configurations

4. **MCP Server Management**:
   - Create MCP server instances from YAML files
   - Start/stop server management
   - Real-time tool execution and testing

## Installation

### Prerequisites

- Python 3.8+
- Redis (for Celery background tasks)
- Node.js (optional, for frontend development)

### Setup Steps

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd rest_api_mcp_tools_generator
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # source venv/bin/activate  # On Linux/Mac
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment configuration**:
   - Copy `.env` file and update settings as needed
   - Ensure Redis is running for Celery tasks

5. **Database setup**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py createsuperuser
   ```

6. **Create required directories**:
   ```bash
   mkdir generated_yaml_files
   mkdir generated_tools
   mkdir staticfiles
   ```

7. **Collect static files**:
   ```bash
   python manage.py collectstatic
   ```

## Running the Application

### Development Server

1. **Start Django development server**:
   ```bash
   python manage.py runserver
   ```

2. **Start Celery worker** (in separate terminal):
   ```bash
   celery -A rest_api_mcp_generator worker --loglevel=info
   ```

3. **Start Redis** (if not running as service):
   ```bash
   redis-server
   ```

### Access the Application

- Web Interface: http://localhost:8000
- Admin Interface: http://localhost:8000/admin
- API Documentation: http://localhost:8000/api

## Usage

### Creating API Configurations

1. Navigate to the Tools Generator section
2. Fill in the API configuration form:
   - **API Name**: Descriptive name for the API
   - **Swagger URL**: URL to the Swagger/OpenAPI specification
   - **API Base URL**: Base URL for the REST API
   - **Description**: Optional description
   - **Authentication Type**: Select appropriate auth method

3. Test the connection using the "Test Connection" button
4. Save the configuration

### Generating YAML Files

1. From the API configurations list, click "Generate YAML"
2. The system will:
   - Parse the Swagger specification
   - Extract all API endpoints
   - Generate tool definitions
   - Create a YAML file with all tools

3. Review and enhance the generated endpoints:
   - Edit descriptions for better clarity
   - Modify parameter descriptions
   - Enable/disable specific endpoints

### Creating MCP Servers

1. From the YAML files list, click "Create Server"
2. Provide a server name
3. The system will:
   - Create an MCP server instance
   - Load the YAML configuration
   - Generate dynamic tool classes
   - Start the server

### Testing Tools

1. View running MCP servers
2. Click "Tools" to see available tools
3. Test individual tools with custom parameters
4. View JSON-RPC formatted responses

## Generated Tool Structure

All tools generated from YAML files inherit from `RestApiTool` and follow this pattern:

```python
class CreateUserTool(RestApiTool):
    For: ClassVar[Annotated[ToolType, ToolType.FOR_SELF]] = ToolType.FOR_SELF
    api_path = "/api/users"
    
    def get_parameters(self):
        extra_properties = {
            "name": Property(type="string", description="User name"),
            "email": Property(type="string", description="User email"),
        }
        extra_required = ["name", "email"]
        return RestApiParameters(extra_properties, extra_required)
    
    async def invoke(self, name, email, id=None):
        # Implementation generated from YAML specification
        pass
```

## API Endpoints

### Tools Generator APIs

- `GET /api/tools-generator/api-configs/` - List API configurations
- `POST /api/tools-generator/api-configs/` - Create API configuration
- `POST /api/tools-generator/api-configs/{id}/test_connection/` - Test API connection
- `POST /api/tools-generator/api-configs/{id}/generate_yaml/` - Generate YAML
- `GET /api/tools-generator/yaml-files/` - List generated YAML files
- `GET /api/tools-generator/yaml-files/{id}/download/` - Download YAML file

### MCP Server APIs

- `GET /api/mcp-server/instances/` - List MCP server instances
- `POST /api/mcp-server/instances/` - Create MCP server instance
- `POST /api/mcp-server/instances/{id}/start_server/` - Start server
- `POST /api/mcp-server/instances/{id}/stop_server/` - Stop server
- `GET /api/mcp-server/instances/{id}/get_tools/` - Get server tools
- `POST /api/mcp-server/instances/{id}/execute_tool/` - Execute tool

## File Structure

```
rest_api_mcp_tools_generator/
├── core/                           # Core models and base classes
│   ├── models.py                   # Database models
│   ├── tools_base.py              # RestApiTool base class
│   └── views.py                   # Core views
├── tools_generator/               # Tools generation functionality
│   ├── services.py                # Swagger parsing and YAML generation
│   ├── views.py                   # API views
│   ├── serializers.py             # API serializers
│   └── tasks.py                   # Celery background tasks
├── mcp_server/                    # MCP server management
│   ├── services.py                # MCP server implementation
│   ├── views.py                   # Server management APIs
│   └── serializers.py             # Server serializers
├── templates/                     # HTML templates
├── static/                        # CSS, JS, and other static files
├── generated_yaml_files/          # Generated YAML files storage
├── generated_tools/               # Generated Python tool files
└── manage.py                      # Django management script
```

## Troubleshooting

### Common Issues

1. **Celery worker not starting**:
   - Ensure Redis is running
   - Check CELERY_BROKER_URL in settings

2. **Swagger parsing errors**:
   - Verify Swagger URL is accessible
   - Check if specification is valid OpenAPI/Swagger format

3. **Tool execution failures**:
   - Verify API base URL is correct
   - Check authentication configuration
   - Ensure required parameters are provided

### Logs

- Django logs: Check console output or configure logging in settings
- Celery logs: Monitor Celery worker output
- Redis logs: Check Redis server logs if connection issues occur

## Contributing

1. Follow Django coding standards
2. Add tests for new functionality
3. Update documentation for API changes
4. Ensure proper error handling and validation

## License

See LICENSE file for details.
