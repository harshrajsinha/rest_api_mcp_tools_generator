"""
Swagger parser and YAML generator service
"""
import requests
import yaml
import json
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin
try:
    from swagger_spec_validator.validator20 import validate_spec
    from swagger_spec_validator.common import SwaggerValidationError
    SWAGGER_VALIDATOR_AVAILABLE = True
except ImportError:
    SWAGGER_VALIDATOR_AVAILABLE = False

from jsonschema import ValidationError
import logging

logger = logging.getLogger(__name__)


class SwaggerParser:
    """
    Parses Swagger/OpenAPI specifications and extracts API endpoint information
    """
    
    def __init__(self, swagger_url: str, api_base_url: str):
        self.swagger_url = swagger_url
        self.api_base_url = api_base_url
        self.spec = None
        
    def fetch_swagger_spec(self) -> Dict[str, Any]:
        """
        Fetch and validate Swagger specification from URL
        """
        try:
            response = requests.get(self.swagger_url, timeout=30)
            response.raise_for_status()
            
            # Try to parse as JSON first, then YAML
            try:
                spec = response.json()
            except json.JSONDecodeError:
                try:
                    spec = yaml.safe_load(response.text)
                except yaml.YAMLError as ye:
                    raise Exception(f"Invalid YAML/JSON format: {str(ye)}")
            
            # Basic validation - check if it's a valid Swagger/OpenAPI spec
            self._basic_spec_validation(spec)
            
            # Try strict validation but don't fail if it doesn't pass
            try:
                if SWAGGER_VALIDATOR_AVAILABLE:
                    validate_spec(spec)
                    logger.info("Swagger spec passed strict validation")
                else:
                    logger.warning("Swagger validator not available, skipping strict validation")
            except (ValidationError, Exception) as ve:
                logger.warning(f"Swagger spec failed strict validation but proceeding: {str(ve)}")
                # Don't raise the error, just log it and continue
            
            self.spec = spec
            return spec
            
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch Swagger spec: {str(e)}")
        except Exception as e:
            raise Exception(f"Error parsing Swagger spec: {str(e)}")
    
    def _basic_spec_validation(self, spec: Dict[str, Any]) -> None:
        """
        Perform basic validation to ensure it's a valid Swagger/OpenAPI spec
        """
        if not isinstance(spec, dict):
            raise Exception("Specification must be a JSON object")
        
        # Check for required fields
        swagger_version = spec.get('swagger')
        openapi_version = spec.get('openapi')
        
        if not swagger_version and not openapi_version:
            raise Exception("Missing 'swagger' or 'openapi' version field")
        
        if not spec.get('info'):
            raise Exception("Missing 'info' section")
        
        if not spec.get('paths'):
            logger.warning("No 'paths' section found in specification")
        
        # Validate version format
        if swagger_version and not swagger_version.startswith('2.'):
            logger.warning(f"Unsupported Swagger version: {swagger_version}. Expected 2.x")
        
        if openapi_version and not (openapi_version.startswith('3.') or openapi_version.startswith('2.')):
            logger.warning(f"Unsupported OpenAPI version: {openapi_version}. Expected 3.x or 2.x")
    
    def extract_endpoints(self) -> List[Dict[str, Any]]:
        """
        Extract all API endpoints from the Swagger specification
        """
        if not self.spec:
            raise Exception("Swagger spec not loaded. Call fetch_swagger_spec() first.")
        
        endpoints = []
        paths = self.spec.get('paths', {})
        
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method.lower() in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
                    endpoint_info = self._extract_operation_info(path, method, operation)
                    endpoints.append(endpoint_info)
        
        return endpoints
    
    def _extract_operation_info(self, path: str, method: str, operation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract information from a single operation
        """
        return {
            'path': path,
            'method': method.upper(),
            'operation_id': operation.get('operationId', ''),
            'summary': operation.get('summary', ''),
            'description': operation.get('description', ''),
            'tags': operation.get('tags', []),
            'parameters': self._extract_parameters(operation.get('parameters', [])),
            'request_body': self._extract_request_body(operation.get('requestBody', {})),
            'responses': self._extract_responses(operation.get('responses', {})),
            'security': operation.get('security', []),
        }
    
    def _extract_parameters(self, parameters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract and normalize parameter information
        """
        extracted_params = []
        
        for param in parameters:
            param_info = {
                'name': param.get('name', ''),
                'in': param.get('in', ''),  # query, path, header, cookie
                'description': param.get('description', ''),
                'required': param.get('required', False),
                'schema': param.get('schema', {}),
                'type': self._get_parameter_type(param),
            }
            extracted_params.append(param_info)
        
        return extracted_params
    
    def _extract_request_body(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract request body information
        """
        if not request_body:
            return {}
        
        content = request_body.get('content', {})
        media_types = list(content.keys())
        
        # Focus on JSON content type
        json_content = content.get('application/json', {})
        
        return {
            'description': request_body.get('description', ''),
            'required': request_body.get('required', False),
            'content_types': media_types,
            'schema': json_content.get('schema', {}),
        }
    
    def _extract_responses(self, responses: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract response information
        """
        extracted_responses = {}
        
        for status_code, response in responses.items():
            extracted_responses[status_code] = {
                'description': response.get('description', ''),
                'content': response.get('content', {}),
                'headers': response.get('headers', {}),
            }
        
        return extracted_responses
    
    def _get_parameter_type(self, param: Dict[str, Any]) -> str:
        """
        Determine the parameter type from schema (handles both Swagger 2.0 and OpenAPI 3.0)
        """
        # For OpenAPI 3.0, type is in schema
        schema = param.get('schema', {})
        param_type = schema.get('type')
        
        # For Swagger 2.0, type is directly in parameter
        if not param_type:
            param_type = param.get('type', 'string')
        
        # Handle array types
        if param_type == 'array':
            # OpenAPI 3.0 format
            items_schema = schema.get('items', {})
            items_type = items_schema.get('type', 'string')
            
            # Swagger 2.0 format
            if not items_type:
                items_obj = param.get('items', {})
                items_type = items_obj.get('type', 'string')
            
            return f"array[{items_type}]"
        
        # Handle file uploads
        if param_type == 'file':
            return 'file'
        
        return param_type or 'string'


class YAMLGenerator:
    """
    Generates YAML files for REST API tools based on parsed Swagger data
    """
    
    def __init__(self, api_config: Dict[str, Any], endpoints: List[Dict[str, Any]], yaml_file=None):
        self.api_config = api_config
        self.endpoints = endpoints
        self.yaml_file = yaml_file  # Optional: for enhanced descriptions
    
    def generate_yaml_structure(self) -> Dict[str, Any]:
        """
        Generate the complete YAML structure for the API tools
        """
        yaml_structure = {
            'api_info': {
                'name': self.api_config.get('name', 'Generated API Tools'),
                'description': self.api_config.get('description', ''),
                'base_url': self.api_config.get('api_base_url', ''),
                'swagger_url': self.api_config.get('swagger_url', ''),
                'auth_type': self.api_config.get('auth_type', 'none'),
                'auth_config': self.api_config.get('auth_config', {}),
            },
            'tools': []
        }
        
        for endpoint in self.endpoints:
            tool_info = self._generate_tool_info(endpoint)
            yaml_structure['tools'].append(tool_info)
        
        return yaml_structure
    
    def generate_enhanced_yaml_structure(self) -> Dict[str, Any]:
        """
        Generate YAML structure using enhanced descriptions from the database
        """
        if not self.yaml_file:
            return self.generate_yaml_structure()
        
        # Import here to avoid circular import
        from core.models import APIEndpoint, ParameterEnhancement
        
        yaml_structure = {
            'api_info': {
                'name': self.api_config.get('name', 'Generated API Tools'),
                'description': self.api_config.get('description', ''),
                'base_url': self.api_config.get('api_base_url', ''),
                'swagger_url': self.api_config.get('swagger_url', ''),
                'auth_type': self.api_config.get('auth_type', 'none'),
                'auth_config': self.api_config.get('auth_config', {}),
            },
            'tools': []
        }
        
        # Get enhanced endpoints from database
        db_endpoints = APIEndpoint.objects.filter(yaml_file=self.yaml_file).prefetch_related('parameter_enhancements')
        
        for db_endpoint in db_endpoints:
            # Find corresponding endpoint data
            endpoint_data = None
            for endpoint in self.endpoints:
                if (endpoint['path'] == db_endpoint.path and 
                    endpoint['method'].upper() == db_endpoint.method.upper()):
                    endpoint_data = endpoint
                    break
            
            if not endpoint_data:
                continue
            
            tool_info = self._generate_enhanced_tool_info(endpoint_data, db_endpoint)
            yaml_structure['tools'].append(tool_info)
        
        return yaml_structure
    
    def _generate_enhanced_tool_info(self, endpoint_data: Dict[str, Any], db_endpoint) -> Dict[str, Any]:
        """
        Generate tool information using enhanced descriptions from database
        """
        from core.models import ParameterEnhancement
        
        # Use enhanced descriptions if available
        description = db_endpoint.display_description
        summary = db_endpoint.display_summary
        
        tool_info = {
            'name': db_endpoint.tool_name or self._generate_tool_name(endpoint_data),
            'description': description or endpoint_data.get('summary', ''),
            'summary': summary or endpoint_data.get('summary', ''),
            'method': endpoint_data['method'],
            'path': endpoint_data['path'],
            'operation_id': endpoint_data.get('operation_id', ''),
            'parameters': self._generate_enhanced_tool_parameters(endpoint_data, db_endpoint),
            'request_body': endpoint_data.get('request_body', {}),
            'responses': endpoint_data.get('responses', {}),
            'tags': endpoint_data.get('tags', []),
        }
        
        return tool_info
    
    def _generate_enhanced_tool_parameters(self, endpoint_data: Dict[str, Any], db_endpoint) -> Dict[str, Any]:
        """
        Generate tool parameters using enhanced descriptions from database
        """
        parameters = {
            'type': 'object',
            'properties': {},
            'required': []
        }
        
        # Get parameter enhancements
        enhancements = {pe.parameter_name: pe for pe in db_endpoint.parameter_enhancements.all()}
        
        # Add path parameters
        for param in endpoint_data.get('parameters', []):
            if param['in'] == 'path':
                param_name = param['name']
                enhancement = enhancements.get(param_name)
                
                parameters['properties'][param_name] = {
                    'type': param.get('type', 'string'),
                    'description': enhancement.enhanced_description if enhancement else param.get('description', ''),
                }
                if param.get('required', False):
                    parameters['required'].append(param_name)
        
        # Add query parameters
        for param in endpoint_data.get('parameters', []):
            if param['in'] == 'query':
                param_name = param['name']
                enhancement = enhancements.get(param_name)
                
                parameters['properties'][param_name] = {
                    'type': param.get('type', 'string'),
                    'description': enhancement.enhanced_description if enhancement else param.get('description', ''),
                }
                if param.get('required', False):
                    parameters['required'].append(param_name)
        
        # Add request body parameters if present
        request_body = endpoint_data.get('request_body', {})
        if request_body and request_body.get('schema'):
            self._add_enhanced_request_body_parameters(parameters, request_body['schema'], enhancements)
        
        return parameters
    
    def _add_enhanced_request_body_parameters(self, parameters: Dict[str, Any], schema: Dict[str, Any], enhancements: Dict):
        """
        Add request body parameters with enhanced descriptions to the parameters structure
        """
        if schema.get('type') == 'object':
            properties = schema.get('properties', {})
            required = schema.get('required', [])
            
            for prop_name, prop_schema in properties.items():
                enhancement = enhancements.get(prop_name)
                
                parameters['properties'][prop_name] = {
                    'type': prop_schema.get('type', 'string'),
                    'description': enhancement.enhanced_description if enhancement else prop_schema.get('description', ''),
                }
                if prop_name in required:
                    parameters['required'].append(prop_name)
    
    def _generate_tool_info(self, endpoint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate tool information for a single endpoint
        """
        # Generate tool name based on operation_id or path/method
        tool_name = self._generate_tool_name(endpoint)
        
        return {
            'name': tool_name,
            'description': endpoint.get('description') or endpoint.get('summary', ''),
            'method': endpoint['method'],
            'path': endpoint['path'],
            'operation_id': endpoint.get('operation_id', ''),
            'parameters': self._generate_tool_parameters(endpoint),
            'request_body': endpoint.get('request_body', {}),
            'responses': endpoint.get('responses', {}),
            'tags': endpoint.get('tags', []),
        }
    
    def _generate_tool_name(self, endpoint: Dict[str, Any]) -> str:
        """
        Generate a meaningful tool name for the endpoint
        """
        operation_id = endpoint.get('operation_id', '')
        if operation_id:
            # Convert camelCase to PascalCase and add 'Tool' suffix
            return f"{operation_id[0].upper()}{operation_id[1:]}Tool"
        
        # Fallback: generate from method and path
        method = endpoint['method'].lower()
        path = endpoint['path']
        
        # Extract resource name from path
        path_parts = [part for part in path.split('/') if part and not part.startswith('{')]
        resource = path_parts[-1] if path_parts else 'resource'
        
        # Capitalize first letter and add method prefix
        method_prefix = method.capitalize()
        resource_name = resource.capitalize()
        
        return f"{method_prefix}{resource_name}Tool"
    
    def _generate_tool_parameters(self, endpoint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate tool parameters structure
        """
        parameters = {
            'type': 'object',
            'properties': {},
            'required': []
        }
        
        # Add path parameters
        for param in endpoint.get('parameters', []):
            if param['in'] == 'path':
                parameters['properties'][param['name']] = {
                    'type': param.get('type', 'string'),
                    'description': param.get('description', ''),
                }
                if param.get('required', False):
                    parameters['required'].append(param['name'])
        
        # Add query parameters
        for param in endpoint.get('parameters', []):
            if param['in'] == 'query':
                parameters['properties'][param['name']] = {
                    'type': param.get('type', 'string'),
                    'description': param.get('description', ''),
                }
                if param.get('required', False):
                    parameters['required'].append(param['name'])
        
        # Add request body parameters if present
        request_body = endpoint.get('request_body', {})
        if request_body and request_body.get('schema'):
            self._add_request_body_parameters(parameters, request_body['schema'])
        
        return parameters
    
    def _add_request_body_parameters(self, parameters: Dict[str, Any], schema: Dict[str, Any]):
        """
        Add request body parameters to the parameters structure
        """
        if schema.get('type') == 'object':
            properties = schema.get('properties', {})
            required = schema.get('required', [])
            
            for prop_name, prop_schema in properties.items():
                parameters['properties'][prop_name] = {
                    'type': prop_schema.get('type', 'string'),
                    'description': prop_schema.get('description', ''),
                }
                if prop_name in required:
                    parameters['required'].append(prop_name)
    
    def save_yaml_file(self, file_path: str) -> str:
        """
        Save the generated YAML structure to a file
        """
        yaml_structure = self.generate_yaml_structure()
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(yaml_structure, f, default_flow_style=False, allow_unicode=True)
            
            return file_path
        except Exception as e:
            raise Exception(f"Failed to save YAML file: {str(e)}")


class ToolClassGenerator:
    """
    Generates Python tool classes dynamically from YAML files
    """
    
    def __init__(self, yaml_file_path: str):
        self.yaml_file_path = yaml_file_path
        self.yaml_data = None
    
    def load_yaml_data(self) -> Dict[str, Any]:
        """
        Load YAML data from file
        """
        try:
            with open(self.yaml_file_path, 'r', encoding='utf-8') as f:
                self.yaml_data = yaml.safe_load(f)
            return self.yaml_data
        except Exception as e:
            raise Exception(f"Failed to load YAML file: {str(e)}")
    
    def generate_tool_classes_code(self) -> str:
        """
        Generate Python code for all tool classes
        """
        if not self.yaml_data:
            self.load_yaml_data()
        
        code_parts = []
        
        # Add imports
        code_parts.append(self._generate_imports())
        
        # Add API configuration class
        code_parts.append(self._generate_config_class())
        
        # Generate tool classes
        for tool in self.yaml_data.get('tools', []):
            tool_class_code = self._generate_tool_class(tool)
            code_parts.append(tool_class_code)
        
        return '\n\n'.join(code_parts)
    
    def _generate_imports(self) -> str:
        """
        Generate import statements
        """
        return """from core.tools_base import RestApiTool, RestApiParameters, Property, ToolType
from typing import ClassVar, Annotated, Optional
import requests
import json"""
    
    def _generate_config_class(self) -> str:
        """
        Generate API configuration class
        """
        api_info = self.yaml_data.get('api_info', {})
        
        return f"""
class APIConfig:
    def __init__(self):
        self.base_url = "{api_info.get('base_url', '')}"
        self.auth_type = "{api_info.get('auth_type', 'none')}"
        self.auth_config = {json.dumps(api_info.get('auth_config', {}), indent=8)}
        self.client_key = None
        self.entity_key = None
        self.user_key = None"""
    
    def _generate_tool_class(self, tool: Dict[str, Any]) -> str:
        """
        Generate a single tool class
        """
        class_name = tool['name']
        description = tool.get('description', '')
        method = tool.get('method', 'GET')
        path = tool.get('path', '')
        parameters = tool.get('parameters', {})
        
        # Generate parameters method
        params_code = self._generate_parameters_method(parameters)
        
        # Generate invoke method
        invoke_code = self._generate_invoke_method(tool)
        
        return f"""
class {class_name}(RestApiTool):
    For: ClassVar[Annotated[ToolType, ToolType.FOR_SELF]] = ToolType.FOR_SELF
    api_path = "{path}"
    
    def get_parameters(self):
{params_code}
    
    async def invoke(self, {self._generate_invoke_parameters(parameters)}, id=None):
        \"\"\"
        {description}
        \"\"\"
{invoke_code}"""
    
    def _generate_parameters_method(self, parameters: Dict[str, Any]) -> str:
        """
        Generate the get_parameters method code
        """
        properties = parameters.get('properties', {})
        required = parameters.get('required', [])
        
        if not properties:
            return "        return RestApiParameters()"
        
        extra_properties = {}
        extra_required = []
        
        for prop_name, prop_info in properties.items():
            # Skip base parameters (client_key, entity_key, user_key)
            if prop_name not in ['client_key', 'entity_key', 'user_key']:
                extra_properties[prop_name] = {
                    'type': prop_info.get('type', 'string'),
                    'description': prop_info.get('description', '')
                }
                if prop_name in required:
                    extra_required.append(prop_name)
        
        if not extra_properties:
            return "        return RestApiParameters()"
        
        code_lines = ["        extra_properties = {"]
        for prop_name, prop_info in extra_properties.items():
            code_lines.append(f'            "{prop_name}": Property(type="{prop_info["type"]}", description="{prop_info["description"]}"),')
        code_lines.append("        }")
        
        if extra_required:
            code_lines.append(f"        extra_required = {extra_required}")
            code_lines.append("        return RestApiParameters(extra_properties, extra_required)")
        else:
            code_lines.append("        return RestApiParameters(extra_properties)")
        
        return '\n'.join(code_lines)
    
    def _generate_invoke_parameters(self, parameters: Dict[str, Any]) -> str:
        """
        Generate parameters for the invoke method signature
        """
        properties = parameters.get('properties', {})
        required = parameters.get('required', [])
        
        params = []
        
        # Add required parameters first
        for prop_name in required:
            if prop_name not in ['client_key', 'entity_key', 'user_key']:
                params.append(prop_name)
        
        # Add optional parameters
        for prop_name in properties:
            if prop_name not in required and prop_name not in ['client_key', 'entity_key', 'user_key']:
                params.append(f"{prop_name}=None")
        
        return ", ".join(params)
    
    def _generate_invoke_method(self, tool: Dict[str, Any]) -> str:
        """
        Generate the invoke method implementation
        """
        method = tool.get('method', 'GET').upper()
        path = tool.get('path', '')
        parameters = tool.get('parameters', {})
        
        code_lines = [
            "        url = self.get_api_url(self.api_path)",
            "        data = {",
            '            "client_key": self.client_key,',
            '            "entity_key": self.entity_key,',
            '            "user_key": self.user_key,',
            "        }"
        ]
        
        # Add parameter assignments
        properties = parameters.get('properties', {})
        for prop_name in properties:
            if prop_name not in ['client_key', 'entity_key', 'user_key']:
                code_lines.append(f'        if {prop_name} is not None:')
                code_lines.append(f'            data["{prop_name}"] = {prop_name}')
        
        # Add request call
        if method in ['POST', 'PUT', 'PATCH']:
            code_lines.append("        ")
            code_lines.append(f'        res = requests.{method.lower()}(url, data=data)')
        else:
            code_lines.append("        ")
            code_lines.append(f'        res = requests.{method.lower()}(url, params=data)')
        
        code_lines.extend([
            "        response = res.json()",
            "        return self.to_jsonrpc(response, id=id)"
        ])
        
        return '\n'.join(code_lines)
    
    def save_tool_classes_file(self, file_path: str) -> str:
        """
        Save the generated tool classes to a Python file
        """
        code = self.generate_tool_classes_code()
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
            return file_path
        except Exception as e:
            raise Exception(f"Failed to save tool classes file: {str(e)}")
