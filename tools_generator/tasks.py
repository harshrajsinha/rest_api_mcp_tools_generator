"""
Celery tasks for Tools Generator
"""
from celery import shared_task
from django.conf import settings
from pathlib import Path
import logging

from core.models import APIConfiguration, GeneratedYAMLFile, APIEndpoint
from .services import SwaggerParser, YAMLGenerator

logger = logging.getLogger(__name__)


@shared_task
def generate_yaml_from_swagger(api_config_id):
    """
    Background task to generate YAML file from Swagger specification
    """
    try:
        api_config = APIConfiguration.objects.get(id=api_config_id)
        
        # Create or get the YAML file record
        yaml_file, created = GeneratedYAMLFile.objects.get_or_create(
            api_configuration=api_config,
            defaults={
                'file_name': f"{api_config.name.lower().replace(' ', '_')}_tools.yaml",
                'generation_status': 'processing'
            }
        )
        
        # Ensure file name is set even for existing records
        if not yaml_file.file_name or yaml_file.file_name == '':
            yaml_file.file_name = f"{api_config.name.lower().replace(' ', '_')}_tools.yaml"
        
        yaml_file.generation_status = 'processing'
        yaml_file.error_message = ''
        yaml_file.save()
        
        # Parse Swagger specification
        parser = SwaggerParser(api_config.swagger_url, api_config.api_base_url)
        spec = parser.fetch_swagger_spec()
        endpoints = parser.extract_endpoints()
        
        # Generate YAML structure
        api_config_dict = {
            'name': api_config.name,
            'description': api_config.description,
            'api_base_url': api_config.api_base_url,
            'swagger_url': api_config.swagger_url,
            'auth_type': api_config.auth_type,
            'auth_config': api_config.auth_config,
        }
        
        generator = YAMLGenerator(api_config_dict, endpoints)
        
        # Create YAML files directory if it doesn't exist
        yaml_dir = settings.YAML_FILES_DIR
        yaml_dir.mkdir(exist_ok=True)
        
        # Generate file path
        file_path = yaml_dir / yaml_file.file_name
        
        # Save YAML file
        generator.save_yaml_file(str(file_path))
        
        # Update YAML file record
        yaml_file.file_path = str(file_path)
        yaml_file.tools_count = len(endpoints)
        yaml_file.generation_status = 'completed'
        yaml_file.save()
        
        # Create endpoint records
        for endpoint_data in endpoints:
            APIEndpoint.objects.update_or_create(
                yaml_file=yaml_file,
                path=endpoint_data['path'],
                method=endpoint_data['method'],
                defaults={
                    'operation_id': endpoint_data.get('operation_id', ''),
                    'summary': endpoint_data.get('summary', ''),
                    'description': endpoint_data.get('description', ''),
                    'parameters': endpoint_data.get('parameters', []),
                    'responses': endpoint_data.get('responses', {}),
                    'tool_name': generator._generate_tool_name(endpoint_data),
                }
            )
        
        logger.info(f"Successfully generated YAML file for API config {api_config.name}")
        return {
            'status': 'success',
            'yaml_file_id': yaml_file.id,
            'tools_count': len(endpoints)
        }
        
    except APIConfiguration.DoesNotExist:
        logger.error(f"API Configuration with id {api_config_id} not found")
        return {'status': 'error', 'message': 'API Configuration not found'}
    
    except Exception as e:
        logger.error(f"Error generating YAML file: {str(e)}")
        
        # Update the YAML file record with error status
        try:
            yaml_file = GeneratedYAMLFile.objects.get(api_configuration_id=api_config_id)
            yaml_file.generation_status = 'failed'
            yaml_file.error_message = str(e)
            yaml_file.save()
        except GeneratedYAMLFile.DoesNotExist:
            pass
        
        return {'status': 'error', 'message': str(e)}


@shared_task
def regenerate_yaml_file(yaml_file_id):
    """
    Task to regenerate an existing YAML file
    """
    try:
        yaml_file = GeneratedYAMLFile.objects.get(id=yaml_file_id)
        return generate_yaml_from_swagger(yaml_file.api_config.id)
        
    except GeneratedYAMLFile.DoesNotExist:
        logger.error(f"YAML file with id {yaml_file_id} not found")
        return {'status': 'error', 'message': 'YAML file not found'}


@shared_task
def cleanup_old_files():
    """
    Task to cleanup old generated files
    """
    # This task can be run periodically to clean up old files
    # Implementation depends on your cleanup requirements
    pass
