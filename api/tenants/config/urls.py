"""
URL Configuration for Tenant Management System

Comprehensive URL routing for all tenant management endpoints including
API routes, admin interface, and utility endpoints.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

from api.tenants import urls as tenants_urls

urlpatterns = [
    # Admin interface
    path(f'{settings.ADMIN_URL}/', admin.site.urls),
    
    # Tenant Management API
    path('api/v1/tenants/', include(tenants_urls)),
    
    # Health check endpoint
    path('health/', TemplateView.as_view(template_name='health.html'), name='health_check'),
    
    # Root redirect to API documentation
    path('', TemplateView.as_view(template_name='index.html'), name='index'),
    
    # API Documentation
    path('api/docs/', TemplateView.as_view(template_name='api_docs.html'), name='api_docs'),
    
    # Static files (for development)
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Error handlers
handler404 = 'api.tenants.views.custom_404'
handler500 = 'api.tenants.views.custom_500'
