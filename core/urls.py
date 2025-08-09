from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('enhance-endpoints/', views.EnhanceEndpointsView.as_view(), name='enhance-endpoints'),
]
