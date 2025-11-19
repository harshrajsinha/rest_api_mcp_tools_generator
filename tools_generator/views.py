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
    
    @action(detail=True, methods=['post'])
    def generate_installer(self, request, pk=None):
        """
        Generate and download auto-installer package from YAML file
        
        Creates a ZIP containing:
        - MCP server files (YAML + Python)
        - install.bat (Windows auto-installer)
        - install.sh (macOS/Linux auto-installer)
        - update_claude_config.py (cross-platform config updater)
        - requirements.txt
        - README.md with instructions
        """
        from mcp_server.installer_utils import create_installer_package
        from django.http import HttpResponse
        
        yaml_file = self.get_object()
        
        try:
            # Parse YAML to get server name
            with open(yaml_file.file_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f.read())
            
            server_name = yaml_data.get('name', f'mcp_server_{pk}')
            
            # Create installer package - pass file path, not content
            zip_path = create_installer_package(yaml_file.file_path, server_name)
            
            # Return the ZIP file
            with open(zip_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/zip')
                response['Content-Disposition'] = f'attachment; filename="{server_name}_installer.zip"'
                
            # Clean up temp file
            import threading
            def cleanup():
                import time
                time.sleep(5)  # Give time for download to complete
                try:
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                except:
                    pass
            
            threading.Thread(target=cleanup, daemon=True).start()
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating installer: {e}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
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
    
    @action(detail=False, methods=['get'])
    def endpoints_with_descriptions(self, request):
        """
        Get all endpoints for a YAML file with their current descriptions from both YAML and database
        """
        yaml_file_id = request.query_params.get('yaml_file')
        if not yaml_file_id:
            return Response({
                'status': 'error',
                'message': 'yaml_file parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            yaml_file = GeneratedYAMLFile.objects.get(id=yaml_file_id)
            
            # Load the YAML file to get original descriptions
            yaml_content = yaml_file.get_yaml_content()
            
            # If yaml_content is empty, try reading from file path
            if not yaml_content and yaml_file.file_path:
                try:
                    import yaml
                    from pathlib import Path
                    file_path = Path(yaml_file.file_path)
                    if file_path.exists():
                        with open(file_path, 'r', encoding='utf-8') as f:
                            yaml_content = yaml.safe_load(f)
                except Exception as e:
                    logger.error(f"Error reading YAML file from path: {e}")
                    yaml_content = {}
            
            yaml_endpoints = yaml_content.get('tools', [])
            
            # Get database endpoints
            db_endpoints = APIEndpoint.objects.filter(yaml_file=yaml_file).prefetch_related('parameter_enhancements')
            db_endpoints_dict = {f"{ep.method}:{ep.path}": ep for ep in db_endpoints}
            
            endpoints_data = []
            
            for yaml_endpoint in yaml_endpoints:
                endpoint_key = f"{yaml_endpoint.get('method', '').upper()}:{yaml_endpoint.get('path', '')}"
                db_endpoint = db_endpoints_dict.get(endpoint_key)
                
                # Get parameter enhancements
                param_enhancements = {}
                if db_endpoint:
                    for pe in db_endpoint.parameter_enhancements.all():
                        param_enhancements[pe.parameter_name] = {
                            'enhanced_description': pe.enhanced_description
                        }
                
                endpoint_data = {
                    'id': db_endpoint.id if db_endpoint else None,
                    'method': yaml_endpoint.get('method', '').upper(),
                    'path': yaml_endpoint.get('path', ''),
                    'original_summary': yaml_endpoint.get('summary', ''),
                    'original_description': yaml_endpoint.get('description', ''),
                    'enhanced_summary': db_endpoint.enhanced_summary if db_endpoint else '',
                    'enhanced_description': db_endpoint.enhanced_description if db_endpoint else '',
                    'parameters': yaml_endpoint.get('parameters', {}),
                    'parameter_enhancements': param_enhancements,
                    'has_enhancement': bool(db_endpoint and (db_endpoint.enhanced_summary or db_endpoint.enhanced_description)),
                    'needs_enhancement': not bool(yaml_endpoint.get('description') or (db_endpoint and db_endpoint.enhanced_description))
                }
                endpoints_data.append(endpoint_data)
            
            return Response({
                'status': 'success',
                'data': {
                    'yaml_file': {
                        'id': yaml_file.id,
                        'name': yaml_file.file_name,
                        'api_name': yaml_file.api_configuration.name if yaml_file.api_configuration else 'Unknown API'
                    },
                    'endpoints': endpoints_data
                }
            })
            
        except GeneratedYAMLFile.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'YAML file not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error loading endpoints with descriptions: {str(e)}")
            return Response({
                'status': 'error',
                'message': f'Error loading endpoint data: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
    
    @action(detail=False, methods=['post'])
    def generate_llm_description(self, request):
        """
        Generate LLM-powered description for an endpoint
        """
        try:
            from .llm_service import llm_service
            
            endpoint_data = request.data.get('endpoint_data', {})
            if not endpoint_data:
                return Response({
                    'status': 'error',
                    'message': 'endpoint_data is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not llm_service.is_available():
                return Response({
                    'status': 'error',
                    'message': 'LLM service is not available. Please configure OpenAI API key in settings.'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Generate enhanced description
            enhanced = llm_service.generate_endpoint_description(endpoint_data)
            
            return Response({
                'status': 'success',
                'data': {
                    'enhanced_summary': enhanced.get('summary', ''),
                    'enhanced_description': enhanced.get('description', '')
                }
            })
            
        except Exception as e:
            logger.error(f"Error generating LLM description: {str(e)}")
            return Response({
                'status': 'error',
                'message': f'Error generating description: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def generate_llm_parameter_description(self, request):
        """
        Generate LLM-powered description for a parameter
        """
        try:
            from .llm_service import llm_service
            
            param_data = request.data.get('parameter_data', {})
            endpoint_context = request.data.get('endpoint_context', {})
            
            if not param_data:
                return Response({
                    'status': 'error',
                    'message': 'parameter_data is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not llm_service.is_available():
                return Response({
                    'status': 'error',
                    'message': 'LLM service is not available. Please configure OpenAI API key in settings.'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Generate enhanced parameter description
            enhanced_description = llm_service.generate_parameter_description(param_data, endpoint_context)
            
            return Response({
                'status': 'success',
                'data': {
                    'enhanced_description': enhanced_description
                }
            })
            
        except Exception as e:
            logger.error(f"Error generating LLM parameter description: {str(e)}")
            return Response({
                'status': 'error',
                'message': f'Error generating parameter description: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def save_enhancement(self, request):
        """
        Save enhancement for an endpoint (create if doesn't exist)
        """
        try:
            yaml_file_id = request.data.get('yaml_file_id')
            endpoint_data = request.data.get('endpoint_data')
            enhanced_summary = request.data.get('enhanced_summary', '')
            enhanced_description = request.data.get('enhanced_description', '')
            
            if not yaml_file_id or not endpoint_data:
                return Response({
                    'status': 'error',
                    'message': 'yaml_file_id and endpoint_data are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get the YAML file
            yaml_file = GeneratedYAMLFile.objects.get(id=yaml_file_id)
            
            # Get or create the endpoint
            method = endpoint_data.get('method', '').upper()
            path = endpoint_data.get('path', '')
            
            endpoint, created = APIEndpoint.objects.get_or_create(
                yaml_file=yaml_file,
                method=method,
                path=path,
                defaults={
                    'operation_id': endpoint_data.get('operation_id', ''),
                    'summary': endpoint_data.get('original_summary', ''),
                    'description': endpoint_data.get('original_description', ''),
                    'parameters': endpoint_data.get('parameters', []),
                    'enhanced_summary': enhanced_summary,
                    'enhanced_description': enhanced_description,
                }
            )
            
            # If endpoint already exists, update the enhanced fields
            if not created:
                endpoint.enhanced_summary = enhanced_summary
                endpoint.enhanced_description = enhanced_description
                endpoint.save()
            
            return Response({
                'status': 'success',
                'message': 'Enhancement saved successfully',
                'endpoint_id': endpoint.id
            })
            
        except GeneratedYAMLFile.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'YAML file not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error saving enhancement: {str(e)}")
            return Response({
                'status': 'error',
                'message': f'Error saving enhancement: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def bulk_generate_descriptions(self, request):
        """
        Generate LLM descriptions for multiple endpoints in bulk
        """
        try:
            from .llm_service import llm_service
            
            yaml_file_id = request.data.get('yaml_file_id')
            endpoints_data = request.data.get('endpoints_data', [])
            
            if not yaml_file_id or not endpoints_data:
                return Response({
                    'status': 'error',
                    'message': 'yaml_file_id and endpoints_data are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not llm_service.is_available():
                return Response({
                    'status': 'error',
                    'message': 'LLM service is not available. Please configure Azure OpenAI API key in settings.'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Get the YAML file
            yaml_file = GeneratedYAMLFile.objects.get(id=yaml_file_id)
            
            results = []
            successful = 0
            errors = 0
            
            for endpoint_data in endpoints_data:
                try:
                    # Generate enhanced description
                    enhanced = llm_service.generate_endpoint_description(endpoint_data)
                    
                    # Save enhancement
                    method = endpoint_data.get('method', '').upper()
                    path = endpoint_data.get('path', '')
                    
                    endpoint, created = APIEndpoint.objects.get_or_create(
                        yaml_file=yaml_file,
                        method=method,
                        path=path,
                        defaults={
                            'operation_id': endpoint_data.get('operation_id', ''),
                            'summary': endpoint_data.get('original_summary', ''),
                            'description': endpoint_data.get('original_description', ''),
                            'parameters': endpoint_data.get('parameters', []),
                            'enhanced_summary': enhanced.get('summary', ''),
                            'enhanced_description': enhanced.get('description', ''),
                        }
                    )
                    
                    # If endpoint already exists, update the enhanced fields
                    if not created:
                        endpoint.enhanced_summary = enhanced.get('summary', '')
                        endpoint.enhanced_description = enhanced.get('description', '')
                        endpoint.save()
                    
                    results.append({
                        'endpoint': f"{method} {path}",
                        'status': 'success',
                        'enhanced_summary': enhanced.get('summary', ''),
                        'enhanced_description': enhanced.get('description', '')
                    })
                    successful += 1
                    
                except Exception as e:
                    logger.error(f"Error processing endpoint {endpoint_data.get('method', '')} {endpoint_data.get('path', '')}: {str(e)}")
                    results.append({
                        'endpoint': f"{endpoint_data.get('method', '')} {endpoint_data.get('path', '')}",
                        'status': 'error',
                        'message': str(e)
                    })
                    errors += 1
            
            return Response({
                'status': 'success',
                'message': f'Bulk generation completed. {successful} successful, {errors} errors.',
                'results': results,
                'summary': {
                    'total': len(endpoints_data),
                    'successful': successful,
                    'errors': errors
                }
            })
            
        except GeneratedYAMLFile.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'YAML file not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error in bulk generation: {str(e)}")
            return Response({
                'status': 'error',
                'message': f'Error in bulk generation: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def regenerate_with_enhancements(self, request, pk=None):
        """
        Regenerate YAML file with all current enhancements
        """
        try:
            yaml_file = self.get_object()
            
            # Parse the original Swagger spec again
            parser = SwaggerParser(yaml_file.api_configuration.swagger_url, yaml_file.api_configuration.api_base_url)
            spec = parser.fetch_swagger_spec()
            endpoints = parser.extract_endpoints()
            
            # Get all enhanced endpoints from database
            enhanced_endpoints = APIEndpoint.objects.filter(yaml_file=yaml_file)
            enhanced_dict = {}
            
            for enhanced_ep in enhanced_endpoints:
                key = f"{enhanced_ep.method.upper()}:{enhanced_ep.path}"
                enhanced_dict[key] = enhanced_ep
            
            # Update endpoints with enhancements
            for endpoint in endpoints:
                endpoint_key = f"{endpoint.get('method', '').upper()}:{endpoint.get('path', '')}"
                enhanced_ep = enhanced_dict.get(endpoint_key)
                
                if enhanced_ep:
                    # Update with enhanced descriptions if available
                    if enhanced_ep.enhanced_summary:
                        endpoint['summary'] = enhanced_ep.enhanced_summary
                    if enhanced_ep.enhanced_description:
                        endpoint['description'] = enhanced_ep.enhanced_description
            
            # Create API config dictionary
            api_config_dict = {
                'name': yaml_file.api_configuration.name,
                'description': yaml_file.api_configuration.description,
                'api_base_url': yaml_file.api_configuration.api_base_url,
                'swagger_url': yaml_file.api_configuration.swagger_url,
                'auth_type': yaml_file.api_configuration.auth_type,
                'auth_config': yaml_file.api_configuration.auth_config,
            }
            
            # Generate enhanced YAML
            generator = YAMLGenerator(api_config_dict, endpoints, yaml_file)
            enhanced_yaml = generator.generate_yaml_structure()
            
            # Save the enhanced YAML file
            yaml_dir = Path(settings.BASE_DIR) / 'generated_yaml_files'
            yaml_dir.mkdir(exist_ok=True)
            
            # Create new filename with _enhanced suffix if not already present
            base_name = yaml_file.file_name.replace('.yaml', '').replace('.yml', '')
            if not base_name.endswith('_enhanced'):
                enhanced_filename = f"{base_name}_enhanced.yaml"
            else:
                enhanced_filename = yaml_file.file_name
            
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
                'file_path': str(enhanced_file_path),
                'enhancements_applied': len([ep for ep in enhanced_endpoints if ep.enhanced_summary or ep.enhanced_description])
            })
        
        except Exception as e:
            logger.error(f"Error regenerating YAML with enhancements: {e}")
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
            logger.error(f"Error testing Swagger URL {swagger_url}: {str(e)}")
            
            # Provide more specific error messages
            error_message = str(e)
            if "Failed to fetch" in error_message:
                error_message = f"Cannot connect to the URL. Please check if the URL is accessible: {error_message}"
            elif "parsing Swagger spec" in error_message:
                error_message = f"The response is not a valid Swagger/OpenAPI specification: {error_message}"
            elif "Invalid YAML/JSON" in error_message:
                error_message = f"The response is not valid JSON or YAML format: {error_message}"
            
            return Response({
                'status': 'error',
                'message': error_message,
                'url_tested': swagger_url
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
