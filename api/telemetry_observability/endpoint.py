"""
Endpoint definitions for Telemetry Observability.
"""
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from dataclasses import dataclass


class HttpMethod(Enum):
    """HTTP method constants."""
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'
    PATCH = 'PATCH'


@dataclass
class Endpoint:
    """
    Represents an API endpoint.
    """
    
    name: str
    path: str
    method: HttpMethod
    description: str
    handler: Optional[Callable] = None
    auth_required: bool = True
    rate_limit: Optional[int] = None
    cache_timeout: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert endpoint to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'name': self.name,
            'path': self.path,
            'method': self.method.value,
            'description': self.description,
            'auth_required': self.auth_required,
            'rate_limit': self.rate_limit,
            'cache_timeout': self.cache_timeout
        }


class EndpointGroup:
    """
    Group of related endpoints.
    """
    
    def __init__(self, name: str, description: str):
        """
        Initialize the endpoint group.
        
        Args:
            name: Group name
            description: Group description
        """
        self.name = name
        self.description = description
        self.endpoints: List[Endpoint] = []
    
    def add_endpoint(self, endpoint: Endpoint) -> None:
        """
        Add an endpoint to the group.
        
        Args:
            endpoint: Endpoint to add
        """
        self.endpoints.append(endpoint)
    
    def get_endpoint(self, name: str) -> Optional[Endpoint]:
        """
        Get an endpoint by name.
        
        Args:
            name: Endpoint name
            
        Returns:
            Endpoint or None
        """
        for endpoint in self.endpoints:
            if endpoint.name == name:
                return endpoint
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert group to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'name': self.name,
            'description': self.description,
            'endpoints': [e.to_dict() for e in self.endpoints]
        }


class EndpointRegistry:
    """
    Singleton registry for endpoints.
    """
    
    _instance = None
    
    def __new__(cls):
        """
        Create singleton instance.
        
        Returns:
            EndpointRegistry instance
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._endpoints: Dict[str, Endpoint] = {}
            cls._instance._groups: Dict[str, EndpointGroup] = {}
        return cls._instance
    
    def register(self, endpoint: Endpoint) -> None:
        """
        Register an endpoint.
        
        Args:
            endpoint: Endpoint to register
        """
        self._endpoints[endpoint.name] = endpoint
    
    def unregister(self, endpoint_name: str) -> bool:
        """
        Unregister an endpoint.
        
        Args:
            endpoint_name: Name of the endpoint
            
        Returns:
            True if unregistered successfully
        """
        if endpoint_name in self._endpoints:
            del self._endpoints[endpoint_name]
            return True
        return False
    
    def get_endpoint(self, endpoint_name: str) -> Optional[Endpoint]:
        """
        Get an endpoint by name.
        
        Args:
            endpoint_name: Name of the endpoint
            
        Returns:
            Endpoint or None
        """
        return self._endpoints.get(endpoint_name)
    
    def list_endpoints(self) -> List[str]:
        """
        List all endpoint names.
        
        Returns:
            List of endpoint names
        """
        return list(self._endpoints.keys())
    
    def register_group(self, group: EndpointGroup) -> None:
        """
        Register an endpoint group.
        
        Args:
            group: Endpoint group to register
        """
        self._groups[group.name] = group
        
        # Register all endpoints in the group
        for endpoint in group.endpoints:
            self.register(endpoint)
    
    def get_group(self, group_name: str) -> Optional[EndpointGroup]:
        """
        Get an endpoint group by name.
        
        Args:
            group_name: Name of the group
            
        Returns:
            EndpointGroup or None
        """
        return self._groups.get(group_name)
    
    def list_groups(self) -> List[str]:
        """
        List all group names.
        
        Returns:
            List of group names
        """
        return list(self._groups.keys())


# Singleton instance
endpoint_registry = EndpointRegistry()


def endpoint(name: str, path: str, method: HttpMethod = HttpMethod.GET, **kwargs):
    """
    Decorator for registering an endpoint.
    
    Args:
        name: Endpoint name
        path: Endpoint path
        method: HTTP method
        **kwargs: Additional endpoint configuration
        
    Returns:
        Decorator function
    """
    def decorator(func):
        endpoint_obj = Endpoint(
            name=name,
            path=path,
            method=method,
            description=func.__doc__ or '',
            handler=func,
            **kwargs
        )
        endpoint_registry.register(endpoint_obj)
        return func
    return decorator


def endpoint_group(name: str, description: str):
    """
    Decorator for registering an endpoint group.
    
    Args:
        name: Group name
        description: Group description
        
    Returns:
        Decorator function
    """
    def decorator(func):
        # Create a group and register it
        group = EndpointGroup(name, description)
        endpoint_registry.register_group(group)
        return func
    return decorator


# Example API endpoints
@endpoint('metrics_list', '/api/v1/metrics', HttpMethod.GET, auth_required=True)
def list_metrics():
    """
    List all metrics.
    """
    pass


@endpoint('metric_create', '/api/v1/metrics', HttpMethod.POST, auth_required=True)
def create_metric():
    """
    Create a new metric.
    """
    pass


@endpoint('metric_detail', '/api/v1/metrics/<str:metric_id>', HttpMethod.GET, auth_required=True)
def get_metric():
    """
    Get metric details.
    """
    pass


@endpoint('logs_list', '/api/v1/logs', HttpMethod.GET, auth_required=True)
def list_logs():
    """
    List all logs.
    """
    pass


@endpoint('log_create', '/api/v1/logs', HttpMethod.POST, auth_required=True)
def create_log():
    """
    Create a new log entry.
    """
    pass


@endpoint('traces_list', '/api/v1/traces', HttpMethod.GET, auth_required=True)
def list_traces():
    """
    List all traces.
    """
    pass


@endpoint('trace_detail', '/api/v1/traces/<str:trace_id>', HttpMethod.GET, auth_required=True)
def get_trace():
    """
    Get trace details.
    """
    pass


@endpoint('alerts_list', '/api/v1/alerts', HttpMethod.GET, auth_required=True)
def list_alerts():
    """
    List all alerts.
    """
    pass


@endpoint('alert_create', '/api/v1/alerts', HttpMethod.POST, auth_required=True)
def create_alert():
    """
    Create a new alert.
    """
    pass


@endpoint('alert_acknowledge', '/api/v1/alerts/<int:alert_id>/acknowledge', HttpMethod.POST, auth_required=True)
def acknowledge_alert():
    """
    Acknowledge an alert.
    """
    pass


@endpoint('alert_resolve', '/api/v1/alerts/<int:alert_id>/resolve', HttpMethod.POST, auth_required=True)
def resolve_alert():
    """
    Resolve an alert.
    """
    pass


@endpoint('health_status', '/api/v1/health', HttpMethod.GET, auth_required=False)
def get_health_status():
    """
    Get overall health status.
    """
    pass


@endpoint('health_service', '/api/v1/health/<str:service_name>', HttpMethod.GET, auth_required=False)
def get_service_health():
    """
    Get health status for a specific service.
    """
    pass
