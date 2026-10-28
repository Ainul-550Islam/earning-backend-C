# =============================================================================
# auto_mod/throttling.py
# =============================================================================

"""
Throttling classes for auto moderation system.
"""

import time
from django.core.cache import cache
from django.conf import settings
from rest_framework import throttling
from django.utils import timezone
from django.contrib.auth import get_user_model

from .choices import SubmissionType, ScanType
from .exceptions import ScanRateLimitError

User = get_user_model()


class ScanRateThrottle(throttling.SimpleRateThrottle):
    """
    Rate throttle for scan requests to prevent abuse.
    
    Limits scan requests based on:
    - User-based limits
    - IP-based limits  
    - Scan type-specific limits
    - Time-based windows
    """
    
    scope = 'scan'
    
    def __init__(self):
        super().__init__()
        self.cache = cache
        self.history = []
    
    def get_cache_key(self, request, view):
        """
        Generate cache key for throttling.
        """
        # Use user ID if authenticated, otherwise IP
        if request.user and request.user.is_authenticated:
            ident = f"user_{request.user.pk}"
        else:
            ident = f"ip_{self.get_ident(request)}"
        
        # Add scan type if available
        scan_type = getattr(view, 'scan_type', None) or request.query_params.get('scan_type')
        if scan_type:
            ident = f"{ident}_{scan_type}"
        
        return f"{self.scope}_{ident}"
    
    def get_rate(self):
        """
        Get rate limit based on user and scan type.
        """
        request = getattr(self, 'request', None)
        if not request:
            return super().get_rate()
        
        # Check if user is staff (higher limits)
        if request.user and request.user.is_staff:
            return '500/hour'  # Staff users get higher limits
        
        # Check for premium users (if applicable)
        if self._is_premium_user(request.user):
            return '200/hour'  # Premium users get moderate limits
        
        # Get scan type specific rates
        scan_type = getattr(request, 'query_params', {}).get('scan_type')
        if scan_type:
            return self._get_scan_type_rate(scan_type)
        
        # Default rate for regular users
        return '100/hour'
    
    def _is_premium_user(self, user):
        """
        Check if user has premium access.
        """
        if not user or not user.is_authenticated:
            return False
        
        # Check user profile or subscription status
        # This is a placeholder - implement based on your user model
        return getattr(user, 'is_premium', False)
    
    def _get_scan_type_rate(self, scan_type):
        """
        Get rate limit for specific scan type.
        """
        scan_rates = getattr(settings, 'SCAN_TYPE_RATES', {
            ScanType.OCR: '50/hour',
            ScanType.IMAGE_ANALYSIS: '30/hour',
            ScanType.TEXT_ANALYSIS: '60/hour',
        })
        
        return scan_rates.get(scan_type, '100/hour')
    
    def throttle_success(self, request, response):
        """
        Log successful scan request.
        """
        # Update usage statistics
        self._update_usage_stats(request, True)
        
        # Add rate limit headers
        self._add_rate_limit_headers(request, response)
        
        return super().throttle_success(request, response)
    
    def throttle_failure(self, request, response):
        """
        Handle throttling failure.
        """
        # Update usage statistics
        self._update_usage_stats(request, False)
        
        # Add rate limit headers
        self._add_rate_limit_headers(request, response)
        
        # Log throttling event
        self._log_throttling_event(request)
        
        return super().throttle_failure(request, response)
    
    def _update_usage_stats(self, request, success):
        """
        Update usage statistics for monitoring.
        """
        try:
            # Get cache key for stats
            stats_key = f"scan_stats_{timezone.now().strftime('%Y%m%d')}"
            
            # Get current stats
            stats = self.cache.get(stats_key, {
                'total_requests': 0,
                'successful_requests': 0,
                'throttled_requests': 0,
                'by_user_type': {},
                'by_scan_type': {}
            })
            
            # Update counters
            stats['total_requests'] += 1
            
            if success:
                stats['successful_requests'] += 1
            else:
                stats['throttled_requests'] += 1
            
            # Update user type stats
            user_type = 'staff' if (request.user and request.user.is_staff) else 'regular'
            stats['by_user_type'][user_type] = stats['by_user_type'].get(user_type, 0) + 1
            
            # Update scan type stats
            scan_type = request.query_params.get('scan_type', 'unknown')
            stats['by_scan_type'][scan_type] = stats['by_scan_type'].get(scan_type, 0) + 1
            
            # Save stats back to cache
            self.cache.set(stats_key, stats, timeout=86400)  # 24 hours
            
        except Exception as exc:
            # Don't let stats errors affect throttling
            pass
    
    def _add_rate_limit_headers(self, request, response):
        """
        Add rate limit headers to response.
        """
        try:
            # Get current usage and limits
            cache_key = self.get_cache_key(request, None)
            history = self.cache.get(cache_key, [])
            
            # Calculate remaining requests
            num_requests, duration = self.parse_rate(self.get_rate())
            remaining = max(0, num_requests - len(history))
            
            # Add headers
            response['X-RateLimit-Limit'] = str(num_requests)
            response['X-RateLimit-Remaining'] = str(remaining)
            response['X-RateLimit-Reset'] = str(int(time.time() + duration))
            
            # Add scan-specific headers
            scan_type = request.query_params.get('scan_type')
            if scan_type:
                response['X-Scan-Type'] = scan_type
            
        except Exception:
            # Don't let header errors affect throttling
            pass
    
    def _log_throttling_event(self, request):
        """
        Log throttling events for security monitoring.
        """
        try:
            import json
            
            log_data = {
                'timestamp': timezone.now().isoformat(),
                'event': 'scan_throttled',
                'user_id': request.user.pk if request.user.is_authenticated else None,
                'ip_address': self.get_ident(request),
                'scan_type': request.query_params.get('scan_type'),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'path': request.path,
                'method': request.method
            }
            
            # Log to security log
            import logging
            security_logger = logging.getLogger('security')
            security_logger.warning(f"Scan rate limit exceeded: {json.dumps(log_data)}")
            
        except Exception:
            # Don't let logging errors affect throttling
            pass


class SubmissionRateThrottle(throttling.SimpleRateThrottle):
    """
    Rate throttle for content submissions.
    """
    
    scope = 'submission'
    
    def get_cache_key(self, request, view):
        """
        Generate cache key for submission throttling.
        """
        if request.user and request.user.is_authenticated:
            ident = f"user_{request.user.pk}"
        else:
            ident = f"ip_{self.get_ident(request)}"
        
        # Add submission type if available
        submission_type = request.data.get('submission_type') or request.query_params.get('submission_type')
        if submission_type:
            ident = f"{ident}_{submission_type}"
        
        return f"{self.scope}_{ident}"
    
    def get_rate(self):
        """
        Get rate limit for submissions.
        """
        request = getattr(self, 'request', None)
        if not request:
            return super().get_rate()
        
        # Check if user is staff
        if request.user and request.user.is_staff:
            return '1000/day'  # Staff users get very high limits
        
        # Check for trusted users
        if self._is_trusted_user(request.user):
            return '500/day'  # Trusted users get high limits
        
        # Get submission type specific rates
        submission_type = request.data.get('submission_type') or request.query_params.get('submission_type')
        if submission_type:
            return self._get_submission_type_rate(submission_type)
        
        # Default rate
        return '100/day'
    
    def _is_trusted_user(self, user):
        """
        Check if user is trusted.
        """
        if not user or not user.is_authenticated:
            return False
        
        # Check account age
        account_age = timezone.now() - user.date_joined
        if account_age.days < 7:
            return False  # New accounts are not trusted
        
        # Check submission history
        from .models import SuspiciousSubmission
        submission_count = SuspiciousSubmission.objects.filter(user=user).count()
        if submission_count < 10:
            return False  # Users with few submissions are not fully trusted
        
        # Check approval rate
        approved_count = SuspiciousSubmission.objects.filter(
            user=user,
            status__in=['auto_approved', 'human_approved']
        ).count()
        
        if submission_count > 0 and (approved_count / submission_count) < 0.8:
            return False  # Low approval rate
        
        return True
    
    def _get_submission_type_rate(self, submission_type):
        """
        Get rate limit for specific submission type.
        """
        submission_rates = getattr(settings, 'SUBMISSION_TYPE_RATES', {
            SubmissionType.IMAGE: '50/day',
            SubmissionType.TEXT: '100/day',
            SubmissionType.DOCUMENT: '25/day',
            SubmissionType.VIDEO: '10/day',
            SubmissionType.AUDIO: '20/day',
        })
        
        return submission_rates.get(submission_type, '100/day')


class AppealRateThrottle(throttling.SimpleRateThrottle):
    """
    Rate throttle for appeal submissions.
    """
    
    scope = 'appeal'
    
    def get_cache_key(self, request, view):
        """
        Generate cache key for appeal throttling.
        """
        if request.user and request.user.is_authenticated:
            ident = f"user_{request.user.pk}"
        else:
            ident = f"ip_{self.get_ident(request)}"
        
        return f"{self.scope}_{ident}"
    
    def get_rate(self):
        """
        Get rate limit for appeals.
        """
        request = getattr(self, 'request', None)
        if not request:
            return super().get_rate()
        
        # Check if user is staff
        if request.user and request.user.is_staff:
            return '1000/day'  # Staff users get very high limits
        
        # Appeals should be more restrictive than submissions
        return '10/day'


class QueueActionThrottle(throttling.SimpleRateThrottle):
    """
    Rate throttle for queue actions (assign, escalate, etc.).
    """
    
    scope = 'queue_action'
    
    def get_cache_key(self, request, view):
        """
        Generate cache key for queue action throttling.
        """
        if request.user and request.user.is_authenticated:
            ident = f"user_{request.user.pk}"
        else:
            ident = f"ip_{self.get_ident(request)}"
        
        # Add action type if available
        action_type = getattr(view, 'action_type', None) or request.query_params.get('action')
        if action_type:
            ident = f"{ident}_{action_type}"
        
        return f"{self.scope}_{ident}"
    
    def get_rate(self):
        """
        Get rate limit for queue actions.
        """
        request = getattr(self, 'request', None)
        if not request:
            return super().get_rate()
        
        # Check if user is staff
        if request.user and request.user.is_staff:
            return '1000/hour'  # Staff users get very high limits
        
        # Queue actions should be moderately restrictive
        return '200/hour'


class BurstRateThrottle(throttling.SimpleRateThrottle):
    """
    Burst rate throttle for handling sudden spikes in requests.
    """
    
    scope = 'burst'
    
    def get_rate(self):
        """
        Get burst rate limit.
        """
        return '10/minute'  # Allow short bursts but prevent sustained abuse


class CompositeRateThrottle(throttling.BaseThrottle):
    """
    Composite throttle that applies multiple throttling rules.
    """
    
    def __init__(self):
        self.throttles = [
            ScanRateThrottle(),
            BurstRateThrottle()
        ]
        super().__init__()
    
    def allow_request(self, request, view):
        """
        Check all throttles.
        """
        for throttle in self.throttles:
            if not throttle.allow_request(request, view):
                return False
        return True
    
    def wait(self):
        """
        Get wait time from the most restrictive throttle.
        """
        max_wait = 0
        for throttle in self.throttles:
            try:
                wait = throttle.wait()
                if wait > max_wait:
                    max_wait = wait
            except:
                continue
        return max_wait


class AdaptiveRateThrottle(throttling.SimpleRateThrottle):
    """
    Adaptive throttle that adjusts limits based on system load.
    """
    
    scope = 'adaptive'
    
    def get_rate(self):
        """
        Get rate based on current system load.
        """
        # Get current system load
        load_factor = self._get_system_load_factor()
        
        # Base rates for different load levels
        if load_factor < 0.5:
            return '200/hour'  # Low load - higher limits
        elif load_factor < 0.8:
            return '100/hour'  # Medium load - normal limits
        elif load_factor < 0.95:
            return '50/hour'   # High load - reduced limits
        else:
            return '25/hour'   # Very high load - minimal limits
    
    def _get_system_load_factor(self):
        """
        Get current system load factor (0.0 to 1.0).
        """
        try:
            # Check cache for recent load metrics
            load_key = "system_load_factor"
            cached_load = self.cache.get(load_key)
            
            if cached_load is not None:
                return cached_load
            
            # Calculate load based on various factors
            load_factors = []
            
            # Recent scan requests
            recent_scans = self._get_recent_scan_count()
            scan_load = min(1.0, recent_scans / 1000.0)  # Normalize to 0-1
            load_factors.append(scan_load)
            
            # Database connections (if available)
            db_load = self._get_database_load()
            if db_load is not None:
                load_factors.append(db_load)
            
            # Memory usage (if available)
            memory_load = self._get_memory_load()
            if memory_load is not None:
                load_factors.append(memory_load)
            
            # Calculate average load factor
            if load_factors:
                avg_load = sum(load_factors) / len(load_factors)
            else:
                avg_load = 0.5  # Default to medium load
            
            # Cache for 5 minutes
            self.cache.set(load_key, avg_load, timeout=300)
            
            return avg_load
            
        except Exception:
            return 0.5  # Default to medium load on error
    
    def _get_recent_scan_count(self):
        """
        Get count of recent scan requests.
        """
        try:
            # Count scan requests in the last hour
            from .models import ProofScanner
            one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
            
            count = ProofScanner.objects.filter(
                started_at__gte=one_hour_ago
            ).count()
            
            return count
            
        except Exception:
            return 0
    
    def _get_database_load(self):
        """
        Get database load indicator.
        """
        try:
            # This would typically use database-specific metrics
            # For now, return a simple indicator based on active connections
            from django.db import connection
            
            # Simple heuristic based on recent query count
            # In practice, you'd use proper monitoring
            return 0.3  # Placeholder
            
        except Exception:
            return None
    
    def _get_memory_load(self):
        """
        Get memory usage indicator.
        """
        try:
            import psutil
            
            # Get system memory usage
            memory = psutil.virtual_memory()
            return memory.percent / 100.0  # Convert to 0-1 scale
            
        except Exception:
            return None


class UserRoleBasedThrottle(throttling.BaseThrottle):
    """
    Throttle based on user role and permissions.
    """
    
    def __init__(self):
        self.cache = cache
        super().__init__()
    
    def allow_request(self, request, view):
        """
        Check if request is allowed based on user role.
        """
        if not request.user or not request.user.is_authenticated:
            return self._check_anonymous_limit(request)
        
        # Check user-specific limits
        if request.user.is_staff:
            return self._check_staff_limit(request)
        elif request.user.is_superuser:
            return self._check_superuser_limit(request)
        else:
            return self._check_regular_limit(request)
    
    def _check_anonymous_limit(self, request):
        """
        Check limit for anonymous users.
        """
        cache_key = f"anonymous_{self.get_ident(request)}"
        return self._check_rate_limit(cache_key, '10/hour')
    
    def _check_staff_limit(self, request):
        """
        Check limit for staff users.
        """
        cache_key = f"staff_{request.user.pk}"
        return self._check_rate_limit(cache_key, '1000/hour')
    
    def _check_superuser_limit(self, request):
        """
        Check limit for superusers.
        """
        cache_key = f"superuser_{request.user.pk}"
        return True  # Superusers have no limits
    
    def _check_regular_limit(self, request):
        """
        Check limit for regular users.
        """
        cache_key = f"user_{request.user.pk}"
        
        # Check if user has special permissions
        if hasattr(request.user, 'has_permission') and request.user.has_permission('high_rate_limit'):
            return self._check_rate_limit(cache_key, '500/hour')
        
        return self._check_rate_limit(cache_key, '100/hour')
    
    def _check_rate_limit(self, cache_key, rate):
        """
        Check rate limit for given cache key and rate.
        """
        try:
            history = self.cache.get(cache_key, [])
            now = time.time()
            
            # Parse rate
            num_requests, duration = self.parse_rate(rate)
            
            # Remove old entries
            while history and history[-1] <= now - duration:
                history.pop()
            
            # Check if under limit
            if len(history) >= num_requests:
                return False
            
            # Add current request
            history.insert(0, now)
            self.cache.set(cache_key, history, timeout=duration)
            
            return True
            
        except Exception:
            return True  # Allow request on error


# Throttle class mapping for easy configuration
THROTTLE_CLASSES = {
    'scan': ScanRateThrottle,
    'submission': SubmissionRateThrottle,
    'appeal': AppealRateThrottle,
    'queue': QueueActionThrottle,
    'burst': BurstRateThrottle,
    'composite': CompositeRateThrottle,
    'adaptive': AdaptiveRateThrottle,
    'role_based': UserRoleBasedThrottle,
}


def get_throttle_class(throttle_type='scan'):
    """
    Get throttle class by type.
    
    Args:
        throttle_type: Type of throttle class
        
    Returns:
        Throttle class
    """
    return THROTTLE_CLASSES.get(throttle_type, ScanRateThrottle)
