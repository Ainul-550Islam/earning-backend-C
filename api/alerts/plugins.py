"""
Plugin system for alerts app - allows extending alert functionality
"""
import importlib
import inspect
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class AlertPlugin(ABC):
    """Base class for alert plugins"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = self.__class__.__name__
        self.enabled = self.config.get('enabled', True)
    
    @abstractmethod
    def get_plugin_info(self) -> Dict[str, Any]:
        """Return plugin information"""
        pass
    
    @abstractmethod
    def process_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process alert data"""
        pass
    
    def validate_config(self) -> bool:
        """Validate plugin configuration"""
        return True
    
    def initialize(self) -> bool:
        """Initialize plugin"""
        if not self.validate_config():
            logger.error(f"Invalid config for plugin {self.name}")
            return False
        
        logger.info(f"Initialized plugin: {self.name}")
        return True
    
    def cleanup(self):
        """Cleanup plugin resources"""
        logger.info(f"Cleaning up plugin: {self.name}")


class NotificationPlugin(AlertPlugin):
    """Base class for notification plugins"""
    
    @abstractmethod
    def send_notification(self, recipient: str, message: str, subject: str = None) -> bool:
        """Send notification to recipient"""
        pass
    
    @abstractmethod
    def get_supported_recipient_types(self) -> List[str]:
        """Return list of supported recipient types"""
        pass


class FilterPlugin(AlertPlugin):
    """Base class for filter plugins"""
    
    @abstractmethod
    def should_suppress_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Determine if alert should be suppressed"""
        pass
    
    @abstractmethod
    def get_filter_priority(self) -> int:
        """Return filter priority (higher = processed first)"""
        return 0


class AnalyticsPlugin(AlertPlugin):
    """Base class for analytics plugins"""
    
    @abstractmethod
    def process_analytics(self, analytics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process analytics data"""
        pass
    
    @abstractmethod
    def get_analytics_types(self) -> List[str]:
        """Return list of analytics types this plugin handles"""
        pass


class PluginManager:
    """Manages loading and execution of plugins"""
    
    def __init__(self):
        self.plugins: Dict[str, AlertPlugin] = {}
        self.notification_plugins: Dict[str, NotificationPlugin] = {}
        self.filter_plugins: List[FilterPlugin] = []
        self.analytics_plugins: Dict[str, AnalyticsPlugin] = {}
        
    def load_plugins(self):
        """Load all configured plugins"""
        plugin_configs = getattr(settings, 'ALERT_PLUGINS', {})
        
        for plugin_name, plugin_config in plugin_configs.items():
            try:
                plugin = self._load_plugin(plugin_name, plugin_config)
                if plugin:
                    self._register_plugin(plugin)
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_name}: {e}")
    
    def _load_plugin(self, plugin_name: str, config: Dict[str, Any]) -> Optional[AlertPlugin]:
        """Load a single plugin"""
        try:
            # Get plugin module and class
            module_path = config.get('module')
            class_name = config.get('class')
            
            if not module_path or not class_name:
                logger.error(f"Missing module or class for plugin {plugin_name}")
                return None
            
            # Import module
            module = importlib.import_module(module_path)
            plugin_class = getattr(module, class_name)
            
            # Create plugin instance
            plugin = plugin_class(config)
            
            # Initialize plugin
            if plugin.initialize():
                return plugin
            else:
                logger.error(f"Failed to initialize plugin {plugin_name}")
                return None
        
        except ImportError as e:
            logger.error(f"Could not import plugin {plugin_name}: {e}")
        except AttributeError as e:
            logger.error(f"Plugin class not found {plugin_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading plugin {plugin_name}: {e}")
        
        return None
    
    def _register_plugin(self, plugin: AlertPlugin):
        """Register a plugin"""
        self.plugins[plugin.name] = plugin
        
        # Register in specific categories
        if isinstance(plugin, NotificationPlugin):
            self.notification_plugins[plugin.name] = plugin
        elif isinstance(plugin, FilterPlugin):
            self.filter_plugins.append(plugin)
            # Sort by priority
            self.filter_plugins.sort(key=lambda p: p.get_filter_priority(), reverse=True)
        elif isinstance(plugin, AnalyticsPlugin):
            self.analytics_plugins[plugin.name] = plugin
        
        logger.info(f"Registered plugin: {plugin.name}")
    
    def get_plugin(self, name: str) -> Optional[AlertPlugin]:
        """Get plugin by name"""
        return self.plugins.get(name)
    
    def get_all_plugins(self) -> Dict[str, AlertPlugin]:
        """Get all plugins"""
        return self.plugins.copy()
    
    def get_enabled_plugins(self) -> Dict[str, AlertPlugin]:
        """Get all enabled plugins"""
        return {name: plugin for name, plugin in self.plugins.items() if plugin.enabled}
    
    def process_alert_with_filters(self, alert_data: Dict[str, Any]) -> bool:
        """Process alert through all filter plugins"""
        for plugin in self.filter_plugins:
            if plugin.enabled:
                try:
                    if plugin.should_suppress_alert(alert_data):
                        logger.info(f"Alert suppressed by plugin {plugin.name}")
                        return True
                except Exception as e:
                    logger.error(f"Error in filter plugin {plugin.name}: {e}")
        
        return False
    
    def send_notification_via_plugins(self, notification_type: str, recipient: str, message: str, subject: str = None) -> bool:
        """Send notification via appropriate plugins"""
        success = False
        
        for plugin in self.notification_plugins.values():
            if plugin.enabled and notification_type in plugin.get_supported_recipient_types():
                try:
                    if plugin.send_notification(recipient, message, subject):
                        success = True
                        logger.info(f"Notification sent via plugin {plugin.name}")
                except Exception as e:
                    logger.error(f"Error sending notification via plugin {plugin.name}: {e}")
        
        return success
    
    def process_analytics_via_plugins(self, analytics_type: str, analytics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process analytics via appropriate plugins"""
        processed_data = analytics_data.copy()
        
        for plugin in self.analytics_plugins.values():
            if plugin.enabled and analytics_type in plugin.get_analytics_types():
                try:
                    processed_data = plugin.process_analytics(processed_data)
                    logger.info(f"Analytics processed via plugin {plugin.name}")
                except Exception as e:
                    logger.error(f"Error processing analytics via plugin {plugin.name}: {e}")
        
        return processed_data
    
    def cleanup_all_plugins(self):
        """Cleanup all plugins"""
        for plugin in self.plugins.values():
            try:
                plugin.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up plugin {plugin.name}: {e}")


# Built-in plugins
class EmailNotificationPlugin(NotificationPlugin):
    """Email notification plugin"""
    
    def get_plugin_info(self) -> Dict[str, Any]:
        return {
            'name': 'Email Notification',
            'version': '1.0.0',
            'description': 'Send email notifications',
            'author': 'Alert System'
        }
    
    def send_notification(self, recipient: str, message: str, subject: str = None) -> bool:
        try:
            from django.core.mail import send_mail
            
            send_mail(
                subject=subject or 'Alert Notification',
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'alerts@example.com'),
                recipient_list=[recipient],
                fail_silently=False
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {e}")
            return False
    
    def get_supported_recipient_types(self) -> List[str]:
        return ['email']
    
    def validate_config(self) -> bool:
        required_settings = ['EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD']
        return all(hasattr(settings, setting) for setting in required_settings)


class SlackNotificationPlugin(NotificationPlugin):
    """Slack notification plugin"""
    
    def get_plugin_info(self) -> Dict[str, Any]:
        return {
            'name': 'Slack Notification',
            'version': '1.0.0',
            'description': 'Send Slack notifications',
            'author': 'Alert System'
        }
    
    def send_notification(self, recipient: str, message: str, subject: str = None) -> bool:
        try:
            import requests
            
            webhook_url = self.config.get('webhook_url')
            if not webhook_url:
                logger.error("Slack webhook URL not configured")
                return False
            
            payload = {
                'text': f"*{subject or 'Alert'}*\n{message}",
                'username': 'Alert System',
                'icon_emoji': ':warning:'
            }
            
            response = requests.post(webhook_url, json=payload, timeout=30)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False
    
    def get_supported_recipient_types(self) -> List[str]:
        return ['slack']
    
    def validate_config(self) -> bool:
        return bool(self.config.get('webhook_url'))


class TimeBasedFilterPlugin(FilterPlugin):
    """Time-based alert suppression plugin"""
    
    def get_plugin_info(self) -> Dict[str, Any]:
        return {
            'name': 'Time-based Filter',
            'version': '1.0.0',
            'description': 'Suppress alerts during specific time periods',
            'author': 'Alert System'
        }
    
    def should_suppress_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Check if alert should be suppressed based on time"""
        suppress_hours = self.config.get('suppress_hours', [])
        current_hour = timezone.now().hour
        
        return current_hour in suppress_hours
    
    def get_filter_priority(self) -> int:
        return 10


class RateLimitFilterPlugin(FilterPlugin):
    """Rate limiting filter plugin"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.alert_counts = {}
    
    def get_plugin_info(self) -> Dict[str, Any]:
        return {
            'name': 'Rate Limit Filter',
            'version': '1.0.0',
            'description': 'Limit alert frequency',
            'author': 'Alert System'
        }
    
    def should_suppress_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Check if alert should be suppressed due to rate limiting"""
        rule_id = alert_data.get('rule_id')
        max_alerts_per_hour = self.config.get('max_alerts_per_hour', 10)
        
        if not rule_id:
            return False
        
        current_time = timezone.now()
        hour_key = current_time.strftime('%Y-%m-%d-%H')
        
        if hour_key not in self.alert_counts:
            self.alert_counts[hour_key] = {}
        
        if rule_id not in self.alert_counts[hour_key]:
            self.alert_counts[hour_key][rule_id] = 0
        
        self.alert_counts[hour_key][rule_id] += 1
        
        return self.alert_counts[hour_key][rule_id] > max_alerts_per_hour
    
    def get_filter_priority(self) -> int:
        return 20


class BasicAnalyticsPlugin(AnalyticsPlugin):
    """Basic analytics plugin"""
    
    def get_plugin_info(self) -> Dict[str, Any]:
        return {
            'name': 'Basic Analytics',
            'version': '1.0.0',
            'description': 'Basic alert analytics processing',
            'author': 'Alert System'
        }
    
    def process_analytics(self, analytics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process basic analytics"""
        # Add basic statistics
        if 'alerts' in analytics_data:
            alerts = analytics_data['alerts']
            analytics_data['total_alerts'] = len(alerts)
            analytics_data['resolved_alerts'] = len([a for a in alerts if a.get('is_resolved')])
            analytics_data['resolution_rate'] = (
                analytics_data['resolved_alerts'] / analytics_data['total_alerts'] * 100
                if analytics_data['total_alerts'] > 0 else 0
            )
        
        return analytics_data
    
    def get_analytics_types(self) -> List[str]:
        return ['basic', 'summary']


# Global plugin manager instance
plugin_manager = PluginManager()


def initialize_plugins():
    """Initialize the plugin system"""
    plugin_manager.load_plugins()
    logger.info(f"Plugin system initialized with {len(plugin_manager.plugins)} plugins")


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance"""
    return plugin_manager


# Plugin decorator for easy registration
def alert_plugin(name: str, config: Dict[str, Any] = None):
    """Decorator to register a plugin"""
    def decorator(cls):
        plugin_instance = cls(config or {})
        plugin_manager._register_plugin(plugin_instance)
        return cls
    return decorator


# Hook for Django settings
def get_plugin_settings() -> Dict[str, Any]:
    """Get plugin settings from Django settings"""
    return getattr(settings, 'ALERT_PLUGINS', {})


# Plugin health check
def check_plugin_health() -> Dict[str, Any]:
    """Check health of all plugins"""
    health_status = {}
    
    for name, plugin in plugin_manager.plugins.items():
        try:
            health_status[name] = {
                'enabled': plugin.enabled,
                'configured': plugin.validate_config(),
                'info': plugin.get_plugin_info()
            }
        except Exception as e:
            health_status[name] = {
                'enabled': False,
                'configured': False,
                'error': str(e)
            }
    
    return health_status
