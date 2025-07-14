"""
Serializers for MCP Server management
"""
from rest_framework import serializers
from core.models import MCPServerInstance, GeneratedYAMLFile


class MCPServerInstanceSerializer(serializers.ModelSerializer):
    """
    Serializer for MCP Server Instance
    """
    yaml_file_name = serializers.CharField(source='yaml_file.file_name', read_only=True)
    api_config_name = serializers.CharField(source='yaml_file.api_config.name', read_only=True)
    
    class Meta:
        model = MCPServerInstance
        fields = [
            'id', 'yaml_file', 'yaml_file_name', 'api_config_name',
            'server_name', 'server_port', 'is_running', 'server_config',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class MCPServerCreateSerializer(serializers.Serializer):
    """
    Serializer for creating MCP server from YAML file
    """
    yaml_file_id = serializers.IntegerField()
    server_name = serializers.CharField(max_length=255)
    server_port = serializers.IntegerField(required=False, min_value=1024, max_value=65535)
    server_config = serializers.JSONField(required=False, default=dict)
    
    def validate_yaml_file_id(self, value):
        """
        Validate that the YAML file exists and is completed
        """
        try:
            yaml_file = GeneratedYAMLFile.objects.get(id=value)
            if yaml_file.generation_status != 'completed':
                raise serializers.ValidationError("YAML file generation is not completed")
            return value
        except GeneratedYAMLFile.DoesNotExist:
            raise serializers.ValidationError("YAML file not found")


class ToolExecutionSerializer(serializers.Serializer):
    """
    Serializer for tool execution requests
    """
    tool_name = serializers.CharField(max_length=255)
    parameters = serializers.JSONField(default=dict)
    
    def validate_tool_name(self, value):
        """
        Validate tool name format
        """
        if not value.strip():
            raise serializers.ValidationError("Tool name cannot be empty")
        return value.strip()
