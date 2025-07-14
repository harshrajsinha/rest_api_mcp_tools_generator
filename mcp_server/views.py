"""
REST API views for MCP Server management
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.http import JsonResponse
import os
import json
from pathlib import Path

from core.models import GeneratedYAMLFile, MCPServerInstance
from .serializers import MCPServerInstanceSerializer
from .services import MCPServer, MCPToolRegistry

# Global registry for MCP servers
mcp_registry = MCPToolRegistry()


class MCPServerInstanceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing MCP Server instances
    """
    queryset = MCPServerInstance.objects.all()
    serializer_class = MCPServerInstanceSerializer
    permission_classes = [IsAuthenticated]
    
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
    permission_classes = [IsAuthenticated]
    
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
