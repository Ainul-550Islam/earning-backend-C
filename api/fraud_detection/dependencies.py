# =============================================================================
# fraud_detection/dependencies.py
# =============================================================================
"""
Dependency Management for Fraud Detection System.

Provides dependency injection container, service locator,
and external service management for fraud detection module.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union, Type, TypeVar, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils import timezone

from api.fraud_detection.exceptions import DependencyError


logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class ServiceDependency:
    """Data class for service dependency configuration."""
    name: str
    interface: Type
    implementation: Optional[Type] = None
    singleton: bool = True
    factory: Optional[Callable] = None
    dependencies: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None


class ServiceContainer:
    """
    Dependency injection container for fraud detection services.
    
    Provides service registration, resolution, and lifecycle management
    with support for singleton and factory patterns.
    """
    
    def __init__(self):
        """Initialize service container."""
        self._services: Dict[str, ServiceDependency] = {}
        self._instances: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._loading_order: List[str] = []
        self._loaded = False
    
    def register(self, dependency: ServiceDependency) -> None:
        """
        Register a service dependency.
        
        Args:
            dependency: Service dependency configuration
        """
        if dependency.name in self._services:
            logger.warning(f"Service {dependency.name} already registered, overwriting")
        
        self._services[dependency.name] = dependency
        
        # Add to loading order if not present
        if dependency.name not in self._loading_order:
            self._loading_order.append(dependency.name)
        
        logger.debug(f"Registered service: {dependency.name}")
    
    def register_singleton(self, name: str, interface: Type, 
                          implementation: Type = None,
                          factory: Callable = None,
                          dependencies: List[str] = None,
                          config: Dict[str, Any] = None) -> None:
        """
        Register a singleton service.
        
        Args:
            name: Service name
            interface: Service interface type
            implementation: Service implementation class
            factory: Factory function
            dependencies: List of dependency names
            config: Service configuration
        """
        dependency = ServiceDependency(
            name=name,
            interface=interface,
            implementation=implementation,
            singleton=True,
            factory=factory,
            dependencies=dependencies or [],
            config=config or {}
        )
        
        self.register(dependency)
    
    def register_transient(self, name: str, interface: Type,
                          implementation: Type = None,
                          factory: Callable = None,
                          dependencies: List[str] = None,
                          config: Dict[str, Any] = None) -> None:
        """
        Register a transient service (new instance each time).
        
        Args:
            name: Service name
            interface: Service interface type
            implementation: Service implementation class
            factory: Factory function
            dependencies: List of dependency names
            config: Service configuration
        """
        dependency = ServiceDependency(
            name=name,
            interface=interface,
            implementation=implementation,
            singleton=False,
            factory=factory,
            dependencies=dependencies or [],
            config=config or {}
        )
        
        self.register(dependency)
    
    def resolve(self, name: str) -> Any:
        """
        Resolve a service dependency.
        
        Args:
            name: Service name
            
        Returns:
            Service instance
            
        Raises:
            DependencyError: If service not found or cannot be resolved
        """
        if name not in self._services:
            raise DependencyError(f"Service {name} not registered")
        
        dependency = self._services[name]
        
        if dependency.singleton and name in self._instances:
            return self._instances[name]
        
        # Resolve dependencies first
        resolved_dependencies = {}
        for dep_name in dependency.dependencies:
            resolved_dependencies[dep_name] = self.resolve(dep_name)
        
        # Create instance
        if dependency.factory:
            instance = dependency.factory(
                config=dependency.config,
                dependencies=resolved_dependencies
            )
        elif dependency.implementation:
            instance = dependency.implementation(
                config=dependency.config,
                dependencies=resolved_dependencies
            )
        else:
            instance = dependency.interface(
                config=dependency.config,
                dependencies=resolved_dependencies
            )
        
        # Store singleton instance
        if dependency.singleton:
            self._instances[name] = instance
        
        logger.debug(f"Resolved service: {name}")
        return instance
    
    def get(self, interface: Type) -> Any:
        """
        Get service by interface type.
        
        Args:
            interface: Service interface type
            
        Returns:
            Service instance
            
        Raises:
            DependencyError: If no service found for interface
        """
        for name, dependency in self._services.items():
            if dependency.interface == interface:
                return self.resolve(name)
        
        raise DependencyError(f"No service found for interface {interface}")
    
    def load_all_services(self) -> None:
        """Load all registered services in dependency order."""
        if self._loaded:
            return
        
        logger.info("Loading fraud detection services...")
        
        # Calculate loading order based on dependencies
        ordered_services = self._calculate_loading_order()
        
        for service_name in ordered_services:
            try:
                self.resolve(service_name)
                logger.debug(f"Loaded service: {service_name}")
            except Exception as e:
                logger.error(f"Failed to load service {service_name}: {e}")
        
        self._loaded = True
        logger.info(f"Loaded {len(self._instances)} singleton services")
    
    def _calculate_loading_order(self) -> List[str]:
        """Calculate service loading order based on dependencies."""
        ordered = []
        visited = set()
        
        def visit(service_name: str):
            if service_name in visited:
                return
            
            visited.add(service_name)
            
            if service_name in self._services:
                dependency = self._services[service_name]
                for dep_name in dependency.dependencies:
                    visit(dep_name)
            
            if service_name not in ordered:
                ordered.append(service_name)
        
        for service_name in self._loading_order:
            visit(service_name)
        
        return ordered
    
    def get_service_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all registered services."""
        info = {}
        
        for name, dependency in self._services.items():
            info[name] = {
                'interface': dependency.interface.__name__,
                'implementation': dependency.implementation.__name__ if dependency.implementation else None,
                'singleton': dependency.singleton,
                'has_factory': dependency.factory is not None,
                'dependencies': dependency.dependencies,
                'loaded': name in self._instances if dependency.singleton else False
            }
        
        return info
    
    def clear(self) -> None:
        """Clear all registered services and instances."""
        self._services.clear()
        self._instances.clear()
        self._factories.clear()
        self._loading_order.clear()
        self._loaded = False
        
        logger.info("Service container cleared")


class ServiceLocator:
    """
    Service locator for convenient dependency resolution.
    
    Provides static methods for accessing services from the
    global container.
    """
    
    _container: Optional[ServiceContainer] = None
    
    @classmethod
    def initialize(cls) -> None:
        """Initialize the global service container."""
        cls._container = ServiceContainer()
        cls._register_core_services()
        cls._container.load_all_services()
    
    @classmethod
    def get_container(cls) -> ServiceContainer:
        """Get the global service container."""
        if cls._container is None:
            cls.initialize()
        return cls._container
    
    @classmethod
    def resolve(cls, name: str) -> Any:
        """Resolve a service by name."""
        return cls.get_container().resolve(name)
    
    @classmethod
    def get(cls, interface: Type) -> Any:
        """Get a service by interface type."""
        return cls.get_container().get(interface)
    
    @classmethod
    def _register_core_services(cls) -> None:
        """Register core fraud detection services."""
        container = cls._container
        
        # Repository services
        from api.fraud_detection.repositories import (
            fraud_rule_repository, fraud_case_repository, fraud_alert_repository,
            fraud_risk_profile_repository, fraud_device_fingerprint_repository,
            fraud_suspicious_ip_repository
        )
        
        container.register_singleton(
            name='fraud_rule_repository',
            interface=type(fraud_rule_repository),
            implementation=lambda config, dependencies: fraud_rule_repository
        )
        
        container.register_singleton(
            name='fraud_case_repository',
            interface=type(fraud_case_repository),
            implementation=lambda config, dependencies: fraud_case_repository
        )
        
        container.register_singleton(
            name='fraud_alert_repository',
            interface=type(fraud_alert_repository),
            implementation=lambda config, dependencies: fraud_alert_repository
        )
        
        container.register_singleton(
            name='fraud_risk_profile_repository',
            interface=type(fraud_risk_profile_repository),
            implementation=lambda config, dependencies: fraud_risk_profile_repository
        )
        
        container.register_singleton(
            name='fraud_device_fingerprint_repository',
            interface=type(fraud_device_fingerprint_repository),
            implementation=lambda config, dependencies: fraud_device_fingerprint_repository
        )
        
        container.register_singleton(
            name='fraud_suspicious_ip_repository',
            interface=type(fraud_suspicious_ip_repository),
            implementation=lambda config, dependencies: fraud_suspicious_ip_repository
        )
        
        # Selector services
        from api.fraud_detection.selectors import (
            fraud_rule_selector, fraud_case_selector, fraud_alert_selector,
            fraud_risk_profile_selector, fraud_device_fingerprint_selector,
            fraud_suspicious_ip_selector
        )
        
        container.register_singleton(
            name='fraud_rule_selector',
            interface=type(fraud_rule_selector),
            implementation=lambda config, dependencies: fraud_rule_selector
        )
        
        container.register_singleton(
            name='fraud_case_selector',
            interface=type(fraud_case_selector),
            implementation=lambda config, dependencies: fraud_case_selector
        )
        
        container.register_singleton(
            name='fraud_alert_selector',
            interface=type(fraud_alert_selector),
            implementation=lambda config, dependencies: fraud_alert_selector
        )
        
        container.register_singleton(
            name='fraud_risk_profile_selector',
            interface=type(fraud_risk_profile_selector),
            implementation=lambda config, dependencies: fraud_risk_profile_selector
        )
        
        container.register_singleton(
            name='fraud_device_fingerprint_selector',
            interface=type(fraud_device_fingerprint_selector),
            implementation=lambda config, dependencies: fraud_device_fingerprint_selector
        )
        
        container.register_singleton(
            name='fraud_suspicious_ip_selector',
            interface=type(fraud_suspicious_ip_selector),
            implementation=lambda config, dependencies: fraud_suspicious_ip_selector
        )
        
        # Use case services
        from api.fraud_detection.use_cases import (
            MultiAccountDetectionUseCase, SuspiciousPatternDetectionUseCase,
            RiskAssessmentUseCase
        )
        
        container.register_singleton(
            name='multi_account_detection_use_case',
            interface=MultiAccountDetectionUseCase,
            implementation=lambda config, dependencies: MultiAccountDetectionUseCase()
        )
        
        container.register_singleton(
            name='suspicious_pattern_detection_use_case',
            interface=SuspiciousPatternDetectionUseCase,
            implementation=lambda config, dependencies: SuspiciousPatternDetectionUseCase()
        )
        
        container.register_singleton(
            name='risk_assessment_use_case',
            interface=RiskAssessmentUseCase,
            implementation=lambda config, dependencies: RiskAssessmentUseCase()
        )
        
        # Interactor services
        from api.fraud_detection.interactors import (
            FraudDetectionInteractor, FraudCaseManagementInteractor,
            RiskProfileUpdateInteractor
        )
        
        container.register_singleton(
            name='fraud_detection_interactor',
            interface=FraudDetectionInteractor,
            implementation=lambda config, dependencies: FraudDetectionInteractor()
        )
        
        container.register_singleton(
            name='fraud_case_management_interactor',
            interface=FraudCaseManagementInteractor,
            implementation=lambda config, dependencies: FraudCaseManagementInteractor()
        )
        
        container.register_singleton(
            name='risk_profile_update_interactor',
            interface=RiskProfileUpdateInteractor,
            implementation=lambda config, dependencies: RiskProfileUpdateInteractor()
        )
        
        # External services
        try:
            from api.fraud_detection.webhooks import threat_intelligence_aggregator
            from api.fraud_detection.sanctions import sanctions_manager
            from api.fraud_detection.compliance import aml_compliance_manager
            from api.fraud_detection.monitoring import get_real_time_monitor
            from api.fraud_detection.analytics import get_fraud_analytics
            from api.fraud_detection.caching import get_risk_score_cache
            from api.fraud_detection.notifications_push import get_notification_manager
            
            container.register_singleton(
                name='threat_intelligence_aggregator',
                interface=type(threat_intelligence_aggregator),
                implementation=lambda config, dependencies: threat_intelligence_aggregator
            )
            
            container.register_singleton(
                name='sanctions_manager',
                interface=type(sanctions_manager),
                implementation=lambda config, dependencies: sanctions_manager
            )
            
            container.register_singleton(
                name='aml_compliance_manager',
                interface=type(aml_compliance_manager),
                implementation=lambda config, dependencies: aml_compliance_manager
            )
            
            container.register_singleton(
                name='real_time_monitor',
                interface=type(get_real_time_monitor()),
                implementation=lambda config, dependencies: get_real_time_monitor()
            )
            
            container.register_singleton(
                name='fraud_analytics',
                interface=type(get_fraud_analytics()),
                implementation=lambda config, dependencies: get_fraud_analytics()
            )
            
            container.register_singleton(
                name='risk_score_cache',
                interface=type(get_risk_score_cache()),
                implementation=lambda config, dependencies: get_risk_score_cache()
            )
            
            container.register_singleton(
                name='notification_manager',
                interface=type(get_notification_manager()),
                implementation=lambda config, dependencies: get_notification_manager()
            )
            
        except ImportError as e:
            logger.warning(f"Could not register external service: {e}")


class ExternalServiceManager:
    """
    Manager for external service dependencies.
    
    Handles configuration and access to external APIs,
    databases, and third-party services.
    """
    
    def __init__(self):
        """Initialize external service manager."""
        self._services: Dict[str, Dict[str, Any]] = {}
        self._load_external_services()
    
    def _load_external_services(self) -> None:
        """Load external service configurations."""
        # Redis configuration
        self._services['redis'] = {
            'host': getattr(settings, 'REDIS_HOST', 'localhost'),
            'port': getattr(settings, 'REDIS_PORT', 6379),
            'db': getattr(settings, 'REDIS_DB', 0),
            'password': getattr(settings, 'REDIS_PASSWORD', None),
            'ssl': getattr(settings, 'REDIS_SSL', False),
            'timeout': getattr(settings, 'REDIS_TIMEOUT', 5),
        }
        
        # External API configurations
        self._services['fraud_database'] = {
            'api_key': getattr(settings, 'FRAUD_DATABASE_API_KEY', ''),
            'base_url': getattr(settings, 'FRAUD_DATABASE_URL', ''),
            'timeout': getattr(settings, 'FRAUD_DATABASE_TIMEOUT', 30),
            'retry_attempts': getattr(settings, 'FRAUD_DATABASE_RETRIES', 3),
        }
        
        # Email service configuration
        self._services['email'] = {
            'backend': getattr(settings, 'EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend'),
            'host': getattr(settings, 'EMAIL_HOST', 'localhost'),
            'port': getattr(settings, 'EMAIL_PORT', 587),
            'use_tls': getattr(settings, 'EMAIL_USE_TLS', True),
            'username': getattr(settings, 'EMAIL_HOST_USER', ''),
            'password': getattr(settings, 'EMAIL_HOST_PASSWORD', ''),
        }
        
        # SMS service configuration
        self._services['sms'] = {
            'provider': getattr(settings, 'SMS_PROVIDER', 'twilio'),
            'account_sid': getattr(settings, 'TWILIO_ACCOUNT_SID', ''),
            'auth_token': getattr(settings, 'TWILIO_AUTH_TOKEN', ''),
            'from_number': getattr(settings, 'TWILIO_FROM_NUMBER', ''),
        }
        
        logger.info(f"Loaded {len(self._services)} external service configurations")
    
    def get_service_config(self, service_name: str) -> Dict[str, Any]:
        """
        Get configuration for an external service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Service configuration dictionary
        """
        if service_name not in self._services:
            raise DependencyError(f"External service {service_name} not configured")
        
        return self._services[service_name].copy()
    
    def is_service_available(self, service_name: str) -> bool:
        """
        Check if an external service is available and configured.
        
        Args:
            service_name: Name of the service
            
        Returns:
            True if service is available
        """
        if service_name not in self._services:
            return False
        
        config = self._services[service_name]
        
        # Check for required configuration
        if service_name == 'fraud_database':
            return bool(config.get('api_key') and config.get('base_url'))
        elif service_name == 'sms':
            return bool(config.get('account_sid') and config.get('auth_token'))
        elif service_name == 'email':
            return bool(config.get('host') and config.get('port'))
        else:
            return True
    
    def list_services(self) -> List[str]:
        """List all configured external services."""
        return list(self._services.keys())


# Global instances
_service_container = None
_service_locator = ServiceLocator
_external_service_manager = ExternalServiceManager()


def get_service_container() -> ServiceContainer:
    """Get the global service container."""
    global _service_container
    if _service_container is None:
        _service_container = ServiceLocator.get_container()
    return _service_container


def resolve_service(name: str) -> Any:
    """
    Resolve a service by name.
    
    Args:
        name: Service name
        
    Returns:
        Service instance
    """
    return ServiceLocator.resolve(name)


def get_service(interface: Type) -> Any:
    """
    Get a service by interface type.
    
    Args:
        interface: Service interface type
        
    Returns:
        Service instance
    """
    return ServiceLocator.get(interface)


def get_external_service_config(service_name: str) -> Dict[str, Any]:
    """
    Get external service configuration.
    
    Args:
        service_name: Service name
        
    Returns:
        Service configuration
    """
    return _external_service_manager.get_service_config(service_name)


def is_external_service_available(service_name: str) -> bool:
    """
    Check if external service is available.
    
    Args:
        service_name: Service name
        
    Returns:
        True if available
    """
    return _external_service_manager.is_service_available(service_name)
