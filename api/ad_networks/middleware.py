"""
api/ad_networks/middleware.py
Custom middleware for ad networks module
SaaS-ready with tenant support
"""

import json
import logging
import time
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse, HttpResponseBadRequest
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from datetime import timedelta
import hashlib
import hmac

from api.ad_networks.models import AdNetwork, NetworkAPILog, KnownBadIP
from api.ad_networks.choices import NetworkStatus
from api.ad_networks.constants import (
    API_RATE_LIMIT_PER_IP,
    API_RATE_LIMIT_PER_TENANT,
    POSTBACK_SECURITY_ENABLED,
    POSTBACK_IP_WHITELIST_ENABLED,
    CACHE_KEY_PATTERNS
)

logger = logging.getLogger(__name__)


class OfferTrackingMiddleware(MiddlewareMixin):
    """
    Add offer context to request for tracking and analytics
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """Add offer tracking context to request"""
        
        # Initialize offer tracking context
        request.offer_tracking = {
            'offer_id': None,
            'click_id': None,
            'engagement_id': None,
            'conversion_id': None,
            'network_id': None,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip_address': self._get_client_ip(request),
            'referrer': request.META.get('HTTP_REFERER', ''),
            'session_id': getattr(request, 'session', {}).get('session_key', ''),
            'timestamp': timezone.now().isoformat(),
            'device_info': self._get_device_info(request),
            'location_data': self._get_location_data(request),
        }
        
        # Extract tracking parameters from URL
        if request.GET:
            request.offer_tracking.update({
                'utm_source': request.GET.get('utm_source'),
                'utm_medium': request.GET.get('utm_medium'),
                'utm_campaign': request.GET.get('utm_campaign'),
                'utm_content': request.GET.get('utm_content'),
                'utm_term': request.GET.get('utm_term'),
                'sub_id': request.GET.get('sub_id'),
                'aff_id': request.GET.get('aff_id'),
                'click_id': request.GET.get('click_id'),
                'offer_id': request.GET.get('offer_id'),
                'conversion_id': request.GET.get('conversion_id'),
            })
        
        # Extract from headers (for postback calls)
        if request.META:
            request.offer_tracking.update({
                'x_click_id': request.META.get('HTTP_X_CLICK_ID'),
                'x_offer_id': request.META.get('HTTP_X_OFFER_ID'),
                'x_network_id': request.META.get('HTTP_X_NETWORK_ID'),
                'x_user_id': request.META.get('HTTP_X_USER_ID'),
                'x_conversion_id': request.META.get('HTTP_X_CONVERSION_ID'),
            })
        
        # Add user context if authenticated
        if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
            request.offer_tracking.update({
                'user_id': request.user.id,
                'user_email': request.user.email,
                'user_username': request.user.username,
                'is_authenticated': True,
            })
        else:
            request.offer_tracking['is_authenticated'] = False
        
        # Add tenant context
        if hasattr(request, 'tenant'):
            request.offer_tracking['tenant_id'] = request.tenant.id if request.tenant else None
        
        # Cache tracking context for later use
        tracking_key = f"offer_tracking_{request.offer_tracking.get('click_id', 'unknown')}"
        cache.set(tracking_key, request.offer_tracking, timeout=3600)
        
        return None
    
    def process_response(self, request, response):
        """Process response with offer tracking data"""
        
        # Add tracking headers to response
        if hasattr(request, 'offer_tracking'):
            tracking = request.offer_tracking
            
            # Add correlation ID for tracking
            if tracking.get('click_id'):
                response['X-Click-ID'] = tracking['click_id']
            
            if tracking.get('engagement_id'):
                response['X-Engagement-ID'] = tracking['engagement_id']
            
            # Add analytics headers
            response['X-Tracking-Enabled'] = 'true'
            response['X-Timestamp'] = tracking['timestamp']
        
        return response
    
    def _get_client_ip(self, request):
        """Extract real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _get_device_info(self, request):
        """Extract device information from request"""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Simple device detection (you can use a library like user-agents)
        device_info = {
            'user_agent': user_agent,
            'is_mobile': any(mobile in user_agent.lower() for mobile in ['mobile', 'android', 'iphone']),
            'is_tablet': any(tablet in user_agent.lower() for tablet in ['ipad', 'tablet']),
            'is_desktop': not any(mobile in user_agent.lower() for mobile in ['mobile', 'android', 'iphone', 'ipad', 'tablet']),
        }
        
        # Extract browser
        if 'chrome' in user_agent.lower():
            device_info['browser'] = 'Chrome'
        elif 'firefox' in user_agent.lower():
            device_info['browser'] = 'Firefox'
        elif 'safari' in user_agent.lower():
            device_info['browser'] = 'Safari'
        elif 'edge' in user_agent.lower():
            device_info['browser'] = 'Edge'
        else:
            device_info['browser'] = 'Unknown'
        
        # Extract OS
        if 'android' in user_agent.lower():
            device_info['os'] = 'Android'
        elif 'iphone' in user_agent.lower() or 'ipad' in user_agent.lower():
            device_info['os'] = 'iOS'
        elif 'windows' in user_agent.lower():
            device_info['os'] = 'Windows'
        elif 'mac' in user_agent.lower():
            device_info['os'] = 'macOS'
        elif 'linux' in user_agent.lower():
            device_info['os'] = 'Linux'
        else:
            device_info['os'] = 'Unknown'
        
        return device_info
    
    def _get_location_data(self, request):
        """Extract location data from request"""
        location_data = {}
        
        # Get country from IP (you would use a GeoIP service here)
        ip = self._get_client_ip(request)
        location_data['ip'] = ip
        location_data['country'] = self._get_country_from_ip(ip)
        location_data['city'] = self._get_city_from_ip(ip)
        
        # Get location from headers (if provided by CDN)
        location_data.update({
            'cloudflare_country': request.META.get('HTTP_CF_IPCOUNTRY'),
            'cloudflare_city': request.META.get('HTTP_CF_IPCITY'),
            'aws_region': request.META.get('HTTP_X_AMZN_CF_ID'),
        })
        
        return location_data
    
    def _get_country_from_ip(self, ip):
        """Get country from IP address"""
        # This would integrate with a GeoIP service
        # For demo, return None
        return None
    
    def _get_city_from_ip(self, ip):
        """Get city from IP address"""
        # This would integrate with a GeoIP service
        # For demo, return None
        return None


class NetworkAuthMiddleware(MiddlewareMixin):
    """
    Verify and authenticate network API calls
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """Authenticate network API calls"""
        
        # Only process API calls to ad networks endpoints
        if not self._is_ad_networks_endpoint(request.path):
            return None
        
        # Initialize network auth context
        request.network_auth = {
            'is_authenticated': False,
            'network': None,
            'tenant_id': None,
            'api_key': None,
            'signature_valid': False,
            'rate_limit_ok': True,
            'ip_whitelisted': True,
        }
        
        # Extract authentication information
        auth_result = self._extract_auth_info(request)
        request.network_auth.update(auth_result)
        
        # If authentication fails, return error response
        if not auth_result.get('is_authenticated', False):
            return self._auth_error_response(auth_result.get('error', 'Authentication failed'))
        
        # Rate limiting check
        if not self._check_rate_limit(request):
            request.network_auth['rate_limit_ok'] = False
            return self._rate_limit_response()
        
        # IP whitelist check for postbacks
        if POSTBACK_IP_WHITELIST_ENABLED and 'postback' in request.path:
            if not self._check_ip_whitelist(request):
                request.network_auth['ip_whitelisted'] = False
                return self._ip_whitelist_response()
        
        # Log API call
        self._log_api_call(request)
        
        return None
    
    def process_response(self, request, response):
        """Process response with network auth context"""
        
        # Add network auth headers to response
        if hasattr(request, 'network_auth'):
            auth = request.network_auth
            
            response['X-Network-Auth'] = str(auth['is_authenticated']).lower()
            response['X-Rate-Limit-OK'] = str(auth['rate_limit_ok']).lower()
            
            if auth.get('network'):
                response['X-Network-ID'] = str(auth['network'].id)
                response['X-Network-Name'] = auth['network'].name
            
            if auth.get('tenant_id'):
                response['X-Tenant-ID'] = auth['tenant_id']
        
        return response
    
    def _is_ad_networks_endpoint(self, path):
        """Check if request is for ad networks endpoints"""
        ad_networks_paths = [
            '/api/ad_networks/',
            '/api/ad-networks/',
            '/api/v1/ad_networks/',
            '/api/v1/ad-networks/',
        ]
        
        return any(path.startswith(api_path) for api_path in ad_networks_paths)
    
    def _extract_auth_info(self, request):
        """Extract authentication information from request"""
        auth_info = {
            'is_authenticated': False,
            'error': None,
        }
        
        # Method 1: API Key in header
        api_key = request.META.get('HTTP_X_API_KEY')
        if api_key:
            return self._authenticate_with_api_key(api_key, auth_info)
        
        # Method 2: Bearer token
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Remove 'Bearer '
            return self._authenticate_with_token(token, auth_info)
        
        # Method 3: Network-specific auth (for postbacks)
        if 'postback' in request.path:
            return self._authenticate_postback(request, auth_info)
        
        # Method 4: Basic auth
        if 'HTTP_AUTHORIZATION' in request.META:
            return self._authenticate_basic_auth(request, auth_info)
        
        auth_info['error'] = 'No authentication method provided'
        return auth_info
    
    def _authenticate_with_api_key(self, api_key, auth_info):
        """Authenticate using API key"""
        try:
            # Find network by API key
            network = AdNetwork.objects.filter(
                api_key=api_key,
                is_active=True
            ).first()
            
            if not network:
                auth_info['error'] = 'Invalid API key'
                return auth_info
            
            # Check if network is verified
            if not network.is_verified:
                auth_info['error'] = 'Network not verified'
                return auth_info
            
            auth_info.update({
                'is_authenticated': True,
                'network': network,
                'tenant_id': getattr(network, 'tenant_id', None),
                'api_key': api_key,
                'auth_method': 'api_key',
            })
            
            return auth_info
            
        except Exception as e:
            logger.error(f"API key authentication error: {str(e)}")
            auth_info['error'] = 'Authentication error'
            return auth_info
    
    def _authenticate_with_token(self, token, auth_info):
        """Authenticate using JWT token"""
        try:
            # This would integrate with your JWT authentication system
            # For demo, we'll validate token format
            
            if not token or len(token) < 10:
                auth_info['error'] = 'Invalid token format'
                return auth_info
            
            # Extract network ID from token (simplified)
            # In real implementation, you'd decode JWT
            try:
                payload = json.loads(atob(token.split('.')[1]))  # Simplified
                network_id = payload.get('network_id')
                
                if not network_id:
                    auth_info['error'] = 'Invalid token payload'
                    return auth_info
                
                network = AdNetwork.objects.filter(
                    id=network_id,
                    is_active=True
                ).first()
                
                if not network:
                    auth_info['error'] = 'Network not found'
                    return auth_info
                
                auth_info.update({
                    'is_authenticated': True,
                    'network': network,
                    'tenant_id': getattr(network, 'tenant_id', None),
                    'auth_method': 'jwt_token',
                })
                
                return auth_info
                
            except Exception:
                auth_info['error'] = 'Invalid token'
                return auth_info
                
        except Exception as e:
            logger.error(f"Token authentication error: {str(e)}")
            auth_info['error'] = 'Token authentication error'
            return auth_info
    
    def _authenticate_postback(self, request, auth_info):
        """Authenticate postback requests"""
        try:
            # Get network type from URL
            network_type = request.resolver_match.kwargs.get('network_type') if hasattr(request, 'resolver_match') else None
            
            if not network_type:
                auth_info['error'] = 'Network type not specified'
                return auth_info
            
            # Find network by type
            network = AdNetwork.objects.filter(
                network_type=network_type,
                is_active=True
            ).first()
            
            if not network:
                auth_info['error'] = 'Network not found'
                return auth_info
            
            # Validate postback signature if enabled
            if POSTBACK_SECURITY_ENABLED:
                if not self._validate_postback_signature(request, network):
                    auth_info['error'] = 'Invalid postback signature'
                    return auth_info
            
            auth_info.update({
                'is_authenticated': True,
                'network': network,
                'tenant_id': getattr(network, 'tenant_id', None),
                'auth_method': 'postback',
                'signature_valid': True,
            })
            
            return auth_info
            
        except Exception as e:
            logger.error(f"Postback authentication error: {str(e)}")
            auth_info['error'] = 'Postback authentication error'
            return auth_info
    
    def _authenticate_basic_auth(self, request, auth_info):
        """Authenticate using Basic Auth"""
        try:
            import base64
            
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if not auth_header.startswith('Basic '):
                auth_info['error'] = 'Invalid basic auth format'
                return auth_info
            
            # Decode credentials
            encoded_credentials = auth_header[6:]  # Remove 'Basic '
            decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
            username, password = decoded_credentials.split(':', 1)
            
            # Find network by credentials (using postback_key as username)
            network = AdNetwork.objects.filter(
                postback_key=username,
                postback_password=password,
                is_active=True
            ).first()
            
            if not network:
                auth_info['error'] = 'Invalid credentials'
                return auth_info
            
            auth_info.update({
                'is_authenticated': True,
                'network': network,
                'tenant_id': getattr(network, 'tenant_id', None),
                'auth_method': 'basic_auth',
            })
            
            return auth_info
            
        except Exception as e:
            logger.error(f"Basic auth error: {str(e)}")
            auth_info['error'] = 'Basic authentication error'
            return auth_info
    
    def _validate_postback_signature(self, request, network):
        """Validate postback signature"""
        try:
            # Get signature from request
            signature = request.META.get('HTTP_X_SIGNATURE') or request.GET.get('signature')
            if not signature:
                return False
            
            # Get postback key
            postback_key = network.postback_key or network.api_key
            if not postback_key:
                return False
            
            # Generate expected signature
            payload = request.body.decode('utf-8')
            expected_signature = hmac.new(
                postback_key.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Signature validation error: {str(e)}")
            return False
    
    def _check_rate_limit(self, request):
        """Check rate limiting"""
        try:
            if not hasattr(request, 'network_auth') or not request.network_auth.get('network'):
                return True
            
            network = request.network_auth['network']
            client_ip = self._get_client_ip(request)
            tenant_id = request.network_auth.get('tenant_id')
            
            # Check IP-based rate limit
            ip_key = f"rate_limit_ip_{client_ip}"
            ip_count = cache.get(ip_key, 0)
            
            if ip_count >= API_RATE_LIMIT_PER_IP:
                return False
            
            # Check tenant-based rate limit
            if tenant_id:
                tenant_key = f"rate_limit_tenant_{tenant_id}"
                tenant_count = cache.get(tenant_key, 0)
                
                if tenant_count >= API_RATE_LIMIT_PER_TENANT:
                    return False
                
                # Increment tenant counter
                cache.set(tenant_key, tenant_count + 1, timeout=3600)
            
            # Increment IP counter
            cache.set(ip_key, ip_count + 1, timeout=3600)
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limit check error: {str(e)}")
            return True  # Allow on error
    
    def _check_ip_whitelist(self, request):
        """Check if IP is whitelisted for postbacks"""
        try:
            client_ip = self._get_client_ip(request)
            
            # Check if IP is in known bad IPs
            if KnownBadIP.objects.filter(
                ip_address=client_ip,
                is_active=True
            ).exists():
                return False
            
            # You could also check against a whitelist of allowed IPs
            # For demo, we'll allow all non-blacklisted IPs
            return True
            
        except Exception as e:
            logger.error(f"IP whitelist check error: {str(e)}")
            return True  # Allow on error
    
    def _log_api_call(self, request):
        """Log API call for monitoring"""
        try:
            if not hasattr(request, 'network_auth') or not request.network_auth.get('network'):
                return
            
            network = request.network_auth['network']
            
            # Skip logging for health checks to reduce noise
            if 'health' in request.path:
                return
            
            NetworkAPILog.objects.create(
                network=network,
                endpoint=request.path,
                method=request.method,
                request_data=dict(request.POST) if request.method == 'POST' else dict(request.GET),
                request_headers=dict(request.META),
                status_code=200,  # Will be updated in response middleware
                is_success=True,  # Will be updated in response middleware
                tenant_id=request.network_auth.get('tenant_id'),
                user=getattr(request, 'user', None),
            )
            
        except Exception as e:
            logger.error(f"API call logging error: {str(e)}")
    
    def _get_client_ip(self, request):
        """Extract real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _auth_error_response(self, error_message):
        """Return authentication error response"""
        return JsonResponse({
            'error': 'Authentication failed',
            'message': error_message,
            'code': 'AUTH_FAILED'
        }, status=401)
    
    def _rate_limit_response(self):
        """Return rate limit error response"""
        return JsonResponse({
            'error': 'Rate limit exceeded',
            'message': 'Too many requests. Please try again later.',
            'code': 'RATE_LIMIT_EXCEEDED'
        }, status=429)
    
    def _ip_whitelist_response(self):
        """Return IP whitelist error response"""
        return JsonResponse({
            'error': 'IP not allowed',
            'message': 'Your IP address is not allowed to access this endpoint.',
            'code': 'IP_NOT_ALLOWED'
        }, status=403)


def atob(data):
    """Base64 decode function (simplified)"""
    import base64
    return base64.b64decode(data).decode('utf-8')
