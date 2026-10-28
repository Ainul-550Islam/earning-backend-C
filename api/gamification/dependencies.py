"""
Gamification Dependencies — Dependency management and service locator.

This module provides dependency injection and service locator patterns
for the gamification system, enabling better testability and modularity.
"""

from __future__ import annotations
from django.utils import timezone

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, Callable
from functools import wraps
from contextlib import contextmanager
from dataclasses import dataclass

from api.gamification.exceptions import GamificationServiceError

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceLocator:
    """Service locator for dependency injection."""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
    
    def register(self, name: str, service: Any, singleton: bool = False) -> None:
        """Register a service instance."""
        if singleton:
            self._singletons[name] = service
        else:
            self._services[name] = service
        self.logger.debug(f"Registered service: {name}")
    
    def register_factory(self, name: str, factory: Callable, singleton: bool = False) -> None:
        """Register a service factory."""
        self._factories[name] = (factory, singleton)
        self.logger.debug(f"Registered factory: {name}")
    
    def get(self, name: str) -> Any:
        """Get a service instance."""
        # Check singletons first
        if name in self._singletons:
            return self._singletons[name]
        
        # Check registered services
        if name in self._services:
            return self._services[name]
        
        # Check factories
        if name in self._factories:
            factory, is_singleton = self._factories[name]
            service = factory()
            if is_singleton:
                self._singletons[name] = service
            return service
        
        raise GamificationServiceError(f"Service not found: {name}")
    
    def has(self, name: str) -> bool:
        """Check if a service is registered."""
        return name in self._services or name in self._factories or name in self._singletons
    
    def clear(self) -> None:
        """Clear all registered services."""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()
        self.logger.info("Cleared all services")
    
    def list_services(self) -> List[str]:
        """List all registered service names."""
        return list(self._services.keys()) + list(self._factories.keys()) + list(self._singletons.keys())


# Global service locator
service_locator = ServiceLocator()


class DependencyContainer:
    """Dependency container with scope management."""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._parent: Optional[DependencyContainer] = None
        self.logger = logging.getLogger(__name__)
    
    def __init__(self, parent: Optional[DependencyContainer] = None):
        self._services: Dict[str, Any] = {}
        self._parent = parent
        self.logger = logging.getLogger(__name__)
    
    def register(self, name: str, service: Any) -> None:
        """Register a service in this container."""
        self._services[name] = service
        self.logger.debug(f"Registered service in container: {name}")
    
    def get(self, name: str) -> Any:
        """Get a service from this container or parent."""
        if name in self._services:
            return self._services[name]
        
        if self._parent:
            return self._parent.get(name)
        
        raise GamificationServiceError(f"Service not found: {name}")
    
    def has(self, name: str) -> bool:
        """Check if service exists in this container or parent."""
        return name in self._services or (self._parent and self._parent.has(name))
    
    def create_child(self) -> DependencyContainer:
        """Create a child container."""
        return DependencyContainer(self)


@dataclass
class ServiceDefinition:
    """Service definition metadata."""
    name: str
    interface: Type
    implementation: Type
    singleton: bool = True
    dependencies: List[str] = None
    factory: Optional[Callable] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class ServiceRegistry:
    """Service registry for managing service definitions."""
    
    def __init__(self):
        self._definitions: Dict[str, ServiceDefinition] = {}
        self._instances: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_service(self, definition: ServiceDefinition) -> None:
        """Register a service definition."""
        self._definitions[definition.name] = definition
        self.logger.debug(f"Registered service definition: {definition.name}")
    
    def get_service(self, name: str) -> Any:
        """Get a service instance."""
        if name not in self._definitions:
            raise GamificationServiceError(f"Service definition not found: {name}")
        
        definition = self._definitions[name]
        
        # Check if singleton and already instantiated
        if definition.singleton and name in self._instances:
            return self._instances[name]
        
        # Create instance
        instance = self._create_instance(definition)
        
        # Store singleton instances
        if definition.singleton:
            self._instances[name] = instance
        
        return instance
    
    def _create_instance(self, definition: ServiceDefinition) -> Any:
        """Create a service instance."""
        try:
            # Use factory if provided
            if definition.factory:
                return definition.factory()
            
            # Resolve dependencies
            dependencies = []
            for dep_name in definition.dependencies:
                dependencies.append(self.get_service(dep_name))
            
            # Create instance
            if dependencies:
                return definition.implementation(*dependencies)
            else:
                return definition.implementation()
                
        except Exception as e:
            self.logger.error(f"Error creating service {definition.name}: {e}")
            raise GamificationServiceError(f"Failed to create service {definition.name}: {e}")
    
    def has_service(self, name: str) -> bool:
        """Check if service is registered."""
        return name in self._definitions
    
    def clear_instances(self) -> None:
        """Clear all service instances."""
        self._instances.clear()
        self.logger.info("Cleared all service instances")


# Global service registry
service_registry = ServiceRegistry()


class ServiceProvider(ABC):
    """Abstract base class for service providers."""
    
    @abstractmethod
    def register_services(self, container: ServiceLocator) -> None:
        """Register services with the container."""
        pass


class GamificationServiceProvider(ServiceProvider):
    """Gamification service provider."""
    
    def register_services(self, container: ServiceLocator) -> None:
        """Register gamification services."""
        try:
            # Import here to avoid circular imports
            from api.gamification.repositories import (
                BadgeRepository, UserBadgeRepository, StreakRepository,
                UserAchievementRepository, WebhookDeliveryRepository,
                UserPointsRepository, PointsTransactionRepository, StreakFreezeRepository,
                ContestParticipantRepository, GamificationConfigRepository, GamificationInsightRepository
            )
            from api.gamification.interactors import (
                BadgeInteractor, StreakInteractor, ChallengeInteractor,
                LevelInteractor, ContestInteractor, GamificationInteractor,
                UserPointsInteractor, PointsTransactionInteractor, StreakFreezeInteractor,
                ContestParticipantInteractor, GamificationConfigInteractor, GamificationInsightInteractor
            )
            from api.gamification.helpers import (
                BadgeHelper, StreakHelper, ChallengeHelper,
                LeaderboardHelper, CacheHelper
            )
            from api.gamification.analytics import (
                analytics_tracker, UserAnalytics, SystemAnalytics, ReportGenerator
            )
            from api.gamification.caching import (
                gamification_cache, cache_warmer, cache_invalidator
            )
            from api.gamification.encryption import (
                encryption_provider, hash_provider, token_generator,
                secure_data_handler, data_masking, security_audit_logger
            )
            from api.gamification.background_jobs import (
                background_job_manager
            )
            from api.gamification.webhooks import (
                WebhookService
            )
            from api.gamification.notifications_push import (
                push_notification_service
            )
            from api.gamification.monitoring import (
                monitoring_service
            )
            from api.gamification.compliance import (
                compliance_manager
            )
            
            # Register repositories
            container.register('badge_repository', BadgeRepository(), singleton=True)
            container.register('user_badge_repository', UserBadgeRepository(), singleton=True)
            container.register('streak_repository', StreakRepository(), singleton=True)
            container.register('user_achievement_repository', UserAchievementRepository(), singleton=True)
            container.register('webhook_delivery_repository', WebhookDeliveryRepository(), singleton=True)
            
            # Register new repositories for enhanced gamification models
            container.register('user_points_repository', UserPointsRepository(), singleton=True)
            container.register('points_transaction_repository', PointsTransactionRepository(), singleton=True)
            container.register('streak_freeze_repository', StreakFreezeRepository(), singleton=True)
            container.register('contest_participant_repository', ContestParticipantRepository(), singleton=True)
            container.register('gamification_config_repository', GamificationConfigRepository(), singleton=True)
            container.register('gamification_insight_repository', GamificationInsightRepository(), singleton=True)
            
            # Register interactors
            container.register('badge_interactor', BadgeInteractor(), singleton=True)
            container.register('streak_interactor', StreakInteractor(), singleton=True)
            container.register('challenge_interactor', ChallengeInteractor(), singleton=True)
            container.register('level_interactor', LevelInteractor(), singleton=True)
            container.register('contest_interactor', ContestInteractor(), singleton=True)
            container.register('gamification_interactor', GamificationInteractor(), singleton=True)
            
            # Register new interactors for enhanced gamification models
            container.register('user_points_interactor', UserPointsInteractor(), singleton=True)
            container.register('points_transaction_interactor', PointsTransactionInteractor(), singleton=True)
            container.register('streak_freeze_interactor', StreakFreezeInteractor(), singleton=True)
            container.register('contest_participant_interactor', ContestParticipantInteractor(), singleton=True)
            container.register('gamification_config_interactor', GamificationConfigInteractor(), singleton=True)
            container.register('gamification_insight_interactor', GamificationInsightInteractor(), singleton=True)
            
            # Register helpers
            container.register('badge_helper', BadgeHelper(), singleton=True)
            container.register('streak_helper', StreakHelper(), singleton=True)
            container.register('challenge_helper', ChallengeHelper(), singleton=True)
            container.register('leaderboard_helper', LeaderboardHelper(), singleton=True)
            container.register('cache_helper', CacheHelper(), singleton=True)
            
            # Register analytics services
            container.register('analytics_tracker', analytics_tracker, singleton=True)
            container.register_factory('user_analytics', lambda: UserAnalytics, singleton=False)
            container.register('system_analytics', SystemAnalytics(), singleton=True)
            container.register('report_generator', ReportGenerator(), singleton=True)
            
            # Register caching services
            container.register('gamification_cache', gamification_cache, singleton=True)
            container.register('cache_warmer', cache_warmer, singleton=True)
            container.register('cache_invalidator', cache_invalidator, singleton=True)
            
            # Register security services
            container.register('encryption_provider', encryption_provider, singleton=True)
            container.register('hash_provider', hash_provider, singleton=True)
            container.register('token_generator', token_generator, singleton=True)
            container.register('secure_data_handler', secure_data_handler, singleton=True)
            container.register('data_masking', data_masking, singleton=True)
            container.register('security_audit_logger', security_audit_logger, singleton=True)
            
            # Register background job manager
            container.register('background_job_manager', background_job_manager, singleton=True)
            
            # Register webhook service
            container.register('webhook_service', WebhookService(), singleton=True)
            
            # Register notification service
            container.register('push_notification_service', push_notification_service, singleton=True)
            
            # Register monitoring service
            container.register('monitoring_service', monitoring_service, singleton=True)
            
            # Register compliance manager
            container.register('compliance_manager', compliance_manager, singleton=True)
            
            logger.info("Gamification services registered successfully")
            
        except Exception as e:
            logger.error(f"Error registering gamification services: {e}")
            raise GamificationServiceError(f"Failed to register services: {e}")


# Dependency injection decorators
def inject(service_name: str):
    """Decorator for dependency injection."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            service = service_locator.get(service_name)
            return func(service, *args, **kwargs)
        return wrapper
    return decorator


def inject_async(service_name: str):
    """Decorator for async dependency injection."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            service = service_locator.get(service_name)
            return await func(service, *args, **kwargs)
        return wrapper
    return decorator


def inject_multiple(*service_names: str):
    """Decorator for multiple dependency injection."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            services = [service_locator.get(name) for name in service_names]
            return func(*services, *args, **kwargs)
        return wrapper
    return decorator


def inject_multiple_async(*service_names: str):
    """Decorator for multiple async dependency injection."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            services = [service_locator.get(name) for name in service_names]
            return await func(*services, *args, **kwargs)
        return wrapper
    return decorator


# Context managers
@contextmanager
def service_container():
    """Context manager for service container."""
    container = DependencyContainer()
    try:
        yield container
    finally:
        pass


@contextmanager
def scoped_services(scope_name: str):
    """Context manager for scoped services."""
    # Create scoped container with global services
    container = DependencyContainer()
    
    # Register global services
    for service_name in service_locator.list_services():
        try:
            service = service_locator.get(service_name)
            container.register(service_name, service)
        except:
            pass
    
    try:
        yield container
    finally:
        pass


# Service configuration
def configure_services() -> None:
    """Configure all services."""
    try:
        # Register service provider
        provider = GamificationServiceProvider()
        provider.register_services(service_locator)
        
        logger.info("Services configured successfully")
        
    except Exception as e:
        logger.error(f"Error configuring services: {e}")
        raise GamificationServiceError(f"Failed to configure services: {e}")


def get_service(name: str) -> Any:
    """Get a service by name."""
    return service_locator.get(name)


def has_service(name: str) -> bool:
    """Check if service exists."""
    return service_locator.has(name)


# Service health check
def check_service_health() -> Dict[str, Any]:
    """Check health of all registered services."""
    health_status = {
        'total_services': 0,
        'healthy_services': 0,
        'unhealthy_services': 0,
        'service_details': {}
    }
    
    for service_name in service_locator.list_services():
        try:
            service = service_locator.get(service_name)
            health_status['total_services'] += 1
            
            # Check if service has health check method
            if hasattr(service, 'health_check') and callable(getattr(service, 'health_check')):
                service_health = service.health_check()
                health_status['service_details'][service_name] = {
                    'status': 'healthy' if service_health else 'unhealthy',
                    'details': service_health
                }
                if service_health:
                    health_status['healthy_services'] += 1
                else:
                    health_status['unhealthy_services'] += 1
            else:
                # Assume healthy if no health check method
                health_status['service_details'][service_name] = {
                    'status': 'unknown',
                    'details': 'No health check method'
                }
                health_status['healthy_services'] += 1
                
        except Exception as e:
            health_status['total_services'] += 1
            health_status['unhealthy_services'] += 1
            health_status['service_details'][service_name] = {
                'status': 'error',
                'details': str(e)
            }
    
    return health_status


# Service metrics
def get_service_metrics() -> Dict[str, Any]:
    """Get service metrics."""
    return {
        'total_services': len(service_locator.list_services()),
        'service_count': len(service_locator._services),
        'factory_count': len(service_locator._factories),
        'singleton_count': len(service_locator._singletons),
        'services': service_locator.list_services(),
        'timestamp': timezone.now().isoformat()
    }


# Initialize services on import
try:
    configure_services()
except Exception as e:
    logger.warning(f"Failed to configure services on import: {e}")
