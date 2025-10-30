"""
Core models for the REST API MCP Tools Generator
"""
from django.db import models
from django.contrib.auth.models import User
import json


class APIConfiguration(models.Model):
    """Model to store API configuration details"""
    
    name = models.CharField(max_length=255, help_text="Name of the API configuration")
    swagger_url = models.URLField(help_text="Swagger/OpenAPI specification URL")
    api_base_url = models.URLField(help_text="Base URL of the REST API")
    description = models.TextField(blank=True, help_text="Description of the REST API service")
    
    # Authentication details
    AUTH_TYPES = [
        ('none', 'No Authentication'),
        ('api_key', 'API Key'),
        ('bearer_token', 'Bearer Token'),
        ('basic_auth', 'Basic Authentication'),
        ('oauth2', 'OAuth2'),
    ]
    auth_type = models.CharField(max_length=20, choices=AUTH_TYPES, default='none')
    auth_config = models.JSONField(default=dict, help_text="Authentication configuration")
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'core_api_configuration'
        verbose_name = 'API Configuration'
        verbose_name_plural = 'API Configurations'
    
    def __str__(self):
        return self.name


class GeneratedYAMLFile(models.Model):
    """Model to store generated YAML files information"""
    
    api_configuration = models.ForeignKey(APIConfiguration, on_delete=models.CASCADE, related_name='yaml_files')
    file_name = models.CharField(max_length=255, blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    yaml_content = models.TextField(blank=True, default="", help_text="Generated YAML content")
    tools_count = models.IntegerField(default=0)
    generation_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_generated_yaml_file'
        verbose_name = 'Generated YAML File'
        verbose_name_plural = 'Generated YAML Files'
    
    def __str__(self):
        return f"{self.api_configuration.name} - {self.file_name or 'Untitled'}"
    
    def get_yaml_content(self):
        """Parse and return YAML content as Python dict"""
        if not self.yaml_content:
            return {}
        
        try:
            import yaml
            return yaml.safe_load(self.yaml_content)
        except yaml.YAMLError:
            return {}


class APIEndpoint(models.Model):
    """Model to store individual API endpoint details"""
    
    yaml_file = models.ForeignKey(GeneratedYAMLFile, on_delete=models.CASCADE, related_name='endpoints')
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    operation_id = models.CharField(max_length=255, blank=True)
    summary = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    
    # Enhanced descriptions (user can modify these)
    enhanced_description = models.TextField(blank=True)
    enhanced_summary = models.CharField(max_length=500, blank=True)
    
    parameters = models.JSONField(default=list)
    responses = models.JSONField(default=dict)
    
    # Tool generation settings
    is_enabled = models.BooleanField(default=True)
    tool_name = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_api_endpoint'
        verbose_name = 'API Endpoint'
        verbose_name_plural = 'API Endpoints'
        unique_together = ['yaml_file', 'path', 'method']
    
    def __str__(self):
        return f"{self.method.upper()} {self.path}"
    
    @property
    def display_description(self):
        return self.enhanced_description or self.description
    
    @property
    def display_summary(self):
        return self.enhanced_summary or self.summary


class ParameterEnhancement(models.Model):
    """Model to store enhanced parameter descriptions"""
    
    endpoint = models.ForeignKey(APIEndpoint, on_delete=models.CASCADE, related_name='parameter_enhancements')
    parameter_name = models.CharField(max_length=255)
    original_description = models.TextField(blank=True)
    enhanced_description = models.TextField()
    parameter_type = models.CharField(max_length=50, blank=True)
    is_required = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_parameter_enhancement'
        verbose_name = 'Parameter Enhancement'
        verbose_name_plural = 'Parameter Enhancements'
        unique_together = ['endpoint', 'parameter_name']
    
    def __str__(self):
        return f"{self.endpoint} - {self.parameter_name}"


class MCPServerInstance(models.Model):
    """Model to track MCP Server instances"""
    
    yaml_file = models.OneToOneField(GeneratedYAMLFile, on_delete=models.CASCADE, related_name='mcp_server')
    server_name = models.CharField(max_length=255)
    server_port = models.IntegerField(null=True, blank=True)
    is_running = models.BooleanField(default=False)
    
    # Server configuration
    server_config = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_mcp_server_instance'
        verbose_name = 'MCP Server Instance'
        verbose_name_plural = 'MCP Server Instances'
    
    def __str__(self):
        return f"MCP Server: {self.server_name}"
