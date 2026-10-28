"""
Integration System - Rate Limit Module Integration

Comprehensive integration system for the rate limiting module with support for:
- Core connectors and adapters
- Event-driven architecture
- Cross-system data synchronization
- Performance monitoring
- Security and validation
- Health checking and audit logging

This module provides enterprise-grade integration capabilities for the
rate limiting system, enabling seamless communication with external services,
real-time monitoring, and robust error handling.
"""

from .integ_handler import integration_handler
from .integ_signals import signal_manager
from .integ_adapter import IntegrationAdapter, AdapterFactory
from .integ_registry import integration_registry
from .integ_constants import IntegrationEvent, IntegrationStatus, IntegrationPriority
from .bridge import bridge_manager, create_synchronous_bridge, create_asynchronous_bridge
from .event_bus import event_bus, EventBuilder
from .transformer import data_transformer
from .circuit_breaker import circuit_breaker_manager, circuit_breaker_protection
from .versioning import version_manager
from .webhooks_integration import webhook_manager
from .data_bridge import data_bridge_manager
from .message_queue import message_queue_manager
from .data_validator import data_validator
from .integ_exceptions import IntegrationError, ValidationError
from .fallback_logic import fallback_manager
from .auth_bridge import auth_bridge
from .performance_monitor import performance_monitor
from .integ_audit_logs import audit_logger
from .health_check import health_checker
from .sync_manager import sync_manager

# Export main components
__all__ = [
    # Core handlers and managers
    'integration_handler',
    'signal_manager',
    'integration_registry',
    'event_bus',
    
    # Adapters and factories
    'IntegrationAdapter',
    'AdapterFactory',
    'data_transformer',
    
    # Bridge and communication
    'bridge_manager',
    'create_synchronous_bridge',
    'create_asynchronous_bridge',
    
    # Circuit breaker and fallback
    'circuit_breaker_manager',
    'circuit_breaker_protection',
    'fallback_manager',
    
    # Monitoring and health
    'performance_monitor',
    'health_checker',
    'audit_logger',
    
    # Authentication and authorization
    'auth_bridge',
    
    # Data management
    'data_validator',
    'sync_manager',
    'data_bridge_manager',
    'message_queue_manager',
    'webhook_manager',
    'version_manager',
    
    # Constants and enums
    'IntegrationEvent',
    'IntegrationStatus',
    'IntegrationPriority',
    
    # Exceptions
    'IntegrationError',
    'ValidationError',
]

# Version information
__version__ = '1.0.0'
__author__ = 'Rate Limit Integration Team'
__description__ = 'Enterprise-grade integration system for rate limiting'

# Initialize integration system
def initialize_integration_system():
    """Initialize the integration system."""
    try:
        # Start all background services
        logger.info("Initializing integration system...")
        
        # The background services are started automatically in their __init__ methods
        # We just need to ensure they're properly configured
        
        # Register default integration handlers
        from .integ_constants import EVENT_HANDLERS
        for event_type, handlers in EVENT_HANDLERS.items():
            for handler in handlers:
                integration_handler.register_handler(event_type, handler)
        
        # Register default webhooks
        from .webhooks_integration import create_slack_webhook, create_discord_webhook
        # Webhooks would be configured based on environment variables
        
        logger.info("Integration system initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize integration system: {str(e)}")
        return False

# Auto-initialize when imported
initialize_integration_system()
