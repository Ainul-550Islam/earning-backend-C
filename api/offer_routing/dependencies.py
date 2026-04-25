"""
Dependencies Management for Offer Routing System

This module manages external dependencies and integrations for the offer routing system,
including third-party services, APIs, and libraries.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from abc import ABC, abstractmethod
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class BaseDependency(ABC):
    """
    Abstract base class for all external dependencies.
    
    Provides a common interface for managing external services,
    APIs, and integrations.
    """
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.is_available = False
        self.last_check = None
        self.error_count = 0
        self.max_errors = getattr(settings, 'MAX_DEPENDENCY_ERRORS', 5)
    
    @abstractmethod
    def check_availability(self) -> bool:
        """Check if the dependency is available and working."""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the dependency."""
        pass
    
    def mark_error(self):
        """Mark an error for this dependency."""
        self.error_count += 1
        if self.error_count >= self.max_errors:
            self.is_available = False
            logger.warning(f"Dependency {self.name} marked as unavailable after {self.error_count} errors")
    
    def reset_errors(self):
        """Reset error count for this dependency."""
        self.error_count = 0
        self.is_available = True
    
    def update_status(self):
        """Update the availability status of the dependency."""
        try:
            self.last_check = timezone.now()
            was_available = self.is_available
            self.is_available = self.check_availability()
            
            if self.is_available and not was_available:
                self.reset_errors()
                logger.info(f"Dependency {self.name} is now available")
            elif not self.is_available and was_available:
                logger.warning(f"Dependency {self.name} is now unavailable")
                
        except Exception as e:
            self.mark_error()
            logger.error(f"Error checking dependency {self.name}: {str(e)}")


class DatabaseDependency(BaseDependency):
    """
    Database dependency for the offer routing system.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("database", config)
        self.connection_pool_size = self.config.get('connection_pool_size', 10)
        self.max_connections = self.config.get('max_connections', 100)
    
    def check_availability(self) -> bool:
        """Check database connection availability."""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get database status information."""
        try:
            from django.db import connection
            return {
                'available': self.is_available,
                'last_check': self.last_check,
                'error_count': self.error_count,
                'connection_pool_size': self.connection_pool_size,
                'max_connections': self.max_connections,
                'current_connections': len(connection.queries) if settings.DEBUG else 'N/A'
            }
        except Exception as e:
            return {
                'available': False,
                'error': str(e),
                'last_check': self.last_check,
                'error_count': self.error_count
            }


class RedisDependency(BaseDependency):
    """
    Redis dependency for caching and session management.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("redis", config)
        self.redis_url = self.config.get('redis_url', getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'))
        self.max_connections = self.config.get('max_connections', 50)
    
    def check_availability(self) -> bool:
        """Check Redis connection availability."""
        try:
            import redis
            r = redis.from_url(self.redis_url)
            r.ping()
            return True
        except Exception as e:
            logger.error(f"Redis connection error: {str(e)}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get Redis status information."""
        try:
            import redis
            r = redis.from_url(self.redis_url)
            info = r.info()
            
            return {
                'available': self.is_available,
                'last_check': self.last_check,
                'error_count': self.error_count,
                'redis_url': self.redis_url,
                'max_connections': self.max_connections,
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory_human', 'N/A'),
                'uptime_in_seconds': info.get('uptime_in_seconds', 0)
            }
        except Exception as e:
            return {
                'available': False,
                'error': str(e),
                'last_check': self.last_check,
                'error_count': self.error_count
            }


class CeleryDependency(BaseDependency):
    """
    Celery dependency for background task processing.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("celery", config)
        self.broker_url = self.config.get('broker_url', getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'))
        self.result_backend = self.config.get('result_backend', getattr(settings, 'CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'))
    
    def check_availability(self) -> bool:
        """Check Celery broker and worker availability."""
        try:
            from .celery_config import app
            inspect = app.control.inspect()
            
            # Check if workers are active
            stats = inspect.stats()
            if not stats:
                return False
            
            # Check if workers are responding
            active_tasks = inspect.active()
            if active_tasks is None:
                return False
            
            return True
        except Exception as e:
            logger.error(f"Celery connection error: {str(e)}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get Celery status information."""
        try:
            from .celery_config import app
            inspect = app.control.inspect()
            
            stats = inspect.stats() or {}
            active_tasks = inspect.active() or {}
            scheduled_tasks = inspect.scheduled() or {}
            
            total_workers = len(stats)
            total_active_tasks = sum(len(tasks) for tasks in active_tasks.values())
            total_scheduled_tasks = sum(len(tasks) for tasks in scheduled_tasks.values())
            
            return {
                'available': self.is_available,
                'last_check': self.last_check,
                'error_count': self.error_count,
                'broker_url': self.broker_url,
                'result_backend': self.result_backend,
                'total_workers': total_workers,
                'total_active_tasks': total_active_tasks,
                'total_scheduled_tasks': total_scheduled_tasks,
                'worker_stats': stats
            }
        except Exception as e:
            return {
                'available': False,
                'error': str(e),
                'last_check': self.last_check,
                'error_count': self.error_count
            }


class ExternalAPIDependency(BaseDependency):
    """
    External API dependency for third-party integrations.
    """
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        super().__init__(name, config)
        self.base_url = self.config.get('base_url')
        self.api_key = self.config.get('api_key')
        self.timeout = self.config.get('timeout', 30)
        self.max_retries = self.config.get('max_retries', 3)
    
    def check_availability(self) -> bool:
        """Check external API availability."""
        try:
            import requests
            
            if not self.base_url:
                return False
            
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.timeout,
                headers={'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
            )
            
            return response.status_code == 200
        except Exception as e:
            logger.error(f"External API {self.name} connection error: {str(e)}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get external API status information."""
        return {
            'available': self.is_available,
            'last_check': self.last_check,
            'error_count': self.error_count,
            'base_url': self.base_url,
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'has_api_key': bool(self.api_key)
        }


class DependencyManager:
    """
    Manager for all external dependencies.
    
    Provides centralized management and monitoring of all
    external services and integrations.
    """
    
    def __init__(self):
        self.dependencies: Dict[str, BaseDependency] = {}
        self.logger = logging.getLogger(__name__)
        self._setup_dependencies()
    
    def _setup_dependencies(self):
        """Setup all required dependencies."""
        # Database dependency
        self.dependencies['database'] = DatabaseDependency()
        
        # Redis dependency
        self.dependencies['redis'] = RedisDependency()
        
        # Celery dependency
        self.dependencies['celery'] = CeleryDependency()
        
        # External API dependencies from settings
        external_apis = getattr(settings, 'EXTERNAL_API_DEPENDENCIES', {})
        for api_name, api_config in external_apis.items():
            self.dependencies[api_name] = ExternalAPIDependency(api_name, api_config)
        
        self.logger.info(f"Setup {len(self.dependencies)} dependencies")
    
    def check_all_dependencies(self) -> Dict[str, bool]:
        """Check availability of all dependencies."""
        results = {}
        for name, dependency in self.dependencies.items():
            dependency.update_status()
            results[name] = dependency.is_available
        return results
    
    def get_dependency_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific dependency."""
        dependency = self.dependencies.get(name)
        if dependency:
            dependency.update_status()
            return dependency.get_status()
        return None
    
    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all dependencies."""
        statuses = {}
        for name, dependency in self.dependencies.items():
            dependency.update_status()
            statuses[name] = dependency.get_status()
        return statuses
    
    def is_system_healthy(self) -> bool:
        """Check if the system is healthy (all critical dependencies available)."""
        critical_dependencies = getattr(settings, 'CRITICAL_DEPENDENCIES', ['database', 'redis'])
        
        for dep_name in critical_dependencies:
            dependency = self.dependencies.get(dep_name)
            if not dependency or not dependency.is_available:
                return False
        
        return True
    
    def get_available_dependencies(self) -> List[str]:
        """Get list of available dependencies."""
        available = []
        for name, dependency in self.dependencies.items():
            dependency.update_status()
            if dependency.is_available:
                available.append(name)
        return available
    
    def get_unavailable_dependencies(self) -> List[str]:
        """Get list of unavailable dependencies."""
        unavailable = []
        for name, dependency in self.dependencies.items():
            dependency.update_status()
            if not dependency.is_available:
                unavailable.append(name)
        return unavailable
    
    def reset_dependency_errors(self, name: str) -> bool:
        """Reset error count for a dependency."""
        dependency = self.dependencies.get(name)
        if dependency:
            dependency.reset_errors()
            return True
        return False
    
    def add_dependency(self, dependency: BaseDependency):
        """Add a new dependency."""
        self.dependencies[dependency.name] = dependency
        self.logger.info(f"Added dependency: {dependency.name}")
    
    def remove_dependency(self, name: str) -> bool:
        """Remove a dependency."""
        if name in self.dependencies:
            del self.dependencies[name]
            self.logger.info(f"Removed dependency: {name}")
            return True
        return False


# Global dependency manager instance
dependency_manager = DependencyManager()


def check_dependencies():
    """Check all dependencies and return status."""
    return dependency_manager.check_all_dependencies()


def get_dependency_status(name: str) -> Optional[Dict[str, Any]]:
    """Get status of a specific dependency."""
    return dependency_manager.get_dependency_status(name)


def is_system_healthy() -> bool:
    """Check if the system is healthy."""
    return dependency_manager.is_system_healthy()


def get_health_summary() -> Dict[str, Any]:
    """Get a summary of system health."""
    all_statuses = dependency_manager.get_all_statuses()
    available = dependency_manager.get_available_dependencies()
    unavailable = dependency_manager.get_unavailable_dependencies()
    
    return {
        'healthy': dependency_manager.is_system_healthy(),
        'total_dependencies': len(all_statuses),
        'available_dependencies': len(available),
        'unavailable_dependencies': len(unavailable),
        'available': available,
        'unavailable': unavailable,
        'statuses': all_statuses,
        'last_check': timezone.now()
    }


# Export the dependency manager and utility functions
__all__ = [
    'BaseDependency',
    'DatabaseDependency',
    'RedisDependency',
    'CeleryDependency',
    'ExternalAPIDependency',
    'DependencyManager',
    'dependency_manager',
    'check_dependencies',
    'get_dependency_status',
    'is_system_healthy',
    'get_health_summary',
]
