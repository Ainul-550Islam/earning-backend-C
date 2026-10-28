"""
Integration Registry Module
Registry for managing integration system components
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_handler import integration_handler, BaseIntegrationHandler
from .integ_adapter import adapter_registry, IntegrationAdapter

User = get_user_model()
logger = logging.getLogger('security.integration.registry')


class IntegrationRegistry:
    """Registry for managing integration system components"""
    
    def __init__(self):
        self.integrations = {}
        self.adapters = {}
        self.handlers = {}
        self.configurations = {}
        self.dependencies = {}
        self.health_status = {}
        self.metrics = {}
        self.enabled = True
        self.last_health_check = None
        self.health_check_interval = 300  # 5 minutes
    
    def register_integration(self, integration_name: str, integration_class: Type[BaseIntegrationHandler],
                          dependencies: List[str] = None, configuration: Dict[str, Any] = None):
        """Register an integration"""
        self.integrations[integration_name] = integration_class
        self.dependencies[integration_name] = dependencies or []
        self.configurations[integration_name] = configuration or {}
        self.health_status[integration_name] = 'registered'
        self.metrics[integration_name] = {
            'registrations': 1,
            'activations': 0,
            'deactivations': 0,
            'errors': 0,
            'last_activity': None
        }
        
        logger.info(f"Registered integration: {integration_name}")
    
    def unregister_integration(self, integration_name: str) -> bool:
        """Unregister an integration"""
        if integration_name in self.integrations:
            # Deactivate if active
            if integration_name in integration_handler.active_handlers:
                integration_handler.deactivate_handler(integration_name)
            
            # Remove from registry
            del self.integrations[integration_name]
            del self.dependencies[integration_name]
            del self.configurations[integration_name]
            del self.health_status[integration_name]
            del self.metrics[integration_name]
            
            logger.info(f"Unregistered integration: {integration_name}")
            return True
        
        return False
    
    def register_adapter(self, adapter_name: str, adapter_class: Type[IntegrationAdapter],
                       configuration: Dict[str, Any] = None):
        """Register an adapter"""
        self.adapters[adapter_name] = adapter_class
        self.configurations[adapter_name] = configuration or {}
        self.health_status[adapter_name] = 'registered'
        self.metrics[adapter_name] = {
            'registrations': 1,
            'connections': 0,
            'disconnections': 0,
            'errors': 0,
            'last_activity': None
        }
        
        logger.info(f"Registered adapter: {adapter_name}")
    
    def unregister_adapter(self, adapter_name: str) -> bool:
        """Unregister an adapter"""
        if adapter_name in self.adapters:
            # Disconnect if connected
            adapter = adapter_registry.get_adapter(adapter_name)
            if adapter:
                adapter.disconnect()
            
            # Remove from registry
            del self.adapters[adapter_name]
            del self.configurations[adapter_name]
            del self.health_status[adapter_name]
            del self.metrics[adapter_name]
            
            logger.info(f"Unregistered adapter: {adapter_name}")
            return True
        
        return False
    
    def activate_integration(self, integration_name: str, configuration: Dict[str, Any] = None) -> bool:
        """Activate an integration"""
        if integration_name not in self.integrations:
            logger.error(f"Integration not found: {integration_name}")
            return False
        
        # Check dependencies
        dependencies = self.dependencies[integration_name]
        for dep in dependencies:
            if dep not in integration_handler.active_handlers:
                logger.error(f"Dependency not active: {dep}")
                return False
        
        # Use provided config or registered config
        config = configuration or self.configurations[integration_name]
        
        # Activate handler
        if integration_handler.activate_handler(integration_name, config):
            self.health_status[integration_name] = 'active'
            self.metrics[integration_name]['activations'] += 1
            self.metrics[integration_name]['last_activity'] = timezone.now()
            
            logger.info(f"Activated integration: {integration_name}")
            return True
        
        return False
    
    def deactivate_integration(self, integration_name: str) -> bool:
        """Deactivate an integration"""
        if integration_handler.deactivate_handler(integration_name):
            self.health_status[integration_name] = 'inactive'
            self.metrics[integration_name]['deactivations'] += 1
            
            logger.info(f"Deactivated integration: {integration_name}")
            return True
        
        return False
    
    def connect_adapter(self, adapter_name: str, configuration: Dict[str, Any] = None) -> bool:
        """Connect an adapter"""
        if adapter_name not in self.adapters:
            logger.error(f"Adapter not found: {adapter_name}")
            return False
        
        # Create adapter instance
        adapter_class = self.adapters[adapter_name]
        config = configuration or self.configurations[adapter_name]
        
        try:
            # Create adapter (this is a simplified approach)
            # In practice, you'd need to handle different adapter types
            adapter = adapter_class(adapter_name, config.get('connection_string', ''))
            
            # Configure adapter
            adapter.configure(config)
            
            # Connect adapter
            if adapter.connect():
                # Register with adapter registry
                adapter_registry.register_adapter(adapter)
                
                self.health_status[adapter_name] = 'connected'
                self.metrics[adapter_name]['connections'] += 1
                self.metrics[adapter_name]['last_activity'] = timezone.now()
                
                logger.info(f"Connected adapter: {adapter_name}")
                return True
            else:
                self.health_status[adapter_name] = 'connection_failed'
                self.metrics[adapter_name]['errors'] += 1
                
                return False
                
        except Exception as e:
            logger.error(f"Error connecting adapter {adapter_name}: {e}")
            self.health_status[adapter_name] = 'error'
            self.metrics[adapter_name]['errors'] += 1
            return False
    
    def disconnect_adapter(self, adapter_name: str) -> bool:
        """Disconnect an adapter"""
        adapter = adapter_registry.get_adapter(adapter_name)
        
        if adapter:
            adapter.disconnect()
            self.health_status[adapter_name] = 'disconnected'
            self.metrics[adapter_name]['disconnections'] += 1
            
            logger.info(f"Disconnected adapter: {adapter_name}")
            return True
        
        return False
    
    def get_integration_status(self, integration_name: str) -> Dict[str, Any]:
        """Get integration status"""
        status = {
            'name': integration_name,
            'registered': integration_name in self.integrations,
            'health': self.health_status.get(integration_name, 'unknown'),
            'metrics': self.metrics.get(integration_name, {}),
            'dependencies': self.dependencies.get(integration_name, []),
            'configuration_keys': list(self.configurations.get(integration_name, {}).keys())
        }
        
        # Add handler status if active
        if integration_name in integration_handler.active_handlers:
            handler_status = integration_handler.get_handler_status(integration_name)
            status.update({
                'handler_status': handler_status,
                'active': True
            })
        else:
            status['active'] = False
        
        return status
    
    def get_adapter_status(self, adapter_name: str) -> Dict[str, Any]:
        """Get adapter status"""
        status = {
            'name': adapter_name,
            'registered': adapter_name in self.adapters,
            'health': self.health_status.get(adapter_name, 'unknown'),
            'metrics': self.metrics.get(adapter_name, {}),
            'configuration_keys': list(self.configurations.get(adapter_name, {}).keys())
        }
        
        # Add adapter status if connected
        adapter = adapter_registry.get_adapter(adapter_name)
        if adapter:
            adapter_status = adapter.get_status()
            status.update({
                'adapter_status': adapter_status,
                'connected': adapter.connection_status == 'connected'
            })
        else:
            status['connected'] = False
        
        return status
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all integrations and adapters"""
        return {
            'enabled': self.enabled,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'integrations': {
                name: self.get_integration_status(name)
                for name in self.integrations
            },
            'adapters': {
                name: self.get_adapter_status(name)
                for name in self.adapters
            },
            'summary': {
                'total_integrations': len(self.integrations),
                'active_integrations': len(integration_handler.active_handlers),
                'total_adapters': len(self.adapters),
                'connected_adapters': len([
                    name for name, adapter in adapter_registry.adapters.items()
                    if adapter.connection_status == 'connected'
                ])
            }
        }
    
    def perform_health_check(self) -> Dict[str, Any]:
        """Perform health check on all components"""
        health_results = {
            'timestamp': timezone.now(),
            'integrations': {},
            'adapters': {},
            'overall_health': 'healthy'
        }
        
        # Check integrations
        for integration_name in self.integrations:
            integration_health = self._check_integration_health(integration_name)
            health_results['integrations'][integration_name] = integration_health
            
            if integration_health['status'] != 'healthy':
                health_results['overall_health'] = 'degraded'
        
        # Check adapters
        for adapter_name in self.adapters:
            adapter_health = self._check_adapter_health(adapter_name)
            health_results['adapters'][adapter_name] = adapter_health
            
            if adapter_health['status'] != 'healthy':
                health_results['overall_health'] = 'degraded'
        
        self.last_health_check = timezone.now()
        
        # Log health check results
        SecurityLog.objects.create(
            security_type='health_check',
            severity='info' if health_results['overall_health'] == 'healthy' else 'warning',
            description=f"Integration system health check: {health_results['overall_health']}",
            metadata=health_results
        )
        
        return health_results
    
    def _check_integration_health(self, integration_name: str) -> Dict[str, Any]:
        """Check integration health"""
        health = {
            'status': 'unknown',
            'checks': {},
            'issues': []
        }
        
        try:
            # Check if registered
            if integration_name not in self.integrations:
                health['status'] = 'error'
                health['issues'].append('Integration not registered')
                return health
            
            # Check if active
            handler = integration_handler.get_handler(integration_name)
            if not handler:
                health['status'] = 'inactive'
                health['checks']['active'] = False
                return health
            
            health['checks']['active'] = True
            
            # Check error count
            error_count = integration_handler.error_counts.get(integration_name, 0)
            health['checks']['error_count'] = error_count
            
            if error_count >= 5:
                health['status'] = 'unhealthy'
                health['issues'].append(f'High error count: {error_count}')
            else:
                health['status'] = 'healthy'
            
            # Check dependencies
            dependencies = self.dependencies[integration_name]
            health['checks']['dependencies'] = {}
            
            for dep in dependencies:
                dep_active = dep in integration_handler.active_handlers
                health['checks']['dependencies'][dep] = dep_active
                
                if not dep_active:
                    health['status'] = 'degraded'
                    health['issues'].append(f'Dependency inactive: {dep}')
            
        except Exception as e:
            health['status'] = 'error'
            health['issues'].append(f'Health check error: {str(e)}')
        
        return health
    
    def _check_adapter_health(self, adapter_name: str) -> Dict[str, Any]:
        """Check adapter health"""
        health = {
            'status': 'unknown',
            'checks': {},
            'issues': []
        }
        
        try:
            # Check if registered
            if adapter_name not in self.adapters:
                health['status'] = 'error'
                health['issues'].append('Adapter not registered')
                return health
            
            # Check if connected
            adapter = adapter_registry.get_adapter(adapter_name)
            if not adapter:
                health['status'] = 'disconnected'
                health['checks']['connected'] = False
                return health
            
            health['checks']['connected'] = adapter.connection_status == 'connected'
            health['checks']['connection_status'] = adapter.connection_status
            
            if adapter.connection_status != 'connected':
                health['status'] = 'unhealthy'
                health['issues'].append(f'Connection status: {adapter.connection_status}')
            else:
                health['status'] = 'healthy'
            
            # Check last activity
            if adapter.last_activity:
                time_since_activity = timezone.now() - adapter.last_activity
                health['checks']['last_activity_minutes'] = time_since_activity.total_seconds() / 60
                
                if time_since_activity > timedelta(hours=1):
                    health['status'] = 'degraded'
                    health['issues'].append('No recent activity')
            
        except Exception as e:
            health['status'] = 'error'
            health['issues'].append(f'Health check error: {str(e)}')
        
        return health
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get integration metrics"""
        metrics = {
            'timestamp': timezone.now(),
            'integrations': {},
            'adapters': {},
            'totals': {
                'total_integrations': len(self.integrations),
                'active_integrations': len(integration_handler.active_handlers),
                'total_adapters': len(self.adapters),
                'connected_adapters': len([
                    name for name, adapter in adapter_registry.adapters.items()
                    if adapter.connection_status == 'connected'
                ])
            }
        }
        
        # Integration metrics
        for integration_name in self.integrations:
            integration_metrics = self.metrics.get(integration_name, {}).copy()
            
            # Add current error count
            integration_metrics['current_error_count'] = integration_handler.error_counts.get(integration_name, 0)
            
            metrics['integrations'][integration_name] = integration_metrics
        
        # Adapter metrics
        for adapter_name in self.adapters:
            adapter_metrics = self.metrics.get(adapter_name, {}).copy()
            
            # Add connection status
            adapter = adapter_registry.get_adapter(adapter_name)
            if adapter:
                adapter_metrics['connection_status'] = adapter.connection_status
                adapter_metrics['last_activity'] = adapter.last_activity.isoformat() if adapter.last_activity else None
            
            metrics['adapters'][adapter_name] = adapter_metrics
        
        return metrics
    
    def update_configuration(self, component_name: str, configuration: Dict[str, Any]) -> bool:
        """Update component configuration"""
        if component_name in self.integrations:
            self.configurations[component_name] = configuration
            
            # Reactivate if active
            if component_name in integration_handler.active_handlers:
                integration_handler.deactivate_handler(component_name)
                integration_handler.activate_handler(component_name, configuration)
            
            logger.info(f"Updated configuration for integration: {component_name}")
            return True
        
        elif component_name in self.adapters:
            self.configurations[component_name] = configuration
            
            # Reconnect if connected
            adapter = adapter_registry.get_adapter(component_name)
            if adapter:
                adapter.disconnect()
                adapter.configure(configuration)
                adapter.connect()
            
            logger.info(f"Updated configuration for adapter: {component_name}")
            return True
        
        return False
    
    def enable(self):
        """Enable registry"""
        self.enabled = True
        logger.info("Integration registry enabled")
    
    def disable(self):
        """Disable registry"""
        self.enabled = False
        logger.info("Integration registry disabled")
    
    def cleanup(self):
        """Clean up registry"""
        # Deactivate all integrations
        for integration_name in list(integration_handler.active_handlers.keys()):
            integration_handler.deactivate_handler(integration_name)
        
        # Disconnect all adapters
        adapter_registry.disconnect_all()
        
        logger.info("Integration registry cleaned up")


# Global integration registry
integration_registry = IntegrationRegistry()


# Export symbols
__all__ = [
    'IntegrationRegistry',
    'integration_registry'
]