"""
Factory classes for alerts app
"""
from typing import Dict, Any, Optional, Type, List
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class AlertProcessorFactory:
    """Factory for creating alert processors"""
    
    _processors = {}
    
    @classmethod
    def register_processor(cls, name: str, processor_class: Type):
        """Register a processor class"""
        cls._processors[name] = processor_class
        logger.info(f"Registered processor: {name}")
    
    @classmethod
    def create_processor(cls, name: str, config: Dict[str, Any] = None) -> Optional[Any]:
        """Create processor instance"""
        if name not in cls._processors:
            logger.error(f"Unknown processor: {name}")
            return None
        
        processor_class = cls._processors[name]
        config = config or {}
        
        try:
            return processor_class(config)
        except Exception as e:
            logger.error(f"Error creating processor {name}: {e}")
            return None
    
    @classmethod
    def get_available_processors(cls) -> List[str]:
        """Get list of available processors"""
        return list(cls._processors.keys())
    
    @classmethod
    def get_processor_info(cls, name: str) -> Optional[Dict[str, Any]]:
        """Get processor information"""
        if name not in cls._processors:
            return None
        
        processor_class = cls._processors[name]
        if hasattr(processor_class, 'get_info'):
            try:
                return processor_class.get_info()
            except Exception as e:
                logger.error(f"Error getting processor info {name}: {e}")
                return None
        
        return {'name': name, 'class': processor_class.__name__}


class NotificationChannelFactory:
    """Factory for creating notification channels"""
    
    _channels = {}
    
    @classmethod
    def register_channel(cls, name: str, channel_class: Type):
        """Register a channel class"""
        cls._channels[name] = channel_class
        logger.info(f"Registered channel: {name}")
    
    @classmethod
    def create_channel(cls, name: str, config: Dict[str, Any] = None) -> Optional[Any]:
        """Create channel instance"""
        if name not in cls._channels:
            logger.error(f"Unknown channel: {name}")
            return None
        
        channel_class = cls._channels[name]
        config = config or {}
        
        try:
            return channel_class(config)
        except Exception as e:
            logger.error(f"Error creating channel {name}: {e}")
            return None
    
    @classmethod
    def get_available_channels(cls) -> List[str]:
        """Get list of available channels"""
        return list(cls._channels.keys())
    
    @classmethod
    def create_channels_from_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create multiple channels from configuration"""
        channels = {}
        
        for channel_name, channel_config in config.items():
            channel = cls.create_channel(channel_name, channel_config)
            if channel:
                channels[channel_name] = channel
        
        return channels


class FilterFactory:
    """Factory for creating alert filters"""
    
    _filters = {}
    
    @classmethod
    def register_filter(cls, name: str, filter_class: Type):
        """Register a filter class"""
        cls._filters[name] = filter_class
        logger.info(f"Registered filter: {name}")
    
    @classmethod
    def create_filter(cls, name: str, config: Dict[str, Any] = None) -> Optional[Any]:
        """Create filter instance"""
        if name not in cls._filters:
            logger.error(f"Unknown filter: {name}")
            return None
        
        filter_class = cls._filters[name]
        config = config or {}
        
        try:
            return filter_class(config)
        except Exception as e:
            logger.error(f"Error creating filter {name}: {e}")
            return None
    
    @classmethod
    def create_filter_chain(cls, filter_configs: List[Dict[str, Any]]) -> List[Any]:
        """Create a chain of filters"""
        filters = []
        
        for filter_config in filter_configs:
            filter_name = filter_config.get('name')
            filter_instance = cls.create_filter(filter_name, filter_config)
            if filter_instance:
                filters.append(filter_instance)
        
        return filters


class AnalyticsFactory:
    """Factory for creating analytics processors"""
    
    _analytics = {}
    
    @classmethod
    def register_analytics(cls, name: str, analytics_class: Type):
        """Register an analytics class"""
        cls._analytics[name] = analytics_class
        logger.info(f"Registered analytics: {name}")
    
    @classmethod
    def create_analytics(cls, name: str, config: Dict[str, Any] = None) -> Optional[Any]:
        """Create analytics instance"""
        if name not in cls._analytics:
            logger.error(f"Unknown analytics: {name}")
            return None
        
        analytics_class = cls._analytics[name]
        config = config or {}
        
        try:
            return analytics_class(config)
        except Exception as e:
            logger.error(f"Error creating analytics {name}: {e}")
            return None


class ReporterFactory:
    """Factory for creating reporters"""
    
    _reporters = {}
    
    @classmethod
    def register_reporter(cls, name: str, reporter_class: Type):
        """Register a reporter class"""
        cls._reporters[name] = reporter_class
        logger.info(f"Registered reporter: {name}")
    
    @classmethod
    def create_reporter(cls, name: str, config: Dict[str, Any] = None) -> Optional[Any]:
        """Create reporter instance"""
        if name not in cls._reporters:
            logger.error(f"Unknown reporter: {name}")
            return None
        
        reporter_class = cls._reporters[name]
        config = config or {}
        
        try:
            return reporter_class(config)
        except Exception as e:
            logger.error(f"Error creating reporter {name}: {e}")
            return None


class ValidatorFactory:
    """Factory for creating validators"""
    
    _validators = {}
    
    @classmethod
    def register_validator(cls, name: str, validator_class: Type):
        """Register a validator class"""
        cls._validators[name] = validator_class
        logger.info(f"Registered validator: {name}")
    
    @classmethod
    def create_validator(cls, name: str, config: Dict[str, Any] = None) -> Optional[Any]:
        """Create validator instance"""
        if name not in cls._validators:
            logger.error(f"Unknown validator: {name}")
            return None
        
        validator_class = cls._validators[name]
        config = config or {}
        
        try:
            return validator_class(config)
        except Exception as e:
            logger.error(f"Error creating validator {name}: {e}")
            return None


class ServiceFactory:
    """Factory for creating service instances"""
    
    _services = {}
    
    @classmethod
    def register_service(cls, name: str, service_class: Type):
        """Register a service class"""
        cls._services[name] = service_class
        logger.info(f"Registered service: {name}")
    
    @classmethod
    def create_service(cls, name: str, **kwargs) -> Optional[Any]:
        """Create service instance"""
        if name not in cls._services:
            logger.error(f"Unknown service: {name}")
            return None
        
        service_class = cls._services[name]
        
        try:
            return service_class(**kwargs)
        except Exception as e:
            logger.error(f"Error creating service {name}: {e}")
            return None
    
    @classmethod
    def get_service(cls, name: str) -> Optional[Any]:
        """Get service instance (singleton pattern)"""
        if name not in cls._services:
            return None
        
        if not hasattr(cls, f'_{name}_instance'):
            service_class = cls._services[name]
            instance = service_class()
            setattr(cls, f'_{name}_instance', instance)
            return instance
        
        return getattr(cls, f'_{name}_instance')


class TaskFactory:
    """Factory for creating background tasks"""
    
    _tasks = {}
    
    @classmethod
    def register_task(cls, name: str, task_func):
        """Register a task function"""
        cls._tasks[name] = task_func
        logger.info(f"Registered task: {name}")
    
    @classmethod
    def create_task(cls, name: str, **kwargs):
        """Create task instance"""
        if name not in cls._tasks:
            logger.error(f"Unknown task: {name}")
            return None
        
        task_func = cls._tasks[name]
        
        try:
            return task_func(**kwargs)
        except Exception as e:
            logger.error(f"Error creating task {name}: {e}")
            return None


class MiddlewareFactory:
    """Factory for creating middleware"""
    
    _middleware = {}
    
    @classmethod
    def register_middleware(cls, name: str, middleware_class: Type):
        """Register a middleware class"""
        cls._middleware[name] = middleware_class
        logger.info(f"Registered middleware: {name}")
    
    @classmethod
    def create_middleware(cls, name: str, **kwargs):
        """Create middleware instance"""
        if name not in cls._middleware:
            logger.error(f"Unknown middleware: {name}")
            return None
        
        middleware_class = cls._middleware[name]
        
        try:
            return middleware_class(**kwargs)
        except Exception as e:
            logger.error(f"Error creating middleware {name}: {e}")
            return None


class ConfigFactory:
    """Factory for creating configuration objects"""
    
    @staticmethod
    def create_alert_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create alert configuration from data"""
        default_config = {
            'enabled': True,
            'severity': 'medium',
            'threshold': 100.0,
            'time_window': 60,
            'cooldown': 30,
            'notifications': {
                'email': False,
                'sms': False,
                'webhook': False
            }
        }
        
        # Merge with provided config
        config = {**default_config, **config_data}
        
        # Validate configuration
        ConfigFactory._validate_alert_config(config)
        
        return config
    
    @staticmethod
    def create_notification_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create notification configuration from data"""
        default_config = {
            'enabled': True,
            'retry_count': 3,
            'timeout': 30,
            'rate_limit': 100,
            'batch_size': 50
        }
        
        config = {**default_config, **config_data}
        
        # Validate configuration
        ConfigFactory._validate_notification_config(config)
        
        return config
    
    @staticmethod
    def create_webhook_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create webhook configuration from data"""
        default_config = {
            'enabled': True,
            'url': '',
            'secret': '',
            'events': ['*'],
            'timeout': 30,
            'retry_count': 3,
            'headers': {}
        }
        
        config = {**default_config, **config_data}
        
        # Validate configuration
        ConfigFactory._validate_webhook_config(config)
        
        return config
    
    @staticmethod
    def _validate_alert_config(config: Dict[str, Any]):
        """Validate alert configuration"""
        required_fields = ['threshold', 'time_window']
        
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field: {field}")
        
        if config['threshold'] <= 0:
            raise ValueError("Threshold must be positive")
        
        if config['time_window'] <= 0:
            raise ValueError("Time window must be positive")
    
    @staticmethod
    def _validate_notification_config(config: Dict[str, Any]):
        """Validate notification configuration"""
        if config.get('retry_count', 0) < 0:
            raise ValueError("Retry count must be non-negative")
        
        if config.get('timeout', 0) <= 0:
            raise ValueError("Timeout must be positive")
        
        if config.get('rate_limit', 0) <= 0:
            raise ValueError("Rate limit must be positive")
    
    @staticmethod
    def _validate_webhook_config(config: Dict[str, Any]):
        """Validate webhook configuration"""
        if not config.get('url'):
            raise ValueError("Webhook URL is required")
        
        if config.get('timeout', 0) <= 0:
            raise ValueError("Timeout must be positive")


class ModelFactory:
    """Factory for creating model instances"""
    
    @staticmethod
    def create_alert_rule(**kwargs) -> Optional[Any]:
        """Create AlertRule instance"""
        try:
            from .models import AlertRule
            return AlertRule.objects.create(**kwargs)
        except Exception as e:
            logger.error(f"Error creating AlertRule: {e}")
            return None
    
    @staticmethod
    def create_alert_log(**kwargs) -> Optional[Any]:
        """Create AlertLog instance"""
        try:
            from .models import AlertLog
            return AlertLog.objects.create(**kwargs)
        except Exception as e:
            logger.error(f"Error creating AlertLog: {e}")
            return None
    
    @staticmethod
    def create_notification(**kwargs) -> Optional[Any]:
        """Create Notification instance"""
        try:
            from .models import Notification
            return Notification.objects.create(**kwargs)
        except Exception as e:
            logger.error(f"Error creating Notification: {e}")
            return None


class ResponseFactory:
    """Factory for creating API responses"""
    
    @staticmethod
    def success_response(data: Any = None, message: str = "Success") -> Dict[str, Any]:
        """Create success response"""
        return {
            'success': True,
            'message': message,
            'data': data,
            'timestamp': timezone.now().isoformat()
        }
    
    @staticmethod
    def error_response(message: str, error_code: str = None, details: Any = None) -> Dict[str, Any]:
        """Create error response"""
        response = {
            'success': False,
            'message': message,
            'timestamp': timezone.now().isoformat()
        }
        
        if error_code:
            response['error_code'] = error_code
        
        if details:
            response['details'] = details
        
        return response
    
    @staticmethod
    def paginated_response(data: List[Any], page: int, per_page: int, total: int) -> Dict[str, Any]:
        """Create paginated response"""
        total_pages = (total + per_page - 1) // per_page
        
        return {
            'success': True,
            'data': data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            },
            'timestamp': timezone.now().isoformat()
        }


class ComponentFactory:
    """Generic factory for creating components"""
    
    _components = {}
    
    @classmethod
    def register_component(cls, category: str, name: str, component_class: Type):
        """Register a component"""
        if category not in cls._components:
            cls._components[category] = {}
        
        cls._components[category][name] = component_class
        logger.info(f"Registered component {category}.{name}")
    
    @classmethod
    def create_component(cls, category: str, name: str, **kwargs):
        """Create component instance"""
        if category not in cls._components or name not in cls._components[category]:
            logger.error(f"Unknown component: {category}.{name}")
            return None
        
        component_class = cls._components[category][name]
        
        try:
            return component_class(**kwargs)
        except Exception as e:
            logger.error(f"Error creating component {category}.{name}: {e}")
            return None
    
    @classmethod
    def get_components_by_category(cls, category: str) -> Dict[str, Type]:
        """Get all components in a category"""
        return cls._components.get(category, {})
    
    @classmethod
    def get_all_components(cls) -> Dict[str, Dict[str, Type]]:
        """Get all registered components"""
        return cls._components.copy()


# Auto-registration from settings
def register_factories_from_settings():
    """Register components from Django settings"""
    from django.conf import settings
    
    # Register processors
    processors = getattr(settings, 'ALERT_PROCESSORS', {})
    for name, processor_class in processors.items():
        AlertProcessorFactory.register_processor(name, processor_class)
    
    # Register channels
    channels = getattr(settings, 'ALERT_CHANNELS', {})
    for name, channel_class in channels.items():
        NotificationChannelFactory.register_channel(name, channel_class)
    
    # Register filters
    filters = getattr(settings, 'ALERT_FILTERS', {})
    for name, filter_class in filters.items():
        FilterFactory.register_filter(name, filter_class)
    
    # Register analytics
    analytics = getattr(settings, 'ALERT_ANALYTICS', {})
    for name, analytics_class in analytics.items():
        AnalyticsFactory.register_analytics(name, analytics_class)
    
    # Register reporters
    reporters = getattr(settings, 'ALERT_REPORTERS', {})
    for name, reporter_class in reporters.items():
        ReporterFactory.register_reporter(name, reporter_class)
    
    # Register validators
    validators = getattr(settings, 'ALERT_VALIDATORS', {})
    for name, validator_class in validators.items():
        ValidatorFactory.register_validator(name, validator_class)
    
    # Register services
    services = getattr(settings, 'ALERT_SERVICES', {})
    for name, service_class in services.items():
        ServiceFactory.register_service(name, service_class)
    
    # Register tasks
    tasks = getattr(settings, 'ALERT_TASKS', {})
    for name, task_func in tasks.items():
        TaskFactory.register_task(name, task_func)
    
    # Register middleware
    middleware = getattr(settings, 'ALERT_MIDDLEWARE', {})
    for name, middleware_class in middleware.items():
        MiddlewareFactory.register_middleware(name, middleware_class)
    
    logger.info("Factories registered from settings")


# Initialize factories on import
try:
    register_factories_from_settings()
except Exception as e:
    logger.error(f"Error registering factories: {e}")
