"""
Integration Registry - Service Registration and Discovery

Registry system for managing integration services, adapters, and handlers
with support for dynamic registration, discovery, and lifecycle management.
"""

import logging
import threading
from typing import Dict, Any, List, Optional, Callable, Type, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .integ_constants import IntegrationEvent, IntegrationStatus, IntegrationPriority
from .integ_exceptions import IntegrationError, IntegrationRegistrationError
from .integ_adapter import IntegrationAdapter, AdapterConfig, AdapterFactory

logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """Types of services in the registry."""
    ADAPTER = "adapter"
    HANDLER = "handler"
    MIDDLEWARE = "middleware"
    VALIDATOR = "validator"
    TRANSFORMER = "transformer"
    MONITOR = "monitor"


class ServiceStatus(Enum):
    """Service status in the registry."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    ERROR = "error"


@dataclass
class ServiceRegistration:
    """Service registration information."""
    name: str
    service_type: ServiceType
    service_class: Type
    config: Dict[str, Any] = field(default_factory=dict)
    status: ServiceStatus = ServiceStatus.ACTIVE
    priority: int = 0
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    registered_at: datetime = field(default_factory=timezone.now)
    last_used: Optional[datetime] = None
    usage_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceInstance:
    """Service instance information."""
    registration: ServiceRegistration
    instance: Any
    created_at: datetime = field(default_factory=timezone.now)
    last_health_check: Optional[datetime] = None
    health_status: str = "unknown"


class IntegrationRegistry:
    """Registry for managing integration services and components."""
    
    def __init__(self):
        self._services: Dict[str, ServiceRegistration] = {}
        self._instances: Dict[str, ServiceInstance] = {}
        self._lock = threading.RLock()
        self._health_check_interval = 300  # 5 minutes
        self._max_idle_time = timedelta(hours=1)
        self._initialize_default_services()
    
    def _initialize_default_services(self):
        """Initialize default integration services."""
        # Register default adapters
        self.register_adapter(
            name='default_webhook',
            adapter_class='WebhookAdapter',
            config={'timeout': 30, 'retry_attempts': 3},
            tags=['webhook', 'notification']
        )
        
        self.register_adapter(
            name='default_rest_api',
            adapter_class='RestAPIAdapter',
            config={'timeout': 30, 'retry_attempts': 3},
            tags=['api', 'rest']
        )
        
        # Register default handlers
        self.register_handler(
            name='rate_limit_handler',
            handler_class='RateLimitHandler',
            config={'priority': IntegrationPriority.NORMAL},
            tags=['rate_limit', 'core']
        )
        
        self.register_handler(
            name='abuse_detection_handler',
            handler_class='AbuseDetectionHandler',
            config={'priority': IntegrationPriority.HIGH},
            tags=['abuse', 'security']
        )
    
    def register_service(self, registration: ServiceRegistration) -> bool:
        """Register a service in the registry."""
        with self._lock:
            try:
                # Check if service already exists
                if registration.name in self._services:
                    logger.warning(f"Service already exists: {registration.name}")
                    return False
                
                # Validate dependencies
                for dependency in registration.dependencies:
                    if dependency not in self._services:
                        raise IntegrationRegistrationError(f"Dependency not found: {dependency}")
                
                # Register service
                self._services[registration.name] = registration
                
                logger.info(f"Registered service: {registration.name} ({registration.service_type.value})")
                return True
                
            except Exception as e:
                logger.error(f"Failed to register service {registration.name}: {str(e)}")
                raise IntegrationRegistrationError(f"Registration failed: {str(e)}")
    
    def register_adapter(self, name: str, adapter_class: Union[str, Type], 
                         config: Dict[str, Any] = None, tags: List[str] = None) -> bool:
        """Register an adapter service."""
        if isinstance(adapter_class, str):
            # Import class dynamically
            module_name, class_name = adapter_class.rsplit('.', 1)
            module = __import__(module_name, fromlist=[class_name])
            adapter_class = getattr(module, class_name)
        
        registration = ServiceRegistration(
            name=name,
            service_type=ServiceType.ADAPTER,
            service_class=adapter_class,
            config=config or {},
            tags=tags or []
        )
        
        return self.register_service(registration)
    
    def register_handler(self, name: str, handler_class: Union[str, Type],
                        config: Dict[str, Any] = None, tags: List[str] = None) -> bool:
        """Register a handler service."""
        if isinstance(handler_class, str):
            # Import class dynamically
            module_name, class_name = handler_class.rsplit('.', 1)
            module = __import__(module_name, fromlist=[class_name])
            handler_class = getattr(module, class_name)
        
        registration = ServiceRegistration(
            name=name,
            service_type=ServiceType.HANDLER,
            service_class=handler_class,
            config=config or {},
            tags=tags or []
        )
        
        return self.register_service(registration)
    
    def register_middleware(self, name: str, middleware_class: Union[str, Type],
                           config: Dict[str, Any] = None, tags: List[str] = None) -> bool:
        """Register a middleware service."""
        if isinstance(middleware_class, str):
            # Import class dynamically
            module_name, class_name = middleware_class.rsplit('.', 1)
            module = __import__(module_name, fromlist=[class_name])
            middleware_class = getattr(module, class_name)
        
        registration = ServiceRegistration(
            name=name,
            service_type=ServiceType.MIDDLEWARE,
            service_class=middleware_class,
            config=config or {},
            tags=tags or []
        )
        
        return self.register_service(registration)
    
    def unregister_service(self, name: str) -> bool:
        """Unregister a service from the registry."""
        with self._lock:
            if name in self._services:
                # Clean up instance if exists
                if name in self._instances:
                    del self._instances[name]
                
                del self._services[name]
                logger.info(f"Unregistered service: {name}")
                return True
            return False
    
    def get_service(self, name: str) -> Optional[ServiceRegistration]:
        """Get service registration by name."""
        return self._services.get(name)
    
    def get_instance(self, name: str) -> Optional[Any]:
        """Get service instance by name."""
        with self._lock:
            if name not in self._instances:
                # Create instance if not exists
                registration = self._services.get(name)
                if registration:
                    instance = self._create_instance(registration)
                    if instance:
                        self._instances[name] = instance
            else:
                # Update usage statistics
                instance_info = self._instances[name]
                instance_info.last_used = timezone.now()
                instance_info.registration.usage_count += 1
            
            return self._instances.get(name)
    
    def _create_instance(self, registration: ServiceRegistration) -> Optional[Any]:
        """Create service instance from registration."""
        try:
            if registration.service_type == ServiceType.ADAPTER:
                # Create adapter instance
                if registration.service_class == IntegrationAdapter:
                    # Create adapter config
                    adapter_config = AdapterConfig(
                        name=registration.name,
                        adapter_type=registration.config.get('adapter_type', 'rest_api'),
                        **registration.config
                    )
                    instance = AdapterFactory.create_adapter(adapter_config)
                else:
                    instance = registration.service_class(**registration.config)
            
            elif registration.service_type == ServiceType.HANDLER:
                instance = registration.service_class(**registration.config)
            
            elif registration.service_type == ServiceType.MIDDLEWARE:
                instance = registration.service_class(**registration.config)
            
            else:
                instance = registration.service_class(**registration.config)
            
            return ServiceInstance(
                registration=registration,
                instance=instance
            )
            
        except Exception as e:
            logger.error(f"Failed to create instance for {registration.name}: {str(e)}")
            return None
    
    def find_services(self, service_type: ServiceType = None, 
                     tags: List[str] = None, status: ServiceStatus = None) -> List[ServiceRegistration]:
        """Find services by type, tags, or status."""
        services = list(self._services.values())
        
        if service_type:
            services = [s for s in services if s.service_type == service_type]
        
        if tags:
            services = [s for s in services if any(tag in s.tags for tag in tags)]
        
        if status:
            services = [s for s in services if s.status == status]
        
        return services
    
    def get_services_by_event(self, event: IntegrationEvent) -> List[ServiceRegistration]:
        """Get services that handle specific events."""
        # Find handlers with event tag
        event_tag = event.value
        return self.find_services(
            service_type=ServiceType.HANDLER,
            tags=[event_tag]
        )
    
    def get_adapter_by_type(self, adapter_type: str) -> Optional[ServiceRegistration]:
        """Get adapter by type."""
        adapters = self.find_services(
            service_type=ServiceType.ADAPTER,
            tags=[adapter_type]
        )
        return adapters[0] if adapters else None
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all services."""
        health_status = {
            'total_services': len(self._services),
            'active_instances': len(self._instances),
            'services': {}
        }
        
        for name, instance_info in self._instances.items():
            try:
                # Basic health check - try to access the instance
                if hasattr(instance_info.instance, 'health_check'):
                    health = instance_info.instance.health_check()
                else:
                    health = {'status': 'ok', 'message': 'No health check method'}
                
                instance_info.last_health_check = timezone.now()
                instance_info.health_status = health.get('status', 'unknown')
                
                health_status['services'][name] = {
                    'status': health.get('status', 'unknown'),
                    'message': health.get('message', ''),
                    'last_check': instance_info.last_health_check.isoformat(),
                    'usage_count': instance_info.registration.usage_count
                }
                
            except Exception as e:
                instance_info.health_status = 'error'
                health_status['services'][name] = {
                    'status': 'error',
                    'message': str(e),
                    'last_check': timezone.now().isoformat(),
                    'usage_count': instance_info.registration.usage_count
                }
        
        return health_status
    
    def cleanup_idle_instances(self) -> int:
        """Clean up idle service instances."""
        with self._lock:
            current_time = timezone.now()
            instances_to_remove = []
            
            for name, instance_info in self._instances.items():
                if (instance_info.last_used and 
                    current_time - instance_info.last_used > self._max_idle_time):
                    instances_to_remove.append(name)
            
            for name in instances_to_remove:
                del self._instances[name]
                logger.info(f"Cleaned up idle instance: {name}")
            
            return len(instances_to_remove)
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        stats = {
            'total_services': len(self._services),
            'active_instances': len(self._instances),
            'services_by_type': {},
            'services_by_status': {},
            'most_used_services': [],
            'recently_registered': []
        }
        
        # Count by type
        for service_type in ServiceType:
            stats['services_by_type'][service_type.value] = len(
                [s for s in self._services.values() if s.service_type == service_type]
            )
        
        # Count by status
        for status in ServiceStatus:
            stats['services_by_status'][status.value] = len(
                [s for s in self._services.values() if s.status == status]
            )
        
        # Most used services
        most_used = sorted(
            self._services.values(),
            key=lambda s: s.usage_count,
            reverse=True
        )[:5]
        
        stats['most_used_services'] = [
            {
                'name': s.name,
                'type': s.service_type.value,
                'usage_count': s.usage_count,
                'last_used': s.last_used.isoformat() if s.last_used else None
            }
            for s in most_used
        ]
        
        # Recently registered
        recent = sorted(
            self._services.values(),
            key=lambda s: s.registered_at,
            reverse=True
        )[:5]
        
        stats['recently_registered'] = [
            {
                'name': s.name,
                'type': s.service_type.value,
                'registered_at': s.registered_at.isoformat()
            }
            for s in recent
        ]
        
        return stats
    
    def export_registry(self) -> Dict[str, Any]:
        """Export registry configuration."""
        export_data = {
            'services': {},
            'metadata': {
                'exported_at': timezone.now().isoformat(),
                'total_services': len(self._services),
                'version': '1.0'
            }
        }
        
        for name, registration in self._services.items():
            export_data['services'][name] = {
                'type': registration.service_type.value,
                'class': f"{registration.service_class.__module__}.{registration.service_class.__name__}",
                'config': registration.config,
                'status': registration.status.value,
                'priority': registration.priority,
                'dependencies': registration.dependencies,
                'tags': registration.tags,
                'metadata': registration.metadata
            }
        
        return export_data
    
    def import_registry(self, import_data: Dict[str, Any]) -> int:
        """Import registry configuration."""
        imported_count = 0
        
        for name, service_data in import_data.get('services', {}).items():
            try:
                # Parse service type
                service_type = ServiceType(service_data['type'])
                
                # Parse class
                module_name, class_name = service_data['class'].rsplit('.', 1)
                module = __import__(module_name, fromlist=[class_name])
                service_class = getattr(module, class_name)
                
                # Create registration
                registration = ServiceRegistration(
                    name=name,
                    service_type=service_type,
                    service_class=service_class,
                    config=service_data.get('config', {}),
                    status=ServiceStatus(service_data.get('status', 'active')),
                    priority=service_data.get('priority', 0),
                    dependencies=service_data.get('dependencies', []),
                    tags=service_data.get('tags', []),
                    metadata=service_data.get('metadata', {})
                )
                
                if self.register_service(registration):
                    imported_count += 1
                
            except Exception as e:
                logger.error(f"Failed to import service {name}: {str(e)}")
        
        logger.info(f"Imported {imported_count} services")
        return imported_count


# Global registry instance
integration_registry = IntegrationRegistry()
