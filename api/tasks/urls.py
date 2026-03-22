"""
URL configuration for the task management system.
Follows bulletproof patterns with comprehensive error handling and versioning.
"""

import logging
from typing import Optional, List
from django.urls import path, include, reverse
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.contrib.sitemaps.views import sitemap
from django.contrib.sitemaps import GenericSitemap
from django.contrib.admin.views.decorators import staff_member_required
from rest_framework.routers import DefaultRouter, SimpleRouter
from rest_framework import permissions
from django.db import connection

# Import viewsets
from . import views
from .models import MasterTask

# Setup logging
logger = logging.getLogger(__name__)

# ============ API VERSIONING ============

API_VERSION = 'v1'
API_PREFIX = f'api/{API_VERSION}'

# ============ ROUTER CONFIGURATION ============

class BulletproofRouter(DefaultRouter):
    """
    Custom router with additional error handling and features
    """
    
    def __init__(self, *args, **kwargs):
        self.trailing_slash = kwargs.pop('trailing_slash', '/?')
        super().__init__(*args, **kwargs)
    
    def get_urls(self):
        """Override to add custom error handling"""
        urls = super().get_urls()
        wrapped_urls = []
        for url_pattern in urls:
            wrapped_urls.append(url_pattern)
        return wrapped_urls


# Create routers
router = BulletproofRouter(trailing_slash='/?')
admin_router = BulletproofRouter(trailing_slash='/?')

# ============ REGISTER VIEWSETS ============

# ✅ FIX: r'tasks/completions' → r'completions'
# main urls.py তে path('api/tasks/', ...) আছে
# তাই এখানে শুধু r'completions' দিলেই /api/tasks/completions/ হবে

router.register(
    r'tasks',
    views.MasterTaskViewSet,
    basename='task'
)
router.register(
    r'completions',   # ✅ FIXED: আগে ছিল r'tasks/completions' যা কাজ করে না
    views.TaskCompletionViewSet,
    basename='completion'
)

# Admin routes
admin_router.register(
    r'tasks',
    views.AdminTaskViewSet,
    basename='admin-task'
)

# ============ DRF YASG SCHEMA VIEW (Optional) ============

try:
    from drf_yasg.views import get_schema_view
    from drf_yasg import openapi
    
    schema_view = get_schema_view(
        openapi.Info(
            title="Task Management API",
            default_version=API_VERSION,
            description="API for managing 70+ task types with metadata-driven architecture",
            terms_of_service="https://www.example.com/terms/",
            contact=openapi.Contact(email="admin@example.com"),
            license=openapi.License(name="Proprietary"),
        ),
        public=True,
        permission_classes=[permissions.AllowAny],
    )
    
    DRF_YASG_INSTALLED = True
    logger.info("drf-yasg installed - API documentation enabled")
    
except ImportError:
    DRF_YASG_INSTALLED = False
    schema_view = None
    logger.info("drf-yasg not installed - API documentation disabled")

# ============ HEALTH CHECK VIEW ============

def health_check(request):
    """Simple health check endpoint"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        
        return JsonResponse({
            'status': 'healthy',
            'version': API_VERSION,
            'timestamp': timezone.now().isoformat(),
            'services': {
                'api': 'operational',
                'database': 'operational',
                'cache': 'checking...'
            }
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)

# ============ ERROR HANDLING VIEWS ============

def handler400(request, exception=None):
    return JsonResponse({
        'error': 'Bad Request',
        'error_code': 'BAD_REQUEST',
        'message': str(exception) if exception else 'Invalid request',
        'path': request.path,
        'timestamp': timezone.now().isoformat()
    }, status=400)


def handler403(request, exception=None):
    return JsonResponse({
        'error': 'Permission Denied',
        'error_code': 'FORBIDDEN',
        'message': str(exception) if exception else 'You do not have permission to access this resource',
        'path': request.path,
        'timestamp': timezone.now().isoformat()
    }, status=403)


def handler404(request, exception=None):
    return JsonResponse({
        'error': 'Not Found',
        'error_code': 'NOT_FOUND',
        'message': str(exception) if exception else 'The requested resource was not found',
        'path': request.path,
        'timestamp': timezone.now().isoformat()
    }, status=404)


def handler500(request):
    return JsonResponse({
        'error': 'Internal Server Error',
        'error_code': 'INTERNAL_ERROR',
        'message': 'An unexpected error occurred',
        'path': getattr(request, 'path', 'unknown'),
        'timestamp': timezone.now().isoformat()
    }, status=500)

# ============ ROBOTS.TXT VIEW ============

def robots_txt(request):
    try:
        content = "User-agent: *\n"
        if not settings.DEBUG:
            content += "Disallow:\n"
        else:
            content += "Disallow: /\n"
        return HttpResponse(content, content_type='text/plain')
    except Exception as e:
        logger.error(f"Error serving robots.txt: {str(e)}")
        return HttpResponse("User-agent: *\nDisallow: /", content_type='text/plain')

# ============ SITEMAP VIEW ============

def sitemap_xml(request):
    try:
        if 'django.contrib.sitemaps' not in settings.INSTALLED_APPS:
            return HttpResponse("Sitemap not available", status=404)
        
        sitemaps = {
            'tasks': GenericSitemap({
                'queryset': MasterTask.objects.filter(is_active=True),
                'date_field': 'updated_at',
            }, priority=0.8),
        }
        
        return sitemap(request, sitemaps=sitemaps)
        
    except Exception as e:
        logger.error(f"Error generating sitemap: {str(e)}")
        return HttpResponse("Error generating sitemap", status=500)

# ============ PERFORMANCE DASHBOARD VIEW ============

def performance_dashboard(request):
    try:
        from time import time
        start = time()
        queries = len(connection.queries)
        query_time = sum(float(q.get('time', 0)) for q in connection.queries)
        from django.core.cache import cache
        cache_stats = {
            'hits': getattr(cache, 'hits', 0),
            'misses': getattr(cache, 'misses', 0),
        }
        end = time()
        return JsonResponse({
            'request_time': round(end - start, 4),
            'database_queries': queries,
            'database_time': round(query_time, 4),
            'cache_stats': cache_stats,
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error in performance dashboard: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


# ============ URL PATTERNS ============

urlpatterns = []

# API Documentation
if DRF_YASG_INSTALLED and schema_view:
    urlpatterns += [
        path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
        path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
        path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    ]

# Health checks
urlpatterns += [
    path('health/', views.HealthCheckView.as_view(), name='health-check'),
    path('health/simple/', health_check, name='simple-health'),
]

# ✅ Router URLs — completions এখন /api/tasks/completions/ হবে
urlpatterns += [
    path('tasks/dashboard-stats/', views.task_dashboard_stats, name='task-dashboard-stats'),
]

urlpatterns += [
    path('', include(router.urls)),
    path('admin/', include(admin_router.urls)),
]

# Statistics
urlpatterns += [
    path('tasks/bulk-activate/', views.bulk_activate, name='bulk-activate'),
    path('tasks/bulk-deactivate/', views.bulk_deactivate, name='bulk-deactivate'),
    path('admin-ledger/', views.admin_ledger_list, name='admin-ledger'),
    path('admin-ledger/profit-summary/', views.admin_profit_summary, name='profit-summary'),
    path('admin-ledger/daily-profit/', views.admin_daily_profit, name='daily-profit'),
    path('admin-ledger/by-source/', views.admin_profit_by_source, name='profit-by-source'),
    path('statistics/', views.TaskStatisticsView.as_view(), name='task-statistics'),
]

# SEO (production only)
if not settings.DEBUG:
    urlpatterns += [
        path('robots.txt', robots_txt, name='robots-txt'),
        path('sitemap.xml', sitemap_xml, name='sitemap-xml'),
    ]

# Performance monitoring
if settings.DEBUG:
    urlpatterns += [
        path('debug/performance/', performance_dashboard, name='performance-dashboard'),
    ]
else:
    urlpatterns += [
        path('admin/performance/', staff_member_required(performance_dashboard), name='performance-dashboard'),
    ]


# ============ CUSTOM URL CONVERTERS ============

from django.urls import register_converter

class TaskIDConverter:
    regex = '[A-Za-z0-9_]+'
    def to_python(self, value): return str(value)
    def to_url(self, value): return str(value)

class PositiveIntConverter:
    regex = '[1-9][0-9]*'
    def to_python(self, value): return int(value)
    def to_url(self, value): return str(value)

register_converter(TaskIDConverter, 'task_id')
register_converter(PositiveIntConverter, 'posint')


# ============ MAINTENANCE MODE MIDDLEWARE ============

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.maintenance_mode = getattr(settings, 'MAINTENANCE_MODE', False)
    
    def __call__(self, request):
        if self.maintenance_mode:
            if not request.path.startswith('/maintenance/') and \
               not request.path.startswith('/admin/') and \
               not request.user.is_staff:
                return RedirectView.as_view(url='/maintenance/')(request)
        return self.get_response(request)


# ============ HELPER FUNCTIONS ============

def get_versioned_urls(version: str = API_VERSION) -> List:
    versioned_patterns = []
    try:
        for pattern in urlpatterns:
            pattern_str = str(pattern.pattern)
            if f'api/{version}' in pattern_str or version == API_VERSION:
                versioned_patterns.append(pattern)
    except Exception as e:
        logger.error(f"Error getting versioned URLs: {str(e)}")
    return versioned_patterns


def get_absolute_url(url_name: str, *args, **kwargs) -> Optional[str]:
    try:
        return reverse(url_name, args=args, kwargs=kwargs)
    except Exception as e:
        logger.error(f"Error resolving URL {url_name}: {str(e)}")
        return None


# ============ URL NAMES CONSTANTS ============

class URLNames:
    TASK_LIST = 'task-list'
    TASK_DETAIL = 'task-detail'
    COMPLETION_LIST = 'completion-list'
    COMPLETION_DETAIL = 'completion-detail'
    ADMIN_TASK_LIST = 'admin-task-list'
    ADMIN_TASK_DETAIL = 'admin-task-detail'
    STATISTICS = 'task-statistics'
    HEALTH_CHECK = 'health-check'
    SIMPLE_HEALTH = 'simple-health'
    SWAGGER_UI = 'schema-swagger-ui'
    REDOC = 'schema-redoc'
    SWAGGER_JSON = 'schema-json'


# ============ EXPORT ============

__all__ = [
    'urlpatterns',
    'router',
    'admin_router',
    'URLNames',
    'get_absolute_url',
    'get_versioned_urls',
    'handler400',
    'handler403',
    'handler404',
    'handler500',
    'MaintenanceModeMiddleware',
]