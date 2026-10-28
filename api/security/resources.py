"""
Security Resources Module
Resource management and configuration for security operations
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model

from .registry import security_registry, ComponentType
from .utils import SecurityUtils

User = get_user_model()
logger = logging.getLogger('security.resources')


class ResourceType(Enum):
    """Types of security resources"""
    DATABASE = 'database'
    CACHE = 'cache'
    STORAGE = 'storage'
    NETWORK = 'network'
    MEMORY = 'memory'
    CPU = 'cpu'
    API = 'api'
    WEBHOOK = 'webhook'
    EMAIL = 'email'
    SMS = 'sms'
    FILESYSTEM = 'filesystem'
    LOG = 'log'
    MONITORING = 'monitoring'
    BACKUP = 'backup'
    ENCRYPTION = 'encryption'
    AUTHENTICATION = 'authentication'
    AUTHORIZATION = 'authorization'


class ResourceStatus(Enum):
    """Resource status"""
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    ERROR = 'error'
    MAINTENANCE = 'maintenance'
    DEGRADED = 'degraded'
    UNKNOWN = 'unknown'


@dataclass
class ResourceConfig:
    """Configuration for a security resource"""
    name: str
    resource_type: ResourceType
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 100
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    health_check_interval: int = 300  # 5 minutes
    retry_attempts: int = 3
    retry_delay: int = 60
    timeout: int = 30
    
    def __post_init__(self):
        """Validate resource configuration"""
        if not self.name:
            raise ValueError("Resource name cannot be empty")
        if not self.resource_type:
            raise ValueError("Resource type is required")


@dataclass
class ResourceMetrics:
    """Resource metrics"""
    name: str
    status: ResourceStatus
    last_check: timezone.datetime
    response_time: Optional[float] = None
    error_count: int = 0
    success_count: int = 0
    availability_percentage: float = 100.0
    custom_metrics: Dict[str, Any] = field(default_factory=dict)
    
    def update_status(self, status: ResourceStatus, response_time: Optional[float] = None):
        """Update resource status"""
        self.status = status
        self.last_check = timezone.now()
        self.response_time = response_time
        
        if status == ResourceStatus.ACTIVE:
            self.success_count += 1
        else:
            self.error_count += 1
        
        # Calculate availability
        total_checks = self.success_count + self.error_count
        if total_checks > 0:
            self.availability_percentage = (self.success_count / total_checks) * 100


class SecurityResource:
    """Base class for security resources"""
    
    def __init__(self, config: ResourceConfig):
        self.config = config
        self.metrics = ResourceMetrics(
            name=config.name,
            status=ResourceStatus.UNKNOWN,
            last_check=timezone.now()
        )
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize the resource"""
        try:
            if self._initialize():
                self._initialized = True
                self.metrics.update_status(ResourceStatus.ACTIVE)
                logger.info(f"Resource {self.config.name} initialized successfully")
                return True
            else:
                self.metrics.update_status(ResourceStatus.ERROR)
                logger.error(f"Failed to initialize resource {self.config.name}")
                return False
        except Exception as e:
            self.metrics.update_status(ResourceStatus.ERROR)
            logger.error(f"Error initializing resource {self.config.name}: {e}")
            return False
    
    def _initialize(self) -> bool:
        """Override in subclasses"""
        return True
    
    def health_check(self) -> bool:
        """Perform health check"""
        try:
            if not self._initialized:
                return False
            
            start_time = timezone.now()
            is_healthy = self._health_check()
            response_time = (timezone.now() - start_time).total_seconds()
            
            if is_healthy:
                self.metrics.update_status(ResourceStatus.ACTIVE, response_time)
            else:
                self.metrics.update_status(ResourceStatus.ERROR, response_time)
            
            return is_healthy
            
        except Exception as e:
            logger.error(f"Health check failed for resource {self.config.name}: {e}")
            self.metrics.update_status(ResourceStatus.ERROR)
            return False
    
    def _health_check(self) -> bool:
        """Override in subclasses"""
        return True
    
    def cleanup(self) -> bool:
        """Cleanup resource"""
        try:
            if self._cleanup():
                self._initialized = False
                self.metrics.update_status(ResourceStatus.INACTIVE)
                logger.info(f"Resource {self.config.name} cleaned up successfully")
                return True
            else:
                logger.error(f"Failed to cleanup resource {self.config.name}")
                return False
        except Exception as e:
            logger.error(f"Error cleaning up resource {self.config.name}: {e}")
            return False
    
    def _cleanup(self) -> bool:
        """Override in subclasses"""
        return True
    
    def get_info(self) -> Dict[str, Any]:
        """Get resource information"""
        return {
            'name': self.config.name,
            'type': self.config.resource_type.value,
            'enabled': self.config.enabled,
            'status': self.metrics.status.value,
            'last_check': self.metrics.last_check.isoformat(),
            'response_time': self.metrics.response_time,
            'availability': self.metrics.availability_percentage,
            'error_count': self.metrics.error_count,
            'success_count': self.metrics.success_count,
            'metadata': self.config.metadata,
            'custom_metrics': self.metrics.custom_metrics,
        }


class DatabaseResource(SecurityResource):
    """Database resource"""
    
    def _initialize(self) -> bool:
        """Initialize database connection"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    def _health_check(self) -> bool:
        """Check database health"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except Exception:
            return False
    
    def _cleanup(self) -> bool:
        """Cleanup database connections"""
        try:
            from django.db import connection
            connection.close()
            return True
        except Exception:
            return False


class CacheResource(SecurityResource):
    """Cache resource"""
    
    def _initialize(self) -> bool:
        """Initialize cache connection"""
        try:
            cache.set('health_check', 'ok', 10)
            cache.get('health_check')
            return True
        except Exception:
            return False
    
    def _health_check(self) -> bool:
        """Check cache health"""
        try:
            test_key = f"health_check_{timezone.now().timestamp()}"
            cache.set(test_key, 'ok', 10)
            result = cache.get(test_key)
            cache.delete(test_key)
            return result == 'ok'
        except Exception:
            return False


class StorageResource(SecurityResource):
    """Storage resource"""
    
    def _initialize(self) -> bool:
        """Initialize storage"""
        try:
            # Check if storage is accessible
            import os
            storage_path = self.config.config.get('path', '/tmp')
            return os.path.exists(storage_path) and os.access(storage_path, os.W_OK)
        except Exception:
            return False
    
    def _health_check(self) -> bool:
        """Check storage health"""
        try:
            import os
            storage_path = self.config.config.get('path', '/tmp')
            test_file = os.path.join(storage_path, 'health_check.tmp')
            
            # Write test
            with open(test_file, 'w') as f:
                f.write('health_check')
            
            # Read test
            with open(test_file, 'r') as f:
                content = f.read()
            
            # Cleanup
            os.remove(test_file)
            
            return content == 'health_check'
        except Exception:
            return False


class APIResource(SecurityResource):
    """API resource"""
    
    def _initialize(self) -> bool:
        """Initialize API connection"""
        try:
            url = self.config.config.get('url')
            if not url:
                return False
            
            import requests
            response = requests.get(f"{url}/health", timeout=self.config.timeout)
            return response.status_code == 200
        except Exception:
            return False
    
    def _health_check(self) -> bool:
        """Check API health"""
        try:
            url = self.config.config.get('url')
            if not url:
                return False
            
            import requests
            response = requests.get(f"{url}/health", timeout=self.config.timeout)
            return response.status_code == 200
        except Exception:
            return False


class WebhookResource(SecurityResource):
    """Webhook resource"""
    
    def _initialize(self) -> bool:
        """Initialize webhook"""
        try:
            url = self.config.config.get('url')
            return bool(url)
        except Exception:
            return False
    
    def _health_check(self) -> bool:
        """Check webhook health"""
        try:
            url = self.config.config.get('url')
            if not url:
                return False
            
            import requests
            response = requests.post(
                url,
                json={'test': 'health_check'},
                timeout=self.config.timeout
            )
            return response.status_code in [200, 201, 202]
        except Exception:
            return False


class EmailResource(SecurityResource):
    """Email resource"""
    
    def _initialize(self) -> bool:
        """Initialize email service"""
        try:
            from django.core.mail import send_mail
            # Test email configuration
            return bool(settings.EMAIL_HOST and settings.EMAIL_PORT)
        except Exception:
            return False
    
    def _health_check(self) -> bool:
        """Check email service health"""
        try:
            from django.core.mail import get_connection
            connection = get_connection()
            connection.open()
            connection.close()
            return True
        except Exception:
            return False


class SMSResource(SecurityResource):
    """SMS resource"""
    
    def _initialize(self) -> bool:
        """Initialize SMS service"""
        try:
            # Check SMS configuration
            return bool(self.config.config.get('provider') and self.config.config.get('api_key'))
        except Exception:
            return False
    
    def _health_check(self) -> bool:
        """Check SMS service health"""
        try:
            # This would depend on the SMS provider
            provider = self.config.config.get('provider')
            if provider == 'twilio':
                return self._check_twilio_health()
            # Add other providers as needed
            return False
        except Exception:
            return False
    
    def _check_twilio_health(self) -> bool:
        """Check Twilio health"""
        try:
            from twilio.rest import Client
            account_sid = self.config.config.get('account_sid')
            auth_token = self.config.config.get('auth_token')
            
            client = Client(account_sid, auth_token)
            client.api.accounts(account_sid).fetch()
            return True
        except Exception:
            return False


class MonitoringResource(SecurityResource):
    """Monitoring resource"""
    
    def _initialize(self) -> bool:
        """Initialize monitoring"""
        try:
            # Check monitoring configuration
            return bool(self.config.config.get('service'))
        except Exception:
            return False
    
    def _health_check(self) -> bool:
        """Check monitoring service health"""
        try:
            service = self.config.config.get('service')
            if service == 'prometheus':
                return self._check_prometheus_health()
            elif service == 'grafana':
                return self._check_grafana_health()
            return False
        except Exception:
            return False
    
    def _check_prometheus_health(self) -> bool:
        """Check Prometheus health"""
        try:
            import requests
            url = self.config.config.get('url')
            response = requests.get(f"{url}/-/healthy", timeout=self.config.timeout)
            return response.status_code == 200
        except Exception:
            return False
    
    def _check_grafana_health(self) -> bool:
        """Check Grafana health"""
        try:
            import requests
            url = self.config.config.get('url')
            response = requests.get(f"{url}/api/health", timeout=self.config.timeout)
            return response.status_code == 200
        except Exception:
            return False


class ResourceRegistry:
    """Registry for security resources"""
    
    def __init__(self):
        self._resources: Dict[str, SecurityResource] = {}
        self._type_index: Dict[ResourceType, List[SecurityResource]] = {}
        self._status_index: Dict[ResourceStatus, List[SecurityResource]] = {}
    
    def register(self, resource: SecurityResource) -> None:
        """Register a security resource"""
        try:
            # Check for conflicts
            if resource.config.name in self._resources:
                logger.warning(f"Resource {resource.config.name} already registered, updating...")
            
            # Add to main registry
            self._resources[resource.config.name] = resource
            
            # Update type index
            if resource.config.resource_type not in self._type_index:
                self._type_index[resource.config.resource_type] = []
            self._type_index[resource.config.resource_type].append(resource)
            
            # Update status index
            if resource.metrics.status not in self._status_index:
                self._status_index[resource.metrics.status] = []
            self._status_index[resource.metrics.status].append(resource)
            
            logger.info(f"Registered resource: {resource.config.name}")
            
        except Exception as e:
            logger.error(f"Failed to register resource {resource.config.name}: {e}")
            raise
    
    def unregister(self, name: str) -> bool:
        """Unregister a security resource"""
        try:
            if name not in self._resources:
                logger.warning(f"Resource {name} not found in registry")
                return False
            
            resource = self._resources[name]
            
            # Remove from main registry
            del self._resources[name]
            
            # Remove from type index
            if resource.config.resource_type in self._type_index:
                self._type_index[resource.config.resource_type] = [
                    res for res in self._type_index[resource.config.resource_type]
                    if res.config.name != name
                ]
            
            # Remove from status index
            if resource.metrics.status in self._status_index:
                self._status_index[resource.metrics.status] = [
                    res for res in self._status_index[resource.metrics.status]
                    if res.config.name != name
                ]
            
            logger.info(f"Unregistered resource: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister resource {name}: {e}")
            return False
    
    def get_resource(self, name: str) -> Optional[SecurityResource]:
        """Get resource by name"""
        return self._resources.get(name)
    
    def get_resources_by_type(self, resource_type: ResourceType) -> List[SecurityResource]:
        """Get all resources of a specific type"""
        return self._type_index.get(resource_type, [])
    
    def get_resources_by_status(self, status: ResourceStatus) -> List[SecurityResource]:
        """Get all resources with a specific status"""
        return self._status_index.get(status, [])
    
    def get_enabled_resources(self) -> Dict[str, SecurityResource]:
        """Get all enabled resources"""
        return {
            name: resource for name, resource in self._resources.items()
            if resource.config.enabled
        }
    
    def initialize_all(self) -> Dict[str, bool]:
        """Initialize all enabled resources"""
        results = {}
        
        for name, resource in self.get_enabled_resources().items():
            try:
                results[name] = resource.initialize()
            except Exception as e:
                logger.error(f"Error initializing resource {name}: {e}")
                results[name] = False
        
        return results
    
    def health_check_all(self) -> Dict[str, bool]:
        """Perform health check on all enabled resources"""
        results = {}
        
        for name, resource in self.get_enabled_resources().items():
            try:
                results[name] = resource.health_check()
            except Exception as e:
                logger.error(f"Error health checking resource {name}: {e}")
                results[name] = False
        
        return results
    
    def cleanup_all(self) -> Dict[str, bool]:
        """Cleanup all resources"""
        results = {}
        
        for name, resource in self._resources.items():
            try:
                results[name] = resource.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up resource {name}: {e}")
                results[name] = False
        
        return results
    
    def get_resource_info(self) -> Dict[str, Any]:
        """Get registry information"""
        return {
            'total_resources': len(self._resources),
            'enabled_resources': len(self.get_enabled_resources()),
            'resources_by_type': {
                resource_type.value: len(resources)
                for resource_type, resources in self._type_index.items()
            },
            'resources_by_status': {
                status.value: len(resources)
                for status, resources in self._status_index.items()
            },
            'resource_details': {
                name: resource.get_info()
                for name, resource in self._resources.items()
            }
        }


class ResourceManager:
    """Manager for security resources"""
    
    def __init__(self):
        self.registry = ResourceRegistry()
        self.health_check_interval = 300  # 5 minutes
        self._health_check_task = None
    
    def create_resource(self, config: ResourceConfig) -> SecurityResource:
        """Create resource based on type"""
        resource_classes = {
            ResourceType.DATABASE: DatabaseResource,
            ResourceType.CACHE: CacheResource,
            ResourceType.STORAGE: StorageResource,
            ResourceType.API: APIResource,
            ResourceType.WEBHOOK: WebhookResource,
            ResourceType.EMAIL: EmailResource,
            ResourceType.SMS: SMSResource,
            ResourceType.MONITORING: MonitoringResource,
        }
        
        resource_class = resource_classes.get(config.resource_type, SecurityResource)
        return resource_class(config)
    
    def register_from_config(self, configs: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Register resources from configuration"""
        results = {}
        
        for config_dict in configs:
            try:
                # Convert dict to ResourceConfig
                resource_type = ResourceType(config_dict['type'])
                config = ResourceConfig(
                    name=config_dict['name'],
                    resource_type=resource_type,
                    config=config_dict.get('config', {}),
                    enabled=config_dict.get('enabled', True),
                    priority=config_dict.get('priority', 100),
                    dependencies=config_dict.get('dependencies', []),
                    metadata=config_dict.get('metadata', {}),
                    health_check_interval=config_dict.get('health_check_interval', 300),
                    retry_attempts=config_dict.get('retry_attempts', 3),
                    retry_delay=config_dict.get('retry_delay', 60),
                    timeout=config_dict.get('timeout', 30)
                )
                
                # Create and register resource
                resource = self.create_resource(config)
                self.registry.register(resource)
                results[config.name] = True
                
            except Exception as e:
                logger.error(f"Failed to register resource {config_dict.get('name', 'unknown')}: {e}")
                results[config_dict.get('name', 'unknown')] = False
        
        return results
    
    def start_health_monitoring(self):
        """Start health monitoring task"""
        if self._health_check_task:
            return  # Already running
        
        # This would typically be implemented with Celery or another task queue
        logger.info("Health monitoring started")
    
    def stop_health_monitoring(self):
        """Stop health monitoring task"""
        if self._health_check_task:
            # Cancel the task
            self._health_check_task = None
            logger.info("Health monitoring stopped")


# Global resource manager
resource_manager = ResourceManager()


# Built-in resource configurations
def get_default_resource_configs() -> List[Dict[str, Any]]:
    """Get default resource configurations"""
    return [
        {
            'name': 'database',
            'type': 'database',
            'enabled': True,
            'config': {},
            'priority': 100,
        },
        {
            'name': 'cache',
            'type': 'cache',
            'enabled': True,
            'config': {},
            'priority': 90,
        },
        {
            'name': 'storage',
            'type': 'storage',
            'enabled': True,
            'config': {
                'path': getattr(settings, 'MEDIA_ROOT', '/tmp')
            },
            'priority': 80,
        },
        {
            'name': 'email',
            'type': 'email',
            'enabled': bool(settings.EMAIL_HOST),
            'config': {},
            'priority': 70,
        },
    ]


# Initialize default resources
def initialize_default_resources():
    """Initialize default security resources"""
    configs = get_default_resource_configs()
    resource_manager.register_from_config(configs)
    
    # Initialize all resources
    results = resource_manager.registry.initialize_all()
    
    logger.info(f"Default resources initialized: {sum(results.values())}/{len(results)} successful")


# Export classes and utilities
__all__ = [
    'ResourceType',
    'ResourceStatus',
    'ResourceConfig',
    'ResourceMetrics',
    'SecurityResource',
    'DatabaseResource',
    'CacheResource',
    'StorageResource',
    'APIResource',
    'WebhookResource',
    'EmailResource',
    'SMSResource',
    'MonitoringResource',
    'ResourceRegistry',
    'ResourceManager',
    'resource_manager',
    'get_default_resource_configs',
    'initialize_default_resources'
]