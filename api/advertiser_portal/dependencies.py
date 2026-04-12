"""
Dependency Injection for Advertiser Portal

This module contains dependency injection setup and provider classes
for managing service dependencies and promoting loose coupling.
"""

from typing import Any, Dict, Optional, Type, TypeVar, Callable
from functools import wraps
import inspect

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model

from .services import *
from .repository import *
from .validators import *
from .utils import *
from .exceptions import *


User = get_user_model()
T = TypeVar('T')


class DIContainer:
    """Dependency Injection Container."""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._instances: Dict[str, Any] = {}
    
    def register_singleton(self, interface: Type[T], implementation: Type[T]) -> None:
        """
        Register a singleton service.
        
        Args:
            interface: Service interface type
            implementation: Service implementation type
        """
        key = interface.__name__
        self._services[key] = implementation
        self._singletons[key] = True
    
    def register_factory(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """
        Register a factory function for service creation.
        
        Args:
            interface: Service interface type
            factory: Factory function
        """
        key = interface.__name__
        self._factories[key] = factory
    
    def register_transient(self, interface: Type[T], implementation: Type[T]) -> None:
        """
        Register a transient service (new instance each time).
        
        Args:
            interface: Service interface type
            implementation: Service implementation type
        """
        key = interface.__name__
        self._services[key] = implementation
        self._singletons[key] = False
    
    def get(self, interface: Type[T]) -> T:
        """
        Get service instance.
        
        Args:
            interface: Service interface type
            
        Returns:
            Service instance
        """
        key = interface.__name__
        
        # Check if we have a factory
        if key in self._factories:
            return self._factories[key]()
        
        # Check if we have a registered service
        if key not in self._services:
            raise ValueError(f"Service {key} not registered")
        
        # Check if it's a singleton
        if self._singletons.get(key, False):
            if key not in self._instances:
                self._instances[key] = self._services[key]()
            return self._instances[key]
        
        # Create new instance for transient
        return self._services[key]()
    
    def has(self, interface: Type[T]) -> bool:
        """
        Check if service is registered.
        
        Args:
            interface: Service interface type
            
        Returns:
            True if service is registered
        """
        key = interface.__name__
        return key in self._services or key in self._factories
    
    def clear(self) -> None:
        """Clear all registered services."""
        self._services.clear()
        self._singletons.clear()
        self._factories.clear()
        self._instances.clear()


# Global container instance
container = DIContainer()


def inject(interface: Type[T]) -> T:
    """
    Dependency injection decorator.
    
    Args:
        interface: Service interface type
        
    Returns:
        Service instance
    """
    return container.get(interface)


def service_dependency(interface: Type[T]):
    """
    Decorator for injecting service dependencies into functions.
    
    Args:
        interface: Service interface type
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get service instance
            service_instance = container.get(interface)
            
            # Add service to kwargs if not already present
            if interface.__name__.lower() not in kwargs:
                kwargs[interface.__name__.lower()] = service_instance
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


class ServiceProvider:
    """Service provider for managing service lifecycles."""
    
    def __init__(self, container: DIContainer):
        self.container = container
        self._initialized = False
    
    def initialize(self) -> None:
        """Initialize all registered services."""
        if self._initialized:
            return
        
        # Pre-create singleton instances
        for key, is_singleton in self.container._singletons.items():
            if is_singleton and key not in self.container._instances:
                if key in self.container._services:
                    self.container._instances[key] = self.container._services[key]()
        
        self._initialized = True
    
    def shutdown(self) -> None:
        """Shutdown all services and cleanup resources."""
        # Cleanup singleton instances if they have cleanup method
        for instance in self.container._instances.values():
            if hasattr(instance, 'cleanup'):
                try:
                    instance.cleanup()
                except Exception as e:
                    # Log error but continue cleanup
                    print(f"Error during service cleanup: {e}")
        
        self.container.clear()
        self._initialized = False


class AdvertiserServiceProvider(ServiceProvider):
    """Service provider for advertiser portal services."""
    
    def register_services(self) -> None:
        """Register all advertiser portal services."""
        # Register repositories
        self.container.register_singleton(AdvertiserRepository, AdvertiserRepository)
        self.container.register_singleton(CampaignRepository, CampaignRepository)
        self.container.register_singleton(CreativeRepository, CreativeRepository)
        self.container.register_singleton(TargetingRepository, TargetingRepository)
        self.container.register_singleton(AnalyticsRepository, AnalyticsRepository)
        self.container.register_singleton(BillingRepository, BillingRepository)
        self.container.register_singleton(FraudDetectionRepository, FraudDetectionRepository)
        
        # Register validators
        self.container.register_singleton(AdvertiserValidator, AdvertiserValidator)
        self.container.register_singleton(CampaignValidator, CampaignValidator)
        self.container.register_singleton(CreativeValidator, CreativeValidator)
        self.container.register_singleton(TargetingValidator, TargetingValidator)
        self.container.register_singleton(BillingValidator, BillingValidator)
        
        # Register services as singletons
        self.container.register_singleton(AdvertiserService, AdvertiserService)
        self.container.register_singleton(CampaignService, CampaignService)
        self.container.register_singleton(CreativeService, CreativeService)
        self.container.register_singleton(TargetingService, TargetingService)
        self.container.register_singleton(AnalyticsService, AnalyticsService)
        self.container.register_singleton(BillingService, BillingService)
        
        # Register utility classes
        self.container.register_singleton(AdvertiserUtils, AdvertiserUtils)
        self.container.register_singleton(CampaignUtils, CampaignUtils)
        self.container.register_singleton(CreativeUtils, CreativeUtils)
        self.container.register_singleton(TargetingUtils, TargetingUtils)
        self.container.register_singleton(AnalyticsUtils, AnalyticsUtils)
        self.container.register_singleton(BillingUtils, BillingUtils)
        self.container.register_singleton(CacheUtils, CacheUtils)
        self.container.register_singleton(ValidationUtils, ValidationUtils)
        self.container.register_singleton(DateUtils, DateUtils)


class RequestContext:
    """Request context for dependency injection."""
    
    def __init__(self, user: Optional[User] = None, request_id: Optional[str] = None):
        self.user = user
        self.request_id = request_id
        self._data: Dict[str, Any] = {}
    
    def set(self, key: str, value: Any) -> None:
        """Set value in request context."""
        self._data[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from request context."""
        return self._data.get(key, default)
    
    def has(self, key: str) -> bool:
        """Check if key exists in request context."""
        return key in self._data


class ContextManager:
    """Manager for request contexts."""
    
    def __init__(self):
        self._contexts: Dict[str, RequestContext] = {}
    
    def create_context(self, request_id: str, user: Optional[User] = None) -> RequestContext:
        """
        Create new request context.
        
        Args:
            request_id: Unique request identifier
            user: User instance
            
        Returns:
            RequestContext instance
        """
        context = RequestContext(user=user, request_id=request_id)
        self._contexts[request_id] = context
        return context
    
    def get_context(self, request_id: str) -> Optional[RequestContext]:
        """
        Get request context by ID.
        
        Args:
            request_id: Request identifier
            
        Returns:
            RequestContext instance or None
        """
        return self._contexts.get(request_id)
    
    def remove_context(self, request_id: str) -> None:
        """
        Remove request context.
        
        Args:
            request_id: Request identifier
        """
        self._contexts.pop(request_id, None)
    
    def clear_all(self) -> None:
        """Clear all contexts."""
        self._contexts.clear()


# Global context manager
context_manager = ContextManager()


def get_current_context() -> Optional[RequestContext]:
    """
    Get current request context.
    
    Returns:
        RequestContext instance or None
    """
    # This would typically get the request ID from thread-local storage
    # For now, returning None as placeholder
    return None


def with_context(func):
    """
    Decorator to ensure function runs with request context.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Ensure context exists
        context = get_current_context()
        if not context:
            # Create temporary context
            import uuid
            request_id = str(uuid.uuid4())
            context = context_manager.create_context(request_id)
        
        # Add context to kwargs
        kwargs['context'] = context
        
        try:
            return func(*args, **kwargs)
        finally:
            # Cleanup temporary context if created
            if hasattr(context, 'request_id'):
                context_manager.remove_context(context.request_id)
    
    return wrapper


class LazyService:
    """Lazy service loader."""
    
    def __init__(self, interface: Type[T]):
        self.interface = interface
        self._instance: Optional[T] = None
    
    def __call__(self) -> T:
        """Get service instance."""
        if self._instance is None:
            self._instance = container.get(self.interface)
        return self._instance
    
    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to service instance."""
        if self._instance is None:
            self._instance = container.get(self.interface)
        return getattr(self._instance, name)


class ServiceLocator:
    """Service locator pattern implementation."""
    
    @staticmethod
    def get_advertiser_service() -> AdvertiserService:
        """Get advertiser service."""
        return container.get(AdvertiserService)
    
    @staticmethod
    def get_campaign_service() -> CampaignService:
        """Get campaign service."""
        return container.get(CampaignService)
    
    @staticmethod
    def get_creative_service() -> CreativeService:
        """Get creative service."""
        return container.get(CreativeService)
    
    @staticmethod
    def get_targeting_service() -> TargetingService:
        """Get targeting service."""
        return container.get(TargetingService)
    
    @staticmethod
    def get_analytics_service() -> AnalyticsService:
        """Get analytics service."""
        return container.get(AnalyticsService)
    
    @staticmethod
    def get_billing_service() -> BillingService:
        """Get billing service."""
        return container.get(BillingService)
    
    @staticmethod
    def get_advertiser_repository() -> AdvertiserRepository:
        """Get advertiser repository."""
        return container.get(AdvertiserRepository)
    
    @staticmethod
    def get_campaign_repository() -> CampaignRepository:
        """Get campaign repository."""
        return container.get(CampaignRepository)
    
    @staticmethod
    def get_creative_repository() -> CreativeRepository:
        """Get creative repository."""
        return container.get(CreativeRepository)
    
    @staticmethod
    def get_targeting_repository() -> TargetingRepository:
        """Get targeting repository."""
        return container.get(TargetingRepository)
    
    @staticmethod
    def get_analytics_repository() -> AnalyticsRepository:
        """Get analytics repository."""
        return container.get(AnalyticsRepository)
    
    @staticmethod
    def get_billing_repository() -> BillingRepository:
        """Get billing repository."""
        return container.get(BillingRepository)


# Configuration for dependency injection
class DIConfig:
    """Configuration for dependency injection."""
    
    @staticmethod
    def configure() -> None:
        """Configure dependency injection container."""
        # Register services
        provider = AdvertiserServiceProvider(container)
        provider.register_services()
        
        # Initialize services
        provider.initialize()
    
    @staticmethod
    def configure_for_testing() -> None:
        """Configure dependency injection for testing."""
        # Register mock services for testing
        from unittest.mock import Mock
        
        # Register mock services
        container.register_singleton(AdvertiserService, Mock)
        container.register_singleton(CampaignService, Mock)
        container.register_singleton(CreativeService, Mock)
        container.register_singleton(TargetingService, Mock)
        container.register_singleton(AnalyticsService, Mock)
        container.register_singleton(BillingService, Mock)
        
        # Initialize
        provider = ServiceProvider(container)
        provider.initialize()


# Decorators for common dependency patterns
def require_authentication(func):
    """
    Decorator to require user authentication.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        context = get_current_context()
        if not context or not context.user:
            raise AuthenticationError("Authentication required")
        
        return func(*args, **kwargs)
    return wrapper


def require_permission(permission: str):
    """
    Decorator to require specific permission.
    
    Args:
        permission: Required permission
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            context = get_current_context()
            if not context or not context.user:
                raise AuthenticationError("Authentication required")
            
            if not context.user.has_perm(permission):
                raise PermissionError(f"Permission '{permission}' required")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def with_transaction(func):
    """
    Decorator to run function within database transaction.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from django.db import transaction
        
        try:
            with transaction.atomic():
                return func(*args, **kwargs)
        except Exception as e:
            # Log error and re-raise
            print(f"Transaction failed: {e}")
            raise
    return wrapper


def cache_result(key_template: str, timeout: int = 300):
    """
    Decorator to cache function results.
    
    Args:
        key_template: Cache key template
        timeout: Cache timeout in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = key_template.format(*args, **kwargs)
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator


def rate_limit(max_requests: int, period: int = 60):
    """
    Decorator for rate limiting.
    
    Args:
        max_requests: Maximum requests allowed
        period: Time period in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            context = get_current_context()
            if not context or not context.user:
                return func(*args, **kwargs)
            
            # Generate rate limit key
            user_id = context.user.id
            key = f"rate_limit:{func.__name__}:{user_id}"
            
            # Check current count
            current_count = cache.get(key, 0)
            
            if current_count >= max_requests:
                raise RateLimitError(f"Rate limit exceeded: {max_requests} requests per {period} seconds")
            
            # Increment counter
            cache.set(key, current_count + 1, period)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Initialize dependency injection on module import
if not hasattr(settings, 'TESTING') or not settings.TESTING:
    DIConfig.configure()
