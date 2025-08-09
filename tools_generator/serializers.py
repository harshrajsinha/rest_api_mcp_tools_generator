"""
Serializers for Tools Generator API
"""
from rest_framework import serializers
from core.models import (
    APIConfiguration,
    GeneratedYAMLFile,
    APIEndpoint,
    ParameterEnhancement,
    MCPServerInstance
)


class APIConfigurationSerializer(serializers.ModelSerializer):
    """
    Serializer for API Configuration
    """
    created_by = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = APIConfiguration
        fields = [
            'id', 'name', 'swagger_url', 'api_base_url', 'description',
            'auth_type', 'auth_config', 'created_by', 'created_at', 
            'updated_at', 'is_active'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class GeneratedYAMLFileSerializer(serializers.ModelSerializer):
    """
    Serializer for Generated YAML File
    """
    api_config_name = serializers.CharField(source='api_configuration.name', read_only=True)
    
    class Meta:
        model = GeneratedYAMLFile
        fields = [
            'id', 'api_configuration', 'api_config_name', 'file_name', 'file_path',
            'tools_count', 'generation_status', 'error_message', 'created_at'
        ]
        read_only_fields = ['created_at']


class APIEndpointSerializer(serializers.ModelSerializer):
    """
    Serializer for API Endpoint
    """
    yaml_file_name = serializers.CharField(source='yaml_file.file_name', read_only=True)
    display_description = serializers.CharField(read_only=True)
    display_summary = serializers.CharField(read_only=True)
    
    class Meta:
        model = APIEndpoint
        fields = [
            'id', 'yaml_file', 'yaml_file_name', 'path', 'method', 'operation_id',
            'summary', 'description', 'enhanced_description', 'enhanced_summary',
            'display_description', 'display_summary', 'parameters', 'responses',
            'is_enabled', 'tool_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ParameterEnhancementSerializer(serializers.ModelSerializer):
    """
    Serializer for Parameter Enhancement
    """
    endpoint_path = serializers.CharField(source='endpoint.path', read_only=True)
    endpoint_method = serializers.CharField(source='endpoint.method', read_only=True)
    
    class Meta:
        model = ParameterEnhancement
        fields = [
            'id', 'endpoint', 'endpoint_path', 'endpoint_method', 'parameter_name',
            'original_description', 'enhanced_description', 'parameter_type',
            'is_required', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SwaggerTestSerializer(serializers.Serializer):
    """
    Serializer for testing Swagger URLs
    """
    swagger_url = serializers.URLField(required=True)
    api_base_url = serializers.URLField(required=False, allow_blank=True)
    
    def validate_swagger_url(self, value):
        """
        Validate that the swagger URL is accessible
        """
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("URL must start with http:// or https://")
        return value


class EndpointEnhancementSerializer(serializers.Serializer):
    """
    Serializer for enhancing endpoint descriptions
    """
    enhanced_description = serializers.CharField(required=False, allow_blank=True)
    enhanced_summary = serializers.CharField(required=False, allow_blank=True)


class YAMLGenerationSerializer(serializers.Serializer):
    """
    Serializer for YAML generation parameters
    """
    include_optional_params = serializers.BooleanField(default=True)
    include_response_schemas = serializers.BooleanField(default=True)
    tool_name_format = serializers.ChoiceField(
        choices=[
            ('operation_id', 'Use Operation ID'),
            ('path_method', 'Use Path + Method'),
            ('custom', 'Custom Names')
        ],
        default='operation_id'
    )
