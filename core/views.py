from django.shortcuts import render
from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = 'core/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'REST API MCP Tools Generator'
        return context


class EnhanceEndpointsView(TemplateView):
    template_name = 'core/enhance_endpoints.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Enhance API Endpoints'
        return context
