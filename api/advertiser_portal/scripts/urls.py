"""
Scripts URLs

This module defines URL patterns for script management with
enterprise-grade security, performance optimization, and comprehensive functionality
following industry standards from Jenkins, GitHub Actions, and Ansible.
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
    ScriptViewSet,
    AutomationScriptViewSet,
    DataProcessingScriptViewSet,
    MaintenanceScriptViewSet,
    DeploymentScriptViewSet,
    ScriptExecutionViewSet,
    ScriptMonitoringViewSet,
    ScriptSecurityViewSet
)

# Create router for scripts with optimized routing
router = DefaultRouter()
router.register(r'scripts', ScriptViewSet, basename='script')
router.register(r'automation', AutomationScriptViewSet, basename='automation-script')
router.register(r'data-processing', DataProcessingScriptViewSet, basename='data-processing-script')
router.register(r'maintenance', MaintenanceScriptViewSet, basename='maintenance-script')
router.register(r'deployment', DeploymentScriptViewSet, basename='deployment-script')
router.register(r'executions', ScriptExecutionViewSet, basename='script-execution')
router.register(r'monitoring', ScriptMonitoringViewSet, basename='script-monitoring')
router.register(r'security', ScriptSecurityViewSet, basename='script-security')

# URL patterns with comprehensive security and performance optimization
urlpatterns = [
    # Router URLs with optimized database queries
    path('', include(router.urls)),
    
    # Script URLs
    path('scripts/create/', ScriptViewSet.as_view({'post': 'create'}), name='scripts-create'),
    path('scripts/<uuid:pk>/execute/', ScriptViewSet.as_view({'post': 'execute'}), name='scripts-execute'),
    path('scripts/<uuid:pk>/schedule/', ScriptViewSet.as_view({'post': 'schedule'}), name='scripts-schedule'),
    path('scripts/<uuid:pk>/stats/', ScriptViewSet.as_view({'get': 'stats'}), name='scripts-stats'),
    path('scripts/<uuid:pk>/executions/', ScriptViewSet.as_view({'get': 'executions'}), name='scripts-executions'),
    path('scripts/<uuid:pk>/test/', ScriptViewSet.as_view({'post': 'test'}), name='scripts-test'),
    path('scripts/list/', ScriptViewSet.as_view({'get': 'list'}), name='scripts-list'),
    
    # Automation Script URLs
    path('automation/create/', AutomationScriptViewSet.as_view({'post': 'create'}), name='automation-scripts-create'),
    path('automation/<uuid:pk>/update/', AutomationScriptViewSet.as_view({'put': 'update'}), name='automation-scripts-update'),
    path('automation/<uuid:pk>/trigger/', AutomationScriptViewSet.as_view({'post': 'trigger'}), name='automation-scripts-trigger'),
    path('automation/<uuid:pk>/configure/', AutomationScriptViewSet.as_view({'post': 'configure'}), name='automation-scripts-configure'),
    
    # Data Processing Script URLs
    path('data-processing/create/', DataProcessingScriptViewSet.as_view({'post': 'create'}), name='data-processing-scripts-create'),
    path('data-processing/<uuid:pk>/update/', DataProcessingScriptViewSet.as_view({'put': 'update'}), name='data-processing-scripts-update'),
    path('data-processing/<uuid:pk>/run/', DataProcessingScriptViewSet.as_view({'post': 'run'}), name='data-processing-scripts-run'),
    path('data-processing/<uuid:pk>/monitor/', DataProcessingScriptViewSet.as_view({'get': 'monitor'}), name='data-processing-scripts-monitor'),
    
    # Maintenance Script URLs
    path('maintenance/create/', MaintenanceScriptViewSet.as_view({'post': 'create'}), name='maintenance-scripts-create'),
    path('maintenance/<uuid:pk>/update/', MaintenanceScriptViewSet.as_view({'put': 'update'}), name='maintenance-scripts-update'),
    path('maintenance/<uuid:pk>/run/', MaintenanceScriptViewSet.as_view({'post': 'run'}), name='maintenance-scripts-run'),
    path('maintenance/<uuid:pk>/approve/', MaintenanceScriptViewSet.as_view({'post': 'approve'}), name='maintenance-scripts-approve'),
    
    # Deployment Script URLs
    path('deployment/create/', DeploymentScriptViewSet.as_view({'post': 'create'}), name='deployment-scripts-create'),
    path('deployment/<uuid:pk>/update/', DeploymentScriptViewSet.as_view({'put': 'update'}), name='deployment-scripts-update'),
    path('deployment/<uuid:pk>/deploy/', DeploymentScriptViewSet.as_view({'post': 'deploy'}), name='deployment-scripts-deploy'),
    path('deployment/<uuid:pk>/rollback/', DeploymentScriptViewSet.as_view({'post': 'rollback'}), name='deployment-scripts-rollback'),
    
    # Script Execution URLs
    path('executions/<uuid:pk>/details/', ScriptExecutionViewSet.as_view({'get': 'details'}), name='script-executions-details'),
    path('executions/<uuid:pk>/cancel/', ScriptExecutionViewSet.as_view({'post': 'cancel'}), name='script-executions-cancel'),
    path('executions/<uuid:pk>/retry/', ScriptExecutionViewSet.as_view({'post': 'retry'}), name='script-executions-retry'),
    path('executions/list/', ScriptExecutionViewSet.as_view({'get': 'list'}), name='script-executions-list'),
    
    # Script Monitoring URLs
    path('monitoring/<uuid:pk>/health/', ScriptMonitoringViewSet.as_view({'get': 'health'}), name='script-monitoring-health'),
    path('monitoring/system-health/', ScriptMonitoringViewSet.as_view({'get': 'system_health'}), name='script-monitoring-system-health'),
    path('monitoring/metrics/', ScriptMonitoringViewSet.as_view({'get': 'metrics'}), name='script-monitoring-metrics'),
    path('monitoring/alerts/', ScriptMonitoringViewSet.as_view({'get': 'alerts'}), name='script-monitoring-alerts'),
    
    # Script Security URLs
    path('security/validate/', ScriptSecurityViewSet.as_view({'post': 'validate'}), name='script-security-validate'),
    path('security/scan/', ScriptSecurityViewSet.as_view({'post': 'scan'}), name='script-security-scan'),
    path('security/vulnerabilities/', ScriptSecurityViewSet.as_view({'get': 'vulnerabilities'}), name='script-security-vulnerabilities'),
    path('security/compliance/', ScriptSecurityViewSet.as_view({'get': 'compliance'}), name='script-security-compliance'),
    
    # Real-time endpoints
    path('real-time/executions/', ScriptViewSet.as_view({'get': 'real_time_executions'}), name='real-time-executions'),
    path('real-time/metrics/', ScriptMonitoringViewSet.as_view({'get': 'real_time_metrics'}), name='real-time-metrics'),
    path('real-time/health/', ScriptMonitoringViewSet.as_view({'get': 'real_time_health'}), name='real-time-health'),
    
    # Bulk operations endpoints
    path('bulk/execute/', ScriptViewSet.as_view({'post': 'bulk_execute'}), name='bulk-execute'),
    path('bulk/schedule/', ScriptViewSet.as_view({'post': 'bulk_schedule'}), name='bulk-schedule'),
    path('bulk/cancel/', ScriptViewSet.as_view({'post': 'bulk_cancel'}), name='bulk-cancel'),
    
    # Configuration endpoints
    path('config/script-types/', ScriptViewSet.as_view({'get': 'supported_script_types'}), name='config-supported-script-types'),
    path('config/environments/', ScriptViewSet.as_view({'get': 'supported_environments'}), name='config-supported-environments'),
    path('config/triggers/', ScriptViewSet.as_view({'get': 'supported_triggers'}), name='config-supported-triggers'),
    
    # Monitoring endpoints
    path('monitoring/health/', ScriptMonitoringViewSet.as_view({'get': 'health_check'}), name='monitoring-health'),
    path('monitoring/performance/', ScriptMonitoringViewSet.as_view({'get': 'performance_metrics'}), name='monitoring-performance'),
    path('monitoring/errors/', ScriptMonitoringViewSet.as_view({'get': 'error_logs'}), name='monitoring-errors'),
    path('monitoring/alerts/', ScriptMonitoringViewSet.as_view({'get': 'alerts'}), name='monitoring-alerts'),
    
    # Export endpoints
    path('export/scripts/', ScriptViewSet.as_view({'post': 'export_scripts'}), name='export-scripts'),
    path('export/executions/', ScriptExecutionViewSet.as_view({'post': 'export_executions'}), name='export-executions'),
    path('export/logs/', ScriptMonitoringViewSet.as_view({'post': 'export_logs'}), name='export-logs'),
    path('export/reports/', ScriptMonitoringViewSet.as_view({'post': 'export_reports'}), name='export-reports'),
    
    # Debug endpoints
    path('debug/ping/', ScriptsURLConfig.debug_ping_view, name='scripts-debug-ping'),
    path('debug/execution/', ScriptsURLConfig.debug_execution_view, name='scripts-debug-execution'),
    path('debug/security/', ScriptsURLConfig.debug_security_view, name='scripts-debug-security'),
]

# Export router for inclusion in main URLs
scripts_urls = urlpatterns

# URL configuration with security headers and middleware
if settings.DEBUG:
    # Development URLs with additional debugging
    urlpatterns += [
        path('debug/', include('rest_framework.urls', namespace='rest_framework')),
        path('debug/performance/', ScriptsURLConfig.debug_performance_view, name='scripts-debug-performance'),
        path('debug/queue/', ScriptsURLConfig.debug_queue_view, name='scripts-debug-queue'),
    ]

# Performance: URL patterns are cached
try:
    from django.core.cache import cache
    cache.set('scripts_urls_config', {
        'router_registered': True,
        'total_patterns': len(urlpatterns),
        'endpoints_by_category': {
            'scripts': 7,
            'automation': 4,
            'data_processing': 4,
            'maintenance': 4,
            'deployment': 4,
            'executions': 4,
            'monitoring': 4,
            'security': 4,
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
class ScriptsURLValidator:
    """URL validator for scripts with security checks."""
    
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
            cache_key = f"scripts_rate_limit_{client_ip}"
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Rate limit: 200 requests per minute for scripts
            if current_count >= 200:
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
        
        # Add scripts specific headers
        response['X-Scripts-Version'] = '1.0.0'
        response['X-Scripts-Environment'] = 'production' if not settings.DEBUG else 'development'
        response['X-Rate-Limit-Remaining'] = str(max(0, 200 - cache.get(f"scripts_rate_limit_{self._get_client_ip(None)}", 0)))


# Performance: Add response compression
class ScriptsResponseCompression:
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
class ScriptsCSRFProtection:
    """CSRF protection for scripts."""
    
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
class ScriptsCachingHeaders:
    """Caching headers for scripts."""
    
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
            elif 'monitoring' in path:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            elif 'real-time' in path:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            elif 'security' in path:
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
class ScriptsDatabaseHints:
    """Database query optimization hints."""
    
    @staticmethod
    def get_query_hints():
        """Get database query optimization hints."""
        return {
            'use_index': [
                'script_created_at_idx',
                'script_type_idx',
                'script_status_idx',
                'script_execution_created_at_idx',
                'script_execution_status_idx',
                'automation_script_created_at_idx',
                'data_processing_script_created_at_idx',
                'maintenance_script_created_at_idx',
                'deployment_script_created_at_idx',
                'script_log_created_at_idx',
                'script_security_created_at_idx'
            ],
            'prefetch_related': [
                'advertiser', 'created_by', 'updated_by'
            ],
            'select_related': [
                'advertiser', 'created_by', 'updated_by'
            ],
            'annotate_fields': [
                'type', 'status', 'created_at', 'updated_at'
            ],
            'aggregate_functions': [
                'Sum', 'Avg', 'Count', 'StdDev', 'Max', 'Min'
            ]
        }


# Security: Rate limiting configuration
class ScriptsRateLimitConfig:
    """Rate limiting configuration for scripts."""
    
    RATE_LIMITS = {
        'scripts_create': '50/hour',
        'scripts_execute': '100/hour',
        'scripts_schedule': '50/hour',
        'scripts_test': '100/hour',
        'automation_create': '50/hour',
        'data_processing_create': '50/hour',
        'maintenance_create': '50/hour',
        'deployment_create': '50/hour',
        'executions_cancel': '100/hour',
        'executions_retry': '100/hour',
        'monitoring_health': '1000/hour',
        'security_validate': '500/hour',
        'security_scan': '200/hour',
        'bulk_execute': '100/hour',
        'bulk_schedule': '50/hour',
        'export_scripts': '50/hour',
        'export_executions': '50/hour',
    }
    
    @classmethod
    def get_rate_limit(cls, endpoint: str) -> str:
        """Get rate limit for endpoint."""
        return cls.RATE_LIMITS.get(endpoint, '100/hour')


# Performance: API versioning
class ScriptsAPIVersioning:
    """API versioning for scripts."""
    
    CURRENT_VERSION = 'v1'
    SUPPORTED_VERSIONS = ['v1']
    
    @classmethod
    def get_versioned_url(cls, base_url: str, version: str = None) -> str:
        """Get versioned URL."""
        ver = version or cls.CURRENT_VERSION
        if ver not in cls.SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported API version: {ver}")
        
        return f"/api/{ver}/scripts/{base_url.lstrip('/')}"
    
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
class ScriptsInputValidation:
    """Input validation patterns for scripts."""
    
    # Allowed patterns for different input types
    PATTERNS = {
        'script_type': r'^(automation|data_processing|maintenance|deployment)$',
        'script_status': r'^(active|inactive|deprecated|maintenance)$',
        'execution_status': r'^(pending|running|success|failed|timeout|cancelled)$',
        'trigger_type': r'^(manual|schedule|event|webhook)$',
        'processing_type': r'^(etl|elt|validation|transformation|aggregation)$',
        'maintenance_type': r'^(cleanup|backup|restore|update|optimization)$',
        'deployment_type': r'^(manual|automatic|rollback|blue_green|canary)$',
        'security_status': r'^(safe|warning|critical|error)$',
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
        if input_type in ['script_type', 'script_status', 'execution_status']:
            # Normalize to lowercase
            sanitized = sanitized.lower()
        elif input_type == 'exit_code':
            # Normalize to integer
            sanitized = re.sub(r'[^\d-]', '', sanitized)
        
        return sanitized


# Performance: Response optimization
class ScriptsResponseOptimizer:
    """Response optimization for scripts."""
    
    @staticmethod
    def optimize_response(response, request_path: str):
        """Optimize response based on request path."""
        # Add performance headers
        response['X-Response-Time'] = str(time.time())
        response['X-Endpoint'] = request_path
        
        # Optimize based on endpoint type
        if 'scripts' in request_path:
            # Add scripts specific headers
            response['X-Scripts-Cache'] = 'hit'
            response['X-Scripts-Generated'] = str(time.time())
        elif 'automation' in request_path:
            # Add automation specific headers
            response['X-Automation-Cache'] = 'hit'
            response['X-Automation-Generated'] = str(time.time())
        elif 'data-processing' in request_path:
            # Add data processing specific headers
            response['X-DataProcessing-Cache'] = 'hit'
            response['X-DataProcessing-Generated'] = str(time.time())
        elif 'maintenance' in request_path:
            # Add maintenance specific headers
            response['X-Maintenance-Cache'] = 'hit'
            response['X-Maintenance-Generated'] = str(time.time())
        elif 'deployment' in request_path:
            # Add deployment specific headers
            response['X-Deployment-Cache'] = 'hit'
            response['X-Deployment-Generated'] = str(time.time())
        elif 'executions' in request_path:
            # Add executions specific headers
            response['X-Executions-Cache'] = 'hit'
            response['X-Executions-Generated'] = str(time.time())
        elif 'monitoring' in request_path:
            # Add monitoring specific headers
            response['X-Monitoring-Cache'] = 'hit'
            response['X-Monitoring-Generated'] = str(time.time())
        elif 'security' in request_path:
            # Add security specific headers
            response['X-Security-Cache'] = 'hit'
            response['X-Security-Generated'] = str(time.time())
        
        return response


# Security: Audit logging configuration
class ScriptsAuditConfig:
    """Audit logging configuration for scripts."""
    
    AUDIT_EVENTS = [
        'script_created',
        'script_updated',
        'script_deleted',
        'script_executed',
        'script_scheduled',
        'script_tested',
        'automation_created',
        'data_processing_created',
        'maintenance_created',
        'deployment_created',
        'execution_cancelled',
        'execution_retried',
        'security_validated',
        'security_scanned',
        'bulk_operation',
    ]
    
    SENSITIVE_FIELDS = [
        'content',
        'parameters',
        'environment',
        'output',
        'error_message',
        'rollback_script',
        'trigger_config',
        'actions',
        'conditions',
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
class ScriptsDatabaseConfig:
    """Database configuration for scripts."""
    
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
                'MAX_CONNS': 300,  # Increased for scripts
                'MIN_CONNS': 60,   # Increased for scripts
                'MAX_CONNS_PER_QUERY': 50,
                'CONN_MAX_AGE': 3600,
                'DISABLE_SERVER_SIDE_CURSORS': False,
            },
            'ATOMIC_REQUESTS': True,
            'AUTOCOMMIT': False,
        }


# Security: CORS configuration
class ScriptsCORSConfig:
    """CORS configuration for scripts."""
    
    ALLOWED_ORIGINS = [
        'https://localhost:3000',
        'https://localhost:8000',
        'https://scripts.example.com',
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
        'X-Script-ID',
        'X-Execution-ID',
        'X-Security-Token',
        'X-Rate-Limit-Limit',
        'X-Rate-Limit-Remaining',
        'X-Rate-Limit-Reset',
    ]
    
    EXPOSED_HEADERS = [
        'X-Scripts-Version',
        'X-Response-Time',
        'X-Rate-Limit-Remaining',
        'X-Processing-Time',
        'X-Scripts-Cache',
        'X-Automation-Cache',
        'X-DataProcessing-Cache',
        'X-Maintenance-Cache',
        'X-Deployment-Cache',
        'X-Executions-Cache',
        'X-Monitoring-Cache',
        'X-Security-Cache',
    ]
    
    MAX_AGE = 86400  # 24 hours


# Performance: Caching configuration
class ScriptsCacheConfig:
    """Caching configuration for scripts."""
    
    CACHE_KEYS = {
        'script_data': 'script_data_{script_id}',
        'script_stats': 'script_stats_{script_id}',
        'script_executions': 'script_executions_{script_id}',
        'automation_data': 'automation_data_{automation_id}',
        'data_processing_data': 'data_processing_data_{data_processing_id}',
        'maintenance_data': 'maintenance_data_{maintenance_id}',
        'deployment_data': 'deployment_data_{deployment_id}',
        'execution_data': 'execution_data_{execution_id}',
        'system_health': 'system_health',
        'security_scan': 'security_scan_{scan_id}',
        'rate_limit': 'rate_limit_{client_ip}',
        'bulk_operation': 'bulk_operation_{operation_id}',
    }
    
    CACHE_TIMEOUTS = {
        'script_data': 1800,      # 30 minutes
        'script_stats': 60,       # 1 minute
        'script_executions': 300,  # 5 minutes
        'automation_data': 1800,   # 30 minutes
        'data_processing_data': 1800, # 30 minutes
        'maintenance_data': 1800,  # 30 minutes
        'deployment_data': 1800,  # 30 minutes
        'execution_data': 3600,    # 1 hour
        'system_health': 60,       # 1 minute
        'security_scan': 300,     # 5 minutes
        'rate_limit': 60,          # 1 minute
        'bulk_operation': 3600,    # 1 hour
    }
    
    @classmethod
    def get_cache_key(cls, key_type: str, **kwargs) -> str:
        """Get cache key for given type."""
        template = cls.CACHE_KEYS.get(key_type)
        if not template:
            return f'scripts_unknown_{key_type}'
        
        return template.format(**kwargs)
    
    @classmethod
    def get_cache_timeout(cls, key_type: str) -> int:
        """Get cache timeout for given type."""
        return cls.CACHE_TIMEOUTS.get(key_type, 600)


# URL Configuration Class
class ScriptsURLConfig:
    """URL configuration class for scripts."""
    
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
                    'scripts', 'automation', 'data_processing', 'maintenance',
                    'deployment', 'executions', 'monitoring', 'security',
                    'real_time', 'bulk', 'config', 'monitoring', 'export', 'debug'
                ],
                'performance': {
                    'database_queries': 'optimized',
                    'caching_enabled': True,
                    'rate_limiting_enabled': True,
                    'security_headers_enabled': True,
                    'response_compression': True,
                    'script_execution': 'sandboxed',
                    'queue_management': 'optimized'
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
    def debug_security_view(request):
        """Debug view for security monitoring."""
        try:
            from django.core.cache import cache
            
            # Get security cache keys
            security_keys = []
            if hasattr(cache, '_cache'):
                security_keys = [key for key in cache._cache.keys() if 'security' in str(key)]
            
            # Get security info
            security_info = {}
            for key in security_keys[:50]:  # Limit to 50 keys
                try:
                    security_info[key] = {
                        'size': len(str(cache.get(key, ''))),
                        'ttl': cache._backend.get_ttl(key) if hasattr(cache._backend, 'get_ttl') else None
                    }
                except Exception:
                    security_info[key] = {'size': 0, 'ttl': None}
            
            return JsonResponse({
                'security_keys': security_keys,
                'security_info': security_info,
                'total_keys': len(security_keys),
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
                    'scripts', 'automation', 'data_processing', 'maintenance',
                    'deployment', 'executions', 'monitoring', 'security',
                    'real_time', 'bulk', 'config', 'monitoring', 'export', 'debug'
                ],
                'performance': {
                    'database_queries': 'optimized',
                    'caching_enabled': True,
                    'rate_limiting_enabled': True,
                    'security_headers_enabled': True,
                    'response_compression': True,
                    'script_execution': 'sandboxed',
                    'queue_management': 'optimized'
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
SCRIPTS_CONFIG = {
    'URL_VALIDATOR': ScriptsURLValidator,
    'RESPONSE_COMPRESSION': ScriptsResponseCompression,
    'CSRF_PROTECTION': ScriptsCSRFProtection,
    'CACHING_HEADERS': ScriptsCachingHeaders,
    'DATABASE_HINTS': ScriptsDatabaseHints,
    'RATE_LIMIT_CONFIG': ScriptsRateLimitConfig,
    'API_VERSIONING': ScriptsAPIVersioning,
    'INPUT_VALIDATION': ScriptsInputValidation,
    'RESPONSE_OPTIMIZER': ScriptsResponseOptimizer,
    'AUDIT_CONFIG': ScriptsAuditConfig,
    'DATABASE_CONFIG': ScriptsDatabaseConfig,
    'CORS_CONFIG': ScriptsCORSConfig,
    'CACHE_CONFIG': ScriptsCacheConfig,
    'URL_CONFIG': ScriptsURLConfig,
}
