from django.shortcuts import render
from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = 'core/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'REST API MCP Tools Generator'
        return context


class EnhanceEndpointsView(TemplateView):
    template_name = 'core/enhance_endpoints_enhanced.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Enhance API Endpoints'
        
        # Get YAML file ID from query parameters
        yaml_file_id = self.request.GET.get('yaml_file')
        context['yaml_file_id'] = yaml_file_id
        
        return context


class MCPTestView(TemplateView):
    template_name = 'core/mcp_test.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'MCP Server Test'
        return context
