"""
URL configuration for MCP Server app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'instances', views.MCPServerInstanceViewSet)
router.register(r'registry', views.MCPRegistryViewSet, basename='mcp-registry')

urlpatterns = [
    path('', include(router.urls)),
]
