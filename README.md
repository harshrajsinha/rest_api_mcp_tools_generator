# REST API MCP Tools Generator

A Django-based application that processes Swagger/OpenAPI interfaces and generates MCP (Model Context Protocol) servers for REST API services. This tool automatically creates tool definitions from API specifications and serves them through MCP servers.

## 🚀 Features

### 1. Tools Generator Component

**Input:**
- REST API Swagger/OpenAPI URL
- REST API Base URL  
- Authentication Mechanism
- API Service Description
- Custom descriptions for APIs and parameters

**Output:**
- YAML files containing tool definitions
- Complete API endpoint mappings
- Parameter specifications
- Authentication configurations

**Capabilities:**
- ✅ Test Swagger URL connectivity and validation
- ✅ Parse all API endpoints from Swagger specifications
- ✅ Extract parameters, request/response schemas
- ✅ Support multiple authentication methods (API Key, Bearer Token, Basic Auth, OAuth2)
- ✅ Web UI for easy configuration and testing
- ✅ Enhance API descriptions and parameter details
- ✅ Background processing with Celery for large APIs

### 2. MCP Server Component

**Features:**
- ✅ Dynamic tool loading from YAML files
- ✅ Tool classes automatically inherit from `RestApiTool`
- ✅ Multiple server instance management
- ✅ Real-time tool execution and testing
- ✅ JSON-RPC 2.0 compatible responses
- ✅ RESTful API for server management

## 🏗️ Architecture

### Core Components

```
rest_api_mcp_tools_generator/
├── core/                    # Base models and RestApiTool class
├── tools_generator/         # Swagger parsing and YAML generation  
├── mcp_server/             # MCP server management and tool execution
├── templates/              # Web UI templates
└── static/                 # CSS, JavaScript, and assets
```

### Generated Tool Structure

All tools are dynamically created and inherit from `RestApiTool`:

```python
class CreateUserTool(RestApiTool):
    For: ClassVar[Annotated[ToolType, ToolType.FOR_SCIKIQ]] = ToolType.FOR_SCIKIQ
    api_path = "/base/user/save"

    def get_parameters(self):
        extra_properties = {
            "first_name": Property(type="string", description="First name of the new user"),
            "last_name": Property(type="string", description="Last name of the new user"),
            "email": Property(type="string", description="Email address of the user"),
            # ... more parameters
        }
        extra_required = ["first_name", "last_name", "email", "password"]
        return RestApiParameters(extra_properties, extra_required)

    async def invoke(self, first_name, last_name, email, password, **kwargs):
        """Create a new user in the system"""
        # Auto-generated implementation based on Swagger spec
        # Handles authentication, parameter validation, API calls
        pass
```

## 🔧 Technology Stack

- **Backend:** Django 4.2 + Django REST Framework
- **Task Queue:** Celery with Redis
- **Frontend:** Bootstrap 5 + jQuery + Axios
- **API Processing:** Swagger Spec Validator + PyYAML
- **Database:** SQLite (default) / PostgreSQL (production)

## 📦 Installation

### Prerequisites
- Python 3.8+
- Redis server
- Git

### Quick Setup

1. **Clone and Setup:**
```bash
git clone <repository-url>
cd rest_api_mcp_tools_generator
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

2. **Configure Environment:**
```bash
cp .env.example .env  # Edit with your settings
```

3. **Initialize Database:**
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py init_project --create-superuser
```

4. **Start Services:**
```bash
# Terminal 1: Django server
python manage.py runserver

# Terminal 2: Celery worker  
celery -A rest_api_mcp_generator worker --loglevel=info

# Terminal 3: Redis (if not running as service)
redis-server
```

5. **Access Application:**
- Web Interface: http://localhost:8000
- Admin Panel: http://localhost:8000/admin (admin/admin123)

## 🖥️ Usage

### 1. Create API Configuration
1. Navigate to the Tools Generator section
2. Enter API details:
   - **Name:** Descriptive name
   - **Swagger URL:** OpenAPI specification URL
   - **Base URL:** API base endpoint
   - **Auth Type:** Authentication method
3. Test connection and save

### 2. Generate YAML Tools
1. Select API configuration
2. Click "Generate YAML"
3. Monitor background processing
4. Review and enhance endpoint descriptions

### 3. Create MCP Server
1. Select completed YAML file
2. Click "Create Server"
3. Provide server name
4. Server starts automatically

### 4. Test Tools
1. View running servers
2. Browse available tools
3. Execute tools with parameters
4. View JSON-RPC responses

## 🔌 API Endpoints

### Tools Generator APIs
```
GET    /api/tools-generator/api-configs/           # List configurations
POST   /api/tools-generator/api-configs/           # Create configuration
POST   /api/tools-generator/api-configs/{id}/test_connection/
POST   /api/tools-generator/api-configs/{id}/generate_yaml/
GET    /api/tools-generator/yaml-files/            # List YAML files
GET    /api/tools-generator/endpoints/              # List API endpoints
```

### MCP Server APIs
```
GET    /api/mcp-server/instances/                  # List server instances
POST   /api/mcp-server/instances/                  # Create server
POST   /api/mcp-server/instances/{id}/start_server/
POST   /api/mcp-server/instances/{id}/stop_server/
GET    /api/mcp-server/instances/{id}/get_tools/
POST   /api/mcp-server/instances/{id}/execute_tool/
```

## 🧪 Example

Using the Petstore API example:

1. **Configure API:**
   - Swagger URL: `https://petstore.swagger.io/v2/swagger.json`
   - Base URL: `https://petstore.swagger.io/v2`

2. **Generated Tools:**
   - `AddPetTool` - Add a new pet to the store
   - `FindPetsByStatusTool` - Find pets by status
   - `GetPetByIdTool` - Find pet by ID
   - `UpdatePetTool` - Update an existing pet
   - And more...

3. **Tool Execution:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "msg": "Pet created successfully",
    "data": {"id": 123, "name": "Fluffy", "status": "available"},
    "status": 200
  },
  "id": 1
}
```

## 📁 File Structure

```
rest_api_mcp_tools_generator/
├── 📁 core/                          # Core application
│   ├── models.py                     # Database models
│   ├── tools_base.py                 # RestApiTool base class
│   └── admin.py                      # Django admin
├── 📁 tools_generator/               # Tools generation
│   ├── services.py                   # Swagger parsing logic
│   ├── views.py                      # API endpoints
│   ├── tasks.py                      # Background tasks
│   └── serializers.py                # API serializers
├── 📁 mcp_server/                    # MCP server management
│   ├── services.py                   # Server implementation
│   ├── views.py                      # Server management APIs
│   └── serializers.py                # Server serializers
├── 📁 templates/                     # HTML templates
├── 📁 static/                        # Static assets
├── 📁 generated_yaml_files/          # Generated YAML storage
├── 📁 generated_tools/               # Generated Python tools
├── requirements.txt                  # Python dependencies
├── .env                             # Environment configuration
└── manage.py                        # Django management
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For detailed setup instructions, see [SETUP.md](SETUP.md)

For issues and questions:
1. Check existing GitHub issues
2. Create new issue with detailed description
3. Include error logs and environment details
