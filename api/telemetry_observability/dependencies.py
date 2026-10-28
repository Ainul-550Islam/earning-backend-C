"""
Dependency management for Telemetry Observability.
"""
from typing import Dict, Any, Optional, List
from enum import Enum


class DependencyType(Enum):
    """Dependency type constants."""
    DATABASE = 'database'
    CACHE = 'cache'
    QUEUE = 'queue'
    API = 'api'
    SERVICE = 'service'
    EXTERNAL = 'external'


class DependencyStatus(Enum):
    """Dependency status constants."""
    HEALTHY = 'healthy'
    DEGRADED = 'degraded'
    UNHEALTHY = 'unhealthy'
    UNKNOWN = 'unknown'


class Dependency:
    """
    Represents a system dependency.
    """
    
    def __init__(
        self,
        name: str,
        dependency_type: DependencyType,
        endpoint: str,
        required: bool = True,
        timeout: int = 30
    ):
        """
        Initialize a dependency.
        
        Args:
            name: Dependency name
            dependency_type: Type of dependency
            endpoint: Dependency endpoint
            required: Whether the dependency is required
            timeout: Timeout in seconds
        """
        self.name = name
        self.dependency_type = dependency_type
        self.endpoint = endpoint
        self.required = required
        self.timeout = timeout
        self.status = DependencyStatus.UNKNOWN
        self.last_check = None
        self.response_time_ms = None
    
    def check_health(self) -> bool:
        """
        Check the health of the dependency.
        
        Returns:
            True if healthy
        """
        import requests
        import time
        from datetime import datetime
        
        try:
            start_time = time.time()
            response = requests.get(self.endpoint, timeout=self.timeout)
            end_time = time.time()
            
            self.response_time_ms = (end_time - start_time) * 1000
            self.last_check = datetime.now()
            
            if response.status_code == 200:
                self.status = DependencyStatus.HEALTHY
                return True
            else:
                self.status = DependencyStatus.DEGRADED
                return False
        except Exception:
            self.status = DependencyStatus.UNHEALTHY
            self.last_check = datetime.now()
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert dependency to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'name': self.name,
            'type': self.dependency_type.value,
            'endpoint': self.endpoint,
            'required': self.required,
            'timeout': self.timeout,
            'status': self.status.value,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'response_time_ms': self.response_time_ms
        }


class DependencyManager:
    """
    Manager for system dependencies.
    """
    
    def __init__(self):
        """
        Initialize the dependency manager.
        """
        self.dependencies: Dict[str, Dependency] = {}
    
    def add_dependency(self, dependency: Dependency) -> None:
        """
        Add a dependency.
        
        Args:
            dependency: Dependency to add
        """
        self.dependencies[dependency.name] = dependency
    
    def remove_dependency(self, name: str) -> bool:
        """
        Remove a dependency.
        
        Args:
            name: Dependency name
            
        Returns:
            True if removed
        """
        if name in self.dependencies:
            del self.dependencies[name]
            return True
        return False
    
    def get_dependency(self, name: str) -> Optional[Dependency]:
        """
        Get a dependency by name.
        
        Args:
            name: Dependency name
            
        Returns:
            Dependency or None
        """
        return self.dependencies.get(name)
    
    def check_all_dependencies(self) -> Dict[str, bool]:
        """
        Check the health of all dependencies.
        
        Returns:
            Dictionary mapping dependency names to health status
        """
        results = {}
        for name, dependency in self.dependencies.items():
            results[name] = dependency.check_health()
        return results
    
    def get_healthy_dependencies(self) -> List[Dependency]:
        """
        Get all healthy dependencies.
        
        Returns:
            List of healthy dependencies
        """
        return [
            dep for dep in self.dependencies.values()
            if dep.status == DependencyStatus.HEALTHY
        ]
    
    def get_unhealthy_dependencies(self) -> List[Dependency]:
        """
        Get all unhealthy dependencies.
        
        Returns:
            List of unhealthy dependencies
        """
        return [
            dep for dep in self.dependencies.values()
            if dep.status == DependencyStatus.UNHEALTHY
        ]
    
    def get_required_unhealthy_dependencies(self) -> List[Dependency]:
        """
        Get all required unhealthy dependencies.
        
        Returns:
            List of required unhealthy dependencies
        """
        return [
            dep for dep in self.dependencies.values()
            if dep.required and dep.status == DependencyStatus.UNHEALTHY
        ]
    
    def get_status_summary(self) -> Dict[str, Any]:
        """
        Get a summary of dependency statuses.
        
        Returns:
            Dictionary with status summary
        """
        total = len(self.dependencies)
        healthy = len(self.get_healthy_dependencies())
        unhealthy = len(self.get_unhealthy_dependencies())
        required_unhealthy = len(self.get_required_unhealthy_dependencies())
        
        return {
            'total_dependencies': total,
            'healthy_count': healthy,
            'unhealthy_count': unhealthy,
            'required_unhealthy_count': required_unhealthy,
            'health_percentage': round((healthy / total * 100) if total > 0 else 0, 2),
            'critical': required_unhealthy > 0
        }
    
    def to_dict_list(self) -> List[Dict[str, Any]]:
        """
        Convert all dependencies to a list of dictionaries.
        
        Returns:
            List of dependency dictionaries
        """
        return [dep.to_dict() for dep in self.dependencies.values()]


# Singleton instance
dependency_manager = DependencyManager()
