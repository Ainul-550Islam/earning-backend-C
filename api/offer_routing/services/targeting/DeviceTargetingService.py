"""
Device Targeting Service

Handles user agent parsing and device matching for
device-based targeting rules in offer routing system.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from ....models import (
    OfferRoute, DeviceRouteRule, RoutingDecisionLog
)
from ....choices import DeviceType, OSType, BrowserType
from ....constants import (
    DEVICE_CACHE_TIMEOUT, USER_AGENT_CACHE_TIMEOUT,
    MAX_DEVICE_LOOKUPS_PER_SECOND, DEVICE_PARSE_TIMEOUT
)
from ....exceptions import TargetingError, DeviceParsingError
from ....utils import parse_user_agent, extract_device_info

User = get_user_model()
logger = logging.getLogger(__name__)


class DeviceTargetingService:
    """
    Service for device-based targeting rules.
    
    Provides user agent parsing and device matching against
    device targeting rules for offer routing.
    
    Performance targets:
    - User agent parsing: <10ms (cached), <50ms (uncached)
    - Rule matching: <2ms per rule
    - Cache hit rate: >90%
    """
    
    def __init__(self):
        self.cache_service = cache
        self.parsing_stats = {
            'total_parses': 0,
            'cache_hits': 0,
            'errors': 0,
            'avg_parse_time_ms': 0.0
        }
        self.rate_limiter = {
            'parses': [],
            'window_start': timezone.now()
        }
        
        # Device detection patterns
        self._initialize_device_patterns()
    
    def _initialize_device_patterns(self):
        """Initialize device detection patterns."""
        self.device_patterns = {
            'mobile': [
                r'Mobile|Android|iPhone|iPod|BlackBerry|IEMobile|Opera Mini',
                r'Windows Phone|webOS|Palm|PSP|Tablet'
            ],
            'tablet': [
                r'iPad|Tablet|Kindle|Nexus 10|Nexus 9|Galaxy Tab',
                r'Surface|Transformer|Iconia|Flyer|Slider'
            ],
            'desktop': [
                r'Windows|Macintosh|Linux|X11|Ubuntu|Chrome OS',
                r'FreeBSD|NetBSD|OpenBSD|Solaris'
            ]
        }
        
        self.os_patterns = {
            'windows': [
                r'Windows NT 10\.0|Windows 10|Windows NT 6\.3|Windows 8\.1',
                r'Windows NT 6\.2|Windows 8|Windows NT 6\.1|Windows 7',
                r'Windows NT 6\.0|Windows Vista|Windows NT 5\.1|Windows XP'
            ],
            'macos': [
                r'Mac OS X 10[._][0-9]+|Mac OS X [0-9]+_[0-9]+',
                r'Macintosh|Mac OS|Mac_PowerPC'
            ],
            'linux': [
                r'Linux|Ubuntu|Debian|Fedora|CentOS|Red Hat',
                r'Android|Chrome OS|SteamOS'
            ],
            'ios': [
                r'iPhone OS [0-9]+_[0-9]+|iOS [0-9]+',
                r'iPhone|iPod|iPad'
            ],
            'android': [
                r'Android [0-9]+(\.[0-9]+)*|Android'
            ]
        }
        
        self.browser_patterns = {
            'chrome': [
                r'Chrome/[0-9]+(\.[0-9]+)*|CriOS/[0-9]+(\.[0-9]+)*'
            ],
            'firefox': [
                r'Firefox/[0-9]+(\.[0-9]+)*|FxiOS/[0-9]+(\.[0-9]+)*'
            ],
            'safari': [
                r'Safari/[0-9]+(\.[0-9]+)*|Version/[0-9]+(\.[0-9]+)* Safari'
            ],
            'edge': [
                r'Edge/[0-9]+(\.[0-9]+)*|Edg/[0-9]+(\.[0-9]+)*'
            ],
            'ie': [
                r'MSIE [0-9]+(\.[0-9]+)*|Trident/[0-9]+(\.[0-9]+)*'
            ],
            'opera': [
                r'Opera/[0-9]+(\.[0-9]+)*|OPR/[0-9]+(\.[0-9]+)*'
            ]
        }
    
    def matches_route(self, route: OfferRoute, user: User, 
                     context: Dict[str, Any]) -> bool:
        """
        Check if route matches user's device characteristics.
        
        Args:
            route: Route to check
            user: User object
            context: User context containing user agent or device info
            
        Returns:
            True if route matches device-wise, False otherwise
        """
        try:
            # Get device rules for route
            device_rules = route.device_rules.filter(is_active=True).order_by('priority')
            
            if not device_rules:
                return True  # No device restrictions
            
            # Get user's device information
            user_device = self._get_user_device_info(user, context)
            
            if not user_device:
                logger.warning(f"Could not determine device for user {user.id}")
                return False  # Cannot apply device targeting without device info
            
            # Check each device rule
            for rule in device_rules:
                if self._matches_device_rule(rule, user_device):
                    if rule.is_include:
                        return True  # Include rule matches
                    else:
                        return False  # Exclude rule matches
            
            # If no include rules matched, return False
            return False
            
        except Exception as e:
            logger.error(f"Error checking device targeting for route {route.id}: {e}")
            return False
    
    def _get_user_device_info(self, user: User, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get user's device information from various sources."""
        try:
            # Priority order: context > user profile > user agent parsing
            
            # 1. Check context for explicit device info
            if 'device' in context:
                device_data = context['device']
                if self._validate_device_data(device_data):
                    return device_data
            
            # 2. Check user profile for device preferences
            user_device = self._get_user_device_preferences(user)
            if user_device:
                return user_device
            
            # 3. Parse user agent
            user_agent = self._get_user_agent(user, context)
            if user_agent:
                return self._parse_user_agent(user_agent)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user device info: {e}")
            return None
    
    def _validate_device_data(self, device_data: Dict[str, Any]) -> bool:
        """Validate device data structure."""
        required_fields = ['type']
        optional_fields = ['os', 'browser', 'version', 'screen_resolution']
        
        # Check required fields
        for field in required_fields:
            if field not in device_data or not device_data[field]:
                return False
        
        # Validate device type
        device_type = device_data['type']
        valid_types = [choice[0] for choice in DeviceType.CHOICES]
        if device_type not in valid_types:
            return False
        
        return True
    
    def _get_user_device_preferences(self, user: User) -> Optional[Dict[str, Any]]:
        """Get device preferences from user's profile."""
        try:
            # Check user profile fields
            profile_fields = ['preferred_device_type', 'preferred_os', 'preferred_browser']
            device_data = {}
            
            for field in profile_fields:
                value = getattr(user, field, None)
                if value:
                    # Map field names to standard names
                    if field == 'preferred_device_type':
                        device_data['type'] = value
                    elif field == 'preferred_os':
                        device_data['os'] = value
                    elif field == 'preferred_browser':
                        device_data['browser'] = value
            
            if device_data.get('type'):
                return device_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user device preferences: {e}")
            return None
    
    def _get_user_agent(self, user: User, context: Dict[str, Any]) -> Optional[str]:
        """Get user agent string from context or request."""
        try:
            # Check context for user agent
            if 'user_agent' in context:
                return context['user_agent']
            
            # Check for request in context
            if 'request' in context:
                request = context['request']
                return request.META.get('HTTP_USER_AGENT', '')
            
            # Check user's last known user agent
            last_ua = getattr(user, 'last_user_agent', None)
            if last_ua:
                return last_ua
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user agent: {e}")
            return None
    
    def _parse_user_agent(self, user_agent: str) -> Optional[Dict[str, Any]]:
        """Parse user agent string to extract device information."""
        try:
            if not user_agent or len(user_agent.strip()) == 0:
                return None
            
            # Check rate limiting
            if not self._check_rate_limit():
                logger.warning(f"Rate limit exceeded for user agent parsing")
                return None
            
            start_time = timezone.now()
            
            # Check cache first
            cache_key = f"device_info:{hash(user_agent)}"
            cached_device = self.cache_service.get(cache_key)
            
            if cached_device:
                self.parsing_stats['cache_hits'] += 1
                return cached_device
            
            # Parse user agent
            device_info = self._extract_device_info(user_agent)
            
            if device_info:
                # Cache result
                self.cache_service.set(cache_key, device_info, USER_AGENT_CACHE_TIMEOUT)
                
                # Update stats
                elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
                self._update_parsing_stats(elapsed_ms)
                
                return device_info
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing user agent: {e}")
            self.parsing_stats['errors'] += 1
            return None
    
    def _extract_device_info(self, user_agent: str) -> Optional[Dict[str, Any]]:
        """Extract device information from user agent string."""
        try:
            device_info = {
                'user_agent': user_agent,
                'raw_ua': user_agent,
                'parsed_at': timezone.now().isoformat()
            }
            
            # Detect device type
            device_type = self._detect_device_type(user_agent)
            device_info['type'] = device_type
            
            # Detect operating system
            os_info = self._detect_os(user_agent)
            device_info.update(os_info)
            
            # Detect browser
            browser_info = self._detect_browser(user_agent)
            device_info.update(browser_info)
            
            # Extract additional device info
            additional_info = self._extract_additional_info(user_agent)
            device_info.update(additional_info)
            
            return device_info
            
        except Exception as e:
            logger.error(f"Error extracting device info: {e}")
            return None
    
    def _detect_device_type(self, user_agent: str) -> str:
        """Detect device type from user agent."""
        ua_lower = user_agent.lower()
        
        # Check for mobile devices first (most specific)
        for pattern in self.device_patterns['mobile']:
            if re.search(pattern, ua_lower, re.IGNORECASE):
                # Check if it's actually a tablet
                if self._is_tablet(ua_lower):
                    return DeviceType.TABLET
                return DeviceType.MOBILE
        
        # Check for tablets
        for pattern in self.device_patterns['tablet']:
            if re.search(pattern, ua_lower, re.IGNORECASE):
                return DeviceType.TABLET
        
        # Default to desktop
        return DeviceType.DESKTOP
    
    def _is_tablet(self, ua_lower: str) -> bool:
        """Check if user agent indicates tablet device."""
        tablet_indicators = [
            'ipad', 'tablet', 'kindle', 'nexus 10', 'nexus 9',
            'galaxy tab', 'surface', 'transformer', 'iconia'
        ]
        
        return any(indicator in ua_lower for indicator in tablet_indicators)
    
    def _detect_os(self, user_agent: str) -> Dict[str, Any]:
        """Detect operating system from user agent."""
        ua_lower = user_agent.lower()
        
        os_info = {
            'os': 'unknown',
            'os_version': '',
            'os_family': 'unknown'
        }
        
        # Check each OS pattern
        for os_name, patterns in self.os_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, ua_lower, re.IGNORECASE)
                if match:
                    os_info['os'] = os_name
                    os_info['os_family'] = self._get_os_family(os_name)
                    
                    # Extract version if available
                    version_match = re.search(r'[0-9]+(\.[0-9]+)*', match.group(0))
                    if version_match:
                        os_info['os_version'] = version_match.group(0)
                    
                    return os_info
        
        return os_info
    
    def _get_os_family(self, os_name: str) -> str:
        """Get OS family for grouping."""
        families = {
            'windows': 'windows',
            'macos': 'mac',
            'linux': 'linux',
            'ios': 'mobile',
            'android': 'mobile'
        }
        
        return families.get(os_name, 'other')
    
    def _detect_browser(self, user_agent: str) -> Dict[str, Any]:
        """Detect browser from user agent."""
        ua_lower = user_agent.lower()
        
        browser_info = {
            'browser': 'unknown',
            'browser_version': '',
            'browser_family': 'unknown'
        }
        
        # Check each browser pattern
        for browser_name, patterns in self.browser_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, ua_lower, re.IGNORECASE)
                if match:
                    browser_info['browser'] = browser_name
                    browser_info['browser_family'] = self._get_browser_family(browser_name)
                    
                    # Extract version
                    version_match = re.search(r'[0-9]+(\.[0-9]+)*', match.group(0))
                    if version_match:
                        browser_info['browser_version'] = version_match.group(0)
                    
                    return browser_info
        
        return browser_info
    
    def _get_browser_family(self, browser_name: str) -> str:
        """Get browser family for grouping."""
        families = {
            'chrome': 'chromium',
            'firefox': 'gecko',
            'safari': 'webkit',
            'edge': 'chromium',
            'ie': 'trident',
            'opera': 'chromium'
        }
        
        return families.get(browser_name, 'other')
    
    def _extract_additional_info(self, user_agent: str) -> Dict[str, Any]:
        """Extract additional device information."""
        additional_info = {}
        
        # Screen resolution (if available)
        screen_match = re.search(r'([0-9]+)x([0-9]+)', user_agent)
        if screen_match:
            additional_info['screen_resolution'] = f"{screen_match.group(1)}x{screen_match.group(2)}"
            additional_info['screen_width'] = int(screen_match.group(1))
            additional_info['screen_height'] = int(screen_match.group(2))
        
        # Language (if available)
        lang_match = re.search(r'[a-z]{2}(-[A-Z]{2})?', user_agent)
        if lang_match:
            additional_info['language'] = lang_match.group(0)
        
        # Device capabilities
        capabilities = []
        
        # Touch capability
        if any(indicator in user_agent.lower() for indicator in ['touch', 'mobile', 'tablet']):
            capabilities.append('touch')
        
        # JavaScript capability (modern browsers)
        modern_browsers = ['chrome', 'firefox', 'safari', 'edge']
        if any(browser in user_agent.lower() for browser in modern_browsers):
            capabilities.append('javascript')
        
        # WebGL capability
        if 'webgl' in user_agent.lower():
            capabilities.append('webgl')
        
        additional_info['capabilities'] = capabilities
        
        return additional_info
    
    def _matches_device_rule(self, rule: DeviceRouteRule, 
                             user_device: Dict[str, Any]) -> bool:
        """Check if user device matches a device rule."""
        try:
            # Device type matching
            if rule.device_type:
                if user_device.get('type') != rule.device_type:
                    return False
            
            # OS matching
            if rule.os_type:
                if user_device.get('os') != rule.os_type:
                    return False
            
            # Browser matching
            if rule.browser:
                if user_device.get('browser') != rule.browser:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error matching device rule {rule.id}: {e}")
            return False
    
    def _check_rate_limit(self) -> bool:
        """Check if user agent parsing rate limit is exceeded."""
        try:
            current_time = timezone.now()
            window_start = self.rate_limiter['window_start']
            
            # Reset window if needed
            if (current_time - window_start).seconds >= 60:
                self.rate_limiter['parses'] = []
                self.rate_limiter['window_start'] = current_time
                return True
            
            # Check current parses
            if len(self.rate_limiter['parses']) >= MAX_DEVICE_LOOKUPS_PER_SECOND:
                return False
            
            # Add current parse
            self.rate_limiter['parses'].append(current_time)
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True  # Allow parsing on error
    
    def _update_parsing_stats(self, elapsed_ms: float):
        """Update parsing performance statistics."""
        self.parsing_stats['total_parses'] += 1
        
        # Update average time
        current_avg = self.parsing_stats['avg_parse_time_ms']
        total_parses = self.parsing_stats['total_parses']
        self.parsing_stats['avg_parse_time_ms'] = (
            (current_avg * (total_parses - 1) + elapsed_ms) / total_parses
        )
    
    def get_device_info_by_user_agent(self, user_agent: str) -> Optional[Dict[str, Any]]:
        """
        Public method to get device info by user agent.
        
        Args:
            user_agent: User agent string to parse
            
        Returns:
            Device information or None if not found
        """
        return self._parse_user_agent(user_agent)
    
    def validate_device_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate device rule data.
        
        Args:
            rule_data: Rule data to validate
            
        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []
        
        # Validate device type
        if rule_data.get('device_type'):
            device_type = rule_data['device_type']
            valid_types = [choice[0] for choice in DeviceType.CHOICES]
            if device_type not in valid_types:
                errors.append(f"Invalid device type: {device_type}")
        
        # Validate OS type
        if rule_data.get('os_type'):
            os_type = rule_data['os_type']
            valid_os_types = [choice[0] for choice in OSType.CHOICES]
            if os_type not in valid_os_types:
                errors.append(f"Invalid OS type: {os_type}")
        
        # Validate browser
        if rule_data.get('browser'):
            browser = rule_data['browser']
            valid_browsers = [choice[0] for choice in BrowserType.CHOICES]
            if browser not in valid_browsers:
                errors.append(f"Invalid browser: {browser}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def get_device_targeting_stats(self) -> Dict[str, Any]:
        """Get device targeting performance statistics."""
        total_requests = self.parsing_stats['total_parses']
        cache_hit_rate = (
            self.parsing_stats['cache_hits'] / max(1, total_requests)
        )
        
        return {
            'total_parses': total_requests,
            'cache_hits': self.parsing_stats['cache_hits'],
            'cache_misses': total_requests - self.parsing_stats['cache_hits'],
            'cache_hit_rate': cache_hit_rate,
            'errors': self.parsing_stats['errors'],
            'error_rate': self.parsing_stats['errors'] / max(1, total_requests),
            'avg_parse_time_ms': self.parsing_stats['avg_parse_time_ms'],
            'rate_limit_window': len(self.rate_limiter['parses']),
            'rate_limit_max': MAX_DEVICE_LOOKUPS_PER_SECOND
        }
    
    def clear_cache(self, user_agent: str = None):
        """Clear cached device information."""
        try:
            if user_agent:
                # Clear specific user agent cache
                cache_key = f"device_info:{hash(user_agent)}"
                self.cache_service.delete(cache_key)
                logger.info(f"Cleared cache for user agent hash")
            else:
                # Clear all device info cache
                # This would need pattern deletion support
                logger.info("Cache clearing for specific user agents not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing device cache: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on device targeting service."""
        try:
            # Test user agent parsing with known user agents
            test_user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ]
            
            test_results = []
            for ua in test_user_agents:
                device_info = self.get_device_info_by_user_agent(ua)
                test_results.append(device_info is not None)
            
            # Test rule matching
            test_rule = type('MockDeviceRule', (), {
                'device_type': 'mobile',
                'os_type': '',
                'browser': '',
                'is_include': True
            })()
            
            test_device_info = {
                'type': 'mobile',
                'os': 'android',
                'browser': 'chrome'
            }
            
            rule_matches = self._matches_device_rule(test_rule, test_device_info)
            
            return {
                'status': 'healthy',
                'test_user_agent_parsing': all(test_results),
                'test_rule_matching': rule_matches,
                'stats': self.get_device_targeting_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
