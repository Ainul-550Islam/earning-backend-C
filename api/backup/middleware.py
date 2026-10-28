"""
Backup Module Middleware
Django middleware for backup status monitoring and admin headers
"""

import json
import time
from django.http import HttpResponse
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from .models import Backup, BackupSchedule, BackupAlert


class BackupStatusMiddleware:
    """
    Middleware to add backup status information to admin headers
    and provide real-time backup monitoring
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.start_time = None
        self.cache_timeout = getattr(settings, 'BACKUP_STATUS_CACHE_TIMEOUT', 300)  # 5 minutes
    
    def __call__(self, request):
        self.start_time = time.time()
        
        # Process request
        response = self.get_response(request)
        
        # Add backup status headers if this is an admin request
        if self._is_admin_request(request):
            self._add_backup_headers(response, request)
        
        # Log slow requests if configured
        if self._should_log_slow_request(request, response):
            self._log_slow_request(request, response)
        
        return response
    
    def _is_admin_request(self, request):
        """
        Check if this is an admin request
        """
        path = request.path
        return path.startswith('/admin/') or path.startswith('/api/admin/')
    
    def _add_backup_headers(self, response, request):
        """
        Add backup status information to response headers
        """
        try:
            # Get backup statistics
            backup_stats = self._get_backup_stats()
            
            # Add headers
            response['X-Backup-Status'] = backup_stats['overall_status']
            response['X-Backup-Last-Run'] = backup_stats['last_run']
            response['X-Backup-Total-Count'] = str(backup_stats['total_count'])
            response['X-Backup-Success-Rate'] = f"{backup_stats['success_rate']:.1f}%"
            response['X-Backup-Failed-Count'] = str(backup_stats['failed_count'])
            response['X-Backup-Pending-Count'] = str(backup_stats['pending_count'])
            response['X-Backup-Running-Count'] = str(backup_stats['running_count'])
            
            # Add schedule status
            schedule_stats = self._get_schedule_stats()
            response['X-Backup-Schedule-Count'] = str(schedule_stats['active_count'])
            response['X-Backup-Schedule-Next-Run'] = schedule_stats['next_run']
            
            # Add alert status
            alert_stats = self._get_alert_stats()
            response['X-Backup-Alert-Count'] = str(alert_stats['unresolved_count'])
            response['X-Backup-Critical-Alerts'] = str(alert_stats['critical_count'])
            
            # Add storage status
            storage_stats = self._get_storage_stats()
            response['X-Backup-Storage-Status'] = storage_stats['overall_status']
            response['X-Backup-Storage-Usage'] = f"{storage_stats['usage_percentage']:.1f}%"
            
            # Add performance metrics
            performance_stats = self._get_performance_stats()
            response['X-Backup-Avg-Duration'] = f"{performance_stats['avg_duration']:.1f}s"
            response['X-Backup-Total-Size'] = f"{performance_stats['total_size_mb']:.1f}MB"
            
        except Exception as e:
            # Log error but don't break the request
            import logging
            logger = logging.getLogger('backup.middleware')
            logger.error(f"Error adding backup headers: {str(e)}")
    
    def _get_backup_stats(self):
        """
        Get backup statistics with caching
        """
        cache_key = 'backup_stats'
        stats = cache.get(cache_key)
        
        if stats is None:
            try:
                # Get counts by status
                total_count = Backup.objects.count()
                completed_count = Backup.objects.filter(status='completed').count()
                failed_count = Backup.objects.filter(status='failed').count()
                pending_count = Backup.objects.filter(status='pending').count()
                running_count = Backup.objects.filter(status='running').count()
                
                # Calculate success rate
                success_rate = 0
                if total_count > 0:
                    success_rate = (completed_count / total_count) * 100
                
                # Get last run time
                last_backup = Backup.objects.order_by('-created_at').first()
                last_run = last_backup.created_at.isoformat() if last_backup else None
                
                # Determine overall status
                if failed_count > 0:
                    overall_status = 'error'
                elif running_count > 0:
                    overall_status = 'running'
                elif pending_count > 0:
                    overall_status = 'pending'
                else:
                    overall_status = 'healthy'
                
                stats = {
                    'total_count': total_count,
                    'completed_count': completed_count,
                    'failed_count': failed_count,
                    'pending_count': pending_count,
                    'running_count': running_count,
                    'success_rate': success_rate,
                    'last_run': last_run,
                    'overall_status': overall_status
                }
                
                # Cache the results
                cache.set(cache_key, stats, self.cache_timeout)
                
            except Exception as e:
                # Return default stats on error
                stats = {
                    'total_count': 0,
                    'completed_count': 0,
                    'failed_count': 0,
                    'pending_count': 0,
                    'running_count': 0,
                    'success_rate': 0,
                    'last_run': None,
                    'overall_status': 'unknown'
                }
        
        return stats
    
    def _get_schedule_stats(self):
        """
        Get backup schedule statistics
        """
        cache_key = 'backup_schedule_stats'
        stats = cache.get(cache_key)
        
        if stats is None:
            try:
                active_count = BackupSchedule.objects.filter(is_active=True).count()
                
                # Get next scheduled run
                next_schedule = BackupSchedule.objects.filter(
                    is_active=True,
                    next_run__isnull=False
                ).order_by('next_run').first()
                
                next_run = next_schedule.next_run.isoformat() if next_schedule else None
                
                stats = {
                    'active_count': active_count,
                    'next_run': next_run
                }
                
                cache.set(cache_key, stats, self.cache_timeout)
                
            except Exception as e:
                stats = {
                    'active_count': 0,
                    'next_run': None
                }
        
        return stats
    
    def _get_alert_stats(self):
        """
        Get backup alert statistics
        """
        cache_key = 'backup_alert_stats'
        stats = cache.get(cache_key)
        
        if stats is None:
            try:
                unresolved_count = BackupAlert.objects.filter(is_resolved=False).count()
                critical_count = BackupAlert.objects.filter(
                    is_resolved=False,
                    severity='critical'
                ).count()
                
                stats = {
                    'unresolved_count': unresolved_count,
                    'critical_count': critical_count
                }
                
                cache.set(cache_key, stats, self.cache_timeout)
                
            except Exception as e:
                stats = {
                    'unresolved_count': 0,
                    'critical_count': 0
                }
        
        return stats
    
    def _get_storage_stats(self):
        """
        Get storage statistics
        """
        cache_key = 'backup_storage_stats'
        stats = cache.get(cache_key)
        
        if stats is None:
            try:
                from .models import BackupStorageLocation
                
                total_locations = BackupStorageLocation.objects.count()
                active_locations = BackupStorageLocation.objects.filter(is_active=True).count()
                
                # Calculate usage (this would need to be implemented based on your storage models)
                usage_percentage = 0
                overall_status = 'unknown'
                
                if total_locations > 0:
                    if active_locations == total_locations:
                        overall_status = 'healthy'
                    else:
                        overall_status = 'warning'
                
                stats = {
                    'total_locations': total_locations,
                    'active_locations': active_locations,
                    'usage_percentage': usage_percentage,
                    'overall_status': overall_status
                }
                
                cache.set(cache_key, stats, self.cache_timeout)
                
            except Exception as e:
                stats = {
                    'total_locations': 0,
                    'active_locations': 0,
                    'usage_percentage': 0,
                    'overall_status': 'unknown'
                }
        
        return stats
    
    def _get_performance_stats(self):
        """
        Get backup performance statistics
        """
        cache_key = 'backup_performance_stats'
        stats = cache.get(cache_key)
        
        if stats is None:
            try:
                # Get recent completed backups
                recent_backups = Backup.objects.filter(
                    status='completed',
                    created_at__gte=timezone.now() - timezone.timedelta(days=7)
                )
                
                # Calculate average duration
                avg_duration = 0
                total_size = 0
                
                if recent_backups.exists():
                    durations = [b.duration for b in recent_backups if b.duration]
                    if durations:
                        avg_duration = sum(durations) / len(durations)
                    
                    sizes = [b.file_size for b in recent_backups if b.file_size]
                    if sizes:
                        total_size = sum(sizes)
                
                stats = {
                    'avg_duration': avg_duration,
                    'total_size_mb': total_size / (1024 * 1024),  # Convert to MB
                    'recent_count': recent_backups.count()
                }
                
                cache.set(cache_key, stats, self.cache_timeout)
                
            except Exception as e:
                stats = {
                    'avg_duration': 0,
                    'total_size_mb': 0,
                    'recent_count': 0
                }
        
        return stats
    
    def _should_log_slow_request(self, request, response):
        """
        Determine if this request should be logged as slow
        """
        # Only log admin requests
        if not self._is_admin_request(request):
            return False
        
        # Check if response took too long
        if self.start_time:
            duration = time.time() - self.start_time
            slow_threshold = getattr(settings, 'BACKUP_SLOW_REQUEST_THRESHOLD', 2.0)  # 2 seconds
            return duration > slow_threshold
        
        return False
    
    def _log_slow_request(self, request, response):
        """
        Log slow requests for monitoring
        """
        try:
            duration = time.time() - self.start_time
            
            import logging
            logger = logging.getLogger('backup.middleware.slow')
            
            logger.warning(
                f"Slow admin request: {request.method} {request.path} "
                f"took {duration:.2f}s, status: {response.status_code}"
            )
            
            # You could also log to a database or monitoring service here
            
        except Exception as e:
            # Don't let logging errors break the request
            pass


class BackupMaintenanceMiddleware:
    """
    Middleware to handle backup maintenance mode
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if maintenance mode is active
        if self._is_maintenance_mode():
            return self._handle_maintenance_request(request)
        
        return self.get_response(request)
    
    def _is_maintenance_mode(self):
        """
        Check if backup maintenance mode is active
        """
        from django.core.cache import cache
        
        return cache.get('backup_maintenance_mode', False)
    
    def _handle_maintenance_request(self, request):
        """
        Handle requests during maintenance mode
        """
        # Allow admin users to access during maintenance
        if request.user.is_authenticated and request.user.is_staff:
            return self.get_response(request)
        
        # Check if this is an API request
        if request.path.startswith('/api/'):
            return HttpResponse(
                json.dumps({
                    'error': 'Backup system is under maintenance',
                    'message': 'The backup system is currently undergoing maintenance. Please try again later.',
                    'retry_after': 300  # 5 minutes
                }),
                status=503,
                content_type='application/json'
            )
        
        # Regular web request
        return HttpResponse(
            """
            <html>
            <head>
                <title>Backup System Maintenance</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; margin-top: 100px; }
                    .maintenance-box { 
                        background: #f8f9fa; 
                        border: 1px solid #dee2e6; 
                        border-radius: 8px; 
                        padding: 40px; 
                        max-width: 500px; 
                        margin: 0 auto;
                    }
                    .icon { font-size: 48px; color: #ffc107; margin-bottom: 20px; }
                </style>
            </head>
            <body>
                <div class="maintenance-box">
                    <div class="icon">🔧</div>
                    <h2>Backup System Maintenance</h2>
                    <p>The backup system is currently undergoing maintenance.</p>
                    <p>Please try again in a few minutes.</p>
                    <p><small>If you are an administrator, please log in to access the system.</small></p>
                </div>
            </body>
            </html>
            """,
            status=503,
            content_type='text/html'
        )


class BackupSecurityMiddleware:
    """
    Middleware for backup security monitoring and logging
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Log backup-related security events
        self._log_security_events(request)
        
        # Add security headers
        response = self.get_response(request)
        self._add_security_headers(response)
        
        return response
    
    def _log_security_events(self, request):
        """
        Log security-related events for backup operations
        """
        # Check for suspicious patterns
        suspicious_patterns = [
            'admin/backup/delete',
            'admin/backup/download',
            'admin/backup/restore',
            'api/backup/delete',
            'api/backup/download',
            'api/backup/restore'
        ]
        
        if any(pattern in request.path for pattern in suspicious_patterns):
            import logging
            logger = logging.getLogger('backup.security')
            
            logger.info(
                f"Backup security event: {request.method} {request.path} "
                f"from {request.META.get('REMOTE_ADDR', 'unknown')} "
                f"user: {getattr(request.user, 'username', 'anonymous')}"
            )
    
    def _add_security_headers(self, response):
        """
        Add security headers to backup-related responses
        """
        # Add CSP header if this is a backup-related response
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Add backup-specific security headers
        response['X-Backup-Security-Policy'] = 'strict'
        response['X-Backup-Access-Control'] = 'admin-only'


class BackupRequestLoggingMiddleware:
    """
    Middleware for comprehensive backup request logging and monitoring
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.start_time = None
        
    def __call__(self, request):
        self.start_time = time.time()
        
        # Log request start
        if self._should_log_request(request):
            self._log_request_start(request)
        
        # Process request
        response = self.get_response(request)
        
        # Log request completion
        if self._should_log_request(request):
            self._log_request_completion(request, response)
        
        return response
    
    def _should_log_request(self, request):
        """
        Determine if this request should be logged
        """
        path = request.path
        
        # Log backup-related requests
        backup_patterns = [
            '/api/backup/',
            '/admin/backup/',
            '/backup/',
            '/api/restore/',
            '/admin/restore/',
            '/restore/'
        ]
        
        return any(pattern in path for pattern in backup_patterns)
    
    def _log_request_start(self, request):
        """
        Log the start of a backup-related request
        """
        import logging
        logger = logging.getLogger('backup.requests')
        
        logger.info(
            f"Backup request started: {request.method} {request.path} "
            f"from {request.META.get('REMOTE_ADDR', 'unknown')} "
            f"user: {getattr(request.user, 'username', 'anonymous')} "
            f"headers: {dict(request.headers)}"
        )
    
    def _log_request_completion(self, request, response):
        """
        Log the completion of a backup-related request
        """
        import logging
        logger = logging.getLogger('backup.requests')
        
        duration = time.time() - self.start_time if self.start_time else 0
        
        logger.info(
            f"Backup request completed: {request.method} {request.path} "
            f"status: {response.status_code} "
            f"duration: {duration:.3f}s "
            f"size: {len(response.content) if hasattr(response, 'content') else 0}"
        )


class BackupRateLimitMiddleware:
    """
    Middleware for rate limiting backup operations
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Check rate limits for backup operations
        if self._should_rate_limit(request):
            if not self._check_rate_limit(request):
                return self._rate_limit_response(request)
        
        return self.get_response(request)
    
    def _should_rate_limit(self, request):
        """
        Determine if this request should be rate limited
        """
        path = request.path
        
        # Rate limit backup creation and restoration
        rate_limit_patterns = [
            '/api/backup/create',
            '/api/backup/restore',
            '/api/backup/delete',
            '/api/backup/download'
        ]
        
        return any(pattern in path for pattern in rate_limit_patterns)
    
    def _check_rate_limit(self, request):
        """
        Check if the request exceeds rate limits
        """
        from django.core.cache import cache
        from django.conf import settings
        
        # Get client identifier
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        user_id = getattr(request.user, 'id', None)
        
        # Use user ID if authenticated, otherwise IP
        identifier = f"backup_rate_limit_{user_id or client_ip}"
        
        # Get current count
        current_count = cache.get(identifier, 0)
        
        # Rate limit settings
        max_requests = getattr(settings, 'BACKUP_RATE_LIMIT_REQUESTS', 10)
        window_seconds = getattr(settings, 'BACKUP_RATE_LIMIT_WINDOW', 300)  # 5 minutes
        
        if current_count >= max_requests:
            return False
        
        # Increment counter
        cache.set(identifier, current_count + 1, window_seconds)
        return True
    
    def _rate_limit_response(self, request):
        """
        Return rate limit response
        """
        return HttpResponse(
            json.dumps({
                'error': 'Rate limit exceeded',
                'message': 'Too many backup requests. Please try again later.',
                'retry_after': 300
            }),
            status=429,
            content_type='application/json'
        )


class BackupAuditMiddleware:
    """
    Middleware for comprehensive backup audit logging
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Capture request details for audit
        audit_data = self._capture_audit_data(request)
        
        # Process request
        response = self.get_response(request)
        
        # Log audit trail
        if self._should_audit(request):
            self._log_audit_trail(audit_data, request, response)
        
        return response
    
    def _capture_audit_data(self, request):
        """
        Capture relevant audit data from request
        """
        return {
            'timestamp': timezone.now().isoformat(),
            'method': request.method,
            'path': request.path,
            'user_id': getattr(request.user, 'id', None),
            'username': getattr(request.user, 'username', None),
            'ip_address': request.META.get('REMOTE_ADDR', 'unknown'),
            'user_agent': request.META.get('HTTP_USER_AGENT', 'unknown'),
            'referer': request.META.get('HTTP_REFERER', ''),
            'request_size': len(request.body) if hasattr(request, 'body') else 0
        }
    
    def _should_audit(self, request):
        """
        Determine if this request should be audited
        """
        path = request.path
        
        # Audit sensitive backup operations
        audit_patterns = [
            '/admin/backup/delete',
            '/admin/backup/restore',
            '/admin/backup/download',
            '/api/backup/delete',
            '/api/backup/restore',
            '/api/backup/download',
            '/admin/backup/backupstoragelocation',
            '/admin/backup/backupschedule'
        ]
        
        return any(pattern in path for pattern in audit_patterns)
    
    def _log_audit_trail(self, audit_data, request, response):
        """
        Log audit trail for sensitive operations
        """
        import logging
        logger = logging.getLogger('backup.audit')
        
        audit_data.update({
            'status_code': response.status_code,
            'response_size': len(response.content) if hasattr(response, 'content') else 0,
            'success': 200 <= response.status_code < 300
        })
        
        logger.info(
            f"Backup audit: {audit_data['method']} {audit_data['path']} "
            f"user: {audit_data['username']} "
            f"ip: {audit_data['ip_address']} "
            f"status: {audit_data['status_code']} "
            f"success: {audit_data['success']}"
        )
        
        # Store in database if configured
        if getattr(settings, 'BACKUP_AUDIT_TO_DB', False):
            self._store_audit_record(audit_data)
    
    def _store_audit_record(self, audit_data):
        """
        Store audit record in database
        """
        try:
            from .models import BackupLog
            
            BackupLog.objects.create(
                level='audit',
                category='security',
                action='access',
                source='middleware',
                message=f"Audit trail for {audit_data['method']} {audit_data['path']}",
                metadata=audit_data,
                user_id=audit_data['user_id']
            )
        except Exception as e:
            # Log error but don't break the request
            import logging
            logger = logging.getLogger('backup.audit')
            logger.error(f"Failed to store audit record: {str(e)}")


class BackupPerformanceMiddleware:
    """
    Middleware for monitoring backup operation performance
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.start_time = None
        
    def __call__(self, request):
        self.start_time = time.time()
        
        # Process request
        response = self.get_response(request)
        
        # Monitor performance
        if self._should_monitor_performance(request):
            self._monitor_performance(request, response)
        
        return response
    
    def _should_monitor_performance(self, request):
        """
        Determine if this request should be performance monitored
        """
        path = request.path
        
        # Monitor backup API endpoints
        monitor_patterns = [
            '/api/backup/',
            '/api/restore/',
            '/api/backup-verification/'
        ]
        
        return any(pattern in path for pattern in monitor_patterns)
    
    def _monitor_performance(self, request, response):
        """
        Monitor and log performance metrics
        """
        duration = time.time() - self.start_time if self.start_time else 0
        
        import logging
        logger = logging.getLogger('backup.performance')
        
        # Log slow requests
        slow_threshold = getattr(settings, 'BACKUP_PERFORMANCE_SLOW_THRESHOLD', 5.0)
        if duration > slow_threshold:
            logger.warning(
                f"Slow backup request: {request.method} {request.path} "
                f"took {duration:.3f}s, status: {response.status_code}"
            )
        
        # Store performance metrics
        self._store_performance_metrics(request, response, duration)
    
    def _store_performance_metrics(self, request, response, duration):
        """
        Store performance metrics for analysis
        """
        try:
            from django.core.cache import cache
            
            # Store recent performance data
            cache_key = 'backup_performance_metrics'
            metrics = cache.get(cache_key, [])
            
            metric = {
                'timestamp': timezone.now().isoformat(),
                'method': request.method,
                'path': request.path,
                'duration': duration,
                'status_code': response.status_code,
                'response_size': len(response.content) if hasattr(response, 'content') else 0
            }
            
            metrics.append(metric)
            
            # Keep only last 1000 metrics
            if len(metrics) > 1000:
                metrics = metrics[-1000:]
            
            cache.set(cache_key, metrics, 3600)  # 1 hour
            
        except Exception as e:
            import logging
            logger = logging.getLogger('backup.performance')
            logger.error(f"Failed to store performance metrics: {str(e)}")


class BackupContextMiddleware:
    """
    Middleware to add backup context to requests
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Add backup context to request
        self._add_backup_context(request)
        
        response = self.get_response(request)
        
        return response
    
    def _add_backup_context(self, request):
        """
        Add backup-related context to request object
        """
        from django.core.cache import cache
        
        # Get backup system status
        cache_key = 'backup_system_status'
        status = cache.get(cache_key)
        
        if status is None:
            try:
                from .models import Backup, BackupAlert
                
                # Calculate system status
                total_backups = Backup.objects.count()
                failed_backups = Backup.objects.filter(status='failed').count()
                critical_alerts = BackupAlert.objects.filter(
                    is_resolved=False,
                    severity='critical'
                ).count()
                
                status = {
                    'total_backups': total_backups,
                    'failed_backups': failed_backups,
                    'critical_alerts': critical_alerts,
                    'system_healthy': failed_backups == 0 and critical_alerts == 0
                }
                
                cache.set(cache_key, status, 300)  # 5 minutes
                
            except Exception:
                status = {
                    'total_backups': 0,
                    'failed_backups': 0,
                    'critical_alerts': 0,
                    'system_healthy': False
                }
        
        # Add to request for use in views/templates
        request.backup_context = status


class BackupCORSMiddleware:
    """
    Middleware for handling CORS for backup API endpoints
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Handle preflight requests
        if request.method == 'OPTIONS':
            response = HttpResponse()
            self._add_cors_headers(response)
            return response
        
        response = self.get_response(request)
        
        # Add CORS headers to backup API responses
        if self._is_backup_api_request(request):
            self._add_cors_headers(response)
        
        return response
    
    def _is_backup_api_request(self, request):
        """
        Check if this is a backup API request
        """
        return request.path.startswith('/api/backup/') or request.path.startswith('/api/restore/')
    
    def _add_cors_headers(self, response):
        """
        Add CORS headers to response
        """
        from django.conf import settings
        
        # Get allowed origins from settings
        allowed_origins = getattr(settings, 'BACKUP_CORS_ALLOWED_ORIGINS', [])
        
        if allowed_origins:
            response['Access-Control-Allow-Origin'] = ', '.join(allowed_origins)
        
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
        response['Access-Control-Max-Age'] = '86400'  # 24 hours


# Middleware factory function
def get_backup_middleware():
    """
    Get the list of backup middleware in the correct order
    """
    return [
        'api.backup.middleware.BackupSecurityMiddleware',
        'api.backup.middleware.BackupRateLimitMiddleware',
        'api.backup.middleware.BackupAuditMiddleware',
        'api.backup.middleware.BackupContextMiddleware',
        'api.backup.middleware.BackupPerformanceMiddleware',
        'api.backup.middleware.BackupRequestLoggingMiddleware',
        'api.backup.middleware.BackupCORSMiddleware',
        'api.backup.middleware.BackupMaintenanceMiddleware',
        'api.backup.middleware.BackupStatusMiddleware',
    ]
