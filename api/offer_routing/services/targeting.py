"""
Targeting Service for Offer Routing System

This module provides targeting functionality to determine
which users should see which offers based on various criteria.
"""

import logging
from typing import Dict, List, Any, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..models import (
    OfferRoute, GeoRouteRule, DeviceRouteRule, UserSegmentRule,
    TimeRouteRule, BehaviorRouteRule
)
from ..utils import extract_device_info, get_geo_location_from_ip
from ..exceptions import TargetingError

User = get_user_model()
logger = logging.getLogger(__name__)


class TargetingService:
    """
    Service for evaluating targeting rules and determining
    which routes match a user's profile and context.
    """
    
    def __init__(self):
        self.geo_targeting = GeoTargetingService()
        self.device_targeting = DeviceTargetingService()
        self.segment_targeting = SegmentTargetingService()
        self.time_targeting = TimeTargetingService()
        self.behavior_targeting = BehaviorTargetingService()
    
    def matches_route(self, route: OfferRoute, user: User, 
                     user_segment: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Check if a route matches the user and context.
        
        Args:
            route: Route to check
            user: User object
            user_segment: User segment information
            context: User context (device, location, etc.)
            
        Returns:
            True if route matches, False otherwise
        """
        try:
            # Check each type of targeting rule
            geo_match = self.geo_targeting.matches_route(route, user, context)
            device_match = self.device_targeting.matches_route(route, user, context)
            segment_match = self.segment_targeting.matches_route(route, user, user_segment)
            time_match = self.time_targeting.matches_route(route, user, context)
            behavior_match = self.behavior_targeting.matches_route(route, user, context)
            
            # Route matches if ANY targeting rule matches (OR logic)
            # This could be changed to ALL (AND logic) based on business requirements
            matches = any([geo_match, device_match, segment_match, time_match, behavior_match])
            
            logger.debug(f"Route {route.id} match check: geo={geo_match}, device={device_match}, "
                        f"segment={segment_match}, time={time_match}, behavior={behavior_match}")
            
            return matches
            
        except Exception as e:
            logger.error(f"Error checking route match: {e}")
            return False
    
    def get_matching_rules(self, route: OfferRoute, user: User, 
                          user_segment: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, List]:
        """
        Get all matching targeting rules for a route.
        
        Returns:
            Dictionary with rule types as keys and matching rules as values
        """
        try:
            matching_rules = {
                'geo': self.geo_targeting.get_matching_rules(route, user, context),
                'device': self.device_targeting.get_matching_rules(route, user, context),
                'segment': self.segment_targeting.get_matching_rules(route, user, user_segment),
                'time': self.time_targeting.get_matching_rules(route, user, context),
                'behavior': self.behavior_targeting.get_matching_rules(route, user, context)
            }
            
            return matching_rules
            
        except Exception as e:
            logger.error(f"Error getting matching rules: {e}")
            return {}
    
    def evaluate_user_for_routes(self, user: User, routes: List[OfferRoute], 
                                context: Dict[str, Any]) -> List[OfferRoute]:
        """
        Evaluate which routes match a user.
        
        Args:
            user: User object
            routes: List of routes to evaluate
            context: User context
            
        Returns:
            List of matching routes
        """
        try:
            user_segment = get_user_segment_info(user.id)
            matching_routes = []
            
            for route in routes:
                if self.matches_route(route, user, user_segment, context):
                    matching_routes.append(route)
            
            logger.info(f"User {user.id} matches {len(matching_routes)} out of {len(routes)} routes")
            return matching_routes
            
        except Exception as e:
            logger.error(f"Error evaluating user for routes: {e}")
            return []


class GeoTargetingService:
    """Service for geographic targeting rules."""
    
    def matches_route(self, route: OfferRoute, user: User, context: Dict[str, Any]) -> bool:
        """Check if user matches geographic targeting rules."""
        try:
            geo_rules = route.geo_rules.filter(is_active=True)
            
            if not geo_rules.exists():
                return True  # No geo rules means all users match
            
            # Get user location from context or IP
            user_location = self._get_user_location(user, context)
            
            for rule in geo_rules:
                if self._matches_geo_rule(rule, user_location):
                    return rule.is_include
            
            return False  # No matching rules
            
        except Exception as e:
            logger.error(f"Error in geo targeting: {e}")
            return False
    
    def get_matching_rules(self, route: OfferRoute, user: User, context: Dict[str, Any]) -> List[GeoRouteRule]:
        """Get matching geographic rules."""
        try:
            geo_rules = route.geo_rules.filter(is_active=True)
            user_location = self._get_user_location(user, context)
            
            matching_rules = []
            
            for rule in geo_rules:
                if self._matches_geo_rule(rule, user_location):
                    matching_rules.append(rule)
            
            return matching_rules
            
        except Exception as e:
            logger.error(f"Error getting matching geo rules: {e}")
            return []
    
    def _get_user_location(self, user: User, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get user location from context or IP with spoofing protection."""
        location = {}
        
        # First, get validated IP address
        validated_ip = self._get_validated_ip_address(context)
        
        if not validated_ip:
            logger.warning(f"No valid IP address found for user {user.id}")
            return {}
        
        # Get geo location from validated IP
        geo_data = get_geo_location_from_ip(validated_ip)
        if geo_data:
            location = geo_data
            
            # Cross-validate with context location if provided
            if 'location' in context:
                context_location = context['location']
                if 'country' in context_location and 'country' in location:
                    if context_location['country'].upper() != location['country'].upper():
                        logger.warning(f"Location spoofing detected for user {user.id}: "
                                     f"Context={context_location['country']}, IP={location['country']}")
                        # Use IP-based location as it's more reliable
                        location['spoofing_detected'] = True
                        location['context_country'] = context_location['country']
                        location['ip_country'] = location['country']
        
        return location
    
    def _get_validated_ip_address(self, context: Dict[str, Any]) -> Optional[str]:
        """Get validated IP address with proxy chain validation."""
        ip_address = None
        
        # Check for IP in context
        if 'ip_address' in context:
            ip_address = context['ip_address']
        
        # Check for HTTP headers (with spoofing protection)
        if not ip_address and hasattr(self, 'request'):
            request_headers = getattr(self.request, 'META', {})
            
            # List of headers to check in order of preference
            ip_headers = [
                'HTTP_X_FORWARDED_FOR',
                'HTTP_X_REAL_IP',
                'HTTP_X_CLIENT_IP',
                'HTTP_CLIENT_IP',
                'HTTP_X_FORWARDED',
                'HTTP_FORWARDED_FOR',
                'HTTP_FORWARDED',
                'HTTP_VIA',
                'REMOTE_ADDR'
            ]
            
            for header in ip_headers:
                if header in request_headers:
                    ip_list = request_headers[header].split(',')
                    # Take the first IP in the list
                    candidate_ip = ip_list[0].strip()
                    
                    # Validate this IP against trusted proxies
                    if self._is_valid_ip(candidate_ip):
                        ip_address = candidate_ip
                        break
        
        # Final validation
        if ip_address and self._is_valid_ip(ip_address):
            return ip_address
        
        return None
    
    def _is_valid_ip(self, ip_address: str) -> bool:
        """Validate IP address and check against trusted proxies."""
        import ipaddress
        import re
        
        try:
            # Basic IP format validation
            ip = ipaddress.ip_address(ip_address.strip())
            
            # Check for private/reserved IPs
            if ip.is_private or ip.is_loopback or ip.is_reserved:
                return False
            
            # Check for common proxy/VPN IP ranges (simplified)
            proxy_ranges = [
                '10.0.0.0/8',     # Private
                '172.16.0.0/12',  # Private
                '192.168.0.0/16', # Private
                '127.0.0.0/8',    # Loopback
                '169.254.0.0/16', # Link-local
                '224.0.0.0/4',    # Multicast
                '240.0.0.0/4',    # Reserved
            ]
            
            for range_str in proxy_ranges:
                if ip in ipaddress.ip_network(range_str):
                    return False
            
            # Additional validation: check for suspicious patterns
            if re.match(r'^(0\.|255\.|127\.|169\.254\.|192\.168\.|10\.)', ip_address):
                return False
            
            return True
            
        except (ValueError, AttributeError):
            return False
    
    def _detect_proxy_chain(self, ip_address: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Detect and analyze proxy chain for additional security."""
        proxy_info = {
            'has_proxy': False,
            'proxy_count': 0,
            'trusted_proxy': False,
            'suspicious': False
        }
        
        if hasattr(self, 'request'):
            request_headers = getattr(self.request, 'META', {})
            
            # Check for X-Forwarded-For header
            if 'HTTP_X_FORWARDED_FOR' in request_headers:
                forwarded_for = request_headers['HTTP_X_FORWARDED_FOR']
                ip_list = [ip.strip() for ip in forwarded_for.split(',')]
                proxy_info['proxy_count'] = len(ip_list) - 1
                proxy_info['has_proxy'] = proxy_info['proxy_count'] > 0
                
                # Check if the originating IP is in the list
                if ip_address in ip_list:
                    proxy_info['trusted_proxy'] = True
                
                # Check for suspicious proxy patterns
                if proxy_info['proxy_count'] > 5:
                    proxy_info['suspicious'] = True
                    logger.warning(f"Suspicious proxy chain detected: {len(ip_list)} IPs")
        
        return proxy_info
    
    def _matches_geo_rule(self, rule: GeoRouteRule, user_location: Dict[str, Any]) -> bool:
        """Check if user location matches a geographic rule."""
        if not user_location:
            return False
        
        # Check country match
        if rule.country:
            user_country = user_location.get('country', '').upper()
            if user_country != rule.country.upper():
                return False
        
        # Check region match
        if rule.region:
            user_region = user_location.get('region', '').upper()
            if user_region != rule.region.upper():
                return False
        
        # Check city match
        if rule.city:
            user_city = user_location.get('city', '').upper()
            if user_city != rule.city.upper():
                return False
        
        return True


class DeviceTargetingService:
    """Service for device-based targeting rules."""
    
    def matches_route(self, route: OfferRoute, user: User, context: Dict[str, Any]) -> bool:
        """Check if user matches device targeting rules."""
        try:
            device_rules = route.device_rules.filter(is_active=True)
            
            if not device_rules.exists():
                return True  # No device rules means all users match
            
            # Get user device info from context
            user_device = self._get_user_device_info(user, context)
            
            for rule in device_rules:
                if self._matches_device_rule(rule, user_device):
                    return rule.is_include
            
            return False  # No matching rules
            
        except Exception as e:
            logger.error(f"Error in device targeting: {e}")
            return False
    
    def get_matching_rules(self, route: OfferRoute, user: User, context: Dict[str, Any]) -> List[DeviceRouteRule]:
        """Get matching device rules."""
        try:
            device_rules = route.device_rules.filter(is_active=True)
            user_device = self._get_user_device_info(user, context)
            
            matching_rules = []
            
            for rule in device_rules:
                if self._matches_device_rule(rule, user_device):
                    matching_rules.append(rule)
            
            return matching_rules
            
        except Exception as e:
            logger.error(f"Error getting matching device rules: {e}")
            return []
    
    def _get_user_device_info(self, user: User, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get user device info from context."""
        device_info = {}
        
        # Try to get device info from context
        if 'device_info' in context:
            device_info = context['device_info']
        elif 'user_agent' in context:
            # Extract device info from user agent
            device_info = extract_device_info(context['user_agent'])
        
        return device_info
    
    def _matches_device_rule(self, rule: DeviceRouteRule, user_device: Dict[str, Any]) -> bool:
        """Check if user device matches a device rule."""
        if not user_device:
            return False
        
        # Check device type match
        if rule.device_type:
            user_device_type = user_device.get('device_type', '').lower()
            if user_device_type != rule.device_type.lower():
                return False
        
        # Check OS type match
        if rule.os_type:
            user_os = user_device.get('os', '').lower()
            if user_os != rule.os_type.lower():
                return False
        
        # Check browser match
        if rule.browser:
            user_browser = user_device.get('browser', '').lower()
            if user_browser != rule.browser.lower():
                return False
        
        return True


class SegmentTargetingService:
    """Service for user segment targeting rules."""
    
    def matches_route(self, route: OfferRoute, user: User, user_segment: Dict[str, Any]) -> bool:
        """Check if user matches segment targeting rules."""
        try:
            segment_rules = route.segment_rules.filter(is_active=True)
            
            if not segment_rules.exists():
                return True  # No segment rules means all users match
            
            for rule in segment_rules:
                if self._matches_segment_rule(rule, user, user_segment):
                    return True  # Segment rules are always inclusion
            
            return False  # No matching rules
            
        except Exception as e:
            logger.error(f"Error in segment targeting: {e}")
            return False
    
    def get_matching_rules(self, route: OfferRoute, user: User, user_segment: Dict[str, Any]) -> List[UserSegmentRule]:
        """Get matching segment rules."""
        try:
            segment_rules = route.segment_rules.filter(is_active=True)
            
            matching_rules = []
            
            for rule in segment_rules:
                if self._matches_segment_rule(rule, user, user_segment):
                    matching_rules.append(rule)
            
            return matching_rules
            
        except Exception as e:
            logger.error(f"Error getting matching segment rules: {e}")
            return []
    
    def _matches_segment_rule(self, rule: UserSegmentRule, user: User, user_segment: Dict[str, Any]) -> bool:
        """Check if user matches a segment rule."""
        try:
            # Get user segment value
            user_value = self._get_user_segment_value(user, rule.segment_type, user_segment)
            
            if user_value is None:
                return False
            
            # Apply operator
            if rule.operator == 'equals':
                return str(user_value).lower() == rule.value.lower()
            elif rule.operator == 'not_equals':
                return str(user_value).lower() != rule.value.lower()
            elif rule.operator == 'in':
                return str(user_value).lower() in [v.strip().lower() for v in rule.value.split(',')]
            elif rule.operator == 'not_in':
                return str(user_value).lower() not in [v.strip().lower() for v in rule.value.split(',')]
            elif rule.operator == 'contains':
                return rule.value.lower() in str(user_value).lower()
            elif rule.operator == 'not_contains':
                return rule.value.lower() not in str(user_value).lower()
            
            return False
            
        except Exception as e:
            logger.error(f"Error matching segment rule: {e}")
            return False
    
    def _get_user_segment_value(self, user: User, segment_type: str, user_segment: Dict[str, Any]) -> Any:
        """Get user segment value for a specific segment type."""
        if segment_type == 'tier':
            return user_segment.get('tier', 'basic')
        elif segment_type == 'new_user':
            return user_segment.get('is_new_user', False)
        elif segment_type == 'active_user':
            return user_segment.get('is_active_user', False)
        elif segment_type == 'premium_user':
            return user_segment.get('is_premium_user', False)
        elif segment_type == 'churned_user':
            return user_segment.get('is_churned_user', False)
        elif segment_type == 'engaged_user':
            return user_segment.get('is_engaged_user', False)
        elif segment_type == 'inactive_user':
            return user_segment.get('is_inactive_user', False)
        
        return None
    
    def update_user_segments(self) -> int:
        """Update user segment assignments."""
        try:
            updated_count = 0
            
            # This would implement segment update logic
            # For now, return placeholder
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating user segments: {e}")
            return 0


class TimeTargetingService:
    """Service for time-based targeting rules."""
    
    def matches_route(self, route: OfferRoute, user: User, context: Dict[str, Any]) -> bool:
        """Check if user matches time-based targeting rules."""
        try:
            time_rules = route.time_rules.filter(is_active=True)
            
            if not time_rules.exists():
                return True  # No time rules means all users match
            
            current_time = timezone.now()
            current_hour = current_time.hour
            current_day_of_week = current_time.weekday()  # 0=Monday, 6=Sunday
            
            for rule in time_rules:
                if rule.matches_time(current_hour, current_day_of_week):
                    return True  # Time rules are always inclusion
            
            return False  # No matching rules
            
        except Exception as e:
            logger.error(f"Error in time targeting: {e}")
            return False
    
    def get_matching_rules(self, route: OfferRoute, user: User, context: Dict[str, Any]) -> List[TimeRouteRule]:
        """Get matching time rules."""
        try:
            time_rules = route.time_rules.filter(is_active=True)
            
            current_time = timezone.now()
            current_hour = current_time.hour
            current_day_of_week = current_time.weekday()
            
            matching_rules = []
            
            for rule in time_rules:
                if rule.matches_time(current_hour, current_day_of_week):
                    matching_rules.append(rule)
            
            return matching_rules
            
        except Exception as e:
            logger.error(f"Error getting matching time rules: {e}")
            return []
    
    def update_time_rules(self) -> int:
        """Update time-based targeting rules."""
        try:
            updated_count = 0
            
            # This would implement time rule update logic
            # For now, return placeholder
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating time rules: {e}")
            return 0


class BehaviorTargetingService:
    """Service for behavioral targeting rules."""
    
    def matches_route(self, route: OfferRoute, user: User, context: Dict[str, Any]) -> bool:
        """Check if user matches behavioral targeting rules."""
        try:
            behavior_rules = route.behavior_rules.filter(is_active=True)
            
            if not behavior_rules.exists():
                return True  # No behavior rules means all users match
            
            # Get user behavioral data
            user_events = self._get_user_events(user)
            
            for rule in behavior_rules:
                if rule.matches_behavior(user_events):
                    return True  # Behavior rules are always inclusion
            
            return False  # No matching rules
            
        except Exception as e:
            logger.error(f"Error in behavior targeting: {e}")
            return False
    
    def get_matching_rules(self, route: OfferRoute, user: User, context: Dict[str, Any]) -> List[BehaviorRouteRule]:
        """Get matching behavioral rules."""
        try:
            behavior_rules = route.behavior_rules.filter(is_active=True)
            user_events = self._get_user_events(user)
            
            matching_rules = []
            
            for rule in behavior_rules:
                if rule.matches_behavior(user_events):
                    matching_rules.append(rule)
            
            return matching_rules
            
        except Exception as e:
            logger.error(f"Error getting matching behavior rules: {e}")
            return []
    
    def _get_user_events(self, user: User) -> List[Dict[str, Any]]:
        """Get user behavioral events."""
        try:
            # This would query user events from analytics
            # For now, return empty list
            return []
            
        except Exception as e:
            logger.error(f"Error getting user events: {e}")
            return []
    
    def update_behavioral_rules(self) -> int:
        """Update behavioral targeting rules."""
        try:
            updated_count = 0
            
            # This would implement behavioral rule update logic
            # For now, return placeholder
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating behavioral rules: {e}")
            return 0


# Singleton instances
targeting_service = TargetingService()
geo_targeting_service = GeoTargetingService()
device_targeting_service = DeviceTargetingService()
segment_targeting_service = SegmentTargetingService()
time_targeting_service = TimeTargetingService()
behavior_targeting_service = BehaviorTargetingService()
