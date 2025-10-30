"""
LLM Service for generating API endpoint descriptions
"""
import logging
from typing import Dict, List, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class LLMDescriptionService:
    """
    Service for generating enhanced descriptions using LLM
    """
    
    def __init__(self):
        self.client = None
        self.use_azure = False
        self.setup_client()
    
    def setup_client(self):
        """Setup OpenAI or Azure OpenAI client if API key is available"""
        try:
            # Check for Azure OpenAI configuration first
            azure_endpoint = getattr(settings, 'AZURE_OPENAI_ENDPOINT', None)
            azure_api_key = getattr(settings, 'AZURE_OPENAI_API_KEY', None)
            azure_deployment = getattr(settings, 'AZURE_OPENAI_DEPLOYMENT_NAME', None)
            
            if azure_endpoint and azure_api_key and azure_deployment:
                try:
                    from openai import AzureOpenAI
                    api_version = getattr(settings, 'AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
                    self.client = AzureOpenAI(
                        api_key=azure_api_key,
                        api_version=api_version,
                        azure_endpoint=azure_endpoint
                    )
                    self.use_azure = True
                    self.deployment_name = azure_deployment
                    logger.info(f"Azure OpenAI client configured successfully with deployment: {azure_deployment}")
                    return
                except ImportError:
                    logger.warning("Azure OpenAI not available, trying regular OpenAI")
            
            # Fallback to regular OpenAI
            openai_api_key = getattr(settings, 'OPENAI_API_KEY', None)
            if openai_api_key:
                try:
                    from openai import OpenAI
                    self.client = OpenAI(api_key=openai_api_key)
                    self.use_azure = False
                    logger.info("OpenAI client configured successfully")
                    return
                except ImportError:
                    logger.error("OpenAI library not available")
            
            logger.warning("No valid OpenAI configuration found")
            
        except Exception as e:
            logger.error(f"Failed to setup OpenAI client: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if LLM service is available"""
        if self.use_azure:
            return (self.client is not None and 
                   hasattr(settings, 'AZURE_OPENAI_ENDPOINT') and
                   hasattr(settings, 'AZURE_OPENAI_API_KEY') and
                   hasattr(settings, 'AZURE_OPENAI_DEPLOYMENT_NAME'))
        else:
            return self.client is not None and hasattr(settings, 'OPENAI_API_KEY')
    
    def generate_endpoint_description(self, endpoint_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate enhanced description for an API endpoint
        
        Args:
            endpoint_data: Dictionary containing endpoint information
            
        Returns:
            Dictionary with 'summary' and 'description' keys
        """
        if not self.is_available():
            return self._fallback_description(endpoint_data)
        
        try:
            prompt = self._create_endpoint_prompt(endpoint_data)
            
            # Use the appropriate model based on Azure vs OpenAI
            model = self.deployment_name if self.use_azure else "gpt-3.5-turbo"
            
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            result = response.choices[0].message.content.strip()
            return self._parse_llm_response(result)
            
        except Exception as e:
            logger.error(f"Failed to generate LLM description: {str(e)}")
            return self._fallback_description(endpoint_data)
    
    def generate_parameter_description(self, param_data: Dict[str, Any], endpoint_context: Dict[str, Any]) -> str:
        """
        Generate enhanced description for a parameter
        
        Args:
            param_data: Parameter information
            endpoint_context: Context about the endpoint
            
        Returns:
            Enhanced parameter description
        """
        if not self.is_available():
            return self._fallback_parameter_description(param_data)
        
        try:
            prompt = self._create_parameter_prompt(param_data, endpoint_context)
            
            # Use the appropriate model based on Azure vs OpenAI
            model = self.deployment_name if self.use_azure else "gpt-3.5-turbo"
            
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an API documentation expert. Generate clear, concise parameter descriptions."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate parameter description: {str(e)}")
            return self._fallback_parameter_description(param_data)
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for endpoint description generation"""
        return """You are an expert API documentation writer. Given API endpoint information, generate clear, professional descriptions that would be helpful for developers using this API.

Return your response in this exact format:
SUMMARY: [A brief, clear summary in one sentence]
DESCRIPTION: [A detailed description explaining what this endpoint does, what it accepts, and what it returns]

Focus on:
- What the endpoint does
- What data it expects
- What it returns
- Any important usage notes
- Keep it professional and clear"""
    
    def _create_endpoint_prompt(self, endpoint_data: Dict[str, Any]) -> str:
        """Create a prompt for endpoint description generation"""
        method = endpoint_data.get('method', 'GET')
        path = endpoint_data.get('path', '')
        summary = endpoint_data.get('summary', '')
        description = endpoint_data.get('description', '')
        parameters = endpoint_data.get('parameters', [])
        
        param_info = []
        if parameters:
            for param in parameters[:5]:  # Limit to first 5 parameters
                param_info.append(f"- {param.get('name', 'unknown')} ({param.get('type', 'string')}): {param.get('description', 'no description')}")
        
        params_text = "\n".join(param_info) if param_info else "No parameters"
        
        return f"""
API Endpoint: {method} {path}
Current Summary: {summary or 'No summary provided'}
Current Description: {description or 'No description provided'}

Parameters:
{params_text}

Please generate an enhanced summary and description for this API endpoint.
"""
    
    def _create_parameter_prompt(self, param_data: Dict[str, Any], endpoint_context: Dict[str, Any]) -> str:
        """Create a prompt for parameter description generation"""
        param_name = param_data.get('name', 'unknown')
        param_type = param_data.get('type', 'string')
        current_desc = param_data.get('description', '')
        required = param_data.get('required', False)
        
        endpoint_path = endpoint_context.get('path', '')
        endpoint_method = endpoint_context.get('method', 'GET')
        
        return f"""
API Endpoint: {endpoint_method} {endpoint_path}
Parameter: {param_name}
Type: {param_type}
Required: {"Yes" if required else "No"}
Current Description: {current_desc or 'No description provided'}

Generate a clear, helpful description for this parameter. Focus on what it represents, its purpose, and any format requirements.
Respond with just the description, no additional formatting.
"""
    
    def _parse_llm_response(self, response: str) -> Dict[str, str]:
        """Parse LLM response into summary and description"""
        result = {'summary': '', 'description': ''}
        
        try:
            lines = response.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('SUMMARY:'):
                    result['summary'] = line.replace('SUMMARY:', '').strip()
                elif line.startswith('DESCRIPTION:'):
                    result['description'] = line.replace('DESCRIPTION:', '').strip()
            
            # If parsing failed, use the whole response as description
            if not result['summary'] and not result['description']:
                result['description'] = response
                result['summary'] = response.split('.')[0] if '.' in response else response[:100]
                
        except Exception:
            result['description'] = response
            result['summary'] = response[:100]
        
        return result
    
    def _fallback_description(self, endpoint_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate a basic description when LLM is not available"""
        method = endpoint_data.get('method', 'GET')
        path = endpoint_data.get('path', '')
        summary = endpoint_data.get('summary', '')
        description = endpoint_data.get('description', '')
        
        if summary or description:
            return {
                'summary': summary or description.split('.')[0] if description else '',
                'description': description or summary or ''
            }
        
        # Generate basic description based on method and path
        action_map = {
            'GET': 'Retrieve',
            'POST': 'Create',
            'PUT': 'Update',
            'DELETE': 'Delete',
            'PATCH': 'Partially update'
        }
        
        action = action_map.get(method.upper(), 'Process')
        resource = path.split('/')[-1] if '/' in path else 'resource'
        
        basic_summary = f"{action} {resource} information"
        basic_description = f"This endpoint allows you to {action.lower()} {resource} data using the {method} method."
        
        return {
            'summary': basic_summary,
            'description': basic_description
        }
    
    def _fallback_parameter_description(self, param_data: Dict[str, Any]) -> str:
        """Generate basic parameter description when LLM is not available"""
        param_name = param_data.get('name', 'parameter')
        param_type = param_data.get('type', 'string')
        current_desc = param_data.get('description', '')
        
        if current_desc:
            return current_desc
        
        # Generate basic description
        type_desc = {
            'string': 'text value',
            'integer': 'numeric value',
            'boolean': 'true/false value',
            'array': 'list of values',
            'object': 'JSON object'
        }
        
        return f"The {param_name} {type_desc.get(param_type, 'parameter')} for this request."


# Global instance
llm_service = LLMDescriptionService()