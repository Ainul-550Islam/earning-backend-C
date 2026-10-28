# Reconstructed from services/FIX_ALL_PART1_Services5-10.py (was never split into
# individual files, leaving alerts.services unimportable — see audit).
# Fixed on extraction: AlertNotification -> Notification (real model name),
# api.alerts.utils.* -> real existing module paths.

import logging

logger = logging.getLogger(__name__)


class RegistryService:
    """
    Consolidates registry and singleton management.
    Eliminates duplicates from: integration/__init__.py + integration/integ_registry.py
    """

    _integrations = {}
    _audit_logger = None
    _circuit_breaker = None

    @staticmethod
    def get_integration_registry():
        """
        Get integration registry (singleton).
        
        Previously duplicated in:
        - alerts/integration/__init__.py
        - alerts/integration/integ_registry.py
        
        Returns:
            dict: Registry of integrations
        """
        logger.info("Accessing integration registry")
        
        if not RegistryService._integrations:
            RegistryService._initialize_registry()
        
        return RegistryService._integrations

    @staticmethod
    def _initialize_registry():
        """Initialize integration registry"""
        from api.alerts.services.channels import (
            SlackAlertService,
            EmailAlertService,
            PagerDutyService,
            OpsGenieService,
            WebhookAlertService
        )
        
        RegistryService._integrations = {
            'slack': SlackAlertService,
            'email': EmailAlertService,
            'pagerduty': PagerDutyService,
            'opsgenie': OpsGenieService,
            'webhook': WebhookAlertService,
        }
        
        logger.info("Integration registry initialized")

    @staticmethod
    def register_integration(name, service_class):
        """Register a new integration"""
        RegistryService._integrations[name] = service_class
        logger.info(f"Registered integration: {name}")

    @staticmethod
    def get_integration(name):
        """Get specific integration"""
        if not RegistryService._integrations:
            RegistryService._initialize_registry()
        
        return RegistryService._integrations.get(name)

    @staticmethod
    def get_audit_logger():
        """
        Get audit logger (singleton).
        
        Previously duplicated in:
        - alerts/integration/__init__.py
        - alerts/integration/integ_audit_logs.py
        
        Returns:
            AuditLogger: Audit logger instance
        """
        if RegistryService._audit_logger is None:
            from api.alerts.integration.integ_audit_logs import AuditLogger
            RegistryService._audit_logger = AuditLogger()
        
        return RegistryService._audit_logger

    @staticmethod
    def get_circuit_breaker():
        """
        Get circuit breaker (singleton).
        
        Previously duplicated in:
        - alerts/circuit_breaker.py
        - alerts/integration/__init__.py
        
        Returns:
            CircuitBreaker: Circuit breaker instance
        """
        if RegistryService._circuit_breaker is None:
            from api.alerts.circuit_breaker import SimpleCircuitBreaker
            RegistryService._circuit_breaker = SimpleCircuitBreaker({})
        
        return RegistryService._circuit_breaker


__all__ = ['RegistryService']
