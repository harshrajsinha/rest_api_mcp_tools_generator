"""
REST API views for Tools Generator
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings
from django.http import JsonResponse, FileResponse
from django.contrib.auth.models import User
import os
import json
import yaml
import logging
from pathlib import Path

from core.models import (
    APIConfiguration, 
    GeneratedYAMLFile, 
    APIEndpoint, 
    ParameterEnhancement
)
from .serializers import (
    APIConfigurationSerializer,
    GeneratedYAMLFileSerializer,
    APIEndpointSerializer,
    ParameterEnhancementSerializer,
    SwaggerTestSerializer
)
from .services import SwaggerParser, YAMLGenerator, ToolClassGenerator
from .tasks import generate_yaml_from_swagger

logger = logging.getLogger(__name__)


class APIConfigurationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing API configurations
    """
    queryset = APIConfiguration.objects.all()
    serializer_class = APIConfigurationSerializer
    permission_classes = [AllowAny]
    
    def perform_create(self, serializer):
        # Get or create a default user for development
        user, created = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com'})
        serializer.save(created_by=user)
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """
        Test the API configuration by fetching the swagger spec
        """
        api_config = self.get_object()
        
        try:
            parser = SwaggerParser(api_config.swagger_url, api_config.api_base_url)
            spec = parser.fetch_swagger_spec()
            
            return Response({
                'status': 'success',
                'message': 'Successfully connected to API',
                'swagger_info': {
                    'title': spec.get('info', {}).get('title', ''),
                    'version': spec.get('info', {}).get('version', ''),
                    'description': spec.get('info', {}).get('description', ''),
                    'paths_count': len(spec.get('paths', {}))
                }
            })
        
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def generate_yaml(self, request, pk=None):
        """
        Generate YAML file from the API configuration
        """
        api_config = self.get_object()
        
        try:
            # Try to use Celery first
            try:
                task = generate_yaml_from_swagger.delay(api_config.id)
                
                return Response({
                    'status': 'success',
                    'message': 'YAML generation started (background task)',
                    'task_id': task.id
                })
            except Exception as celery_error:
                # If Celery fails, run synchronously
                logger.warning(f"Celery not available, running synchronously: {celery_error}")
                
                # Import here to avoid circular imports
                from .tasks import generate_yaml_from_swagger
                
                # Run the task function directly (synchronously)
                result = generate_yaml_from_swagger(api_config.id)
                
                if result.get('status') == 'success':
                    return Response({
                        'status': 'success',
                        'message': 'YAML generation completed successfully',
                        'yaml_file_id': result.get('yaml_file_id'),
                        'tools_count': result.get('tools_count')
                    })
                else:
                    return Response({
                        'status': 'error',
                        'message': result.get('message', 'Unknown error occurred')
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        except Exception as e:
            logger.error(f"Error generating YAML: {e}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GeneratedYAMLFileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing generated YAML files
    """
    queryset = GeneratedYAMLFile.objects.all()
    serializer_class = GeneratedYAMLFileSerializer
    permission_classes = [AllowAny]
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """
        Download the generated YAML file
        """
        yaml_file = self.get_object()
        
        if not os.path.exists(yaml_file.file_path):
            return Response({
                'error': 'File not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        return FileResponse(
            open(yaml_file.file_path, 'rb'),
            as_attachment=True,
            filename=yaml_file.file_name
        )
    
    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Preview the YAML file content
        """
        yaml_file = self.get_object()
        
        try:
            with open(yaml_file.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return Response({
                'content': content,
                'file_name': yaml_file.file_name
            })
        
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def regenerate_with_enhancements(self, request, pk=None):
        """
        Regenerate YAML file using enhanced descriptions
        """
        yaml_file = self.get_object()
        api_config = yaml_file.api_configuration
        
        try:
            # Parse the original Swagger spec again
            parser = SwaggerParser(api_config.swagger_url, api_config.api_base_url)
            spec = parser.fetch_swagger_spec()
            endpoints = parser.extract_endpoints()
            
            # Create API config dictionary
            api_config_dict = {
                'name': api_config.name,
                'description': api_config.description,
                'api_base_url': api_config.api_base_url,
                'swagger_url': api_config.swagger_url,
                'auth_type': api_config.auth_type,
                'auth_config': api_config.auth_config,
            }
            
            # Generate enhanced YAML
            generator = YAMLGenerator(api_config_dict, endpoints, yaml_file)
            enhanced_yaml = generator.generate_enhanced_yaml_structure()
            
            # Save the enhanced YAML file
            yaml_dir = Path(settings.BASE_DIR) / 'generated_yaml_files'
            yaml_dir.mkdir(exist_ok=True)
            
            # Create new filename with _enhanced suffix
            base_name = yaml_file.file_name.replace('.yaml', '').replace('.yml', '')
            enhanced_filename = f"{base_name}_enhanced.yaml"
            enhanced_file_path = yaml_dir / enhanced_filename
            
            with open(enhanced_file_path, 'w', encoding='utf-8') as f:
                yaml.dump(enhanced_yaml, f, default_flow_style=False, allow_unicode=True)
            
            # Update the YAML file record
            yaml_file.yaml_content = yaml.dump(enhanced_yaml, default_flow_style=False, allow_unicode=True)
            yaml_file.file_name = enhanced_filename
            yaml_file.file_path = str(enhanced_file_path)
            yaml_file.save()
            
            return Response({
                'status': 'success',
                'message': 'YAML file regenerated with enhancements successfully',
                'file_name': enhanced_filename,
                'file_path': str(enhanced_file_path)
            })
        
        except Exception as e:
            logger.error(f"Error regenerating YAML with enhancements: {e}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def generate_tools(self, request, pk=None):
        """
        Generate Python tool classes from the YAML file
        """
        yaml_file = self.get_object()
        
        try:
            generator = ToolClassGenerator(yaml_file.file_path)
            
            # Generate output file path
            tools_dir = settings.GENERATED_TOOLS_DIR
            tools_dir.mkdir(exist_ok=True)
            
            output_file = tools_dir / f"{yaml_file.api_config.name.lower().replace(' ', '_')}_tools.py"
            
            # Generate and save tool classes
            generated_file = generator.save_tool_classes_file(str(output_file))
            
            return Response({
                'status': 'success',
                'message': 'Tool classes generated successfully',
                'file_path': generated_file
            })
        
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class APIEndpointViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing API endpoints
    """
    queryset = APIEndpoint.objects.all()
    serializer_class = APIEndpointSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        yaml_file_id = self.request.query_params.get('yaml_file', None)
        if yaml_file_id:
            queryset = queryset.filter(yaml_file_id=yaml_file_id)
        return queryset
    
    @action(detail=True, methods=['post'])
    def enhance_description(self, request, pk=None):
        """
        Update the enhanced description for an endpoint
        """
        endpoint = self.get_object()
        enhanced_description = request.data.get('enhanced_description', '')
        enhanced_summary = request.data.get('enhanced_summary', '')
        
        endpoint.enhanced_description = enhanced_description
        endpoint.enhanced_summary = enhanced_summary
        endpoint.save()
        
        return Response({
            'status': 'success',
            'message': 'Description enhanced successfully'
        })


class ParameterEnhancementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing parameter enhancements
    """
    queryset = ParameterEnhancement.objects.all()
    serializer_class = ParameterEnhancementSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        endpoint_id = self.request.query_params.get('endpoint', None)
        if endpoint_id:
            queryset = queryset.filter(endpoint_id=endpoint_id)
        return queryset


class SwaggerTestView(viewsets.ViewSet):
    """
    ViewSet for testing Swagger URLs without saving configuration
    """
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'])
    def test_swagger_url(self, request):
        """
        Test a Swagger URL and return basic information
        """
        serializer = SwaggerTestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        swagger_url = serializer.validated_data['swagger_url']
        api_base_url = serializer.validated_data.get('api_base_url', '')
        
        try:
            parser = SwaggerParser(swagger_url, api_base_url)
            spec = parser.fetch_swagger_spec()
            endpoints = parser.extract_endpoints()
            
            return Response({
                'status': 'success',
                'swagger_info': {
                    'title': spec.get('info', {}).get('title', ''),
                    'version': spec.get('info', {}).get('version', ''),
                    'description': spec.get('info', {}).get('description', ''),
                    'host': spec.get('host', ''),
                    'base_path': spec.get('basePath', '/'),
                    'schemes': spec.get('schemes', []),
                    'paths_count': len(spec.get('paths', {})),
                    'endpoints_count': len(endpoints)
                },
                'endpoints_preview': endpoints[:5]  # Show first 5 endpoints as preview
            })
        
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class APIEndpointViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing and enhancing API endpoints
    """
    queryset = APIEndpoint.objects.all()
    serializer_class = APIEndpointSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        from django.db import models
        queryset = APIEndpoint.objects.all()
        yaml_file_id = self.request.query_params.get('yaml_file', None)
        if yaml_file_id:
            queryset = queryset.filter(yaml_file_id=yaml_file_id)
        return queryset.select_related('yaml_file').prefetch_related('parameter_enhancements')
    
    @action(detail=True, methods=['put'])
    def enhance_description(self, request, pk=None):
        """
        Update enhanced description and summary for an endpoint
        """
        endpoint = self.get_object()
        
        enhanced_description = request.data.get('enhanced_description', '')
        enhanced_summary = request.data.get('enhanced_summary', '')
        
        endpoint.enhanced_description = enhanced_description
        endpoint.enhanced_summary = enhanced_summary
        endpoint.save()
        
        return Response({
            'status': 'success',
            'message': 'Endpoint description enhanced successfully',
            'data': self.get_serializer(endpoint).data
        })
    
    @action(detail=True, methods=['post'])
    def enhance_parameter(self, request, pk=None):
        """
        Add or update enhanced parameter description
        """
        endpoint = self.get_object()
        parameter_name = request.data.get('parameter_name')
        enhanced_description = request.data.get('enhanced_description')
        
        if not parameter_name or not enhanced_description:
            return Response({
                'status': 'error',
                'message': 'parameter_name and enhanced_description are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Find the parameter in endpoint parameters to get original info
        original_param = None
        for param in endpoint.parameters:
            if param.get('name') == parameter_name:
                original_param = param
                break
        
        if not original_param:
            return Response({
                'status': 'error',
                'message': f'Parameter {parameter_name} not found in endpoint'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create or update parameter enhancement
        param_enhancement, created = ParameterEnhancement.objects.update_or_create(
            endpoint=endpoint,
            parameter_name=parameter_name,
            defaults={
                'enhanced_description': enhanced_description,
                'original_description': original_param.get('description', ''),
                'parameter_type': original_param.get('type', 'string'),
                'is_required': original_param.get('required', False)
            }
        )
        
        return Response({
            'status': 'success',
            'message': f'Parameter {parameter_name} enhanced successfully',
            'data': ParameterEnhancementSerializer(param_enhancement).data
        })
    
    @action(detail=False, methods=['get'])
    def enhancement_summary(self, request):
        """
        Get enhancement progress summary for a YAML file
        """
        from django.db import models
        yaml_file_id = request.query_params.get('yaml_file')
        if not yaml_file_id:
            return Response({
                'status': 'error',
                'message': 'yaml_file parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            yaml_file = GeneratedYAMLFile.objects.get(id=yaml_file_id)
            endpoints = APIEndpoint.objects.filter(yaml_file=yaml_file)
            
            total_endpoints = endpoints.count()
            enhanced_endpoints = endpoints.filter(
                models.Q(enhanced_description__isnull=False) & 
                ~models.Q(enhanced_description='')
            ).count()
            
            total_parameters = sum(len(ep.parameters) for ep in endpoints)
            enhanced_parameters = ParameterEnhancement.objects.filter(
                endpoint__yaml_file=yaml_file
            ).count()
            
            return Response({
                'status': 'success',
                'data': {
                    'yaml_file': yaml_file.file_name,
                    'total_endpoints': total_endpoints,
                    'enhanced_endpoints': enhanced_endpoints,
                    'total_parameters': total_parameters,
                    'enhanced_parameters': enhanced_parameters,
                    'endpoints_progress': f"{enhanced_endpoints}/{total_endpoints}",
                    'parameters_progress': f"{enhanced_parameters}/{total_parameters}",
                }
            })
            
        except GeneratedYAMLFile.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'YAML file not found'
            }, status=status.HTTP_404_NOT_FOUND)


class ParameterEnhancementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing parameter enhancements
    """
    queryset = ParameterEnhancement.objects.all()
    serializer_class = ParameterEnhancementSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = ParameterEnhancement.objects.all()
        endpoint_id = self.request.query_params.get('endpoint', None)
        if endpoint_id:
            queryset = queryset.filter(endpoint_id=endpoint_id)
        return queryset.select_related('endpoint')
