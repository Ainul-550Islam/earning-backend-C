"""
Integration Bridge Module
Bridge system for connecting different integration components
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_handler import integration_handler
from .integ_adapter import adapter_registry
from .integ_constants import *

User = get_user_model()
logger = logging.getLogger('security.integration.bridge')


class IntegrationBridge:
    """Bridge for connecting integration components"""
    
    def __init__(self, name: str):
        self.name = name
        self.source_adapters = {}
        self.target_adapters = {}
        self.transformations = {}
        self.filters = {}
        self.routes = {}
        self.enabled = True
        self.connection_status = 'disconnected'
        self.statistics = {
            'messages_processed': 0,
            'messages_failed': 0,
            'last_activity': None,
            'uptime_start': timezone.now()
        }
    
    def add_source_adapter(self, adapter_name: str, adapter_config: Dict[str, Any] = None):
        """Add source adapter"""
        self.source_adapters[adapter_name] = adapter_config or {}
        logger.info(f"Added source adapter to bridge {self.name}: {adapter_name}")
    
    def add_target_adapter(self, adapter_name: str, adapter_config: Dict[str, Any] = None):
        """Add target adapter"""
        self.target_adapters[adapter_name] = adapter_config or {}
        logger.info(f"Added target adapter to bridge {self.name}: {adapter_name}")
    
    def remove_source_adapter(self, adapter_name: str):
        """Remove source adapter"""
        if adapter_name in self.source_adapters:
            del self.source_adapters[adapter_name]
            logger.info(f"Removed source adapter from bridge {self.name}: {adapter_name}")
    
    def remove_target_adapter(self, adapter_name: str):
        """Remove target adapter"""
        if adapter_name in self.target_adapters:
            del self.target_adapters[adapter_name]
            logger.info(f"Removed target adapter from bridge {self.name}: {adapter_name}")
    
    def add_transformation(self, transformation_name: str, transformation_func: Callable):
        """Add data transformation"""
        self.transformations[transformation_name] = transformation_func
        logger.info(f"Added transformation to bridge {self.name}: {transformation_name}")
    
    def add_filter(self, filter_name: str, filter_func: Callable):
        """Add data filter"""
        self.filters[filter_name] = filter_func
        logger.info(f"Added filter to bridge {self.name}: {filter_name}")
    
    def add_route(self, route_name: str, source: str, target: str, 
                  transformations: List[str] = None, filters: List[str] = None):
        """Add message route"""
        self.routes[route_name] = {
            'source': source,
            'target': target,
            'transformations': transformations or [],
            'filters': filters or []
        }
        logger.info(f"Added route to bridge {self.name}: {route_name}")
    
    def remove_route(self, route_name: str):
        """Remove message route"""
        if route_name in self.routes:
            del self.routes[route_name]
            logger.info(f"Removed route from bridge {self.name}: {route_name}")
    
    def connect(self) -> bool:
        """Connect bridge to all adapters"""
        try:
            connected_sources = 0
            connected_targets = 0
            
            # Connect source adapters
            for adapter_name, config in self.source_adapters.items():
                adapter = adapter_registry.get_adapter(adapter_name)
                if adapter and adapter.connection_status != 'connected':
                    if adapter.connect():
                        connected_sources += 1
                    else:
                        logger.error(f"Failed to connect source adapter: {adapter_name}")
            
            # Connect target adapters
            for adapter_name, config in self.target_adapters.items():
                adapter = adapter_registry.get_adapter(adapter_name)
                if adapter and adapter.connection_status != 'connected':
                    if adapter.connect():
                        connected_targets += 1
                    else:
                        logger.error(f"Failed to connect target adapter: {adapter_name}")
            
            total_adapters = len(self.source_adapters) + len(self.target_adapters)
            total_connected = connected_sources + connected_targets
            
            if total_connected == total_adapters:
                self.connection_status = 'connected'
                logger.info(f"Bridge {self.name} connected successfully")
                return True
            else:
                self.connection_status = 'partial'
                logger.warning(f"Bridge {self.name} partially connected: {total_connected}/{total_adapters}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting bridge {self.name}: {e}")
            self.connection_status = 'error'
            return False
    
    def disconnect(self):
        """Disconnect bridge from all adapters"""
        try:
            # Disconnect source adapters
            for adapter_name in self.source_adapters:
                adapter = adapter_registry.get_adapter(adapter_name)
                if adapter:
                    adapter.disconnect()
            
            # Disconnect target adapters
            for adapter_name in self.target_adapters:
                adapter = adapter_registry.get_adapter(adapter_name)
                if adapter:
                    adapter.disconnect()
            
            self.connection_status = 'disconnected'
            logger.info(f"Bridge {self.name} disconnected")
            
        except Exception as e:
            logger.error(f"Error disconnecting bridge {self.name}: {e}")
    
    def process_message(self, route_name: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process message through bridge"""
        if not self.enabled:
            return {
                'status': 'error',
                'message': 'Bridge disabled'
            }
        
        if self.connection_status not in ['connected', 'partial']:
            return {
                'status': 'error',
                'message': f'Bridge not connected: {self.connection_status}'
            }
        
        try:
            # Get route
            route = self.routes.get(route_name)
            if not route:
                return {
                    'status': 'error',
                    'message': f'Route not found: {route_name}'
                }
            
            # Apply filters
            for filter_name in route['filters']:
                filter_func = self.filters.get(filter_name)
                if filter_func and not filter_func(message):
                    return {
                        'status': 'skipped',
                        'message': f'Message filtered by: {filter_name}'
                    }
            
            # Apply transformations
            transformed_message = message.copy()
            for transformation_name in route['transformations']:
                transformation_func = self.transformations.get(transformation_name)
                if transformation_func:
                    try:
                        transformed_message = transformation_func(transformed_message)
                    except Exception as e:
                        logger.error(f"Error in transformation {transformation_name}: {e}")
                        return {
                            'status': 'error',
                            'message': f'Transformation error: {transformation_name}'
                        }
            
            # Send to target adapter
            target_adapter = adapter_registry.get_adapter(route['target'])
            if not target_adapter:
                return {
                    'status': 'error',
                    'message': f'Target adapter not found: {route["target"]}'
                }
            
            result = target_adapter.send_data(transformed_message)
            
            # Update statistics
            self.statistics['messages_processed'] += 1
            self.statistics['last_activity'] = timezone.now()
            
            if result.get('status') == 'success':
                return {
                    'status': 'success',
                    'message': 'Message processed successfully',
                    'target': route['target']
                }
            else:
                self.statistics['messages_failed'] += 1
                return result
                
        except Exception as e:
            self.statistics['messages_failed'] += 1
            logger.error(f"Error processing message in bridge {self.name}: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def process_message_async(self, route_name: str, message: Dict[str, Any]) -> str:
        """Process message asynchronously"""
        task_id = SecurityUtils.generate_uuid()
        
        # Process asynchronously
        asyncio.create_task(self._process_message_async_task(task_id, route_name, message))
        
        return task_id
    
    async def _process_message_async_task(self, task_id: str, route_name: str, message: Dict[str, Any]):
        """Async message processing task"""
        try:
            result = self.process_message(route_name, message)
            logger.info(f"Async task {task_id} completed: {result.get('status')}")
        except Exception as e:
            logger.error(f"Error in async task {task_id}: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get bridge status"""
        uptime = timezone.now() - self.statistics['uptime_start']
        
        return {
            'name': self.name,
            'enabled': self.enabled,
            'connection_status': self.connection_status,
            'source_adapters': list(self.source_adapters.keys()),
            'target_adapters': list(self.target_adapters.keys()),
            'routes': list(self.routes.keys()),
            'transformations': list(self.transformations.keys()),
            'filters': list(self.filters.keys()),
            'statistics': {
                **self.statistics,
                'uptime_seconds': uptime.total_seconds(),
                'success_rate': (
                    self.statistics['messages_processed'] / 
                    (self.statistics['messages_processed'] + self.statistics['messages_failed'])
                    if (self.statistics['messages_processed'] + self.statistics['messages_failed']) > 0 else 0
                )
            }
        }
    
    def enable(self):
        """Enable bridge"""
        self.enabled = True
        logger.info(f"Bridge {self.name} enabled")
    
    def disable(self):
        """Disable bridge"""
        self.enabled = False
        logger.info(f"Bridge {self.name} disabled")
    
    def reset_statistics(self):
        """Reset bridge statistics"""
        self.statistics = {
            'messages_processed': 0,
            'messages_failed': 0,
            'last_activity': None,
            'uptime_start': timezone.now()
        }
        logger.info(f"Bridge {self.name} statistics reset")


class BridgeManager:
    """Manager for integration bridges"""
    
    def __init__(self):
        self.bridges = {}
        self.bridge_templates = {}
        self.global_filters = {}
        self.global_transformations = {}
        self.enabled = True
    
    def create_bridge(self, bridge_name: str, bridge_config: Dict[str, Any] = None) -> IntegrationBridge:
        """Create a new bridge"""
        bridge = IntegrationBridge(bridge_name)
        
        if bridge_config:
            self._configure_bridge(bridge, bridge_config)
        
        self.bridges[bridge_name] = bridge
        logger.info(f"Created bridge: {bridge_name}")
        
        return bridge
    
    def _configure_bridge(self, bridge: IntegrationBridge, config: Dict[str, Any]):
        """Configure bridge from configuration"""
        # Add source adapters
        for adapter_name, adapter_config in config.get('source_adapters', {}).items():
            bridge.add_source_adapter(adapter_name, adapter_config)
        
        # Add target adapters
        for adapter_name, adapter_config in config.get('target_adapters', {}).items():
            bridge.add_target_adapter(adapter_name, adapter_config)
        
        # Add routes
        for route_name, route_config in config.get('routes', {}).items():
            bridge.add_route(
                route_name,
                route_config['source'],
                route_config['target'],
                route_config.get('transformations'),
                route_config.get('filters')
            )
    
    def remove_bridge(self, bridge_name: str) -> bool:
        """Remove a bridge"""
        if bridge_name in self.bridges:
            bridge = self.bridges[bridge_name]
            bridge.disconnect()
            del self.bridges[bridge_name]
            logger.info(f"Removed bridge: {bridge_name}")
            return True
        return False
    
    def get_bridge(self, bridge_name: str) -> Optional[IntegrationBridge]:
        """Get bridge by name"""
        return self.bridges.get(bridge_name)
    
    def connect_all_bridges(self) -> Dict[str, bool]:
        """Connect all bridges"""
        results = {}
        
        for bridge_name, bridge in self.bridges.items():
            results[bridge_name] = bridge.connect()
        
        return results
    
    def disconnect_all_bridges(self):
        """Disconnect all bridges"""
        for bridge in self.bridges.values():
            bridge.disconnect()
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all bridges"""
        return {
            'enabled': self.enabled,
            'total_bridges': len(self.bridges),
            'connected_bridges': len([
                name for name, bridge in self.bridges.items()
                if bridge.connection_status == 'connected'
            ]),
            'bridges': {
                name: bridge.get_status()
                for name, bridge in self.bridges.items()
            }
        }
    
    def add_global_filter(self, filter_name: str, filter_func: Callable):
        """Add global filter"""
        self.global_filters[filter_name] = filter_func
        logger.info(f"Added global filter: {filter_name}")
    
    def add_global_transformation(self, transformation_name: str, transformation_func: Callable):
        """Add global transformation"""
        self.global_transformations[transformation_name] = transformation_func
        logger.info(f"Added global transformation: {transformation_name}")
    
    def apply_global_filters_to_bridge(self, bridge_name: str):
        """Apply global filters to bridge"""
        bridge = self.get_bridge(bridge_name)
        if bridge:
            for filter_name, filter_func in self.global_filters.items():
                bridge.add_filter(filter_name, filter_func)
    
    def apply_global_transformations_to_bridge(self, bridge_name: str):
        """Apply global transformations to bridge"""
        bridge = self.get_bridge(bridge_name)
        if bridge:
            for transformation_name, transformation_func in self.global_transformations.items():
                bridge.add_transformation(transformation_name, transformation_func)
    
    def create_bridge_from_template(self, template_name: str, bridge_name: str, 
                                  overrides: Dict[str, Any] = None) -> Optional[IntegrationBridge]:
        """Create bridge from template"""
        template = self.bridge_templates.get(template_name)
        if not template:
            logger.error(f"Bridge template not found: {template_name}")
            return None
        
        # Merge template with overrides
        config = template.copy()
        if overrides:
            self._merge_config(config, overrides)
        
        return self.create_bridge(bridge_name, config)
    
    def _merge_config(self, base_config: Dict[str, Any], overrides: Dict[str, Any]):
        """Merge configuration dictionaries"""
        for key, value in overrides.items():
            if isinstance(value, dict) and key in base_config and isinstance(base_config[key], dict):
                self._merge_config(base_config[key], value)
            else:
                base_config[key] = value
    
    def register_bridge_template(self, template_name: str, template_config: Dict[str, Any]):
        """Register bridge template"""
        self.bridge_templates[template_name] = template_config
        logger.info(f"Registered bridge template: {template_name}")
    
    def enable_all_bridges(self):
        """Enable all bridges"""
        for bridge in self.bridges.values():
            bridge.enable()
    
    def disable_all_bridges(self):
        """Disable all bridges"""
        for bridge in self.bridges.values():
            bridge.disable()
    
    def enable(self):
        """Enable bridge manager"""
        self.enabled = True
        logger.info("Bridge manager enabled")
    
    def disable(self):
        """Disable bridge manager"""
        self.enabled = False
        logger.info("Bridge manager disabled")


# Global bridge manager
bridge_manager = BridgeManager()


# Built-in filters and transformations
def security_event_filter(message: Dict[str, Any]) -> bool:
    """Filter for security events"""
    return message.get('event_type') in ['security_event', 'threat_detected', 'incident_created']

def high_severity_filter(message: Dict[str, Any]) -> bool:
    """Filter for high severity events"""
    return message.get('severity') in ['high', 'critical']

def timestamp_transformation(message: Dict[str, Any]) -> Dict[str, Any]:
    """Add timestamp to message"""
    message['timestamp'] = timezone.now().isoformat()
    return message

def add_source_transformation(source_name: str):
    """Create transformation to add source"""
    def transformation(message: Dict[str, Any]) -> Dict[str, Any]:
        message['source'] = source_name
        return message
    return transformation

# Register global filters and transformations
bridge_manager.add_global_filter('security_event', security_event_filter)
bridge_manager.add_global_filter('high_severity', high_severity_filter)
bridge_manager.add_global_transformation('add_timestamp', timestamp_transformation)


# Export symbols
__all__ = [
    'IntegrationBridge',
    'BridgeManager',
    'bridge_manager',
    'security_event_filter',
    'high_severity_filter',
    'timestamp_transformation',
    'add_source_transformation'
]