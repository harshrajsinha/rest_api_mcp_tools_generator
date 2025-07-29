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
            # Start the background task
            task = generate_yaml_from_swagger.delay(api_config.id)
            
            return Response({
                'status': 'success',
                'message': 'YAML generation started',
                'task_id': task.id
            })
        
        except Exception as e:
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
