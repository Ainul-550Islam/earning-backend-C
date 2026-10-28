# api/rate_limit/hooks.py
"""
Hook system for rate limit module.

Provides hooks for extending rate limiting functionality.
"""
from django.utils import timezone

import logging
from typing import Dict, Any, List, Callable, Optional
from abc import ABC, abstractmethod
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class RateLimitHook(ABC):
    """
    Abstract base class for rate limit hooks.
    """
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the hook.
        
        Args:
            context: Hook context data
            
        Returns:
            Modified context data
        """
        pass
    
    def get_priority(self) -> int:
        """Get hook priority (lower number = higher priority)."""
        return 100
    
    def is_enabled(self) -> bool:
        """Check if hook is enabled."""
        return True


class PreRateLimitHook(RateLimitHook):
    """
    Hook executed before rate limit check.
    """
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute pre-rate limit logic.
        
        Args:
            context: Contains request, user, ip_address, etc.
            
        Returns:
            Modified context with potential early decision
        """
        # Default implementation - just return context
        return context


class PostRateLimitHook(RateLimitHook):
    """
    Hook executed after rate limit check.
    """
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute post-rate limit logic.
        
        Args:
            context: Contains request, rate_limit_result, etc.
            
        Returns:
            Modified context
        """
        # Default implementation - just return context
        return context


class AbuseDetectionHook(RateLimitHook):
    """
    Hook for custom abuse detection logic.
    """
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute custom abuse detection.
        
        Args:
            context: Contains request, logs, patterns, etc.
            
        Returns:
            Context with abuse detection results
        """
        return context


class LoggingHook(RateLimitHook):
    """
    Hook for custom logging logic.
    """
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute custom logging.
        
        Args:
            context: Contains event data, log level, etc.
            
        Returns:
            Modified context
        """
        return context


class NotificationHook(RateLimitHook):
    """
    Hook for custom notification logic.
    """
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute custom notifications.
        
        Args:
            context: Contains notification data, recipients, etc.
            
        Returns:
            Modified context
        """
        return context


class CustomValidationHook(RateLimitHook):
    """
    Hook for custom validation logic.
    """
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute custom validation.
        
        Args:
            context: Contains data to validate
            
        Returns:
            Context with validation results
        """
        return context


class WhitelistHook(PreRateLimitHook):
    """
    Hook for custom whitelist logic.
    """
    
    def __init__(self, whitelist_rules: List[Dict[str, Any]]):
        self.whitelist_rules = whitelist_rules
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if request should be whitelisted.
        """
        request = context.get('request')
        if not request:
            return context
        
        ip_address = self._get_client_ip(request)
        user = getattr(request, 'user', None)
        path = request.path
        
        for rule in self.whitelist_rules:
            if self._matches_rule(rule, ip_address, user, path):
                context['whitelisted'] = True
                context['whitelist_rule'] = rule
                logger.info(f"Request whitelisted by rule: {rule.get('name', 'unnamed')}")
                break
        
        return context
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')
    
    def _matches_rule(self, rule: Dict[str, Any], ip_address: str, user, path: str) -> bool:
        """Check if request matches whitelist rule."""
        # Check IP
        if 'ip_addresses' in rule:
            if ip_address not in rule['ip_addresses']:
                return False
        
        # Check user
        if 'users' in rule:
            if not user or user.username not in rule['users']:
                return False
        
        # Check path
        if 'paths' in rule:
            if not any(path.startswith(p) for p in rule['paths']):
                return False
        
        # Check user groups
        if 'groups' in rule:
            if not user or not user.groups.filter(name__in=rule['groups']).exists():
                return False
        
        return True


class BlacklistHook(PreRateLimitHook):
    """
    Hook for custom blacklist logic.
    """
    
    def __init__(self, blacklist_rules: List[Dict[str, Any]]):
        self.blacklist_rules = blacklist_rules
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if request should be blacklisted.
        """
        request = context.get('request')
        if not request:
            return context
        
        ip_address = self._get_client_ip(request)
        user = getattr(request, 'user', None)
        path = request.path
        
        for rule in self.blacklist_rules:
            if self._matches_rule(rule, ip_address, user, path):
                context['blacklisted'] = True
                context['blacklist_rule'] = rule
                logger.warning(f"Request blacklisted by rule: {rule.get('name', 'unnamed')}")
                break
        
        return context
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')
    
    def _matches_rule(self, rule: Dict[str, Any], ip_address: str, user, path: str) -> bool:
        """Check if request matches blacklist rule."""
        # Check IP
        if 'ip_addresses' in rule:
            if ip_address not in rule['ip_addresses']:
                return False
        
        # Check user
        if 'users' in rule:
            if not user or user.username not in rule['users']:
                return False
        
        # Check path
        if 'paths' in rule:
            if not any(path.startswith(p) for p in rule['paths']):
                return False
        
        # Check user agents
        if 'user_agents' in rule:
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            if not any(ua in user_agent for ua in rule['user_agents']):
                return False
        
        return True


class CustomRateLimitHook(PreRateLimitHook):
    """
    Hook for custom rate limiting logic.
    """
    
    def __init__(self, custom_limits: Dict[str, Any]):
        self.custom_limits = custom_limits
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply custom rate limiting logic.
        """
        request = context.get('request')
        if not request:
            return context
        
        user = getattr(request, 'user', None)
        ip_address = self._get_client_ip(request)
        path = request.path
        
        # Check custom limits
        for limit_config in self.custom_limits:
            if self._matches_limit_config(limit_config, user, ip_address, path):
                context['custom_limit'] = limit_config
                context['max_requests'] = limit_config['max_requests']
                context['time_window'] = limit_config['time_window']
                break
        
        return context
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')
    
    def _matches_limit_config(self, config: Dict[str, Any], user, ip_address: str, path: str) -> bool:
        """Check if request matches custom limit configuration."""
        # Check user
        if 'users' in config:
            if not user or user.username not in config['users']:
                return False
        
        # Check IP ranges
        if 'ip_ranges' in config:
            if not self._ip_in_ranges(ip_address, config['ip_ranges']):
                return False
        
        # Check paths
        if 'paths' in config:
            if not any(path.startswith(p) for p in config['paths']):
                return False
        
        # Check time restrictions
        if 'time_restrictions' in config:
            if not self._matches_time_restrictions(config['time_restrictions']):
                return False
        
        return True
    
    def _ip_in_ranges(self, ip_address: str, ip_ranges: List[str]) -> bool:
        """Check if IP is in any of the specified ranges."""
        import ipaddress
        try:
            ip = ipaddress.ip_address(ip_address)
            for range_str in ip_ranges:
                if '/' in range_str:
                    # CIDR range
                    network = ipaddress.ip_network(range_str, strict=False)
                    if ip in network:
                        return True
                else:
                    # Single IP
                    if ip_address == range_str:
                        return True
        except Exception:
            pass
        return False
    
    def _matches_time_restrictions(self, restrictions: Dict[str, Any]) -> bool:
        """Check if current time matches restrictions."""
        from django.utils import timezone
        now = timezone.now()
        
        # Check hours
        if 'hours' in restrictions:
            if now.hour not in restrictions['hours']:
                return False
        
        # Check days of week
        if 'days_of_week' in restrictions:
            if now.weekday() not in restrictions['days_of_week']:
                return False
        
        # Check date range
        if 'date_range' in restrictions:
            start_date = restrictions['date_range'].get('start')
            end_date = restrictions['date_range'].get('end')
            if start_date and now.date() < start_date:
                return False
            if end_date and now.date() > end_date:
                return False
        
        return True


class AnalyticsHook(PostRateLimitHook):
    """
    Hook for analytics collection.
    """
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Collect analytics data.
        """
        rate_limit_result = context.get('rate_limit_result')
        request = context.get('request')
        
        if rate_limit_result and request:
            # Store analytics data
            self._store_analytics_data(request, rate_limit_result)
        
        return context
    
    def _store_analytics_data(self, request: HttpRequest, result: Dict[str, Any]):
        """Store analytics data."""
        try:
            from django.core.cache import cache
            
            # Get current analytics data
            analytics_key = "rate_limit_analytics"
            analytics_data = cache.get(analytics_key, {})
            
            # Update counters
            today = timezone.now().date().isoformat()
            if today not in analytics_data:
                analytics_data[today] = {
                    'total_requests': 0,
                    'blocked_requests': 0,
                    'allowed_requests': 0,
                    'endpoints': {},
                    'ips': {},
                }
            
            daily_stats = analytics_data[today]
            daily_stats['total_requests'] += 1
            
            if not result.get('is_allowed', True):
                daily_stats['blocked_requests'] += 1
            else:
                daily_stats['allowed_requests'] += 1
            
            # Track endpoints
            endpoint = request.path
            daily_stats['endpoints'][endpoint] = daily_stats['endpoints'].get(endpoint, 0) + 1
            
            # Track IPs
            ip_address = self._get_client_ip(request)
            daily_stats['ips'][ip_address] = daily_stats['ips'].get(ip_address, 0) + 1
            
            # Store updated analytics
            cache.set(analytics_key, analytics_data, timeout=86400)  # 24 hours
            
        except Exception as e:
            logger.error(f"Failed to store analytics data: {str(e)}")
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')


class RateLimitHookManager:
    """
    Manager for rate limit hooks.
    """
    
    def __init__(self):
        self.pre_hooks: List[PreRateLimitHook] = []
        self.post_hooks: List[PostRateLimitHook] = []
        self.abuse_hooks: List[AbuseDetectionHook] = []
        self.logging_hooks: List[LoggingHook] = []
        self.notification_hooks: List[NotificationHook] = []
        self.validation_hooks: List[CustomValidationHook] = []
    
    def register_pre_hook(self, hook: PreRateLimitHook):
        """Register a pre-rate limit hook."""
        self.pre_hooks.append(hook)
        self.pre_hooks.sort(key=lambda h: h.get_priority())
        logger.info(f"Registered pre-rate limit hook: {hook.__class__.__name__}")
    
    def register_post_hook(self, hook: PostRateLimitHook):
        """Register a post-rate limit hook."""
        self.post_hooks.append(hook)
        self.post_hooks.sort(key=lambda h: h.get_priority())
        logger.info(f"Registered post-rate limit hook: {hook.__class__.__name__}")
    
    def register_abuse_hook(self, hook: AbuseDetectionHook):
        """Register an abuse detection hook."""
        self.abuse_hooks.append(hook)
        self.abuse_hooks.sort(key=lambda h: h.get_priority())
        logger.info(f"Registered abuse detection hook: {hook.__class__.__name__}")
    
    def register_logging_hook(self, hook: LoggingHook):
        """Register a logging hook."""
        self.logging_hooks.append(hook)
        self.logging_hooks.sort(key=lambda h: h.get_priority())
        logger.info(f"Registered logging hook: {hook.__class__.__name__}")
    
    def register_notification_hook(self, hook: NotificationHook):
        """Register a notification hook."""
        self.notification_hooks.append(hook)
        self.notification_hooks.sort(key=lambda h: h.get_priority())
        logger.info(f"Registered notification hook: {hook.__class__.__name__}")
    
    def register_validation_hook(self, hook: CustomValidationHook):
        """Register a validation hook."""
        self.validation_hooks.append(hook)
        self.validation_hooks.sort(key=lambda h: h.get_priority())
        logger.info(f"Registered validation hook: {hook.__class__.__name__}")
    
    def execute_pre_hooks(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all pre-rate limit hooks."""
        for hook in self.pre_hooks:
            if hook.is_enabled():
                try:
                    context = hook.execute(context)
                except Exception as e:
                    logger.error(f"Pre-rate limit hook failed: {str(e)}")
        
        return context
    
    def execute_post_hooks(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all post-rate limit hooks."""
        for hook in self.post_hooks:
            if hook.is_enabled():
                try:
                    context = hook.execute(context)
                except Exception as e:
                    logger.error(f"Post-rate limit hook failed: {str(e)}")
        
        return context
    
    def execute_abuse_hooks(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all abuse detection hooks."""
        for hook in self.abuse_hooks:
            if hook.is_enabled():
                try:
                    context = hook.execute(context)
                except Exception as e:
                    logger.error(f"Abuse detection hook failed: {str(e)}")
        
        return context
    
    def execute_logging_hooks(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all logging hooks."""
        for hook in self.logging_hooks:
            if hook.is_enabled():
                try:
                    context = hook.execute(context)
                except Exception as e:
                    logger.error(f"Logging hook failed: {str(e)}")
        
        return context
    
    def execute_notification_hooks(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all notification hooks."""
        for hook in self.notification_hooks:
            if hook.is_enabled():
                try:
                    context = hook.execute(context)
                except Exception as e:
                    logger.error(f"Notification hook failed: {str(e)}")
        
        return context
    
    def execute_validation_hooks(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all validation hooks."""
        for hook in self.validation_hooks:
            if hook.is_enabled():
                try:
                    context = hook.execute(context)
                except Exception as e:
                    logger.error(f"Validation hook failed: {str(e)}")
        
        return context


# Global hook manager instance
hook_manager = RateLimitHookManager()


def register_hook(hook: RateLimitHook):
    """
    Register a hook with the appropriate manager.
    
    Args:
        hook: The hook to register
    """
    if isinstance(hook, PreRateLimitHook):
        hook_manager.register_pre_hook(hook)
    elif isinstance(hook, PostRateLimitHook):
        hook_manager.register_post_hook(hook)
    elif isinstance(hook, AbuseDetectionHook):
        hook_manager.register_abuse_hook(hook)
    elif isinstance(hook, LoggingHook):
        hook_manager.register_logging_hook(hook)
    elif isinstance(hook, NotificationHook):
        hook_manager.register_notification_hook(hook)
    elif isinstance(hook, CustomValidationHook):
        hook_manager.register_validation_hook(hook)
    else:
        logger.warning(f"Unknown hook type: {hook.__class__.__name__}")


# Export classes and functions
__all__ = [
    'RateLimitHook',
    'PreRateLimitHook',
    'PostRateLimitHook',
    'AbuseDetectionHook',
    'LoggingHook',
    'NotificationHook',
    'CustomValidationHook',
    'WhitelistHook',
    'BlacklistHook',
    'CustomRateLimitHook',
    'AnalyticsHook',
    'RateLimitHookManager',
    'hook_manager',
    'register_hook'
]
