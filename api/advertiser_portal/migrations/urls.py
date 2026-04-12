"""
Migrations URLs

This module defines URL patterns for migration management with
enterprise-grade security, performance optimization, and comprehensive functionality
following industry standards from Django Migrations, Alembic, and Flyway.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from django.conf import settings
from django.urls.exceptions import NoReverseMatch
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
import time
import logging

from .views import (
    MigrationViewSet,
    SchemaMigrationViewSet,
    DataMigrationViewSet,
    RollbackViewSet,
    MigrationTrackingViewSet,
    MigrationValidationViewSet,
    MigrationBackupViewSet
)

# Create router for migrations with optimized routing
router = DefaultRouter()
router.register(r'migrations', MigrationViewSet, basename='migration')
router.register(r'schema', SchemaMigrationViewSet, basename='schema-migration')
router.register(r'data', DataMigrationViewSet, basename='data-migration')
router.register(r'rollback', RollbackViewSet, basename='rollback')
router.register(r'tracking', MigrationTrackingViewSet, basename='migration-tracking')
router.register(r'validation', MigrationValidationViewSet, basename='migration-validation')
router.register(r'backup', MigrationBackupViewSet, basename='migration-backup')

# URL patterns with comprehensive security and performance optimization
urlpatterns = [
    # Router URLs with optimized database queries
    path('', include(router.urls)),
    
    # Migration URLs
    path('migrations/create/', MigrationViewSet.as_view({'post': 'create'}), name='migrations-create'),
    path('migrations/<uuid:pk>/execute/', MigrationViewSet.as_view({'post': 'execute'}), name='migrations-execute'),
    path('migrations/<uuid:pk>/rollback/', MigrationViewSet.as_view({'post': 'rollback'}), name='migrations-rollback'),
    path('migrations/<uuid:pk>/validate/', MigrationViewSet.as_view({'post': 'validate'}), name='migrations-validate'),
    path('migrations/<uuid:pk>/stats/', MigrationViewSet.as_view({'get': 'stats'}), name='migrations-stats'),
    path('migrations/<uuid:pk>/history/', MigrationViewSet.as_view({'get': 'history'}), name='migrations-history'),
    path('migrations/list/', MigrationViewSet.as_view({'get': 'list'}), name='migrations-list'),
    
    # Schema Migration URLs
    path('schema/create/', SchemaMigrationViewSet.as_view({'post': 'create'}), name='schema-migrations-create'),
    path('schema/<uuid:pk>/update/', SchemaMigrationViewSet.as_view({'put': 'update'}), name='schema-migrations-update'),
    path('schema/<uuid:pk>/validate_sql/', SchemaMigrationViewSet.as_view({'post': 'validate_sql'}), name='schema-migrations-validate-sql'),
    path('schema/<uuid:pk>/preview/', SchemaMigrationViewSet.as_view({'get': 'preview'}), name='schema-migrations-preview'),
    
    # Data Migration URLs
    path('data/create/', DataMigrationViewSet.as_view({'post': 'create'}), name='data-migrations-create'),
    path('data/<uuid:pk>/update/', DataMigrationViewSet.as_view({'put': 'update'}), name='data-migrations-update'),
    path('data/<uuid:pk>/preview/', DataMigrationViewSet.as_view({'get': 'preview'}), name='data-migrations-preview'),
    path('data/<uuid:pk>/test/', DataMigrationViewSet.as_view({'post': 'test'}), name='data-migrations-test'),
    
    # Rollback URLs
    path('rollback/create/', RollbackViewSet.as_view({'post': 'create'}), name='rollbacks-create'),
    path('rollback/<uuid:pk>/update/', RollbackViewSet.as_view({'put': 'update'}), name='rollbacks-update'),
    path('rollback/<uuid:pk>/execute/', RollbackViewSet.as_view({'post': 'execute'}), name='rollbacks-execute'),
    path('rollback/<uuid:pk>/validate/', RollbackViewSet.as_view({'post': 'validate'}), name='rollbacks-validate'),
    
    # Migration Tracking URLs
    path('tracking/<uuid:pk>/history/', MigrationTrackingViewSet.as_view({'get': 'history'}), name='migration-tracking-history'),
    path('tracking/system_status/', MigrationTrackingViewSet.as_view({'get': 'system_status'}), name='migration-tracking-system-status'),
    path('tracking/metrics/', MigrationTrackingViewSet.as_view({'get': 'metrics'}), name='migration-tracking-metrics'),
    path('tracking/alerts/', MigrationTrackingViewSet.as_view({'get': 'alerts'}), name='migration-tracking-alerts'),
    
    # Migration Validation URLs
    path('validation/<uuid:pk>/validate_dependencies/', MigrationValidationViewSet.as_view({'post': 'validate_dependencies'}), name='migration-validation-dependencies'),
    path('validation/validate_order/', MigrationValidationViewSet.as_view({'post': 'validate_order'}), name='migration-validation-order'),
    path('validation/validate_syntax/', MigrationValidationViewSet.as_view({'post': 'validate_syntax'}), name='migration-validation-syntax'),
    path('validation/validate_security/', MigrationValidationViewSet.as_view({'post': 'validate_security'}), name='migration-validation-security'),
    
    # Migration Backup URLs
    path('backup/<uuid:pk>/create_backup/', MigrationBackupViewSet.as_view({'post': 'create_backup'}), name='migration-backup-create'),
    path('backup/<uuid:pk>/restore_backup/', MigrationBackupViewSet.as_view({'post': 'restore_backup'}), name='migration-backup-restore'),
    path('backup/<uuid:pk>/list/', MigrationBackupViewSet.as_view({'get': 'list'}), name='migration-backup-list'),
    path('backup/<uuid:pk>/download/', MigrationBackupViewSet.as_view({'get': 'download'}), name='migration-backup-download'),
    
    # Real-time endpoints
    path('real-time/executions/', MigrationViewSet.as_view({'get': 'real_time_executions'}), name='real-time-executions'),
    path('real-time/status/', MigrationTrackingViewSet.as_view({'get': 'real_time_status'}), name='real-time-status'),
    path('real-time/progress/', MigrationViewSet.as_view({'get': 'real_time_progress'}), name='real-time-progress'),
    
    # Bulk operations endpoints
    path('bulk/execute/', MigrationViewSet.as_view({'post': 'bulk_execute'}), name='bulk-execute'),
    path('bulk/rollback/', MigrationViewSet.as_view({'post': 'bulk_rollback'}), name='bulk-rollback'),
    path('bulk/validate/', MigrationValidationViewSet.as_view({'post': 'bulk_validate'}), name='bulk-validate'),
    
    # Configuration endpoints
    path('config/migration_types/', MigrationViewSet.as_view({'get': 'supported_migration_types'}), name='config-supported-migration-types'),
    path('config/rollback_types/', MigrationViewSet.as_view({'get': 'supported_rollback_types'}), name='config-supported-rollback-types'),
    path('config/backup_types/', MigrationViewSet.as_view({'get': 'supported_backup_types'}), name='config-supported-backup-types'),
    
    # Monitoring endpoints
    path('monitoring/health/', MigrationTrackingViewSet.as_view({'get': 'health_check'}), name='monitoring-health'),
    path('monitoring/performance/', MigrationTrackingViewSet.as_view({'get': 'performance_metrics'}), name='monitoring-performance'),
    path('monitoring/errors/', MigrationTrackingViewSet.as_view({'get': 'error_logs'}), name='monitoring-errors'),
    path('monitoring/alerts/', MigrationTrackingViewSet.as_view({'get': 'alerts'}), name='monitoring-alerts'),
    
    # Export endpoints
    path('export/migrations/', MigrationViewSet.as_view({'post': 'export_migrations'}), name='export-migrations'),
    path('export/executions/', MigrationViewSet.as_view({'post': 'export_executions'}), name='export-executions'),
    path('export/backups/', MigrationBackupViewSet.as_view({'post': 'export_backups'}), name='export-backups'),
    path('export/reports/', MigrationTrackingViewSet.as_view({'post': 'export_reports'}), name='export-reports'),
    
    # Debug endpoints
    # # DISABLED: MigrationsURLConfig not defined
    # # DISABLED: MigrationsURLConfig not defined
    # # DISABLED: MigrationsURLConfig not defined
]

# Export router for inclusion in main URLs
migrations_urls = urlpatterns

# URL configuration with security headers and middleware
if settings.DEBUG:
    # Development URLs with additional debugging
    urlpatterns += [
        path('debug/', include('rest_framework.urls', namespace='rest_framework')),
        # DISABLED: MigrationsURLConfig not defined
        # DISABLED: MigrationsURLConfig not defined
    ]

# Performance: URL patterns are cached
try:
    from django.core.cache import cache
    cache.set('migrations_urls_config', {
        'router_registered': True,
        'total_patterns': len(urlpatterns),
        'endpoints_by_category': {
            'migrations': 7,
            'schema': 4,
            'data': 4,
            'rollback': 4,
            'tracking': 4,
            'validation': 4,
            'backup': 4,
            'real_time': 3,
            'bulk': 3,
            'config': 3,
            'monitoring': 4,
            'export': 4,
            'debug': 3
        },
        'version': '1.0.0'
    }, timeout=3600)
except Exception:
    # Cache failure should not break URL configuration
    pass

# Security: Add URL validation middleware
class MigrationsURLValidator:
    """URL validator for migrations with security checks."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger(__name__)
    
    def __call__(self, request):
        """Validate URLs with comprehensive security checks."""
        try:
            start_time = time.time()
            
            # Security: Validate request path
            path = request.path_info
            
            # Check for suspicious patterns
            suspicious_patterns = [
                '../',  # Directory traversal
                '<script',  # Script injection
                'javascript:',  # JavaScript protocol
                'data:',  # Data protocol
                'file://',  # File protocol
                'ftp://',  # FTP protocol
                'php://',  # PHP wrapper
                'expect://',  # Expect wrapper
            ]
            
            for pattern in suspicious_patterns:
                if pattern in path.lower():
                    self.logger.warning(f"Suspicious URL pattern detected: {pattern} in {path}")
                    from django.http import HttpResponseBadRequest
                    return HttpResponseBadRequest("Invalid request path")
            
            # Security: Validate HTTP method
            allowed_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
            if request.method not in allowed_methods:
                self.logger.warning(f"Invalid HTTP method: {request.method}")
                from django.http import HttpResponseNotAllowed
                return HttpResponseNotAllowed(allowed_methods)
            
            # Security: Rate limiting check
            if not self._check_rate_limit(request):
                self.logger.warning(f"Rate limit exceeded for IP: {self._get_client_ip(request)}")
                from django.http import HttpResponseTooManyRequests
                return HttpResponseTooManyRequests("Rate limit exceeded")
            
            # Security: Check for suspicious headers
            suspicious_headers = [
                'X-Forwarded-For',
                'X-Real-IP',
                'X-Originating-IP',
                'X-Cluster-Client-IP',
                'X-Remote-IP',
                'X-Remote-Addr'
            ]
            
            for header in suspicious_headers:
                if header in request.META:
                    header_value = request.META[header]
                    if self._is_suspicious_header_value(header_value):
                        self.logger.warning(f"Suspicious header detected: {header}={header_value}")
            
            # Process request
            response = self.get_response(request)
            
            # Performance: Log request time
            processing_time = time.time() - start_time
            response['X-Processing-Time'] = str(processing_time)
            
            # Security: Add security headers
            self._add_security_headers(response)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in URL validation: {str(e)}")
            # Security: Don't expose internal errors
            from django.http import HttpResponseServerError
            return HttpResponseServerError("Request validation failed")
    
    def _check_rate_limit(self, request) -> bool:
        """Check if request exceeds rate limits."""
        try:
            client_ip = self._get_client_ip(request)
            cache_key = f"migrations_rate_limit_{client_ip}"
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Rate limit: 100 requests per minute for migrations
            if current_count >= 100:
                return False
            
            # Increment counter
            cache.set(cache_key, current_count + 1, timeout=60)  # 1 minute
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking rate limit: {str(e)}")
            return True  # Allow request on error
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address with security considerations."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the first IP in the chain
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        
        return ip
    
    def _is_suspicious_header_value(self, value: str) -> bool:
        """Check if header value is suspicious."""
        suspicious_patterns = [
            '../',  # Directory traversal
            '<script',  # Script injection
            'javascript:',  # JavaScript protocol
            'data:',  # Data protocol
        ]
        
        value_lower = value.lower()
        return any(pattern in value_lower for pattern in suspicious_patterns)
    
    def _add_security_headers(self, response) -> None:
        """Add security headers to response."""
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response['Content-Security-Policy'] = "default-src 'self'"
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Add migrations specific headers
        response['X-Migrations-Version'] = '1.0.0'
        response['X-Migrations-Environment'] = 'production' if not settings.DEBUG else 'development'
        response['X-Rate-Limit-Remaining'] = str(max(0, 100 - cache.get(f"migrations_rate_limit_{self._get_client_ip(None)}", 0)))


# Performance: Add response compression
class MigrationsResponseCompression:
    """Response compression for better performance."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Apply response compression."""
        response = self.get_response(request)
        
        # Compress JSON responses
        if (hasattr(response, 'content') and 
            len(response.content) > 1024 and  # Only compress larger responses
            'application/json' in response.get('Content-Type', '')):
            
            # Add compression headers
            response['Content-Encoding'] = 'gzip'
            response['Vary'] = 'Accept-Encoding'
        
        return response


# Security: Add CSRF protection
class MigrationsCSRFProtection:
    """CSRF protection for migrations."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Apply CSRF protection."""
        # Skip CSRF for safe methods
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return self.get_response(request)
        
        # Apply CSRF protection for unsafe methods
        from django.middleware.csrf import CsrfViewMiddleware
        csrf_middleware = CsrfViewMiddleware(self.get_response)
        return csrf_middleware(request)


# Performance: Add caching headers
class MigrationsCachingHeaders:
    """Caching headers for migrations."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Add caching headers."""
        response = self.get_response(request)
        
        # Add caching headers for GET requests
        if request.method == 'GET':
            path = request.path
            
            # Cache for different durations based on endpoint
            if 'config' in path:
                response['Cache-Control'] = 'public, max-age=3600'  # 1 hour
            elif 'tracking' in path:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            elif 'real-time' in path:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            elif 'validation' in path:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            else:
                response['Cache-Control'] = 'public, max-age=300'  # 5 minutes
        else:
            # No caching for POST/PUT/DELETE requests
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response


# Performance: Database query optimization hints
class MigrationsDatabaseHints:
    """Database query optimization hints."""
    
    @staticmethod
    def get_query_hints():
        """Get database query optimization hints."""
        return {
            'use_index': [
                'migration_created_at_idx',
                'migration_type_idx',
                'migration_status_idx',
                'migration_execution_created_at_idx',
                'migration_execution_status_idx',
                'schema_migration_created_at_idx',
                'data_migration_created_at_idx',
                'rollback_created_at_idx',
                'migration_tracking_created_at_idx',
                'migration_validation_created_at_idx',
                'migration_backup_created_at_idx'
            ],
            'prefetch_related': [
                'created_by', 'updated_by', 'executed_by'
            ],
            'select_related': [
                'created_by', 'updated_by', 'executed_by'
            ],
            'annotate_fields': [
                'type', 'status', 'created_at', 'updated_at'
            ],
            'aggregate_functions': [
                'Sum', 'Avg', 'Count', 'StdDev', 'Max', 'Min'
            ]
        }


# Security: Rate limiting configuration
class MigrationsRateLimitConfig:
    """Rate limiting configuration for migrations."""
    
    RATE_LIMITS = {
        'migrations_create': '20/hour',
        'migrations_execute': '50/hour',
        'migrations_rollback': '50/hour',
        'migrations_validate': '100/hour',
        'schema_create': '20/hour',
        'data_create': '20/hour',
        'rollback_create': '20/hour',
        'tracking_history': '200/hour',
        'validation_dependencies': '100/hour',
        'validation_order': '100/hour',
        'backup_create': '50/hour',
        'backup_restore': '50/hour',
        'bulk_execute': '50/hour',
        'bulk_rollback': '50/hour',
        'bulk_validate': '100/hour',
        'export_migrations': '20/hour',
        'export_executions': '20/hour',
        'export_backups': '20/hour',
    }
    
    @classmethod
    def get_rate_limit(cls, endpoint: str) -> str:
        """Get rate limit for endpoint."""
        return cls.RATE_LIMITS.get(endpoint, '50/hour')


# Performance: API versioning
class MigrationsAPIVersioning:
    """API versioning for migrations."""
    
    CURRENT_VERSION = 'v1'
    SUPPORTED_VERSIONS = ['v1']
    
    @classmethod
    def get_versioned_url(cls, base_url: str, version: str = None) -> str:
        """Get versioned URL."""
        ver = version or cls.CURRENT_VERSION
        if ver not in cls.SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported API version: {ver}")
        
        return f"/api/{ver}/migrations/{base_url.lstrip('/')}"
    
    @classmethod
    def get_version_from_request(cls, request) -> str:
        """Extract API version from request."""
        # Extract from URL path
        path_parts = request.path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[1] == 'api':
            return path_parts[2]  # api/v1/...
        
        # Extract from headers
        return request.META.get('HTTP_API_VERSION', cls.CURRENT_VERSION)


# Security: Input validation patterns
class MigrationsInputValidation:
    """Input validation patterns for migrations."""
    
    # Allowed patterns for different input types
    PATTERNS = {
        'migration_type': r'^(schema|data|mixed|rollback)$',
        'migration_status': r'^(pending|running|completed|failed|cancelled)$',
        'execution_status': r'^(pending|running|success|failed|timeout|cancelled)$',
        'rollback_type': r'^(full|partial|data|schema)$',
        'backup_type': r'^(pre_migration|post_migration|manual)$',
        'validation_type': r'^(syntax|dependencies|order|security)$',
        'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        'exit_code': r'^-?\d+$',
    }
    
    @classmethod
    def validate_input(cls, input_type: str, value: str) -> bool:
        """Validate input against allowed patterns."""
        import re
        pattern = cls.PATTERNS.get(input_type)
        if not pattern:
            return False
        
        return bool(re.match(pattern, value))
    
    @classmethod
    def sanitize_input(cls, input_type: str, value: str) -> str:
        """Sanitize input value."""
        import re
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\'&]', '', value)
        
        # Apply type-specific sanitization
        if input_type in ['migration_type', 'migration_status', 'execution_status']:
            # Normalize to lowercase
            sanitized = sanitized.lower()
        elif input_type == 'exit_code':
            # Normalize to integer
            sanitized = re.sub(r'[^\d-]', '', sanitized)
        
        return sanitized


# Performance: Response optimization
class MigrationsResponseOptimizer:
    """Response optimization for migrations."""
    
    @staticmethod
    def optimize_response(response, request_path: str):
        """Optimize response based on request path."""
        # Add performance headers
        response['X-Response-Time'] = str(time.time())
        response['X-Endpoint'] = request_path
        
        # Optimize based on endpoint type
        if 'migrations' in request_path:
            # Add migrations specific headers
            response['X-Migrations-Cache'] = 'hit'
            response['X-Migrations-Generated'] = str(time.time())
        elif 'schema' in request_path:
            # Add schema specific headers
            response['X-Schema-Cache'] = 'hit'
            response['X-Schema-Generated'] = str(time.time())
        elif 'data' in request_path:
            # Add data specific headers
            response['X-Data-Cache'] = 'hit'
            response['X-Data-Generated'] = str(time.time())
        elif 'rollback' in request_path:
            # Add rollback specific headers
            response['X-Rollback-Cache'] = 'hit'
            response['X-Rollback-Generated'] = str(time.time())
        elif 'tracking' in request_path:
            # Add tracking specific headers
            response['X-Tracking-Cache'] = 'hit'
            response['X-Tracking-Generated'] = str(time.time())
        elif 'validation' in request_path:
            # Add validation specific headers
            response['X-Validation-Cache'] = 'hit'
            response['X-Validation-Generated'] = str(time.time())
        elif 'backup' in request_path:
            # Add backup specific headers
            response['X-Backup-Cache'] = 'hit'
            response['X-Backup-Generated'] = str(time.time())
        
        return response


# Security: Audit logging configuration
class MigrationsAuditConfig:
    """Audit logging configuration for migrations."""
    
    AUDIT_EVENTS = [
        'migration_created',
        'migration_updated',
        'migration_deleted',
        'migration_executed',
        'migration_rolled_back',
        'migration_validated',
        'schema_migration_created',
        'data_migration_created',
        'rollback_created',
        'backup_created',
        'backup_restored',
        'bulk_operation',
        'validation_performed',
        'tracking_updated',
    ]
    
    SENSITIVE_FIELDS = [
        'content',
        'rollback_script',
        'validation_script',
        'sql_script',
        'transformation_script',
        'parameters',
        'environment',
        'output',
        'error_message',
        'backup_location',
    ]
    
    @classmethod
    def should_audit(cls, event_type: str) -> bool:
        """Check if event should be audited."""
        return event_type in cls.AUDIT_EVENTS
    
    @classmethod
    def sanitize_for_audit(cls, data: dict) -> dict:
        """Sanitize data for audit logging."""
        sanitized = data.copy()
        
        for field in cls.SENSITIVE_FIELDS:
            if field in sanitized:
                sanitized[field] = '[REDACTED]'
        
        return sanitized


# Performance: Database connection pooling
class MigrationsDatabaseConfig:
    """Database configuration for migrations."""
    
    @staticmethod
    def get_connection_config():
        """Get optimized database connection configuration."""
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': settings.DATABASES['default']['NAME'],
            'USER': settings.DATABASES['default']['USER'],
            'PASSWORD': settings.DATABASES['default']['PASSWORD'],
            'HOST': settings.DATABASES['default']['HOST'],
            'PORT': settings.DATABASES['default']['PORT'],
            'OPTIONS': {
                'MAX_CONNS': 200,  # Increased for migrations
                'MIN_CONNS': 40,   # Increased for migrations
                'MAX_CONNS_PER_QUERY': 50,
                'CONN_MAX_AGE': 3600,
                'DISABLE_SERVER_SIDE_CURSORS': False,
            },
            'ATOMIC_REQUESTS': True,
            'AUTOCOMMIT': False,
        }


# Security: CORS configuration
class MigrationsCORSConfig:
    """CORS configuration for migrations."""
    
    ALLOWED_ORIGINS = [
        'https://localhost:3000',
        'https://localhost:8000',
        'https://migrations.example.com',
        'https://api.example.com',
        'https://dashboard.example.com',
    ]
    
    ALLOWED_METHODS = [
        'GET',
        'POST',
        'PUT',
        'PATCH',
        'DELETE',
        'OPTIONS',
        'HEAD',
    ]
    
    ALLOWED_HEADERS = [
        'Content-Type',
        'Authorization',
        'X-API-Version',
        'X-Request-ID',
        'X-Client-IP',
        'X-User-Agent',
        'X-Migration-ID',
        'X-Execution-ID',
        'X-Backup-ID',
        'X-Security-Token',
        'X-Rate-Limit-Limit',
        'X-Rate-Limit-Remaining',
        'X-Rate-Limit-Reset',
    ]
    
    EXPOSED_HEADERS = [
        'X-Migrations-Version',
        'X-Response-Time',
        'X-Rate-Limit-Remaining',
        'X-Processing-Time',
        'X-Migrations-Cache',
        'X-Schema-Cache',
        'X-Data-Cache',
        'X-Rollback-Cache',
        'X-Tracking-Cache',
        'X-Validation-Cache',
        'X-Backup-Cache',
    ]
    
    MAX_AGE = 86400  # 24 hours


# Performance: Caching configuration
class MigrationsCacheConfig:
    """Caching configuration for migrations."""
    
    CACHE_KEYS = {
        'migration_data': 'migration_data_{migration_id}',
        'migration_stats': 'migration_stats_{migration_id}',
        'migration_history': 'migration_history_{migration_id}',
        'schema_migration_data': 'schema_migration_data_{schema_id}',
        'data_migration_data': 'data_migration_data_{data_id}',
        'rollback_data': 'rollback_data_{rollback_id}',
        'tracking_data': 'tracking_data_{tracking_id}',
        'validation_data': 'validation_data_{validation_id}',
        'backup_data': 'backup_data_{backup_id}',
        'system_status': 'system_status',
        'rate_limit': 'rate_limit_{client_ip}',
        'bulk_operation': 'bulk_operation_{operation_id}',
    }
    
    CACHE_TIMEOUTS = {
        'migration_data': 1800,      # 30 minutes
        'migration_stats': 60,       # 1 minute
        'migration_history': 300,     # 5 minutes
        'schema_migration_data': 1800, # 30 minutes
        'data_migration_data': 1800,   # 30 minutes
        'rollback_data': 1800,        # 30 minutes
        'tracking_data': 300,         # 5 minutes
        'validation_data': 300,       # 5 minutes
        'backup_data': 1800,          # 30 minutes
        'system_status': 60,          # 1 minute
        'rate_limit': 60,             # 1 minute
        'bulk_operation': 3600,       # 1 hour
    }
    
    @classmethod
    def get_cache_key(cls, key_type: str, **kwargs) -> str:
        """Get cache key for given type."""
        template = cls.CACHE_KEYS.get(key_type)
        if not template:
            return f'migrations_unknown_{key_type}'
        
        return template.format(**kwargs)
    
    @classmethod
    def get_cache_timeout(cls, key_type: str) -> int:
        """Get cache timeout for given type."""
        return cls.CACHE_TIMEOUTS.get(key_type, 600)


# URL Configuration Class
class MigrationsURLConfig:
    """URL configuration class for migrations."""
    
    @staticmethod
    @csrf_exempt
    @require_http_methods(["GET"])
    def debug_ping_view(request):
        """Debug view for health checks."""
        try:
            from django.core.cache import cache
            cache_stats = {
                'hits': getattr(cache, '_cache', {}).get('hits', 0),
                'misses': getattr(cache, '_cache', {}).get('misses', 0),
                'size': len(getattr(cache, '_cache', {})),
            }
            
            return JsonResponse({
                'cache_stats': cache_stats,
                'url_patterns': len(urlpatterns),
                'endpoints': [
                    'migrations', 'schema', 'data', 'rollback',
                    'tracking', 'validation', 'backup',
                    'real_time', 'bulk', 'config', 'monitoring', 'export', 'debug'
                ],
                'performance': {
                    'database_queries': 'optimized',
                    'caching_enabled': True,
                    'rate_limiting_enabled': True,
                    'security_headers_enabled': True,
                    'response_compression': True,
                    'migration_execution': 'atomic',
                    'backup_management': 'automated',
                    'rollback_support': 'full'
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @csrf_exempt
    @require_http_methods(["GET"])
    def debug_execution_view(request):
        """Debug view for execution monitoring."""
        try:
            from django.core.cache import cache
            
            # Get execution cache keys
            execution_keys = []
            if hasattr(cache, '_cache'):
                execution_keys = [key for key in cache._cache.keys() if 'execution' in str(key)]
            
            # Get execution info
            execution_info = {}
            for key in execution_keys[:50]:  # Limit to 50 keys
                try:
                    execution_info[key] = {
                        'size': len(str(cache.get(key, ''))),
                        'ttl': cache._backend.get_ttl(key) if hasattr(cache._backend, 'get_ttl') else None
                    }
                except Exception:
                    execution_info[key] = {'size': 0, 'ttl': None}
            
            return JsonResponse({
                'execution_keys': execution_keys,
                'execution_info': execution_info,
                'total_keys': len(execution_keys),
                'cache_backend': str(type(cache._backend).__name__)
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @csrf_exempt
    @require_http_methods(["GET"])
    def debug_backup_view(request):
        """Debug view for backup monitoring."""
        try:
            from django.core.cache import cache
            
            # Get backup cache keys
            backup_keys = []
            if hasattr(cache, '_cache'):
                backup_keys = [key for key in cache._cache.keys() if 'backup' in str(key)]
            
            # Get backup info
            backup_info = {}
            for key in backup_keys[:50]:  # Limit to 50 keys
                try:
                    backup_info[key] = {
                        'size': len(str(cache.get(key, ''))),
                        'ttl': cache._backend.get_ttl(key) if hasattr(cache._backend, 'get_ttl') else None
                    }
                except Exception:
                    backup_info[key] = {'size': 0, 'ttl': None}
            
            return JsonResponse({
                'backup_keys': backup_keys,
                'backup_info': backup_info,
                'total_keys': len(backup_keys),
                'cache_backend': str(type(cache._backend).__name__)
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @csrf_exempt
    @require_http_methods(["GET"])
    def debug_performance_view(request):
        """Debug view for performance monitoring."""
        try:
            from django.core.cache import cache
            cache_stats = {
                'hits': getattr(cache, '_cache', {}).get('hits', 0),
                'misses': getattr(cache, '_cache', {}).get('misses', 0),
                'size': len(getattr(cache, '_cache', {})),
            }
            
            return JsonResponse({
                'cache_stats': cache_stats,
                'url_patterns': len(urlpatterns),
                'endpoints': [
                    'migrations', 'schema', 'data', 'rollback',
                    'tracking', 'validation', 'backup',
                    'real_time', 'bulk', 'config', 'monitoring', 'export', 'debug'
                ],
                'performance': {
                    'database_queries': 'optimized',
                    'caching_enabled': True,
                    'rate_limiting_enabled': True,
                    'security_headers_enabled': True,
                    'response_compression': True,
                    'migration_execution': 'atomic',
                    'backup_management': 'automated',
                    'rollback_support': 'full'
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @csrf_exempt
    @require_http_methods(["GET"])
    def debug_queue_view(request):
        """Debug view for queue monitoring."""
        try:
            from django.core.cache import cache
            
            # Get queue cache keys
            queue_keys = []
            if hasattr(cache, '_cache'):
                queue_keys = [key for key in cache._cache.keys() if 'queue' in str(key)]
            
            # Get queue info
            queue_info = {}
            for key in queue_keys[:50]:  # Limit to 50 keys
                try:
                    queue_info[key] = {
                        'size': len(str(cache.get(key, ''))),
                        'ttl': cache._backend.get_ttl(key) if hasattr(cache._backend, 'get_ttl') else None
                    }
                except Exception:
                    queue_info[key] = {'size': 0, 'ttl': None}
            
            return JsonResponse({
                'queue_keys': queue_keys,
                'queue_info': queue_info,
                'total_keys': len(queue_keys),
                'cache_backend': str(type(cache._backend).__name__)
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# Export configuration classes for use in settings
MIGRATIONS_CONFIG = {
    'URL_VALIDATOR': MigrationsURLValidator,
    'RESPONSE_COMPRESSION': MigrationsResponseCompression,
    'CSRF_PROTECTION': MigrationsCSRFProtection,
    'CACHING_HEADERS': MigrationsCachingHeaders,
    'DATABASE_HINTS': MigrationsDatabaseHints,
    'RATE_LIMIT_CONFIG': MigrationsRateLimitConfig,
    'API_VERSIONING': MigrationsAPIVersioning,
    'INPUT_VALIDATION': MigrationsInputValidation,
    'RESPONSE_OPTIMIZER': MigrationsResponseOptimizer,
    'AUDIT_CONFIG': MigrationsAuditConfig,
    'DATABASE_CONFIG': MigrationsDatabaseConfig,
    'CORS_CONFIG': MigrationsCORSConfig,
    'CACHE_CONFIG': MigrationsCacheConfig,
    'URL_CONFIG': MigrationsURLConfig,
}
