"""
Time Targeting Service

Handles time window matching for time-based targeting
rules in offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, time as dt_time, timedelta
import pytz
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from ....models import (
    OfferRoute, TimeRouteRule, RoutingDecisionLog
)
from ....constants import (
    TIME_CACHE_TIMEOUT, TIMEZONE_CACHE_TIMEOUT,
    MAX_TIME_LOOKUPS_PER_SECOND, TIME_PARSE_TIMEOUT
)
from ....exceptions import TargetingError, TimeParsingError
from ....utils import get_user_timezone, parse_time_string

User = get_user_model()
logger = logging.getLogger(__name__)


class TimeTargetingService:
    """
    Service for time-based targeting rules.
    
    Provides time window matching and timezone handling
    for time-based targeting rules in offer routing.
    
    Performance targets:
    - Time parsing: <2ms (cached), <10ms (uncached)
    - Rule matching: <1ms per rule
    - Cache hit rate: >95%
    """
    
    def __init__(self):
        self.cache_service = cache
        self.time_stats = {
            'total_matches': 0,
            'cache_hits': 0,
            'errors': 0,
            'avg_match_time_ms': 0.0
        }
        self.rate_limiter = {
            'matches': [],
            'window_start': timezone.now()
        }
        
        # Timezone cache for performance
        self.timezone_cache = {}
        
        # Common timezone mappings
        self._initialize_timezone_mappings()
    
    def _initialize_timezone_mappings(self):
        """Initialize common timezone mappings and aliases."""
        self.timezone_aliases = {
            # US timezones
            'EST': 'America/New_York',
            'EDT': 'America/New_York',
            'CST': 'America/Chicago',
            'CDT': 'America/Chicago',
            'MST': 'America/Denver',
            'MDT': 'America/Denver',
            'PST': 'America/Los_Angeles',
            'PDT': 'America/Los_Angeles',
            
            # European timezones
            'GMT': 'Europe/London',
            'BST': 'Europe/London',
            'CET': 'Europe/Paris',
            'CEST': 'Europe/Paris',
            
            # Asian timezones
            'JST': 'Asia/Tokyo',
            'KST': 'Asia/Seoul',
            'CST_CHINA': 'Asia/Shanghai',
            
            # Australian timezones
            'AEST': 'Australia/Sydney',
            'AEDT': 'Australia/Sydney'
        }
        
        self.common_timezones = [
            'America/New_York',
            'America/Chicago',
            'America/Denver',
            'America/Los_Angeles',
            'Europe/London',
            'Europe/Paris',
            'Asia/Tokyo',
            'Asia/Shanghai',
            'Australia/Sydney',
            'UTC'
        ]
    
    def matches_route(self, route: OfferRoute, user: User, 
                     context: Dict[str, Any]) -> bool:
        """
        Check if route matches current time window.
        
        Args:
            route: Route to check
            user: User object
            context: User context containing timezone info
            
        Returns:
            True if route matches time-wise, False otherwise
        """
        try:
            # Get time rules for route
            time_rules = route.time_rules.filter(is_active=True).order_by('priority')
            
            if not time_rules:
                return True  # No time restrictions
            
            # Get current time in appropriate timezone
            current_time_info = self._get_current_time_info(user, context)
            
            if not current_time_info:
                logger.warning(f"Could not determine time for user {user.id}")
                return False  # Cannot apply time targeting without time info
            
            # Check each time rule
            for rule in time_rules:
                if self._matches_time_rule(rule, current_time_info):
                    return True  # Time rule matches
            
            # If no rules matched, return False
            return False
            
        except Exception as e:
            logger.error(f"Error checking time targeting for route {route.id}: {e}")
            return False
    
    def _get_current_time_info(self, user: User, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get current time information for user."""
        try:
            # Priority order: context > user profile > detection > default
            
            # 1. Check context for explicit timezone
            if 'timezone' in context:
                timezone_str = context['timezone']
                user_timezone = self._parse_timezone(timezone_str)
                if user_timezone:
                    return self._get_time_in_timezone(user_timezone)
            
            # 2. Check user profile for timezone
            user_timezone = self._get_user_timezone(user)
            if user_timezone:
                return self._get_time_in_timezone(user_timezone)
            
            # 3. Detect timezone from IP/location
            detected_timezone = self._detect_timezone_from_context(context)
            if detected_timezone:
                return self._get_time_in_timezone(detected_timezone)
            
            # 4. Default to UTC
            return self._get_time_in_timezone('UTC')
            
        except Exception as e:
            logger.error(f"Error getting current time info: {e}")
            return None
    
    def _parse_timezone(self, timezone_str: str) -> Optional[str]:
        """Parse and validate timezone string."""
        try:
            if not timezone_str:
                return None
            
            # Check aliases first
            normalized_tz = timezone_str.strip().upper()
            if normalized_tz in self.timezone_aliases:
                return self.timezone_aliases[normalized_tz]
            
            # Try to validate as timezone
            try:
                pytz.timezone(timezone_str)
                return timezone_str
            except pytz.UnknownTimeZoneError:
                pass
            
            # Try common variations
            variations = [
                timezone_str,
                timezone_str.replace(' ', '_'),
                timezone_str.replace('-', '/'),
                timezone_str.replace('_', '/')
            ]
            
            for variation in variations:
                try:
                    pytz.timezone(variation)
                    return variation
                except pytz.UnknownTimeZoneError:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing timezone {timezone_str}: {e}")
            return None
    
    def _get_user_timezone(self, user: User) -> Optional[str]:
        """Get timezone from user's profile."""
        try:
            # Check user profile fields
            profile_fields = ['timezone', 'preferred_timezone', 'time_zone']
            
            for field in profile_fields:
                timezone_value = getattr(user, field, None)
                if timezone_value:
                    parsed_tz = self._parse_timezone(timezone_value)
                    if parsed_tz:
                        return parsed_tz
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user timezone: {e}")
            return None
    
    def _detect_timezone_from_context(self, context: Dict[str, Any]) -> Optional[str]:
        """Detect timezone from context (IP, location, etc.)."""
        try:
            # Check location data for timezone
            if 'location' in context:
                location = context['location']
                if 'timezone' in location:
                    return self._parse_timezone(location['timezone'])
                
                # Try to infer timezone from country/city
                if 'country' in location:
                    country = location['country']
                    inferred_tz = self._infer_timezone_from_country(country)
                    if inferred_tz:
                        return inferred_tz
            
            # Check IP-based timezone detection
            if 'ip_address' in context:
                ip_address = context['ip_address']
                ip_timezone = self._get_timezone_from_ip(ip_address)
                if ip_timezone:
                    return ip_timezone
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting timezone from context: {e}")
            return None
    
    def _infer_timezone_from_country(self, country: str) -> Optional[str]:
        """Infer timezone from country code."""
        try:
            # Common timezone mappings by country
            country_timezones = {
                'US': 'America/New_York',
                'CA': 'America/Toronto',
                'GB': 'Europe/London',
                'DE': 'Europe/Berlin',
                'FR': 'Europe/Paris',
                'IT': 'Europe/Rome',
                'ES': 'Europe/Madrid',
                'NL': 'Europe/Amsterdam',
                'BE': 'Europe/Brussels',
                'CH': 'Europe/Zurich',
                'AT': 'Europe/Vienna',
                'SE': 'Europe/Stockholm',
                'NO': 'Europe/Oslo',
                'DK': 'Europe/Copenhagen',
                'FI': 'Europe/Helsinki',
                'PL': 'Europe/Warsaw',
                'CZ': 'Europe/Prague',
                'HU': 'Europe/Budapest',
                'RO': 'Europe/Bucharest',
                'BG': 'Europe/Sofia',
                'GR': 'Europe/Athens',
                'TR': 'Europe/Istanbul',
                'RU': 'Europe/Moscow',
                'UA': 'Europe/Kiev',
                'IL': 'Asia/Jerusalem',
                'AE': 'Asia/Dubai',
                'SA': 'Asia/Riyadh',
                'IN': 'Asia/Kolkata',
                'PK': 'Asia/Karachi',
                'BD': 'Asia/Dhaka',
                'TH': 'Asia/Bangkok',
                'SG': 'Asia/Singapore',
                'MY': 'Asia/Kuala_Lumpur',
                'ID': 'Asia/Jakarta',
                'PH': 'Asia/Manila',
                'VN': 'Asia/Ho_Chi_Minh',
                'CN': 'Asia/Shanghai',
                'HK': 'Asia/Hong_Kong',
                'TW': 'Asia/Taipei',
                'JP': 'Asia/Tokyo',
                'KR': 'Asia/Seoul',
                'AU': 'Australia/Sydney',
                'NZ': 'Pacific/Auckland',
                'BR': 'America/Sao_Paulo',
                'AR': 'America/Argentina/Buenos_Aires',
                'CL': 'America/Santiago',
                'PE': 'America/Lima',
                'CO': 'America/Bogota',
                'MX': 'America/Mexico_City',
                'ZA': 'Africa/Johannesburg',
                'EG': 'Africa/Cairo',
                'KE': 'Africa/Nairobi',
                'NG': 'Africa/Lagos'
            }
            
            return country_timezones.get(country.upper())
            
        except Exception as e:
            logger.error(f"Error inferring timezone from country {country}: {e}")
            return None
    
    def _get_timezone_from_ip(self, ip_address: str) -> Optional[str]:
        """Get timezone from IP address using external services."""
        try:
            # This would use an IP geolocation service that provides timezone info
            # For now, return None as this requires external API integration
            return None
            
        except Exception as e:
            logger.error(f"Error getting timezone from IP {ip_address}: {e}")
            return None
    
    def _get_time_in_timezone(self, timezone_str: str) -> Dict[str, Any]:
        """Get current time information in specified timezone."""
        try:
            # Check cache first
            cache_key = f"time_info:{timezone_str}"
            cached_time_info = self.cache_service.get(cache_key)
            
            if cached_time_info:
                self.time_stats['cache_hits'] += 1
                return cached_time_info
            
            start_time = timezone.now()
            
            # Get timezone object
            try:
                tz = pytz.timezone(timezone_str)
            except pytz.UnknownTimeZoneError:
                logger.warning(f"Unknown timezone: {timezone_str}")
                tz = pytz.UTC
            
            # Get current time in timezone
            utc_now = timezone.now()
            local_time = utc_now.astimezone(tz)
            
            time_info = {
                'timezone': timezone_str,
                'timezone_obj': tz,
                'utc_time': utc_now,
                'local_time': local_time,
                'hour': local_time.hour,
                'minute': local_time.minute,
                'day_of_week': local_time.weekday(),  # 0=Monday, 6=Sunday
                'day_of_week_name': local_time.strftime('%A'),
                'day_of_month': local_time.day,
                'month': local_time.month,
                'year': local_time.year,
                'is_weekend': local_time.weekday() >= 5,  # Saturday=5, Sunday=6
                'is_business_hours': 9 <= local_time.hour <= 17,  # 9am-5pm
                'formatted_time': local_time.strftime('%H:%M:%S'),
                'formatted_date': local_time.strftime('%Y-%m-%d'),
                'formatted_datetime': local_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'offset_hours': local_time.utcoffset().total_seconds() / 3600,
                'offset_minutes': (local_time.utcoffset().total_seconds() % 3600) / 60,
                'dst_active': local_time.dst() is not None and local_time.dst().total_seconds() > 0,
                'cached_at': timezone.now().isoformat()
            }
            
            # Cache result
            self.cache_service.set(cache_key, time_info, TIME_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_time_stats(elapsed_ms)
            
            return time_info
            
        except Exception as e:
            logger.error(f"Error getting time in timezone {timezone_str}: {e}")
            return None
    
    def _matches_time_rule(self, rule: TimeRouteRule, 
                           current_time_info: Dict[str, Any]) -> bool:
        """Check if current time matches a time rule."""
        try:
            # Check day of week
            if rule.day_of_week:
                if not self._matches_day_of_week(rule.day_of_week, current_time_info['day_of_week']):
                    return False
            
            # Check hour range
            if rule.hour_from is not None and rule.hour_to is not None:
                if not self._matches_hour_range(
                    rule.hour_from, rule.hour_to, current_time_info['hour']
                ):
                    return False
            
            # Check timezone (if specified)
            if rule.timezone and rule.timezone != 'UTC':
                rule_tz = self._parse_timezone(rule.timezone)
                if rule_tz and rule_tz != current_time_info['timezone']:
                    # Get time in rule's timezone
                    rule_time_info = self._get_time_in_timezone(rule_tz)
                    if not rule_time_info:
                        return False
                    
                    # Check if time matches in rule's timezone
                    if not self._matches_hour_range(
                        rule.hour_from, rule.hour_to, rule_time_info['hour']
                    ):
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error matching time rule {rule.id}: {e}")
            return False
    
    def _matches_day_of_week(self, rule_days: Any, current_day: int) -> bool:
        """Check if current day matches rule's day of week."""
        try:
            # Handle different input formats
            if isinstance(rule_days, list):
                return current_day in rule_days
            elif isinstance(rule_days, str):
                # Try to parse as JSON
                try:
                    import json
                    days_list = json.loads(rule_days)
                    return current_day in days_list
                except json.JSONDecodeError:
                    # Try as comma-separated string
                    days_list = [int(d.strip()) for d in rule_days.split(',') if d.strip().isdigit()]
                    return current_day in days_list
            elif isinstance(rule_days, int):
                return current_day == rule_days
            
            return False
            
        except Exception as e:
            logger.error(f"Error matching day of week: {e}")
            return False
    
    def _matches_hour_range(self, hour_from: int, hour_to: int, current_hour: int) -> bool:
        """Check if current hour matches rule's hour range."""
        try:
            if hour_from <= hour_to:
                # Normal range (e.g., 9-17)
                return hour_from <= current_hour <= hour_to
            else:
                # Overnight range (e.g., 22-6)
                return current_hour >= hour_from or current_hour <= hour_to
                
        except Exception as e:
            logger.error(f"Error matching hour range: {e}")
            return False
    
    def _check_rate_limit(self) -> bool:
        """Check if time matching rate limit is exceeded."""
        try:
            current_time = timezone.now()
            window_start = self.rate_limiter['window_start']
            
            # Reset window if needed
            if (current_time - window_start).seconds >= 60:
                self.rate_limiter['matches'] = []
                self.rate_limiter['window_start'] = current_time
                return True
            
            # Check current matches
            if len(self.rate_limiter['matches']) >= MAX_TIME_LOOKUPS_PER_SECOND:
                return False
            
            # Add current match
            self.rate_limiter['matches'].append(current_time)
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True  # Allow matching on error
    
    def _update_time_stats(self, elapsed_ms: float):
        """Update time matching performance statistics."""
        self.time_stats['total_matches'] += 1
        
        # Update average time
        current_avg = self.time_stats['avg_match_time_ms']
        total_matches = self.time_stats['total_matches']
        self.time_stats['avg_match_time_ms'] = (
            (current_avg * (total_matches - 1) + elapsed_ms) / total_matches
        )
    
    def get_current_time_info(self, user: User, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Public method to get current time information.
        
        Args:
            user: User object
            context: User context
            
        Returns:
            Current time information or None
        """
        return self._get_current_time_info(user, context)
    
    def is_business_hours(self, user: User, context: Dict[str, Any]) -> bool:
        """
        Check if current time is within business hours.
        
        Args:
            user: User object
            context: User context
            
        Returns:
            True if within business hours, False otherwise
        """
        try:
            time_info = self._get_current_time_info(user, context)
            
            if not time_info:
                return False
            
            return time_info['is_business_hours']
            
        except Exception as e:
            logger.error(f"Error checking business hours: {e}")
            return False
    
    def is_weekend(self, user: User, context: Dict[str, Any]) -> bool:
        """
        Check if current time is weekend.
        
        Args:
            user: User object
            context: User context
            
        Returns:
            True if weekend, False otherwise
        """
        try:
            time_info = self._get_current_time_info(user, context)
            
            if not time_info:
                return False
            
            return time_info['is_weekend']
            
        except Exception as e:
            logger.error(f"Error checking weekend: {e}")
            return False
    
    def validate_time_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate time rule data.
        
        Args:
            rule_data: Rule data to validate
            
        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []
        
        # Validate hour range
        hour_from = rule_data.get('hour_from')
        hour_to = rule_data.get('hour_to')
        
        if hour_from is not None:
            if not isinstance(hour_from, int) or hour_from < 0 or hour_from > 23:
                errors.append("Hour from must be an integer between 0 and 23")
        
        if hour_to is not None:
            if not isinstance(hour_to, int) or hour_to < 0 or hour_to > 23:
                errors.append("Hour to must be an integer between 0 and 23")
        
        if hour_from is not None and hour_to is not None:
            # Note: overnight ranges (22-6) are valid, so we don't validate hour_from <= hour_to
        
        # Validate day of week
        day_of_week = rule_data.get('day_of_week')
        if day_of_week is not None:
            if isinstance(day_of_week, str):
                # Try to parse as JSON
                try:
                    import json
                    days = json.loads(day_of_week)
                    if not isinstance(days, list):
                        errors.append("Day of week must be a list or JSON array")
                    else:
                        # Validate day values
                        for day in days:
                            if not isinstance(day, int) or day < 0 or day > 6:
                                errors.append("Day of week values must be integers between 0 and 6")
                except json.JSONDecodeError:
                    # Try comma-separated
                    days = [int(d.strip()) for d in day_of_week.split(',') if d.strip().isdigit()]
                    for day in days:
                        if not isinstance(day, int) or day < 0 or day > 6:
                            errors.append("Day of week values must be integers between 0 and 6")
            elif isinstance(day_of_week, list):
                for day in day_of_week:
                    if not isinstance(day, int) or day < 0 or day > 6:
                        errors.append("Day of week values must be integers between 0 and 6")
            elif isinstance(day_of_week, int):
                if day_of_week < 0 or day_of_week > 6:
                    errors.append("Day of week must be an integer between 0 and 6")
            else:
                errors.append("Day of week must be an integer, list, or JSON array")
        
        # Validate timezone
        timezone_str = rule_data.get('timezone')
        if timezone_str:
            parsed_tz = self._parse_timezone(timezone_str)
            if not parsed_tz:
                errors.append(f"Invalid timezone: {timezone_str}")
            elif parsed_tz != timezone_str:
                warnings.append(f"Timezone normalized from {timezone_str} to {parsed_tz}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def get_time_targeting_stats(self) -> Dict[str, Any]:
        """Get time targeting performance statistics."""
        total_requests = self.time_stats['total_matches']
        cache_hit_rate = (
            self.time_stats['cache_hits'] / max(1, total_requests)
        )
        
        return {
            'total_matches': total_requests,
            'cache_hits': self.time_stats['cache_hits'],
            'cache_misses': total_requests - self.time_stats['cache_hits'],
            'cache_hit_rate': cache_hit_rate,
            'errors': self.time_stats['errors'],
            'error_rate': self.time_stats['errors'] / max(1, total_requests),
            'avg_match_time_ms': self.time_stats['avg_match_time_ms'],
            'timezone_cache_size': len(self.timezone_cache),
            'rate_limit_window': len(self.rate_limiter['matches']),
            'rate_limit_max': MAX_TIME_LOOKUPS_PER_SECOND
        }
    
    def clear_cache(self, timezone_str: str = None):
        """Clear cached time information."""
        try:
            if timezone_str:
                # Clear specific timezone cache
                cache_key = f"time_info:{timezone_str}"
                self.cache_service.delete(cache_key)
                logger.info(f"Cleared cache for timezone {timezone_str}")
            else:
                # Clear all time info cache
                # This would need pattern deletion support
                logger.info("Cache clearing for specific timezones not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing time cache: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on time targeting service."""
        try:
            # Test time parsing with common timezones
            test_timezones = ['UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo']
            test_results = []
            
            for tz in test_timezones:
                time_info = self._get_time_in_timezone(tz)
                test_results.append(time_info is not None)
            
            # Test rule matching
            test_rule = type('MockTimeRule', (), {
                'day_of_week': [0, 1, 2, 3, 4],  # Monday-Friday
                'hour_from': 9,
                'hour_to': 17,
                'timezone': 'UTC'
            })()
            
            test_time_info = self._get_time_in_timezone('UTC')
            if test_time_info:
                rule_matches = self._matches_time_rule(test_rule, test_time_info)
            else:
                rule_matches = False
            
            return {
                'status': 'healthy',
                'test_timezone_parsing': all(test_results),
                'test_rule_matching': rule_matches,
                'stats': self.get_time_targeting_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
