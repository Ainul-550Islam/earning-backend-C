"""
Integration Handler

Central handler for all integration operations
in the offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional, Callable
from django.utils import timezone
from django.conf import settings
from .integ_registry import IntegrationRegistry
from .integ_signals import IntegrationSignals
from .integ_constants import IntegrationType, IntegrationStatus
from ..exceptions import IntegrationError

logger = logging.getLogger(__name__)


class IntegrationHandler:
    """
    Central handler for managing all integrations.
    
    Provides unified interface for:
    - External system integrations
    - Internal service communications
    - Data synchronization
    - Event handling
    - Error management
    """
    
    def __init__(self):
        self.registry = IntegrationRegistry()
        self.signals = IntegrationSignals()
        self.active_integrations = {}
        self.error_handlers = {}
        
        # Initialize default integrations
        self._initialize_default_integrations()
    
    def _initialize_default_integrations(self):
        """Initialize default integrations from configuration."""
        try:
            default_integrations = getattr(settings, 'DEFAULT_INTEGRATIONS', {})
            
            for integration_name, integration_config in default_integrations.items():
                self.register_integration(integration_name, integration_config)
                
        except Exception as e:
            logger.error(f"Error initializing default integrations: {e}")
    
    def register_integration(self, name: str, config: Dict[str, Any]) -> bool:
        """
        Register a new integration.
        
        Args:
            name: Integration name
            config: Integration configuration
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate configuration
            if not self._validate_integration_config(config):
                logger.error(f"Invalid configuration for integration {name}")
                return False
            
            # Register with registry
            integration_id = self.registry.register(name, config)
            
            # Initialize integration
            integration = self._create_integration(integration_id, config)
            
            if integration:
                self.active_integrations[integration_id] = integration
                
                # Emit signal
                self.signals.integration_registered.send(
                    sender=self.__class__,
                    integration_id=integration_id,
                    integration_name=name,
                    config=config
                )
                
                logger.info(f"Successfully registered integration: {name}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error registering integration {name}: {e}")
            return False
    
    def _validate_integration_config(self, config: Dict[str, Any]) -> bool:
        """Validate integration configuration."""
        try:
            required_fields = ['type', 'endpoint', 'credentials']
            
            for field in required_fields:
                if field not in config:
                    logger.error(f"Missing required field: {field}")
                    return False
            
            # Validate integration type
            integration_type = config.get('type')
            if integration_type not in [t.value for t in IntegrationType]:
                logger.error(f"Invalid integration type: {integration_type}")
                return False
            
            # Validate endpoint
            endpoint = config.get('endpoint')
            if not endpoint or not isinstance(endpoint, str):
                logger.error(f"Invalid endpoint: {endpoint}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating integration config: {e}")
            return False
    
    def _create_integration(self, integration_id: str, config: Dict[str, Any]):
        """Create integration instance from configuration."""
        try:
            integration_type = config.get('type')
            
            if integration_type == IntegrationType.WEBHOOK.value:
                from .webhooks_integration import WebhookIntegration
                return WebhookIntegration(integration_id, config)
            
            elif integration_type == IntegrationType.API.value:
                from .api_integration import APIIntegration
                return APIIntegration(integration_id, config)
            
            elif integration_type == IntegrationType.DATABASE.value:
                from .database_integration import DatabaseIntegration
                return DatabaseIntegration(integration_id, config)
            
            elif integration_type == IntegrationType.MESSAGE_QUEUE.value:
                from .message_queue_integration import MessageQueueIntegration
                return MessageQueueIntegration(integration_id, config)
            
            else:
                logger.error(f"Unknown integration type: {integration_type}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating integration {integration_id}: {e}")
            return None
    
    def execute_integration(self, integration_id: str, action: str, 
                         data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute action on a specific integration.
        
        Args:
            integration_id: Integration identifier
            action: Action to execute
            data: Action data
            
        Returns:
            Execution result
        """
        try:
            integration = self.active_integrations.get(integration_id)
            
            if not integration:
                raise IntegrationError(f"Integration not found: {integration_id}")
            
            # Pre-execution signal
            self.signals.integration_before_execute.send(
                sender=self.__class__,
                integration_id=integration_id,
                action=action,
                data=data
            )
            
            # Execute action
            result = integration.execute(action, data)
            
            # Post-execution signal
            self.signals.integration_after_execute.send(
                sender=self.__class__,
                integration_id=integration_id,
                action=action,
                data=data,
                result=result
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing integration {integration_id}: {e}")
            
            # Error signal
            self.signals.integration_error.send(
                sender=self.__class__,
                integration_id=integration_id,
                action=action,
                error=str(e)
            )
            
            raise IntegrationError(f"Integration execution failed: {e}")
    
    def get_integration_status(self, integration_id: str) -> Dict[str, Any]:
        """
        Get status of a specific integration.
        
        Args:
            integration_id: Integration identifier
            
        Returns:
            Integration status
        """
        try:
            integration = self.active_integrations.get(integration_id)
            
            if not integration:
                return {
                    'status': IntegrationStatus.NOT_FOUND.value,
                    'message': 'Integration not found'
                }
            
            return integration.get_status()
            
        except Exception as e:
            logger.error(f"Error getting integration status {integration_id}: {e}")
            return {
                'status': IntegrationStatus.ERROR.value,
                'message': str(e)
            }
    
    def list_integrations(self, integration_type: str = None) -> List[Dict[str, Any]]:
        """
        List all registered integrations.
        
        Args:
            integration_type: Filter by integration type
            
        Returns:
            List of integrations
        """
        try:
            integrations = []
            
            for integration_id, integration in self.active_integrations.items():
                if integration_type and integration.get_type() != integration_type:
                    continue
                
                integrations.append({
                    'id': integration_id,
                    'name': integration.get_name(),
                    'type': integration.get_type(),
                    'status': integration.get_status(),
                    'last_sync': integration.get_last_sync(),
                    'config': integration.get_safe_config()
                })
            
            return integrations
            
        except Exception as e:
            logger.error(f"Error listing integrations: {e}")
            return []
    
    def update_integration_config(self, integration_id: str, 
                              config: Dict[str, Any]) -> bool:
        """
        Update integration configuration.
        
        Args:
            integration_id: Integration identifier
            config: New configuration
            
        Returns:
            True if successful, False otherwise
        """
        try:
            integration = self.active_integrations.get(integration_id)
            
            if not integration:
                logger.error(f"Integration not found: {integration_id}")
                return False
            
            # Validate new configuration
            if not self._validate_integration_config(config):
                logger.error(f"Invalid configuration for integration {integration_id}")
                return False
            
            # Update configuration
            result = integration.update_config(config)
            
            if result:
                # Emit update signal
                self.signals.integration_updated.send(
                    sender=self.__class__,
                    integration_id=integration_id,
                    config=config
                )
                
                logger.info(f"Updated configuration for integration {integration_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating integration config {integration_id}: {e}")
            return False
    
    def disable_integration(self, integration_id: str) -> bool:
        """
        Disable an integration.
        
        Args:
            integration_id: Integration identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            integration = self.active_integrations.get(integration_id)
            
            if not integration:
                logger.error(f"Integration not found: {integration_id}")
                return False
            
            # Disable integration
            result = integration.disable()
            
            if result:
                # Emit disable signal
                self.signals.integration_disabled.send(
                    sender=self.__class__,
                    integration_id=integration_id
                )
                
                logger.info(f"Disabled integration {integration_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error disabling integration {integration_id}: {e}")
            return False
    
    def enable_integration(self, integration_id: str) -> bool:
        """
        Enable an integration.
        
        Args:
            integration_id: Integration identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            integration = self.active_integrations.get(integration_id)
            
            if not integration:
                logger.error(f"Integration not found: {integration_id}")
                return False
            
            # Enable integration
            result = integration.enable()
            
            if result:
                # Emit enable signal
                self.signals.integration_enabled.send(
                    sender=self.__class__,
                    integration_id=integration_id
                )
                
                logger.info(f"Enabled integration {integration_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error enabling integration {integration_id}: {e}")
            return False
    
    def remove_integration(self, integration_id: str) -> bool:
        """
        Remove an integration completely.
        
        Args:
            integration_id: Integration identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            integration = self.active_integrations.get(integration_id)
            
            if not integration:
                logger.error(f"Integration not found: {integration_id}")
                return False
            
            # Disable first
            integration.disable()
            
            # Remove from active integrations
            del self.active_integrations[integration_id]
            
            # Remove from registry
            self.registry.unregister(integration_id)
            
            # Emit remove signal
            self.signals.integration_removed.send(
                sender=self.__class__,
                integration_id=integration_id
            )
            
            logger.info(f"Removed integration {integration_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing integration {integration_id}: {e}")
            return False
    
    def register_error_handler(self, integration_id: str, 
                           error_handler: Callable) -> bool:
        """
        Register error handler for integration.
        
        Args:
            integration_id: Integration identifier
            error_handler: Error handler function
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if integration_id not in self.active_integrations:
                logger.error(f"Integration not found: {integration_id}")
                return False
            
            self.error_handlers[integration_id] = error_handler
            
            logger.info(f"Registered error handler for integration {integration_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering error handler {integration_id}: {e}")
            return False
    
    def handle_integration_error(self, integration_id: str, error: Exception, 
                             context: Dict[str, Any] = None) -> bool:
        """
        Handle integration error.
        
        Args:
            integration_id: Integration identifier
            error: Error to handle
            context: Error context
            
        Returns:
            True if handled, False otherwise
        """
        try:
            error_handler = self.error_handlers.get(integration_id)
            
            if error_handler:
                return error_handler(error, context)
            
            # Default error handling
            logger.error(f"Unhandled error in integration {integration_id}: {error}")
            
            # Emit error signal
            self.signals.integration_error.send(
                sender=self.__class__,
                integration_id=integration_id,
                error=str(error),
                context=context
            )
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling integration error: {e}")
            return False
    
    def sync_all_integrations(self) -> Dict[str, Any]:
        """
        Synchronize all active integrations.
        
        Returns:
            Synchronization results
        """
        try:
            results = {}
            
            for integration_id, integration in self.active_integrations.items():
                try:
                    result = integration.sync()
                    results[integration_id] = result
                    
                except Exception as e:
                    logger.error(f"Error syncing integration {integration_id}: {e}")
                    results[integration_id] = {
                        'success': False,
                        'error': str(e)
                    }
            
            # Emit sync signal
            self.signals.integrations_synced.send(
                sender=self.__class__,
                results=results
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error syncing integrations: {e}")
            return {'error': str(e)}
    
    def get_integration_metrics(self, integration_id: str = None) -> Dict[str, Any]:
        """
        Get metrics for integrations.
        
        Args:
            integration_id: Specific integration ID (None for all)
            
        Returns:
            Integration metrics
        """
        try:
            if integration_id:
                integration = self.active_integrations.get(integration_id)
                
                if not integration:
                    return {'error': f'Integration not found: {integration_id}'}
                
                return integration.get_metrics()
            
            # Get metrics for all integrations
            all_metrics = {}
            
            for integ_id, integration in self.active_integrations.items():
                all_metrics[integ_id] = integration.get_metrics()
            
            return all_metrics
            
        except Exception as e:
            logger.error(f"Error getting integration metrics: {e}")
            return {'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all integrations.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall_status': 'healthy',
                'integrations': {},
                'timestamp': timezone.now().isoformat()
            }
            
            for integration_id, integration in self.active_integrations.items():
                integ_health = integration.health_check()
                health_status['integrations'][integration_id] = integ_health
                
                # Update overall status if any integration is unhealthy
                if integ_health.get('status') != 'healthy':
                    health_status['overall_status'] = 'degraded'
            
            return health_status
            
        except Exception as e:
            logger.error(f"Error performing health check: {e}")
            return {
                'overall_status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }


# Global integration handler instance
integration_handler = IntegrationHandler()
