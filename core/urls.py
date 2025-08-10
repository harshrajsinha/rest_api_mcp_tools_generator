from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('enhance-endpoints/', views.EnhanceEndpointsView.as_view(), name='enhance-endpoints'),
]
