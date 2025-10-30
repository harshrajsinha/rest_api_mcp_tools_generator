"""
REST API views for MCP Server management
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings
from django.http import JsonResponse, HttpResponse
import os
import json
import tempfile
import shutil
import zipfile
from pathlib import Path

from core.models import GeneratedYAMLFile, MCPServerInstance
from .serializers import MCPServerInstanceSerializer
from .services import MCPServer, MCPToolRegistry
from .claude_desktop_utils import create_mcp_server_package, generate_claude_desktop_config

# Global registry for MCP servers
mcp_registry = MCPToolRegistry()


class MCPServerInstanceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing MCP Server instances
    """
    queryset = MCPServerInstance.objects.all()
    serializer_class = MCPServerInstanceSerializer
    permission_classes = [AllowAny]
    
    @action(detail=True, methods=['post'])
    def start_server(self, request, pk=None):
        """
        Start an MCP server instance
        """
        server_instance = self.get_object()
        
        try:
            # Check if YAML file exists
            yaml_file = server_instance.yaml_file
            if not os.path.exists(yaml_file.file_path):
                return Response({
                    'status': 'error',
                    'message': 'YAML file not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check if tools file exists (if specified)
            tools_file_path = None
            if 'tools_file_path' in server_instance.server_config:
                tools_file_path = server_instance.server_config['tools_file_path']
                if not os.path.exists(tools_file_path):
                    tools_file_path = None
            
            # Register and start the MCP server
            mcp_server = mcp_registry.register_server(
                server_instance.server_name,
                yaml_file.file_path,
                tools_file_path
            )
            
            # Update server instance status
            server_instance.is_running = True
            server_instance.save()
            
            return Response({
                'status': 'success',
                'message': f'MCP server {server_instance.server_name} started successfully',
                'tools_count': len(mcp_server.tools)
            })
        
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def stop_server(self, request, pk=None):
        """
        Stop an MCP server instance
        """
        server_instance = self.get_object()
        
        try:
            # Remove server from registry
            if server_instance.server_name in mcp_registry.servers:
                del mcp_registry.servers[server_instance.server_name]
            
            # Update server instance status
            server_instance.is_running = False
            server_instance.save()
            
            return Response({
                'status': 'success',
                'message': f'MCP server {server_instance.server_name} stopped successfully'
            })
        
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def get_tools(self, request, pk=None):
        """
        Get all tools available in the MCP server
        """
        server_instance = self.get_object()
        
        if not server_instance.is_running:
            return Response({
                'status': 'error',
                'message': 'Server is not running'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            mcp_server = mcp_registry.get_server(server_instance.server_name)
            if not mcp_server:
                return Response({
                    'status': 'error',
                    'message': 'Server not found in registry'
                }, status=status.HTTP_404_NOT_FOUND)
            
            tools = mcp_server.get_available_tools()
            
            return Response({
                'status': 'success',
                'tools': tools,
                'tools_count': len(tools)
            })
        
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def execute_tool(self, request, pk=None):
        """
        Execute a tool on the MCP server
        """
        server_instance = self.get_object()
        
        if not server_instance.is_running:
            return Response({
                'status': 'error',
                'message': 'Server is not running'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tool_name = request.data.get('tool_name')
        parameters = request.data.get('parameters', {})
        
        if not tool_name:
            return Response({
                'status': 'error',
                'message': 'tool_name is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            mcp_server = mcp_registry.get_server(server_instance.server_name)
            if not mcp_server:
                return Response({
                    'status': 'error',
                    'message': 'Server not found in registry'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Execute the tool (this would be async in a real implementation)
            import asyncio
            result = asyncio.run(mcp_server.execute_tool(tool_name, parameters))
            
            return Response({
                'status': 'success',
                'result': result
            })
        
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MCPRegistryViewSet(viewsets.ViewSet):
    """
    ViewSet for managing the global MCP registry
    """
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['get'])
    def list_servers(self, request):
        """
        List all registered MCP servers
        """
        servers = mcp_registry.list_servers()
        return Response({
            'servers': servers,
            'count': len(servers)
        })
    
    @action(detail=False, methods=['get'])
    def get_all_tools(self, request):
        """
        Get all tools from all registered servers
        """
        all_tools = mcp_registry.get_all_tools()
        return Response({
            'servers_tools': all_tools
        })
    
    @action(detail=False, methods=['post'])
    def create_server_from_yaml(self, request):
        """
        Create and start an MCP server directly from a YAML file
        """
        yaml_file_id = request.data.get('yaml_file_id')
        server_name = request.data.get('server_name')
        
        if not yaml_file_id or not server_name:
            return Response({
                'status': 'error',
                'message': 'yaml_file_id and server_name are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            yaml_file = GeneratedYAMLFile.objects.get(id=yaml_file_id)
            
            # Create MCP server instance record
            server_instance, created = MCPServerInstance.objects.get_or_create(
                yaml_file=yaml_file,
                defaults={
                    'server_name': server_name,
                    'is_running': False,
                    'server_config': {}
                }
            )
            
            if not created:
                server_instance.server_name = server_name
                server_instance.save()
            
            # Register and start the server
            mcp_server = mcp_registry.register_server(
                server_name,
                yaml_file.file_path
            )
            
            server_instance.is_running = True
            server_instance.save()
            
            return Response({
                'status': 'success',
                'message': f'MCP server {server_name} created and started',
                'server_instance_id': server_instance.id,
                'tools_count': len(mcp_server.tools)
            })
        
        except GeneratedYAMLFile.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'YAML file not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def generate_claude_package(self, request, pk=None):
        """
        Generate a complete Claude Desktop package for an MCP server
        """
        try:
            server_instance = self.get_object()
            yaml_file = server_instance.yaml_file
            
            # Create temporary directory for package
            temp_dir = tempfile.mkdtemp()
            package_name = f"{server_instance.server_name}_claude_package"
            package_dir = os.path.join(temp_dir, package_name)
            
            try:
                # Create the MCP server package
                created_files = create_mcp_server_package(
                    yaml_file_path=yaml_file.yaml_file.path,
                    server_name=server_instance.server_name,
                    output_dir=package_dir,
                    include_config=True
                )
                
                # Create ZIP file
                zip_path = os.path.join(temp_dir, f"{package_name}.zip")
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    package_path = Path(package_dir)
                    for file_path in package_path.rglob('*'):
                        if file_path.is_file():
                            arcname = file_path.relative_to(package_path)
                            zipf.write(file_path, arcname)
                
                # Read ZIP file for response
                with open(zip_path, 'rb') as f:
                    zip_data = f.read()
                
                response = HttpResponse(
                    zip_data,
                    content_type='application/zip'
                )
                response['Content-Disposition'] = f'attachment; filename="{package_name}.zip"'
                
                return response
                
            finally:
                # Cleanup temporary directory
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'Failed to generate Claude Desktop package: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def claude_config(self, request, pk=None):
        """
        Generate Claude Desktop configuration JSON for this server
        """
        try:
            server_instance = self.get_object()
            
            # Generate configuration for a single server
            mcp_servers = [{
                'name': server_instance.server_name,
                'yaml_file_path': server_instance.yaml_file.yaml_file.path,
                'server_script': 'mcp_server_fastmcp.py'  # Default script name
            }]
            
            config_json = generate_claude_desktop_config(mcp_servers)
            
            return Response({
                'status': 'success',
                'config': json.loads(config_json),
                'instructions': {
                    'steps': [
                        '1. Copy the configuration below',
                        '2. Locate your Claude Desktop config file:',
                        '   - macOS: ~/Library/Application Support/Claude/claude_desktop_config.json',
                        '   - Windows: %APPDATA%\\Claude\\claude_desktop_config.json',
                        '3. Add this server to the "mcpServers" section',
                        '4. Update the "args" path to the absolute path of your server script',
                        '5. Restart Claude Desktop'
                    ],
                    'config_example': config_json
                }
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'Failed to generate Claude Desktop configuration: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def bulk_claude_config(self, request):
        """
        Generate Claude Desktop configuration for multiple servers
        """
        try:
            server_ids = request.data.get('server_ids', [])
            
            if not server_ids:
                # Get all active servers
                server_instances = MCPServerInstance.objects.filter(is_running=True)
            else:
                server_instances = MCPServerInstance.objects.filter(id__in=server_ids)
            
            mcp_servers = []
            for server_instance in server_instances:
                mcp_servers.append({
                    'name': server_instance.server_name,
                    'yaml_file_path': server_instance.yaml_file.yaml_file.path,
                    'server_script': 'mcp_server_fastmcp.py'
                })
            
            if not mcp_servers:
                return Response({
                    'status': 'error',
                    'message': 'No servers found to configure'
                }, status=status.HTTP_404_NOT_FOUND)
            
            config_json = generate_claude_desktop_config(mcp_servers)
            
            return Response({
                'status': 'success',
                'servers_count': len(mcp_servers),
                'config': json.loads(config_json),
                'instructions': {
                    'steps': [
                        '1. Copy the configuration below',
                        '2. Locate your Claude Desktop config file:',
                        '   - macOS: ~/Library/Application Support/Claude/claude_desktop_config.json',
                        '   - Windows: %APPDATA%\\Claude\\claude_desktop_config.json',
                        '3. Merge this configuration with your existing "mcpServers" section',
                        '4. Update all "args" paths to absolute paths of your server scripts',
                        '5. Restart Claude Desktop'
                    ],
                    'config_example': config_json
                }
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'Failed to generate bulk Claude Desktop configuration: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def download_mcp_package(self, request):
        """
        Generate and download MCP server package directly from YAML file ID
        """
        yaml_file_id = request.data.get('yaml_file_id')
        server_name = request.data.get('server_name')
        
        if not yaml_file_id:
            return Response({
                'status': 'error',
                'message': 'yaml_file_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not server_name:
            server_name = f"mcp_server_{yaml_file_id}"
        
        try:
            # Get YAML file
            yaml_file = GeneratedYAMLFile.objects.get(id=yaml_file_id)
            
            # Check if enhanced version exists
            yaml_file_path = yaml_file.file_path
            enhanced_path = yaml_file_path.replace('.yaml', '_enhanced.yaml').replace('.yml', '_enhanced.yml')
            
            # Use enhanced version if available, otherwise use original
            if os.path.exists(enhanced_path):
                yaml_file_path = enhanced_path
                server_name = server_name + "_enhanced"
            
            # Create temporary directory for package
            temp_dir = tempfile.mkdtemp()
            package_name = f"{server_name}_mcp_package"
            package_dir = os.path.join(temp_dir, package_name)
            
            try:
                # Create the MCP server package
                created_files = create_mcp_server_package(
                    yaml_file_path=yaml_file_path,
                    server_name=server_name,
                    output_dir=package_dir,
                    include_config=True
                )
                
                # Create ZIP file
                zip_path = os.path.join(temp_dir, f"{package_name}.zip")
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    package_path = Path(package_dir)
                    for file_path in package_path.rglob('*'):
                        if file_path.is_file():
                            arcname = file_path.relative_to(package_path)
                            zipf.write(file_path, arcname)
                
                # Read ZIP file for response
                with open(zip_path, 'rb') as f:
                    zip_data = f.read()
                
                response = HttpResponse(
                    zip_data,
                    content_type='application/zip'
                )
                response['Content-Disposition'] = f'attachment; filename="{package_name}.zip"'
                
                return response
                
            finally:
                # Cleanup temporary directory
                import threading
                def cleanup():
                    import time
                    time.sleep(5)  # Wait 5 seconds before cleanup
                    shutil.rmtree(temp_dir, ignore_errors=True)
                
                threading.Thread(target=cleanup).start()
                
        except GeneratedYAMLFile.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'YAML file not found'
            }, status=status.HTTP_404_NOT_FOUND)
                
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'Failed to generate MCP package: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
