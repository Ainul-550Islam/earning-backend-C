"""
Django Middleware for Offer Routing System

This module provides middleware for request/response intercepting,
including tenant/user context, performance tracking, and security logging.
"""

import time
import logging
import json
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings
from ipware import get_client_ip

from .models import RoutingAuditLog, SecurityEvent
from .utils import get_client_user_agent, validate_ip_address

User = get_user_model()
logger = logging.getLogger(__name__)


class RoutingContextMiddleware(MiddlewareMixin):
    """
    Middleware to add routing context to requests.
    
    Adds tenant and user information to request object
    for use throughout the routing system.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.start_time = None
    
    def process_request(self, request):
        """Add routing context to request."""
        self.start_time = time.time()
        
        try:
            # Add tenant context
            if hasattr(request.user, 'tenant'):
                request.routing_tenant = request.user.tenant
                request.routing_tenant_id = request.user.tenant.id
            else:
                request.routing_tenant = None
                request.routing_tenant_id = None
            
            # Add user context
            if request.user.is_authenticated:
                request.routing_user = request.user
                request.routing_user_id = request.user.id
            else:
                request.routing_user = None
                request.routing_user_id = None
            
            # Add client information
            request.client_ip = get_client_ip(request)
            request.client_user_agent = get_client_user_agent(request)
            
            # Add device context
            request.device_context = self._get_device_context(request)
            
            # Add geo context
            request.geo_context = self._get_geo_context(request)
            
            # Add session context
            request.routing_session_id = self._get_or_create_session_id(request)
            
            logger.debug(f"Routing context added for request: {request.routing_session_id}")
            
        except Exception as e:
            logger.error(f"Error in RoutingContextMiddleware: {e}")
            # Set default values on error
            request.routing_tenant = None
            request.routing_user = None
            request.routing_session_id = None
        
        return None
    
    def process_response(self, request, response):
        """Process response with routing context."""
        try:
            if hasattr(request, 'start_time'):
                duration = time.time() - request.start_time
                response['X-Routing-Time'] = f"{duration:.3f}s"
                
                # Log slow requests
                if duration > 1.0:  # 1 second threshold
                    logger.warning(f"Slow routing request: {duration:.3f}s for {request.routing_session_id}")
                    
                    # Log audit event
                    self._log_performance_event(request, duration, 'slow_request')
            
            # Add routing headers
            if hasattr(request, 'routing_session_id'):
                response['X-Routing-Session'] = request.routing_session_id
            
            if hasattr(request, 'routing_tenant_id'):
                response['X-Routing-Tenant'] = str(request.routing_tenant_id)
            
            # Add security headers
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            
        except Exception as e:
            logger.error(f"Error in response processing: {e}")
        
        return response
    
    def _get_device_context(self, request):
        """Get device context from request."""
        try:
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Simple device detection
            device_context = {
                'type': 'unknown',
                'os': 'unknown',
                'browser': 'unknown',
                'is_mobile': False,
                'is_tablet': False
            }
            
            # Mobile detection
            mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'tablet']
            if any(keyword.lower() in user_agent.lower() for keyword in mobile_keywords):
                device_context['is_mobile'] = True
                device_context['type'] = 'mobile'
            
            # Tablet detection
            tablet_keywords = ['ipad', 'tablet', 'kindle']
            if any(keyword.lower() in user_agent.lower() for keyword in tablet_keywords):
                device_context['is_tablet'] = True
                device_context['type'] = 'tablet'
            
            # Desktop detection
            if not device_context['is_mobile'] and not device_context['is_tablet']:
                device_context['type'] = 'desktop'
            
            # OS detection
            os_keywords = {
                'windows': ['windows', 'win32'],
                'mac': ['mac', 'macintosh', 'darwin'],
                'linux': ['linux'],
                'android': ['android'],
                'ios': ['iphone', 'ipad', 'ios']
            }
            
            for os_name, keywords in os_keywords.items():
                if any(keyword.lower() in user_agent.lower() for keyword in keywords):
                    device_context['os'] = os_name
                    break
            
            # Browser detection
            browser_keywords = {
                'chrome': ['chrome'],
                'firefox': ['firefox'],
                'safari': ['safari'],
                'edge': ['edge', 'edg'],
                'opera': ['opera']
            }
            
            for browser_name, keywords in browser_keywords.items():
                if any(keyword.lower() in user_agent.lower() for keyword in keywords):
                    device_context['browser'] = browser_name
                    break
            
            return device_context
            
        except Exception as e:
            logger.error(f"Error getting device context: {e}")
            return {'type': 'unknown'}
    
    def _get_geo_context(self, request):
        """Get geo context from request."""
        try:
            ip_address = get_client_ip(request)
            
            if not ip_address:
                return {'country': 'unknown', 'city': 'unknown'}
            
            # Get geo location from IP
            from .utils import get_geo_location_from_ip
            geo_data = get_geo_location_from_ip(ip_address)
            
            if geo_data:
                return {
                    'country': geo_data.get('country', 'unknown'),
                    'region': geo_data.get('region', 'unknown'),
                    'city': geo_data.get('city', 'unknown'),
                    'latitude': geo_data.get('latitude'),
                    'longitude': geo_data.get('longitude'),
                    'timezone': geo_data.get('timezone', 'unknown')
                }
            
            return {'country': 'unknown', 'city': 'unknown'}
            
        except Exception as e:
            logger.error(f"Error getting geo context: {e}")
            return {'country': 'unknown', 'city': 'unknown'}
    
    def _get_or_create_session_id(self, request):
        """Get or create routing session ID."""
        try:
            session_key = 'routing_session_id'
            
            if session_key in request.session:
                return request.session[session_key]
            
            # Generate new session ID
            import uuid
            session_id = str(uuid.uuid4())
            request.session[session_key] = session_id
            request.session.modified = True
            
            return session_id
            
        except Exception as e:
            logger.error(f"Error creating session ID: {e}")
            return str(uuid.uuid4())
    
    def _log_performance_event(self, request, duration, event_type):
        """Log performance event."""
        try:
            from .tasks.monitoring import log_performance_event
            
            log_performance_event.delay(
                session_id=request.routing_session_id,
                event_type=event_type,
                duration=duration,
                request_path=request.path,
                user_id=getattr(request, 'routing_user_id', None),
                tenant_id=getattr(request, 'routing_tenant_id', None),
                device_context=getattr(request, 'device_context', {}),
                geo_context=getattr(request, 'geo_context', {}),
                timestamp=timezone.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Error logging performance event: {e}")


class RoutingPerformanceMiddleware(MiddlewareMixin):
    """
    Middleware for tracking routing performance metrics.
    
    Tracks response times, memory usage, and system health
    for monitoring and optimization.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.start_time = None
        self.memory_start = None
    
    def process_request(self, request):
        """Start performance tracking."""
        self.start_time = time.time()
        
        try:
            # Get initial memory usage
            import psutil
            process = psutil.Process()
            self.memory_start = process.memory_info().rss / 1024 / 1024  # MB
            
            # Add performance tracking context
            request.performance_tracking = {
                'start_time': self.start_time,
                'memory_start': self.memory_start,
                'request_id': str(uuid.uuid4())
            }
            
        except Exception as e:
            logger.error(f"Error starting performance tracking: {e}")
            request.performance_tracking = {
                'start_time': self.start_time,
                'memory_start': 0,
                'request_id': str(uuid.uuid4())
            }
        
        return None
    
    def process_response(self, request, response):
        """End performance tracking and log metrics."""
        try:
            if hasattr(request, 'performance_tracking'):
                tracking = request.performance_tracking
                
                # Calculate duration
                duration = time.time() - tracking['start_time']
                
                # Get final memory usage
                import psutil
                process = psutil.Process()
                memory_end = process.memory_info().rss / 1024 / 1024  # MB
                
                memory_delta = memory_end - tracking['memory_start']
                
                # Log performance metrics
                performance_data = {
                    'request_id': tracking['request_id'],
                    'duration_ms': duration * 1000,
                    'memory_start_mb': tracking['memory_start'],
                    'memory_end_mb': memory_end,
                    'memory_delta_mb': memory_delta,
                    'response_status': response.status_code,
                    'request_path': request.path,
                    'request_method': request.method,
                    'user_id': getattr(request, 'routing_user_id', None),
                    'tenant_id': getattr(request, 'routing_tenant_id', None),
                    'timestamp': timezone.now().isoformat()
                }
                
                # Store in cache for real-time monitoring
                cache_key = f"performance_metrics:{tracking['request_id']}"
                cache.set(cache_key, performance_data, timeout=300)  # 5 minutes
                
                # Log to database asynchronously
                from .tasks.monitoring import log_performance_metrics
                log_performance_metrics.delay(performance_data)
                
                # Add performance headers
                response['X-Response-Time'] = f"{duration:.3f}s"
                response['X-Memory-Usage'] = f"{memory_delta:.2f}MB"
                
                # Alert on high memory usage
                if memory_delta > 50:  # 50MB threshold
                    from .tasks.monitoring import send_memory_alert
                    send_memory_alert.delay(
                        memory_delta=memory_delta,
                        request_id=tracking['request_id']
                    )
                
                # Alert on slow response
                if duration > 2.0:  # 2 second threshold
                    from .tasks.monitoring import send_slow_response_alert
                    send_slow_response_alert.delay(
                        duration=duration,
                        request_id=tracking['request_id']
                    )
            
        except Exception as e:
            logger.error(f"Error in performance tracking: {e}")
        
        return response


class RoutingAuditMiddleware(MiddlewareMixin):
    """
    Middleware for security and audit logging.
    
    Logs security events, suspicious activities, and access patterns
    for security monitoring and compliance.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.start_time = None
    
    def process_request(self, request):
        """Start audit logging."""
        self.start_time = time.time()
        
        try:
            # Get client information
            ip_address = get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Validate IP address
            ip_validation = validate_ip_address(ip_address)
            
            # Check for suspicious patterns
            suspicious_indicators = self._check_suspicious_patterns(request)
            
            # Log security event if suspicious
            if suspicious_indicators or not ip_validation['is_valid']:
                from .tasks.monitoring import log_security_event
                
                log_security_event.delay(
                    event_type='suspicious_request',
                    ip_address=ip_address,
                    user_agent=user_agent,
                    user_id=getattr(request, 'routing_user_id', None),
                    tenant_id=getattr(request, 'routing_tenant_id', None),
                    request_path=request.path,
                    request_method=request.method,
                    indicators=suspicious_indicators,
                    ip_validation=ip_validation,
                    timestamp=timezone.now().isoformat()
                )
                
                # Add security headers
                request.security_flags = {
                    'suspicious': True,
                    'indicators': suspicious_indicators,
                    'ip_invalid': not ip_validation['is_valid']
                }
            
            # Rate limiting check
            if self._is_rate_limited(request, ip_address):
                from .tasks.monitoring import log_security_event
                
                log_security_event.delay(
                    event_type='rate_limit_exceeded',
                    ip_address=ip_address,
                    user_agent=user_agent,
                    user_id=getattr(request, 'routing_user_id', None),
                    tenant_id=getattr(request, 'routing_tenant_id', None),
                    request_path=request.path,
                    request_method=request.method,
                    timestamp=timezone.now().isoformat()
                )
            
        except Exception as e:
            logger.error(f"Error in audit middleware: {e}")
        
        return None
    
    def process_response(self, request, response):
        """Complete audit logging."""
        try:
            if hasattr(request, 'security_flags') and request.security_flags.get('suspicious'):
                # Add security headers
                response['X-Security-Flag'] = 'suspicious'
                response['X-Security-Reason'] = ','.join(request.security_flags.get('indicators', []))
                
                # Log security response
                from .tasks.monitoring import log_security_response
                
                log_security_response.delay(
                    request_id=getattr(request, 'performance_tracking', {}).get('request_id'),
                    response_status=response.status_code,
                    security_flags=request.security_flags,
                    timestamp=timezone.now().isoformat()
                )
            
        except Exception as e:
            logger.error(f"Error in audit response processing: {e}")
        
        return response
    
    def _check_suspicious_patterns(self, request):
        """Check for suspicious request patterns."""
        indicators = []
        
        try:
            # Check for SQL injection patterns
            sql_patterns = ['--', ';', 'drop', 'union', 'select', 'insert', 'update', 'delete']
            request_str = str(request.GET) + str(request.POST)
            
            if any(pattern.lower() in request_str.lower() for pattern in sql_patterns):
                indicators.append('sql_injection')
            
            # Check for XSS patterns
            xss_patterns = ['<script', 'javascript:', 'onerror=', 'onload=', 'alert(']
            if any(pattern.lower() in request_str.lower() for pattern in xss_patterns):
                indicators.append('xss_attempt')
            
            # Check for suspicious user agents
            user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
            suspicious_uas = ['bot', 'crawler', 'scanner', 'exploit', 'hack']
            
            if any(sus_ua in user_agent for sus_ua in suspicious_uas):
                indicators.append('suspicious_user_agent')
            
            # Check for missing headers
            required_headers = ['HTTP_USER_AGENT']
            missing_headers = [header for header in required_headers if header not in request.META]
            
            if missing_headers:
                indicators.append('missing_headers')
            
            # Check for unusual request size
            content_length = request.META.get('CONTENT_LENGTH', 0)
            if content_length > 10 * 1024 * 1024:  # 10MB
                indicators.append('large_request')
            
            # Check for rapid requests
            client_ip = get_client_ip(request)
            if self._is_rapid_request(client_ip):
                indicators.append('rapid_requests')
            
        except Exception as e:
            logger.error(f"Error checking suspicious patterns: {e}")
        
        return indicators
    
    def _is_rate_limited(self, request, ip_address):
        """Check if IP is rate limited."""
        try:
            # Check cache for rate limiting
            cache_key = f"rate_limit:{ip_address}"
            recent_requests = cache.get(cache_key, 0)
            
            if recent_requests >= 100:  # 100 requests per minute
                return True
            
            # Increment counter
            cache.set(cache_key, recent_requests + 1, timeout=60)  # 1 minute
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False
    
    def _is_rapid_request(self, ip_address):
        """Check for rapid requests from same IP."""
        try:
            cache_key = f"rapid_check:{ip_address}"
            requests = cache.get(cache_key, [])
            
            now = time.time()
            
            # Clean old requests (older than 1 minute)
            requests = [req_time for req_time in requests if now - req_time < 60]
            
            # Add current request
            requests.append(now)
            
            # Check if more than 30 requests in last minute
            if len(requests) > 30:
                cache.set(cache_key, requests, timeout=60)
                return True
            
            cache.set(cache_key, requests, timeout=60)
            return False
            
        except Exception as e:
            logger.error(f"Error checking rapid requests: {e}")
            return False


class RoutingCacheMiddleware(MiddlewareMixin):
    """
    Middleware for intelligent caching of routing responses.
    
    Provides response caching based on request patterns,
    user context, and content type.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def process_request(self, request):
        """Check cache before processing."""
        try:
            # Only cache GET requests
            if request.method != 'GET':
                return None
            
            # Don't cache authenticated requests with sensitive data
            if request.path.startswith('/admin/') or request.path.startswith('/api/auth/'):
                return None
            
            # Generate cache key
            cache_key = self._generate_cache_key(request)
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            
            if cached_response:
                # Return cached response
                from django.http import HttpResponse
                response = HttpResponse(cached_response['content'])
                
                # Copy cached headers
                for header, value in cached_response.get('headers', {}).items():
                    response[header] = value
                
                response['X-Cache'] = 'HIT'
                response['X-Cache-Key'] = cache_key
                
                return response
            
            # Mark request for caching
            request.should_cache_response = True
            request.cache_key = cache_key
            
        except Exception as e:
            logger.error(f"Error in cache middleware: {e}")
        
        return None
    
    def process_response(self, request, response):
        """Cache response if applicable."""
        try:
            if hasattr(request, 'should_cache_response') and request.should_cache_response:
                # Only cache successful responses
                if response.status_code == 200:
                    cache_data = {
                        'content': response.content,
                        'headers': {
                            'Content-Type': response.get('Content-Type'),
                            'X-Routing-Time': response.get('X-Routing-Time'),
                        }
                    }
                    
                    # Cache for 5 minutes
                    cache.set(request.cache_key, cache_data, timeout=300)
                    
                    response['X-Cache'] = 'MISS'
                    response['X-Cache-Key'] = request.cache_key
        
        except Exception as e:
            logger.error(f"Error caching response: {e}")
        
        return response
    
    def _generate_cache_key(self, request):
        """Generate cache key for request."""
        try:
            import hashlib
            
            # Include user context
            user_id = getattr(request, 'routing_user_id', 'anonymous')
            tenant_id = getattr(request, 'routing_tenant_id', 'default')
            
            # Include request context
            path = request.path
            query_string = request.META.get('QUERY_STRING', '')
            
            # Generate key
            key_data = f"{path}:{query_string}:{user_id}:{tenant_id}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            return f"routing_response:{cache_key}"
            
        except Exception as e:
            logger.error(f"Error generating cache key: {e}")
            return f"routing_response:{hash(request.path)}"


# Middleware configuration
def get_routing_middleware():
    """Get list of routing middleware in correct order."""
    return [
        'offer_routing.middleware.RoutingContextMiddleware',
        'offer_routing.middleware.RoutingPerformanceMiddleware',
        'offer_routing.middleware.RoutingAuditMiddleware',
        'offer_routing.middleware.RoutingCacheMiddleware',
    ]
