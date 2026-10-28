# api/rate_limit/plugins.py
"""
Plugin system for rate limit module.

Provides extensible plugin architecture for custom rate limiting functionality.
"""
from django.utils import timezone

import logging
from typing import Dict, Any, List, Optional, Callable
from abc import ABC, abstractmethod
from django.http import HttpRequest, HttpResponse
from django.conf import settings

logger = logging.getLogger(__name__)


class RateLimitPlugin(ABC):
    """
    Abstract base class for rate limit plugins.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        self.name = self.__class__.__name__
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the plugin logic.
        
        Args:
            context: Plugin context data
            
        Returns:
            Modified context data
        """
        pass
    
    def is_enabled(self) -> bool:
        """Check if plugin is enabled."""
        return self.enabled
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)
    
    def validate_config(self) -> bool:
        """Validate plugin configuration."""
        return True


class PreRateLimitPlugin(RateLimitPlugin):
    """
    Plugin executed before rate limit check.
    """
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute pre-rate limit plugin logic.
        """
        pass


class PostRateLimitPlugin(RateLimitPlugin):
    """
    Plugin executed after rate limit check.
    """
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute post-rate limit plugin logic.
        """
        pass


class StoragePlugin(RateLimitPlugin):
    """
    Plugin for custom storage backends.
    """
    
    @abstractmethod
    def store(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        Store value with optional TTL.
        """
        pass
    
    @abstractmethod
    def retrieve(self, key: str) -> Any:
        """
        Retrieve value by key.
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete value by key.
        """
        pass
    
    @abstractmethod
    def increment(self, key: str, amount: int = 1, ttl: int = None) -> int:
        """
        Increment counter value.
        """
        pass


class AnalyticsPlugin(RateLimitPlugin):
    """
    Plugin for custom analytics collection.
    """
    
    @abstractmethod
    def track_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Track analytics event.
        """
        pass
    
    @abstractmethod
    def generate_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Generate analytics report.
        """
        pass


class NotificationPlugin(RateLimitPlugin):
    """
    Plugin for custom notifications.
    """
    
    @abstractmethod
    def send_notification(self, message: str, recipients: List[str], severity: str = 'info') -> bool:
        """
        Send notification to recipients.
        """
        pass


class RedisStoragePlugin(StoragePlugin):
    """
    Redis storage plugin for rate limiting.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.redis_client = None
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis client."""
        try:
            import redis
            redis_url = self.get_config('redis_url', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            logger.info("Redis storage plugin initialized")
        except ImportError:
            logger.error("Redis library not installed")
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {str(e)}")
            self.enabled = False
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Redis storage operations."""
        operation = context.get('operation')
        key = context.get('key')
        
        if operation == 'store':
            value = context.get('value')
            ttl = context.get('ttl')
            result = self.store(key, value, ttl)
            context['result'] = result
        
        elif operation == 'retrieve':
            result = self.retrieve(key)
            context['result'] = result
        
        elif operation == 'delete':
            result = self.delete(key)
            context['result'] = result
        
        elif operation == 'increment':
            amount = context.get('amount', 1)
            ttl = context.get('ttl')
            result = self.increment(key, amount, ttl)
            context['result'] = result
        
        return context
    
    def store(self, key: str, value: Any, ttl: int = None) -> bool:
        """Store value in Redis."""
        if not self.redis_client:
            return False
        
        try:
            if ttl:
                return self.redis_client.setex(key, ttl, value)
            else:
                return self.redis_client.set(key, value)
        except Exception as e:
            logger.error(f"Redis store error: {str(e)}")
            return False
    
    def retrieve(self, key: str) -> Any:
        """Retrieve value from Redis."""
        if not self.redis_client:
            return None
        
        try:
            value = self.redis_client.get(key)
            if value and value.isdigit():
                return int(value)
            return value
        except Exception as e:
            logger.error(f"Redis retrieve error: {str(e)}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete value from Redis."""
        if not self.redis_client:
            return False
        
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Redis delete error: {str(e)}")
            return False
    
    def increment(self, key: str, amount: int = 1, ttl: int = None) -> int:
        """Increment counter in Redis."""
        if not self.redis_client:
            return 0
        
        try:
            # Use pipeline for atomic operation
            pipe = self.redis_client.pipeline()
            pipe.incrby(key, amount)
            if ttl:
                pipe.expire(key, ttl)
            results = pipe.execute()
            return results[0]
        except Exception as e:
            logger.error(f"Redis increment error: {str(e)}")
            return 0


class DatabaseStoragePlugin(StoragePlugin):
    """
    Database storage plugin for rate limiting.
    """
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute database storage operations."""
        # Implementation would use Django models for storage
        # This is a placeholder for database-based rate limiting
        return context
    
    def store(self, key: str, value: Any, ttl: int = None) -> bool:
        """Store value in database."""
        # Implementation would use Django cache or custom model
        return True
    
    def retrieve(self, key: str) -> Any:
        """Retrieve value from database."""
        # Implementation would query database
        return None
    
    def delete(self, key: str) -> bool:
        """Delete value from database."""
        # Implementation would delete from database
        return True
    
    def increment(self, key: str, amount: int = 1, ttl: int = None) -> int:
        """Increment counter in database."""
        # Implementation would update database counter
        return amount


class GeolocationPlugin(PreRateLimitPlugin):
    """
    Plugin for geolocation-based rate limiting.
    """
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute geolocation checks."""
        request = context.get('request')
        if not request:
            return context
        
        ip_address = self._get_client_ip(request)
        country = self._get_country_from_ip(ip_address)
        
        if country:
            context['country'] = country
            
            # Apply country-specific rules
            country_rules = self.get_config('country_rules', {})
            if country in country_rules:
                rule = country_rules[country]
                context['country_rule'] = rule
                
                # Apply multiplier or exemption
                if rule.get('exempt', False):
                    context['exempt'] = True
                elif rule.get('multiplier'):
                    context['multiplier'] = rule['multiplier']
        
        return context
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')
    
    def _get_country_from_ip(self, ip_address: str) -> Optional[str]:
        """Get country code from IP address."""
        try:
            # Use geoip2 library if available
            import geoip2.database
            import geoip2.errors
            
            geoip_path = self.get_config('geoip_database_path')
            if geoip_path:
                with geoip2.database.Reader(geoip_path) as reader:
                    response = reader.city(ip_address)
                    return response.country.iso_code
        except ImportError:
            logger.warning("GeoIP2 library not installed")
        except Exception as e:
            logger.error(f"GeoIP lookup failed: {str(e)}")
        
        return None


class UserBehaviorPlugin(PreRateLimitPlugin):
    """
    Plugin for user behavior-based rate limiting.
    """
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute user behavior analysis."""
        request = context.get('request')
        user = getattr(request, 'user', None)
        
        if not user or not user.is_authenticated:
            return context
        
        # Analyze user behavior patterns
        behavior_score = self._calculate_behavior_score(user)
        context['behavior_score'] = behavior_score
        
        # Adjust rate limits based on behavior
        if behavior_score > 80:  # Good behavior
            context['multiplier'] = context.get('multiplier', 1.0) * 1.5
        elif behavior_score < 30:  # Bad behavior
            context['multiplier'] = context.get('multiplier', 1.0) * 0.5
        
        return context
    
    def _calculate_behavior_score(self, user) -> int:
        """Calculate user behavior score."""
        try:
            from api.rate_limit.models import UserRateLimitProfile
            profile = UserRateLimitProfile.objects.get(user=user)
            
            # Base score from API health
            score = profile.api_health_score
            
            # Adjust based on suspicion score
            score -= profile.suspicion_score
            
            # Adjust based on account age
            account_age_days = (timezone.now() - user.date_joined).days
            if account_age_days < 7:
                score -= 20  # New accounts get lower score
            elif account_age_days > 365:
                score += 10  # Old accounts get bonus
            
            return max(0, min(100, score))
            
        except Exception as e:
            logger.error(f"Behavior score calculation failed: {str(e)}")
            return 50  # Default score


class TimeBasedPlugin(PreRateLimitPlugin):
    """
    Plugin for time-based rate limiting adjustments.
    """
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute time-based adjustments."""
        from django.utils import timezone
        
        now = timezone.now()
        hour = now.hour
        day_of_week = now.weekday()
        
        # Apply time-based rules
        time_rules = self.get_config('time_rules', {})
        
        # Check hour-based rules
        hour_rule = time_rules.get('hours', {}).get(hour)
        if hour_rule:
            context['time_rule'] = hour_rule
            if hour_rule.get('multiplier'):
                context['multiplier'] = context.get('multiplier', 1.0) * hour_rule['multiplier']
        
        # Check day-based rules
        day_rule = time_rules.get('days', {}).get(day_of_week)
        if day_rule:
            context['day_rule'] = day_rule
            if day_rule.get('multiplier'):
                context['multiplier'] = context.get('multiplier', 1.0) * day_rule['multiplier']
        
        # Check business hours
        business_hours = self.get_config('business_hours', {})
        if business_hours:
            start_hour = business_hours.get('start', 9)
            end_hour = business_hours.get('end', 17)
            
            if start_hour <= hour <= end_hour:
                context['is_business_hours'] = True
                context['multiplier'] = context.get('multiplier', 1.0) * 1.2  # 20% increase during business hours
            else:
                context['is_business_hours'] = False
                context['multiplier'] = context.get('multiplier', 1.0) * 0.8  # 20% decrease outside business hours
        
        return context


class SlackNotificationPlugin(NotificationPlugin):
    """
    Plugin for Slack notifications.
    """
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Slack notification."""
        if context.get('send_notification'):
            message = context.get('message')
            recipients = context.get('recipients', [])
            severity = context.get('severity', 'info')
            
            result = self.send_notification(message, recipients, severity)
            context['notification_sent'] = result
        
        return context
    
    def send_notification(self, message: str, recipients: List[str], severity: str = 'info') -> bool:
        """Send Slack notification."""
        try:
            import requests
            
            webhook_url = self.get_config('webhook_url')
            if not webhook_url:
                logger.warning("Slack webhook URL not configured")
                return False
            
            # Prepare Slack payload
            payload = {
                'text': message,
                'username': 'Rate Limit Bot',
                'icon_emoji': self._get_emoji_for_severity(severity),
                'attachments': [
                    {
                        'color': self._get_color_for_severity(severity),
                        'fields': [
                            {
                                'title': 'Severity',
                                'value': severity.upper(),
                                'short': True
                            },
                            {
                                'title': 'Time',
                                'value': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'short': True
                            }
                        ]
                    }
                ]
            }
            
            # Send to Slack
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Slack notification sent: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Slack notification failed: {str(e)}")
            return False
    
    def _get_emoji_for_severity(self, severity: str) -> str:
        """Get emoji for severity level."""
        emoji_map = {
            'info': ':information_source:',
            'warning': ':warning:',
            'error': ':x:',
            'critical': ':rotating_light:'
        }
        return emoji_map.get(severity, ':information_source:')
    
    def _get_color_for_severity(self, severity: str) -> str:
        """Get color for severity level."""
        color_map = {
            'info': 'good',
            'warning': 'warning',
            'error': 'danger',
            'critical': 'danger'
        }
        return color_map.get(severity, 'good')


class EmailNotificationPlugin(NotificationPlugin):
    """
    Plugin for email notifications.
    """
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute email notification."""
        if context.get('send_notification'):
            message = context.get('message')
            recipients = context.get('recipients', [])
            severity = context.get('severity', 'info')
            
            result = self.send_notification(message, recipients, severity)
            context['notification_sent'] = result
        
        return context
    
    def send_notification(self, message: str, recipients: List[str], severity: str = 'info') -> bool:
        """Send email notification."""
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            subject = f"Rate Limit Alert - {severity.upper()}"
            
            # Send email
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                recipient_list=recipients,
                fail_silently=False
            )
            
            logger.info(f"Email notification sent to {recipients}")
            return True
            
        except Exception as e:
            logger.error(f"Email notification failed: {str(e)}")
            return False


class PluginManager:
    """
    Manager for rate limit plugins.
    """
    
    def __init__(self):
        self.plugins: Dict[str, List[RateLimitPlugin]] = {
            'pre_rate_limit': [],
            'post_rate_limit': [],
            'storage': [],
            'analytics': [],
            'notification': []
        }
        self._load_default_plugins()
    
    def _load_default_plugins(self):
        """Load default plugins."""
        # Load plugins from settings
        plugin_configs = getattr(settings, 'RATE_LIMIT_PLUGINS', {})
        
        for plugin_type, configs in plugin_configs.items():
            for config in configs:
                plugin_class = config.get('class')
                plugin_config = config.get('config', {})
                
                if plugin_class:
                    try:
                        # Import plugin class
                        module_path, class_name = plugin_class.rsplit('.', 1)
                        module = __import__(module_path, fromlist=[class_name])
                        plugin_cls = getattr(module, class_name)
                        
                        # Instantiate plugin
                        plugin = plugin_cls(plugin_config)
                        
                        if plugin.is_enabled():
                            self.register_plugin(plugin_type, plugin)
                            logger.info(f"Loaded plugin: {plugin_class}")
                    
                    except Exception as e:
                        logger.error(f"Failed to load plugin {plugin_class}: {str(e)}")
    
    def register_plugin(self, plugin_type: str, plugin: RateLimitPlugin):
        """Register a plugin."""
        if plugin_type in self.plugins:
            self.plugins[plugin_type].append(plugin)
            logger.info(f"Registered {plugin_type} plugin: {plugin.name}")
        else:
            logger.error(f"Unknown plugin type: {plugin_type}")
    
    def unregister_plugin(self, plugin_type: str, plugin_name: str):
        """Unregister a plugin by name."""
        if plugin_type in self.plugins:
            self.plugins[plugin_type] = [
                p for p in self.plugins[plugin_type] 
                if p.name != plugin_name
            ]
            logger.info(f"Unregistered {plugin_type} plugin: {plugin_name}")
    
    def execute_plugins(self, plugin_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all plugins of a specific type."""
        if plugin_type not in self.plugins:
            return context
        
        for plugin in self.plugins[plugin_type]:
            if plugin.is_enabled():
                try:
                    context = plugin.execute(context)
                except Exception as e:
                    logger.error(f"Plugin {plugin.name} failed: {str(e)}")
        
        return context
    
    def get_plugin(self, plugin_type: str, plugin_name: str) -> Optional[RateLimitPlugin]:
        """Get a specific plugin."""
        if plugin_type in self.plugins:
            for plugin in self.plugins[plugin_type]:
                if plugin.name == plugin_name:
                    return plugin
        return None
    
    def list_plugins(self, plugin_type: str = None) -> Dict[str, List[str]]:
        """List all plugins."""
        if plugin_type:
            if plugin_type in self.plugins:
                return {plugin_type: [p.name for p in self.plugins[plugin_type]]}
            else:
                return {}
        
        return {
            ptype: [p.name for p in plugins]
            for ptype, plugins in self.plugins.items()
        }


# Global plugin manager instance
plugin_manager = PluginManager()


# Export classes and functions
__all__ = [
    'RateLimitPlugin',
    'PreRateLimitPlugin',
    'PostRateLimitPlugin',
    'StoragePlugin',
    'AnalyticsPlugin',
    'NotificationPlugin',
    'RedisStoragePlugin',
    'DatabaseStoragePlugin',
    'GeolocationPlugin',
    'UserBehaviorPlugin',
    'TimeBasedPlugin',
    'SlackNotificationPlugin',
    'EmailNotificationPlugin',
    'PluginManager',
    'plugin_manager'
]
