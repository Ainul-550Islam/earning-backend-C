"""
Geographic Targeting Service

Handles IP to country/city matching for geographic
targeting rules in the offer routing system.
"""

import logging
import requests
import geoip2.database
import geoip2.errors
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from ....models import (
    OfferRoute, GeoRouteRule, RoutingDecisionLog
)
from ....choices import GeoTargetingType
from ....constants import (
    GEO_CACHE_TIMEOUT, GEOIP_DATABASE_PATH,
    MAX_GEO_LOOKUPS_PER_SECOND, GEO_LOOKUP_TIMEOUT
)
from ....exceptions import TargetingError, GeoLocationError
from ....utils import get_geo_location_from_ip, normalize_country_code

User = get_user_model()
logger = logging.getLogger(__name__)


class GeoTargetingService:
    """
    Service for geographic targeting rules.
    
    Provides IP geolocation lookup and matching against
    geographic targeting rules for offer routing.
    
    Performance targets:
    - IP lookup: <50ms (cached), <200ms (uncached)
    - Rule matching: <5ms per rule
    - Cache hit rate: >95%
    """
    
    def __init__(self):
        self.geoip_reader = None
        self.cache_service = cache
        self.lookup_stats = {
            'total_lookups': 0,
            'cache_hits': 0,
            'errors': 0,
            'avg_lookup_time_ms': 0.0
        }
        self.rate_limiter = {
            'lookups': [],
            'window_start': timezone.now()
        }
        
        # Initialize GeoIP database
        self._initialize_geoip_database()
    
    def _initialize_geoip_database(self):
        """Initialize GeoIP database reader."""
        try:
            # Try to load GeoIP database from settings
            geoip_path = getattr(settings, 'GEOIP_DATABASE_PATH', GEOIP_DATABASE_PATH)
            
            if geoip_path and geoip_path.exists():
                self.geoip_reader = geoip2.database.Reader(str(geoip_path))
                logger.info(f"GeoIP database loaded from {geoip_path}")
            else:
                logger.warning("GeoIP database not found, using fallback services")
                
        except Exception as e:
            logger.error(f"Failed to initialize GeoIP database: {e}")
            self.geoip_reader = None
    
    def matches_route(self, route: OfferRoute, user: User, 
                     context: Dict[str, Any]) -> bool:
        """
        Check if route matches user's geographic location.
        
        Args:
            route: Route to check
            user: User object
            context: User context containing IP or location
            
        Returns:
            True if route matches geographically, False otherwise
        """
        try:
            # Get geographic rules for route
            geo_rules = route.geo_rules.filter(is_active=True).order_by('priority')
            
            if not geo_rules:
                return True  # No geo restrictions
            
            # Get user's geographic location
            user_location = self._get_user_location(user, context)
            
            if not user_location:
                logger.warning(f"Could not determine location for user {user.id}")
                return False  # Cannot apply geo targeting without location
            
            # Check each geo rule
            for rule in geo_rules:
                if self._matches_geo_rule(rule, user_location):
                    if rule.is_include:
                        return True  # Include rule matches
                    else:
                        return False  # Exclude rule matches
            
            # If no include rules matched, return False
            return False
            
        except Exception as e:
            logger.error(f"Error checking geo targeting for route {route.id}: {e}")
            return False
    
    def _get_user_location(self, user: User, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get user's geographic location from various sources."""
        try:
            # Priority order: context > user profile > IP lookup
            
            # 1. Check context for explicit location
            if 'location' in context:
                location_data = context['location']
                if self._validate_location_data(location_data):
                    return location_data
            
            # 2. Check user profile for location
            user_location = self._get_user_profile_location(user)
            if user_location:
                return user_location
            
            # 3. IP geolocation lookup
            ip_address = self._get_user_ip_address(user, context)
            if ip_address:
                return self._lookup_ip_location(ip_address)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user location: {e}")
            return None
    
    def _validate_location_data(self, location_data: Dict[str, Any]) -> bool:
        """Validate location data structure."""
        required_fields = ['country']
        optional_fields = ['region', 'city', 'latitude', 'longitude']
        
        # Check required fields
        for field in required_fields:
            if field not in location_data or not location_data[field]:
                return False
        
        # Validate country code
        country = location_data['country']
        if len(country) != 2 or not country.isalpha():
            return False
        
        return True
    
    def _get_user_profile_location(self, user: User) -> Optional[Dict[str, Any]]:
        """Get location from user's profile."""
        try:
            # Check user profile fields
            profile_fields = ['country', 'region', 'city']
            location_data = {}
            
            for field in profile_fields:
                value = getattr(user, field, None)
                if value:
                    location_data[field] = value
            
            if location_data.get('country'):
                # Normalize country code
                location_data['country'] = normalize_country_code(location_data['country'])
                return location_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user profile location: {e}")
            return None
    
    def _get_user_ip_address(self, user: User, context: Dict[str, Any]) -> Optional[str]:
        """Get user's IP address from context or request."""
        try:
            # Check context for IP
            if 'ip_address' in context:
                return context['ip_address']
            
            # Check for request in context
            if 'request' in context:
                request = context['request']
                return self._extract_ip_from_request(request)
            
            # Check user's last known IP
            last_ip = getattr(user, 'last_ip', None)
            if last_ip:
                return last_ip
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user IP address: {e}")
            return None
    
    def _extract_ip_from_request(self, request) -> Optional[str]:
        """Extract IP address from Django request."""
        try:
            # Check various IP headers
            ip_headers = [
                'HTTP_X_FORWARDED_FOR',
                'HTTP_X_REAL_IP',
                'HTTP_X_CLIENT_IP',
                'HTTP_CLIENT_IP',
                'HTTP_X_FORWARDED',
                'HTTP_X_CLUSTER_CLIENT_IP',
                'HTTP_FORWARDED_FOR',
                'HTTP_FORWARDED',
                'REMOTE_ADDR'
            ]
            
            for header in ip_headers:
                ip = request.META.get(header)
                if ip:
                    # Handle multiple IPs (X-Forwarded-For)
                    if ',' in ip:
                        ip = ip.split(',')[0].strip()
                    
                    # Validate IP format
                    if self._is_valid_ip(ip):
                        return ip
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting IP from request: {e}")
            return None
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format."""
        try:
            import ipaddress
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def _lookup_ip_location(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Look up geographic location for IP address."""
        try:
            # Check rate limiting
            if not self._check_rate_limit():
                logger.warning(f"Rate limit exceeded for IP lookups")
                return None
            
            start_time = timezone.now()
            
            # Check cache first
            cache_key = f"geo_location:{ip_address}"
            cached_location = self.cache_service.get(cache_key)
            
            if cached_location:
                self.lookup_stats['cache_hits'] += 1
                return cached_location
            
            # Try GeoIP database first
            location = None
            if self.geoip_reader:
                location = self._lookup_geoip_database(ip_address)
            
            # Fallback to external service
            if not location:
                location = self._lookup_external_service(ip_address)
            
            if location:
                # Cache the result
                self.cache_service.set(cache_key, location, GEO_CACHE_TIMEOUT)
                
                # Update stats
                elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
                self._update_lookup_stats(elapsed_ms)
                
                return location
            
            return None
            
        except Exception as e:
            logger.error(f"Error looking up IP location for {ip_address}: {e}")
            self.lookup_stats['errors'] += 1
            return None
    
    def _lookup_geoip_database(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Look up location using GeoIP database."""
        try:
            if not self.geoip_reader:
                return None
            
            # Try city database first
            response = self.geoip_reader.city(ip_address)
            
            if not response or not response.country:
                return None
            
            # Extract location data
            location_data = {
                'country': response.country.iso_code or '',
                'country_name': response.country.name or '',
                'region': response.subdivisions.most_specific.iso_code or '',
                'region_name': response.subdivisions.most_specific.name or '',
                'city': response.city.name or '',
                'postal_code': response.postal.code or '',
                'latitude': float(response.location.latitude) if response.location.latitude else None,
                'longitude': float(response.location.longitude) if response.location.longitude else None,
                'timezone': response.location.time_zone or '',
                'accuracy': 'city',
                'source': 'geoip_database'
            }
            
            # Filter out empty values
            location_data = {k: v for k, v in location_data.items() if v is not None and v != ''}
            
            return location_data if location_data.get('country') else None
            
        except geoip2.errors.AddressNotFoundError:
            logger.debug(f"IP address {ip_address} not found in GeoIP database")
            return None
        except Exception as e:
            logger.error(f"Error looking up GeoIP database for {ip_address}: {e}")
            return None
    
    def _lookup_external_service(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Look up location using external service."""
        try:
            # Try multiple external services
            services = [
                self._lookup_ipapi_service,
                self._lookup_ipstack_service,
                self._lookup_freegeoip_service
            ]
            
            for service_func in services:
                try:
                    location = service_func(ip_address)
                    if location:
                        location['source'] = service_func.__name__
                        return location
                except Exception as e:
                    logger.debug(f"External service {service_func.__name__} failed: {e}")
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error in external service lookup: {e}")
            return None
    
    def _lookup_ipapi_service(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Look up using ipapi.com service."""
        try:
            url = f"http://ipapi.co/{ip_address}/json/"
            response = requests.get(url, timeout=GEO_LOOKUP_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                
                return {
                    'country': data.get('country_code', ''),
                    'country_name': data.get('country_name', ''),
                    'region': data.get('region', ''),
                    'region_name': data.get('region', ''),
                    'city': data.get('city', ''),
                    'postal_code': data.get('postal', ''),
                    'latitude': data.get('latitude'),
                    'longitude': data.get('longitude'),
                    'timezone': data.get('timezone', ''),
                    'accuracy': 'city',
                    'source': 'ipapi'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in ipapi service lookup: {e}")
            return None
    
    def _lookup_ipstack_service(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Look up using ipstack.com service."""
        try:
            api_key = getattr(settings, 'IPSTACK_API_KEY', None)
            if not api_key:
                return None
            
            url = f"http://api.ipstack.com/{ip_address}?access_key={api_key}"
            response = requests.get(url, timeout=GEO_LOOKUP_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                
                return {
                    'country': data.get('country_code', ''),
                    'country_name': data.get('country_name', ''),
                    'region': data.get('region_code', ''),
                    'region_name': data.get('region_name', ''),
                    'city': data.get('city', ''),
                    'postal_code': data.get('zip', ''),
                    'latitude': data.get('latitude'),
                    'longitude': data.get('longitude'),
                    'timezone': data.get('time_zone', {}).get('id', ''),
                    'accuracy': 'city',
                    'source': 'ipstack'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in ipstack service lookup: {e}")
            return None
    
    def _lookup_freegeoip_service(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Look up using freegeoip.app service."""
        try:
            url = f"https://freegeoip.app/json/{ip_address}"
            response = requests.get(url, timeout=GEO_LOOKUP_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                
                return {
                    'country': data.get('country_code', ''),
                    'country_name': data.get('country_name', ''),
                    'region': data.get('region_code', ''),
                    'region_name': data.get('region_name', ''),
                    'city': data.get('city', ''),
                    'postal_code': data.get('zip_code', ''),
                    'latitude': data.get('latitude'),
                    'longitude': data.get('longitude'),
                    'timezone': data.get('time_zone', ''),
                    'accuracy': 'city',
                    'source': 'freegeoip'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in freegeoip service lookup: {e}")
            return None
    
    def _matches_geo_rule(self, rule: GeoRouteRule, 
                          user_location: Dict[str, Any]) -> bool:
        """Check if user location matches a geographic rule."""
        try:
            # Country matching
            if rule.country:
                if user_location.get('country', '').upper() != rule.country.upper():
                    return False
            
            # Region matching
            if rule.region:
                user_region = user_location.get('region', '').upper()
                rule_region = rule.region.upper()
                if user_region != rule_region:
                    return False
            
            # City matching
            if rule.city:
                user_city = user_location.get('city', '').upper()
                rule_city = rule.city.upper()
                if user_city != rule_city:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error matching geo rule {rule.id}: {e}")
            return False
    
    def _check_rate_limit(self) -> bool:
        """Check if IP lookup rate limit is exceeded."""
        try:
            current_time = timezone.now()
            window_start = self.rate_limiter['window_start']
            
            # Reset window if needed
            if (current_time - window_start).seconds >= 60:
                self.rate_limiter['lookups'] = []
                self.rate_limiter['window_start'] = current_time
                return True
            
            # Check current lookups
            if len(self.rate_limiter['lookups']) >= MAX_GEO_LOOKUPS_PER_SECOND:
                return False
            
            # Add current lookup
            self.rate_limiter['lookups'].append(current_time)
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True  # Allow lookup on error
    
    def _update_lookup_stats(self, elapsed_ms: float):
        """Update lookup performance statistics."""
        self.lookup_stats['total_lookups'] += 1
        
        # Update average time
        current_avg = self.lookup_stats['avg_lookup_time_ms']
        total_lookups = self.lookup_stats['total_lookups']
        self.lookup_stats['avg_lookup_time_ms'] = (
            (current_avg * (total_lookups - 1) + elapsed_ms) / total_lookups
        )
    
    def get_location_by_ip(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """
        Public method to get location by IP address.
        
        Args:
            ip_address: IP address to look up
            
        Returns:
            Location data or None if not found
        """
        return self._lookup_ip_location(ip_address)
    
    def validate_geo_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate geographic rule data.
        
        Args:
            rule_data: Rule data to validate
            
        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []
        
        # Validate country code
        if rule_data.get('country'):
            country = rule_data['country']
            if len(country) != 2 or not country.isalpha():
                errors.append("Country code must be 2-letter ISO code")
            else:
                # Check if country code is valid
                normalized = normalize_country_code(country)
                if normalized != country.upper():
                    warnings.append(f"Country code normalized from {country} to {normalized}")
        
        # Validate region
        if rule_data.get('region'):
            region = rule_data['region']
            if len(region) > 100:
                errors.append("Region name cannot exceed 100 characters")
        
        # Validate city
        if rule_data.get('city'):
            city = rule_data['city']
            if len(city) > 100:
                errors.append("City name cannot exceed 100 characters")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def get_geo_targeting_stats(self) -> Dict[str, Any]:
        """Get geographic targeting performance statistics."""
        total_requests = self.lookup_stats['total_lookups']
        cache_hit_rate = (
            self.lookup_stats['cache_hits'] / max(1, total_requests)
        )
        
        return {
            'total_lookups': total_requests,
            'cache_hits': self.lookup_stats['cache_hits'],
            'cache_misses': total_requests - self.lookup_stats['cache_hits'],
            'cache_hit_rate': cache_hit_rate,
            'errors': self.lookup_stats['errors'],
            'error_rate': self.lookup_stats['errors'] / max(1, total_requests),
            'avg_lookup_time_ms': self.lookup_stats['avg_lookup_time_ms'],
            'geoip_database_loaded': self.geoip_reader is not None,
            'rate_limit_window': len(self.rate_limiter['lookups']),
            'rate_limit_max': MAX_GEO_LOOKUPS_PER_SECOND
        }
    
    def clear_cache(self, ip_address: str = None):
        """Clear cached location data."""
        try:
            if ip_address:
                # Clear specific IP cache
                cache_key = f"geo_location:{ip_address}"
                self.cache_service.delete(cache_key)
                logger.info(f"Cleared cache for IP {ip_address}")
            else:
                # Clear all geo location cache
                # This would need pattern deletion support
                logger.info("Cache clearing for specific IPs not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing geo cache: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on geo targeting service."""
        try:
            # Test IP lookup with a known IP
            test_ip = "8.8.8.8"  # Google DNS
            test_location = self.get_location_by_ip(test_ip)
            
            # Test rule matching
            test_rule = type('MockGeoRule', (), {
                'country': 'US',
                'region': '',
                'city': '',
                'is_include': True
            })()
            
            test_user_location = {'country': 'US', 'region': 'CA', 'city': 'Mountain View'}
            rule_matches = self._matches_geo_rule(test_rule, test_user_location)
            
            return {
                'status': 'healthy',
                'test_ip_lookup': test_location is not None,
                'test_rule_matching': rule_matches,
                'geoip_database_loaded': self.geoip_reader is not None,
                'stats': self.get_geo_targeting_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
