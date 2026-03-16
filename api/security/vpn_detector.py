"""
VPN Detection System with Defensive Coding and Bulletproof Patterns
"""

import logging
import requests
import ipaddress
import json
import time
from typing import Optional, Dict, Any, Tuple, List
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import functools

logger = logging.getLogger(__name__)


class VPNServiceError(Exception):
    """Custom exception for VPN service errors"""
    pass


class VPNServiceUnavailableError(VPNServiceError):
    """VPN service is unavailable"""
    pass


class VPNDetector:
    """
    Bulletproof VPN Detector with defensive coding patterns
    """
    
    # Default configuration
    DEFAULT_CONFIG = {
        'cache_timeout': 3600,
        'retry_attempts': 3,
        'retry_delay': 1.0,
        'timeout': 5.0,
        'threshold_score': 70,
        'max_cache_size': 1000,
        'rate_limit_per_minute': 60,
        'enable_fallback': True,
        'log_level': 'WARNING'
    }
    
    # Known VPN/Proxy providers
    KNOWN_VPN_PROVIDERS = [
        'expressvpn', 'nordvpn', 'cyberghost', 'pia', 'surfshark',
        'private internet access', 'purevpn', 'vyprvpn', 'tunnelbear',
        'windscribe', 'hotspot shield', 'protonvpn', 'mullvad'
    ]
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize VPN detector
        """
        try:
            # Merge configs with defensive dict.get()
            user_config = config or {}
            self.config = {**self.DEFAULT_CONFIG, **user_config}
            
            # Services with defensive loading
            self.services = self._load_service_config()
            
            # Cache prefix
            self.cache_prefix = "vpn_detector"
            
            # Rate limiting key
            self.rate_limit_cache_key = f"{self.cache_prefix}_rate_limit"
            
            # Statistics with Null Object Pattern
            self.stats = {
                'total_checks': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'service_calls': 0,
                'errors': 0,
                'vpn_detections': 0,
                'proxy_detections': 0
            }
            
            logger.info("VPNDetector initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize VPNDetector: {str(e)}")
            # Graceful degradation
            self.config = self.DEFAULT_CONFIG
            self.services = {}
            self.stats = {}
    
    def _load_service_config(self) -> Dict[str, Any]:
        """
        Load service configuration with defensive coding
        """
        try:
            # Use getattr() with default
            service_config = getattr(settings, 'VPN_SERVICES', {})
            
            # Null Object Pattern: If no config, use mock
            if not service_config:
                logger.debug("No VPN services configured, using mock service")
                return {
                    'mock': {
                        'enabled': True,
                        'endpoint': 'mock',
                        'api_key': '',
                        'priority': 1
                    }
                }
            
            # Validate each service with dict.get()
            valid_services = {}
            for name, config in service_config.items():
                if isinstance(config, dict) and config.get('enabled', True):
                    valid_services[name] = {
                        'endpoint': config.get('endpoint', ''),
                        'api_key': config.get('api_key', ''),
                        'priority': config.get('priority', 1),
                        'timeout': config.get('timeout', self.config.get('timeout', 5.0))
                    }
            
            return valid_services
            
        except Exception as e:
            logger.error(f"Error loading service config: {str(e)}")
            # Return empty dict on error
            return {}
    
    def _validate_ip_address(self, ip_address: str) -> bool:
        """
        Validate IP address format with defensive coding
        """
        try:
            ipaddress.ip_address(ip_address)
            return True
        except ValueError:
            logger.warning(f"Invalid IP address: {ip_address}")
            return False
        except Exception as e:
            logger.error(f"Error validating IP: {str(e)}")
            return False
    
    def generate_cache_key(self, ip_address: str) -> str:
        """
        Generate cache key with defensive validation
        """
        try:
            # Validate IP
            if not self._validate_ip_address(ip_address):
                return f"{self.cache_prefix}:invalid_ip"
            
            # Create safe cache key
            safe_ip = ip_address.replace('.', '_').replace(':', '_')
            return f"{self.cache_prefix}:{safe_ip}"
            
        except Exception as e:
            logger.error(f"Error generating cache key: {str(e)}")
            # Fallback key
            return f"{self.cache_prefix}:error"
    
    def check_rate_limit(self) -> bool:
        """
        Check rate limiting with defensive coding
        """
        try:
            current_time = timezone.now()
            minute_key = current_time.strftime("%Y%m%d%H%M")
            rate_key = f"{self.rate_limit_cache_key}:{minute_key}"
            
            # Use dict.get() style
            current_count = cache.get(rate_key, 0)
            limit = self.config.get('rate_limit_per_minute', 60)
            
            if current_count >= limit:
                logger.warning(f"Rate limit exceeded: {current_count}/{limit}")
                return False
            
            # Set with expiry
            cache.set(rate_key, current_count + 1, 60)
            return True
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {str(e)}")
            # Graceful degradation: allow on error
            return True
    
    def _safe_request(self, url: str, headers: Dict[str, str], 
                     timeout: float) -> Optional[Dict[str, Any]]:
        """
        Make safe HTTP request with retry logic
        """
        max_retries = self.config.get('retry_attempts', 3)
        
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=timeout,
                    verify=True
                )
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    raise VPNServiceUnavailableError("Request timeout after retries")
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    raise VPNServiceUnavailableError(f"Request failed: {str(e)}")
            
            # Exponential backoff
            delay = self.config.get('retry_delay', 1.0) * (2 ** attempt)
            time.sleep(min(delay, 10))  # Max 10 seconds
        
        return None
    
    def check_ip_with_service(self, ip_address: str, service_name: str, 
                             service_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check IP with specific service with defensive coding
        """
        try:
            # Use dict.get() for safe access
            endpoint = service_config.get('endpoint', '')
            api_key = service_config.get('api_key', '')
            timeout = service_config.get('timeout', self.config.get('timeout', 5.0))
            
            if not endpoint:
                logger.warning(f"Service {service_name} has no endpoint configured")
                return None
            
            # Build URL based on service type
            if 'ipinfo.io' in endpoint:
                url = f"{endpoint}/{ip_address}/json"
                if api_key:
                    url += f"?token={api_key}"
                headers = {'User-Agent': 'VPNDetector/1.0'}  # [OK] headers এখানে
            elif 'vpnapi.io' in endpoint:
                url = f"{endpoint}/{ip_address}"
                headers = {'User-Agent': 'VPNDetector/1.0'}
                if api_key:
                    headers['Authorization'] = f"Bearer {api_key}"
            else:
                url = endpoint.format(ip=ip_address, key=api_key)
                headers = {'User-Agent': 'VPNDetector/1.0'}
            
            # Make request
            result = self._safe_request(url, headers, timeout)
            
            if result:
                return self._parse_service_result(result, service_name)
            
            return None
            
        except VPNServiceUnavailableError as e:
            logger.error(f"Service {service_name} unavailable: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error checking IP with {service_name}: {str(e)}")
            # Return None instead of crashing
            return None
    
    def _parse_service_result(self, result: Dict[str, Any], 
                             service_name: str) -> Dict[str, Any]:
        """
        Parse service result with defensive coding
        """
        try:
            # Null Object Pattern: Default structure
            parsed = {
                'is_vpn': False,
                'is_proxy': False,
                'is_tor': False,
                'is_hosting': False,
                'service': service_name,
                'confidence': 0,
                'details': {},
                'timestamp': timezone.now().isoformat()
            }
            
            # Parse based on service using dict.get()
            if 'ipinfo.io' in service_name:
                parsed.update({
                    'is_vpn': result.get('vpn', False) or result.get('proxy', False),
                    'is_proxy': result.get('proxy', False),
                    'is_tor': result.get('tor', False),
                    'is_hosting': result.get('hosting', False),
                    'confidence': 90 if result.get('vpn') or result.get('proxy') else 0,
                    'details': {
                        'provider': result.get('org', ''),
                        'country': result.get('country', ''),
                        'city': result.get('city', '')
                    }
                })
            elif 'vpnapi.io' in service_name:
                security = result.get('security', {})
                parsed.update({
                    'is_vpn': security.get('vpn', False),
                    'is_proxy': security.get('proxy', False),
                    'is_tor': security.get('tor', False),
                    'confidence': security.get('score', 0) * 100,
                    'details': {
                        'network': result.get('network', ''),
                        'country': result.get('location', {}).get('country', '')
                    }
                })
            elif 'mock' in service_name:
                parsed.update({
                    'is_vpn': False,  # Safe default
                    'is_proxy': False,
                    'confidence': 0,
                    'details': {'mock': True}
                })
            else:
                # Generic parsing with safe defaults
                parsed.update({
                    'is_vpn': result.get('vpn', result.get('is_vpn', False)),
                    'is_proxy': result.get('proxy', result.get('is_proxy', False)),
                    'confidence': result.get('confidence', result.get('score', 0)) * 100,
                    'details': result
                })
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing {service_name} result: {str(e)}")
            # Return safe default on error
            return {
                'is_vpn': False,
                'is_proxy': False,
                'service': service_name,
                'confidence': 0,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _check_local_patterns(self, ip_address: str) -> Dict[str, Any]:
        """
        Check local patterns with defensive coding
        """
        # Null Object Pattern: Default result
        result = {
            'is_vpn': False,
            'is_proxy': False,
            'confidence': 0,
            'patterns': [],
            'timestamp': timezone.now().isoformat()
        }
        
        try:
            # Simple pattern matching
            octets = ip_address.split('.')
            if len(octets) == 4:
                try:
                    first_octet = int(octets[0])
                    
                    # Private IP ranges
                    if first_octet in [10, 172, 192]:
                        result['patterns'].append('private_ip_range')
                        result['confidence'] += 10
                    
                    # Suspicious ranges
                    if first_octet in [5, 45, 46, 89, 103, 104]:
                        result['patterns'].append('suspicious_ip_range')
                        result['confidence'] += 30
                        
                except (ValueError, IndexError):
                    pass
            
            # Check for known providers in IP string
            ip_lower = ip_address.lower()
            for provider in self.KNOWN_VPN_PROVIDERS:
                if provider in ip_lower:
                    result['patterns'].append(f'known_provider_{provider}')
                    result['confidence'] += 50
            
            # Determine if VPN based on threshold
            threshold = self.config.get('threshold_score', 70)
            if result['confidence'] > threshold:
                result['is_vpn'] = True
                result['is_proxy'] = True
            
            return result
            
        except Exception as e:
            logger.error(f"Error in local pattern check: {str(e)}")
            return result
    
    def is_vpn(self, ip_address: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Main method to check if IP is VPN with comprehensive defensive coding
        """
        # Update stats safely
        self.stats['total_checks'] = self.stats.get('total_checks', 0) + 1
        
        # Null Object Pattern: Default response
        default_result = {
            'is_vpn': False,
            'is_proxy': False,
            'is_tor': False,
            'is_hosting': False,
            'confidence': 0,
            'cached': False,
            'service': 'none',
            'error': None,
            'timestamp': timezone.now().isoformat(),
            'patterns': []
        }
        
        try:
            # Validate input
            if not ip_address or not self._validate_ip_address(ip_address):
                logger.warning(f"Invalid IP address provided: {ip_address}")
                return False, default_result
            
            # Check rate limit
            if not self.check_rate_limit():
                logger.warning("Rate limit exceeded, using fallback check")
                return self._fallback_check(ip_address)
            
            # Check cache first
            cache_key = self.generate_cache_key(ip_address)
            cached_result = cache.get(cache_key)
            
            if cached_result:
                self.stats['cache_hits'] = self.stats.get('cache_hits', 0) + 1
                logger.debug(f"Cache hit for IP: {ip_address}")
                # Return cached result with is_vpn from cache
                is_vpn_cached = cached_result.get('is_vpn', False)
                return is_vpn_cached, {**cached_result, 'cached': True}
            
            self.stats['cache_misses'] = self.stats.get('cache_misses', 0) + 1
            
            # Check with services in priority order
            services_by_priority = sorted(
                self.services.items(),
                key=lambda x: x[1].get('priority', 1)
            )
            
            final_result = None
            
            for service_name, service_config in services_by_priority:
                try:
                    self.stats['service_calls'] = self.stats.get('service_calls', 0) + 1
                    
                    service_result = self.check_ip_with_service(
                        ip_address, 
                        service_name, 
                        service_config
                    )
                    
                    if service_result:
                        confidence = service_result.get('confidence', 0)
                        threshold = self.config.get('threshold_score', 70)
                        
                        if confidence >= threshold:
                            final_result = service_result
                            logger.info(f"VPN detected by {service_name} with confidence {confidence}%")
                            break
                        else:
                            logger.debug(f"Service {service_name} returned low confidence: {confidence}%")
                    
                except VPNServiceUnavailableError:
                    logger.warning(f"Service {service_name} unavailable, trying next...")
                    continue
                except Exception as e:
                    logger.error(f"Error with service {service_name}: {str(e)}")
                    self.stats['errors'] = self.stats.get('errors', 0) + 1
                    continue
            
            # If no service returned high confidence, use local patterns
            if not final_result:
                local_result = self._check_local_patterns(ip_address)
                # Merge results with local_result taking priority
                final_result = default_result.copy()
                final_result.update(local_result)
                final_result['service'] = 'local_patterns'
            
            # Update statistics
            if final_result.get('is_vpn', False):
                self.stats['vpn_detections'] = self.stats.get('vpn_detections', 0) + 1
            
            if final_result.get('is_proxy', False):
                self.stats['proxy_detections'] = self.stats.get('proxy_detections', 0) + 1
            
            # Cache the result
            cache_timeout = self.config.get('cache_timeout', 3600)
            cache.set(cache_key, final_result, cache_timeout)
            
            return final_result.get('is_vpn', False), final_result
            
        except Exception as e:
            # Graceful Degradation: Log error but return safe result
            logger.error(f"Critical error in VPN detection: {str(e)}", exc_info=True)
            self.stats['errors'] = self.stats.get('errors', 0) + 1
            
            error_result = default_result.copy()
            error_result.update({
                'error': str(e),
                'service': 'error_fallback'
            })
            
            return False, error_result
    
    def _fallback_check(self, ip_address: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Fallback check when rate limited or services unavailable
        """
        try:
            # Simple heuristics for fallback
            result = {
                'is_vpn': False,
                'is_proxy': False,
                'confidence': 0,
                'service': 'fallback',
                'patterns': [],
                'timestamp': timezone.now().isoformat(),
                'note': 'Fallback check due to rate limiting'
            }
            
            # Very basic checks
            if '192.168.' in ip_address or '10.' in ip_address:
                result['patterns'].append('private_network')
                result['confidence'] = 10
            
            return False, result
            
        except Exception as e:
            logger.error(f"Fallback check failed: {str(e)}")
            return False, {
                'is_vpn': False,
                'is_proxy': False,
                'confidence': 0,
                'service': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get detector statistics with defensive coding
        """
        try:
            return {
                **self.stats,
                'cache_prefix': self.cache_prefix,
                'services_configured': len(self.services),
                'config': {
                    'cache_timeout': self.config.get('cache_timeout'),
                    'rate_limit': self.config.get('rate_limit_per_minute'),
                    'threshold': self.config.get('threshold_score')
                },
                'timestamp': timezone.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return {'error': str(e)}
    
    def clear_cache(self) -> Dict[str, Any]:
        """
        Clear detector cache
        """
        try:
            logger.info("Cache clear requested")
            return {
                'success': True,
                'message': 'Cache clear logged',
                'timestamp': timezone.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return {'success': False, 'error': str(e)}


# ==================== SIMPLIFIED VERSION ====================

class SimpleVPNDetector:
    """
    Simplified VPN detector with minimal defensive coding
    """
    
    def __init__(self):
        # Simple cache using dict
        self.cache = {}
    
    def is_vpn(self, ip_address: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Simple VPN check with defensive coding
        """
        try:
            # Basic validation
            if not ip_address:
                return False, {'error': 'No IP address provided'}
            
            # Check cache using getattr() style
            if ip_address in self.cache:
                return self.cache[ip_address]
            
            # Null Object Pattern: Default result
            result = (False, {
                'is_vpn': False,
                'is_proxy': False,
                'confidence': 0,
                'checked_at': timezone.now().isoformat(),
                'service': 'simple_detector'
            })
            
            # Simple logic for demo (always return False)
            # In production, add actual detection logic
            
            # Cache the result
            self.cache[ip_address] = result
            
            # Limit cache size
            if len(self.cache) > 1000:
                # Remove oldest item
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
            
            return result
            
        except Exception as e:
            # Graceful Degradation
            logger.error(f"Error in SimpleVPNDetector: {str(e)}")
            return False, {
                'is_vpn': False,
                'error': str(e),
                'checked_at': timezone.now().isoformat()
            }


# ==================== DECORATOR ====================

def with_vpn_check(timeout: float = 5.0, fallback: bool = True):
    """
    Decorator to add VPN checking to any function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Find IP address in args or kwargs
            ip_address = None
            
            # Check kwargs first using dict.get()
            ip_address = (kwargs.get('ip_address') or 
                         kwargs.get('ip') or 
                         kwargs.get('client_ip'))
            
            # Check args
            if not ip_address:
                for arg in args:
                    if isinstance(arg, str) and ('.' in arg or ':' in arg):
                        try:
                            ipaddress.ip_address(arg)
                            ip_address = arg
                            break
                        except ValueError:
                            continue
            
            if ip_address:
                try:
                    detector = VPNDetector()
                    is_vpn, details = detector.is_vpn(ip_address)
                    
                    # Add VPN info to kwargs
                    kwargs['vpn_info'] = {
                        'is_vpn': is_vpn,
                        'details': details,
                        'checked_at': timezone.now().isoformat()
                    }
                    
                    # Log if VPN detected
                    if is_vpn:
                        logger.warning(f"VPN detected for IP {ip_address} in function {func.__name__}")
                    
                except Exception as e:
                    logger.error(f"VPN check failed in decorator: {str(e)}")
                    if not fallback:
                        raise
                    # Add error info
                    kwargs['vpn_info'] = {
                        'error': str(e),
                        'checked_at': timezone.now().isoformat()
                    }
            
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# ==================== GLOBAL INSTANCE ====================

# Create global instances for easy import
vpn_detector = VPNDetector()
simple_vpn_detector = SimpleVPNDetector()

# Export all components
__all__ = [
    'VPNDetector',
    'SimpleVPNDetector',
    'vpn_detector',
    'simple_vpn_detector',
    'with_vpn_check',  # [OK] Added decorator
    'VPNServiceError',
    'VPNServiceUnavailableError'
]