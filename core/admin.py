from django.contrib import admin
from .models import (
    APIConfiguration,
    GeneratedYAMLFile,
    APIEndpoint,
    ParameterEnhancement,
    MCPServerInstance
)


@admin.register(APIConfiguration)
class APIConfigurationAdmin(admin.ModelAdmin):
    list_display = ['name', 'api_base_url', 'auth_type', 'created_by', 'created_at', 'is_active']
    list_filter = ['auth_type', 'is_active', 'created_at']
    search_fields = ['name', 'api_base_url', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(GeneratedYAMLFile)
class GeneratedYAMLFileAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'api_configuration', 'tools_count', 'generation_status', 'created_at']
    list_filter = ['generation_status', 'created_at']
    search_fields = ['file_name', 'api_configuration__name']
    readonly_fields = ['created_at']


@admin.register(APIEndpoint)
class APIEndpointAdmin(admin.ModelAdmin):
    list_display = ['path', 'method', 'yaml_file', 'operation_id', 'is_enabled']
    list_filter = ['method', 'is_enabled', 'yaml_file']
    search_fields = ['path', 'operation_id', 'summary']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ParameterEnhancement)
class ParameterEnhancementAdmin(admin.ModelAdmin):
    list_display = ['endpoint', 'parameter_name', 'parameter_type', 'is_required']
    list_filter = ['parameter_type', 'is_required']
    search_fields = ['parameter_name', 'endpoint__path']


@admin.register(MCPServerInstance)
class MCPServerInstanceAdmin(admin.ModelAdmin):
    list_display = ['server_name', 'yaml_file', 'is_running', 'created_at']
    list_filter = ['is_running', 'created_at']
    search_fields = ['server_name', 'yaml_file__file_name']
