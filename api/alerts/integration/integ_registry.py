"""
Integration Registry for alerts app - Central registry for integration management
"""
from typing import Dict, List, Any, Optional, Type
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    """Central registry for managing integrations"""
    
    def __init__(self):
        self.integrations = {}
        self.adapters = {}
        self.handlers = {}
        self.configurations = {}
        self.status_cache = {}
        self.cache_timeout = 300  # 5 minutes
        
    def register_integration(self, integration_name: str, integration_class: Type, config: Dict[str, Any] = None):
        """Register an integration class with configuration"""
        try:
            # Create integration instance - fall back to no-arg construction
            # for integration classes that don't accept a config dict.
            try:
                integration_instance = integration_class(config or {})
            except TypeError:
                integration_instance = integration_class()
            
            # Store in registry
            self.integrations[integration_name] = {
                'class': integration_class,
                'instance': integration_instance,
                'config': config or {},
                'registered_at': timezone.now(),
                'enabled': config.get('enabled', True) if config else True
            }
            
            # Initialize integration if enabled and it supports connecting
            if self.integrations[integration_name]['enabled'] and hasattr(integration_instance, 'connect'):
                success = integration_instance.connect()
                self.integrations[integration_name]['connected'] = success
                logger.info(f"Integration {integration_name} registered and connected: {success}")
            else:
                self.integrations[integration_name]['connected'] = False
                logger.info(f"Integration {integration_name} registered (not connected)")
            
            # Clear cache
            self._clear_status_cache()
            
        except Exception as e:
            logger.error(f"Error registering integration {integration_name}: {e}")
            raise
    
    def unregister_integration(self, integration_name: str):
        """Unregister an integration"""
        if integration_name in self.integrations:
            integration_info = self.integrations[integration_name]
            
            try:
                # Disconnect integration
                if integration_info.get('connected', False):
                    integration_info['instance'].disconnect()
                
                # Remove from registry
                del self.integrations[integration_name]
                
                # Clear cache
                self._clear_status_cache()
                
                logger.info(f"Integration {integration_name} unregistered")
                
            except Exception as e:
                logger.error(f"Error unregistering integration {integration_name}: {e}")
                raise
        else:
            logger.warning(f"Integration {integration_name} not found in registry")
    
    def get_integration(self, integration_name: str) -> Optional[Dict[str, Any]]:
        """Get integration information"""
        return self.integrations.get(integration_name)
    
    def get_integration_instance(self, integration_name: str):
        """Get integration instance"""
        integration_info = self.integrations.get(integration_name)
        return integration_info['instance'] if integration_info else None
    
    def list_integrations(self) -> List[str]:
        """List all registered integration names"""
        return list(self.integrations.keys())
    
    def get_enabled_integrations(self) -> List[str]:
        """List enabled integrations"""
        return [
            name for name, info in self.integrations.items()
            if info.get('enabled', False)
        ]
    
    def get_connected_integrations(self) -> List[str]:
        """List connected integrations"""
        return [
            name for name, info in self.integrations.items()
            if info.get('connected', False)
        ]
    
    def enable_integration(self, integration_name: str) -> bool:
        """Enable an integration"""
        if integration_name not in self.integrations:
            logger.error(f"Integration {integration_name} not found")
            return False
        
        integration_info = self.integrations[integration_name]
        
        if not integration_info.get('enabled', False):
            try:
                # Connect integration
                success = integration_info['instance'].connect()
                integration_info['enabled'] = True
                integration_info['connected'] = success
                
                # Clear cache
                self._clear_status_cache()
                
                logger.info(f"Integration {integration_name} enabled: {success}")
                return success
                
            except Exception as e:
                logger.error(f"Error enabling integration {integration_name}: {e}")
                return False
        else:
            logger.info(f"Integration {integration_name} already enabled")
            return True
    
    def disable_integration(self, integration_name: str) -> bool:
        """Disable an integration"""
        if integration_name not in self.integrations:
            logger.error(f"Integration {integration_name} not found")
            return False
        
        integration_info = self.integrations[integration_name]
        
        if integration_info.get('enabled', False):
            try:
                # Disconnect integration
                success = integration_info['instance'].disconnect()
                integration_info['enabled'] = False
                integration_info['connected'] = False
                
                # Clear cache
                self._clear_status_cache()
                
                logger.info(f"Integration {integration_name} disabled")
                return True
                
            except Exception as e:
                logger.error(f"Error disabling integration {integration_name}: {e}")
                return False
        else:
            logger.info(f"Integration {integration_name} already disabled")
            return True
    
    def update_integration_config(self, integration_name: str, new_config: Dict[str, Any]) -> bool:
        """Update integration configuration"""
        if integration_name not in self.integrations:
            logger.error(f"Integration {integration_name} not found")
            return False
        
        integration_info = self.integrations[integration_name]
        
        try:
            # Update configuration
            integration_info['config'].update(new_config)
            success = integration_info['instance'].update_config(new_config)
            
            # Clear cache
            self._clear_status_cache()
            
            logger.info(f"Integration {integration_name} configuration updated")
            return success
            
        except Exception as e:
            logger.error(f"Error updating integration {integration_name} config: {e}")
            return False
    
    def get_integration_status(self, integration_name: str) -> Optional[Dict[str, Any]]:
        """Get integration status with caching"""
        # Try cache first
        cache_key = f"integ_status_{integration_name}"
        cached_status = cache.get(cache_key)
        
        if cached_status:
            return cached_status
        
        # Get fresh status
        integration_info = self.integrations.get(integration_name)
        if not integration_info:
            return None
        
        try:
            # Get health status
            health_check = integration_info['instance'].health_check()
            
            status = {
                'name': integration_name,
                'enabled': integration_info.get('enabled', False),
                'connected': integration_info.get('connected', False),
                'health': health_check,
                'registered_at': integration_info['registered_at'].isoformat(),
                'last_check': timezone.now().isoformat()
            }
            
            # Cache status
            cache.set(cache_key, status, self.cache_timeout)
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting integration status {integration_name}: {e}")
            return {
                'name': integration_name,
                'enabled': integration_info.get('enabled', False),
                'connected': False,
                'health': {'healthy': False, 'error': 'Operation failed'},
                'last_check': timezone.now().isoformat()
            }
    
    def get_all_integrations_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all integrations"""
        all_status = {}
        
        for integration_name in self.integrations:
            all_status[integration_name] = self.get_integration_status(integration_name)
        
        return all_status
    
    def send_data_to_integration(self, integration_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data to specific integration"""
        integration_info = self.integrations.get(integration_name)
        if not integration_info:
            return {
                'success': False,
                'error': f'Integration {integration_name} not found'
            }
        
        if not integration_info.get('enabled', False):
            return {
                'success': False,
                'error': f'Integration {integration_name} is disabled'
            }
        
        if not integration_info.get('connected', False):
            return {
                'success': False,
                'error': f'Integration {integration_name} is not connected'
            }
        
        try:
            return integration_info['instance'].send_data(data)
        except Exception as e:
            logger.error(f"Error sending data to {integration_name}: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def receive_data_from_integration(self, integration_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Receive data from specific integration"""
        integration_info = self.integrations.get(integration_name)
        if not integration_info:
            logger.error(f"Integration {integration_name} not found")
            return []
        
        if not integration_info.get('enabled', False):
            logger.warning(f"Integration {integration_name} is disabled")
            return []
        
        if not integration_info.get('connected', False):
            logger.warning(f"Integration {integration_name} is not connected")
            return []
        
        try:
            return integration_info['instance'].receive_data(limit)
        except Exception as e:
            logger.error(f"Error receiving data from {integration_name}: {e}")
            return []
    
    def send_data_to_all_integrations(self, data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Send data to all enabled and connected integrations"""
        results = {}
        
        for integration_name, integration_info in self.integrations.items():
            if integration_info.get('enabled', False) and integration_info.get('connected', False):
                try:
                    result = integration_info['instance'].send_data(data)
                    results[integration_name] = result
                except Exception as e:
                    logger.error(f"Error sending data to {integration_name}: {e}")
                    results[integration_name] = {
                        'success': False,
                        'error': str(e)
                    }
        
        return results
    
    def perform_health_checks(self) -> Dict[str, Dict[str, Any]]:
        """Perform health checks on all integrations"""
        health_results = {}
        
        for integration_name, integration_info in self.integrations.items():
            if integration_info.get('enabled', False):
                try:
                    health_check = integration_info['instance'].health_check()
                    health_results[integration_name] = health_check
                except Exception as e:
                    logger.error(f"Error performing health check for {integration_name}: {e}")
                    health_results[integration_name] = {
                        'healthy': False,
                        'error': str(e),
                        'timestamp': timezone.now().isoformat()
                    }
        
        return health_results
    
    def get_integration_metrics(self) -> Dict[str, Any]:
        """Get integration metrics"""
        total_integrations = len(self.integrations)
        enabled_count = len(self.get_enabled_integrations())
        connected_count = len(self.get_connected_integrations())
        
        # Get health status counts
        health_results = self.perform_health_checks()
        healthy_count = sum(1 for result in health_results.values() if result.get('healthy', False))
        
        return {
            'total_integrations': total_integrations,
            'enabled_integrations': enabled_count,
            'connected_integrations': connected_count,
            'healthy_integrations': healthy_count,
            'unhealthy_integrations': enabled_count - healthy_count,
            'last_updated': timezone.now().isoformat()
        }
    
    def _clear_status_cache(self):
        """Clear integration status cache"""
        for integration_name in self.integrations:
            cache_key = f"integ_status_{integration_name}"
            cache.delete(cache_key)
    
    def cleanup(self):
        """Cleanup all integrations"""
        for integration_name in list(self.integrations.keys()):
            try:
                self.unregister_integration(integration_name)
            except Exception as e:
                logger.error(f"Error cleaning up integration {integration_name}: {e}")
        
        self.integrations.clear()
        self._clear_status_cache()
        logger.info("Integration registry cleaned up")


class IntegrationConfigurationManager:
    """Manager for integration configurations"""
    
    def __init__(self):
        self.configurations = {}
        self.load_configurations()
    
    def load_configurations(self):
        """Load configurations from settings"""
        integration_configs = getattr(settings, 'INTEGRATION_CONFIGS', {})
        
        for integration_name, config in integration_configs.items():
            self.configurations[integration_name] = config
            logger.debug(f"Loaded configuration for {integration_name}")
    
    def save_configuration(self, integration_name: str, config: Dict[str, Any]) -> bool:
        """Save integration configuration (to cache or database)"""
        try:
            self.configurations[integration_name] = config
            
            # Save to cache
            cache_key = f"integ_config_{integration_name}"
            cache.set(cache_key, config, timeout=3600)  # 1 hour
            
            logger.info(f"Saved configuration for {integration_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration for {integration_name}: {e}")
            return False
    
    def get_configuration(self, integration_name: str) -> Optional[Dict[str, Any]]:
        """Get integration configuration"""
        # Try cache first
        cache_key = f"integ_config_{integration_name}"
        cached_config = cache.get(cache_key)
        
        if cached_config:
            return cached_config
        
        # Return from memory
        return self.configurations.get(integration_name)
    
    def delete_configuration(self, integration_name: str) -> bool:
        """Delete integration configuration"""
        try:
            if integration_name in self.configurations:
                del self.configurations[integration_name]
            
            # Delete from cache
            cache_key = f"integ_config_{integration_name}"
            cache.delete(cache_key)
            
            logger.info(f"Deleted configuration for {integration_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting configuration for {integration_name}: {e}")
            return False
    
    def validate_configuration(self, integration_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate integration configuration"""
        from api.alerts.integration.integ_adapter import validate_adapter_config
        
        if integration_type in ['webhook', 'api', 'database']:
            return validate_adapter_config(config)
        
        # Default validation
        errors = []
        
        if 'enabled' not in config:
            errors.append('enabled field is required')
        
        if 'name' not in config:
            errors.append('name field is required')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


# Global registry instance
integration_registry = IntegrationRegistry()
configuration_manager = IntegrationConfigurationManager()


def get_integration_registry() -> IntegrationRegistry:
    """Get the global integration registry"""
    return integration_registry


def get_configuration_manager() -> IntegrationConfigurationManager:
    """Get the global configuration manager"""
    return configuration_manager


def initialize_integrations():
    """Initialize integrations from settings"""
    from api.alerts.integration.integ_handler import IntegrationHandlerFactory
    from api.alerts.integration.integ_adapter import AdapterFactory
    
    integration_configs = getattr(settings, 'INTEGRATION_CONFIGS', {})
    
    for integration_name, config in integration_configs.items():
        try:
            # Get integration type and handler type
            integration_type = config.get('type', 'webhook')
            handler_type = config.get('handler_type', integration_type)
            
            # Create handler
            handler = IntegrationHandlerFactory.create_handler(handler_type, config)
            if not handler:
                logger.error(f"Could not create handler for {integration_name}")
                continue
            
            # Create adapter if specified
            adapter_type = config.get('adapter_type')
            if adapter_type:
                adapter = AdapterFactory.create_adapter(adapter_type, config)
                if adapter:
                    # Combine handler and adapter
                    class CombinedIntegration(handler.__class__):
                        def __init__(self, config):
                            super().__init__(config)
                            self.adapter = adapter
                        
                        def send_data(self, data):
                            # Transform with adapter
                            transformed_data = self.adapter.transform_outgoing(data)
                            return super().send_data(transformed_data)
                        
                        def receive_data(self, limit=100):
                            # Receive with handler
                            raw_data = super().receive_data(limit)
                            # Transform with adapter
                            return [self.adapter.transform_incoming(item) for item in raw_data]
                    
                    handler = CombinedIntegration(config)
            
            # Register integration
            integration_registry.register_integration(integration_name, handler.__class__, config)
            
        except Exception as e:
            logger.error(f"Error initializing integration {integration_name}: {e}")


def auto_register_integrations():
    """Auto-register integrations from settings"""
    try:
        initialize_integrations()
        logger.info("Auto-registration of integrations completed")
    except Exception as e:
        logger.error(f"Error in auto-registration: {e}")


# Initialize on module import
try:
    auto_register_integrations()
except Exception as e:
    logger.error(f"Error initializing integration registry: {e}")
