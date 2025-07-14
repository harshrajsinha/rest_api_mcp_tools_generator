"""
URL configuration for Tools Generator app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'api-configs', views.APIConfigurationViewSet)
router.register(r'yaml-files', views.GeneratedYAMLFileViewSet)
router.register(r'endpoints', views.APIEndpointViewSet)
router.register(r'parameter-enhancements', views.ParameterEnhancementViewSet)
router.register(r'swagger-test', views.SwaggerTestView, basename='swagger-test')

urlpatterns = [
    path('', include(router.urls)),
]
