"""
Integration Handler Module
Core integration handler for security system
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
from ..monitoring import monitoring_manager

User = get_user_model()
logger = logging.getLogger('security.integration.handler')


class IntegrationHandler:
    """Core integration handler for security system"""
    
    def __init__(self):
        self.integrations = {}
        self.active_handlers = {}
        self.handler_configs = {}
        self.execution_queue = []
        self.max_queue_size = 1000
        self.processing_enabled = True
        self.error_threshold = 10
        self.error_counts = {}
    
    def register_integration(self, integration_name: str, integration_class: Type):
        """Register an integration"""
        self.integrations[integration_name] = integration_class
        self.error_counts[integration_name] = 0
        logger.info(f"Registered integration: {integration_name}")
    
    def unregister_integration(self, integration_name: str) -> bool:
        """Unregister an integration"""
        if integration_name in self.integrations:
            del self.integrations[integration_name]
            if integration_name in self.active_handlers:
                del self.active_handlers[integration_name]
            if integration_name in self.error_counts:
                del self.error_counts[integration_name]
            logger.info(f"Unregistered integration: {integration_name}")
            return True
        return False
    
    def get_integration(self, integration_name: str) -> Optional[Type]:
        """Get integration class by name"""
        return self.integrations.get(integration_name)
    
    def activate_handler(self, integration_name: str, config: Dict[str, Any] = None) -> bool:
        """Activate an integration handler"""
        integration_class = self.get_integration(integration_name)
        
        if not integration_class:
            logger.error(f"Integration not found: {integration_name}")
            return False
        
        try:
            # Create handler instance
            handler = integration_class()
            
            # Configure handler
            if config:
                handler.configure(config)
                self.handler_configs[integration_name] = config
            
            # Initialize handler
            if handler.initialize():
                self.active_handlers[integration_name] = handler
                logger.info(f"Activated handler: {integration_name}")
                return True
            else:
                logger.error(f"Failed to initialize handler: {integration_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error activating handler {integration_name}: {e}")
            return False
    
    def deactivate_handler(self, integration_name: str) -> bool:
        """Deactivate an integration handler"""
        if integration_name in self.active_handlers:
            handler = self.active_handlers[integration_name]
            
            try:
                handler.cleanup()
                del self.active_handlers[integration_name]
                logger.info(f"Deactivated handler: {integration_name}")
                return True
            except Exception as e:
                logger.error(f"Error deactivating handler {integration_name}: {e}")
                return False
        
        return False
    
    def execute_integration(self, integration_name: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute integration handler"""
        handler = self.active_handlers.get(integration_name)
        
        if not handler:
            return {
                'status': 'error',
                'message': f'Handler not active: {integration_name}'
            }
        
        if not self.processing_enabled:
            return {
                'status': 'skipped',
                'message': 'Integration processing disabled'
            }
        
        try:
            # Check error threshold
            if self.error_counts.get(integration_name, 0) >= self.error_threshold:
                return {
                    'status': 'error',
                    'message': f'Error threshold exceeded for: {integration_name}'
                }
            
            # Execute handler
            result = handler.handle(event_data)
            
            # Reset error count on success
            if result.get('status') == 'success':
                self.error_counts[integration_name] = 0
            
            # Record execution
            self._record_execution(integration_name, event_data, result)
            
            return result
            
        except Exception as e:
            # Increment error count
            self.error_counts[integration_name] = self.error_counts.get(integration_name, 0) + 1
            
            # Log error
            logger.error(f"Error executing integration {integration_name}: {e}")
            
            # Record error execution
            self._record_execution(integration_name, event_data, {'status': 'error', 'error': str(e)})
            
            return {
                'status': 'error',
                'message': str(e),
                'error_count': self.error_counts[integration_name]
            }
    
    def execute_async(self, integration_name: str, event_data: Dict[str, Any]) -> str:
        """Execute integration asynchronously"""
        task_id = SecurityUtils.generate_uuid()
        
        # Add to execution queue
        self.execution_queue.append({
            'task_id': task_id,
            'integration_name': integration_name,
            'event_data': event_data,
            'created_at': timezone.now()
        })
        
        # Maintain queue size
        if len(self.execution_queue) > self.max_queue_size:
            self.execution_queue.pop(0)
        
        # Process queue asynchronously
        asyncio.create_task(self._process_queue_item(task_id))
        
        return task_id
    
    async def _process_queue_item(self, task_id: str):
        """Process item from execution queue"""
        # Find task in queue
        task_item = None
        for item in self.execution_queue:
            if item['task_id'] == task_id:
                task_item = item
                break
        
        if task_item:
            try:
                # Execute integration
                result = self.execute_integration(
                    task_item['integration_name'],
                    task_item['event_data']
                )
                
                # Update task with result
                task_item['result'] = result
                task_item['completed_at'] = timezone.now()
                
            except Exception as e:
                logger.error(f"Error processing queue item {task_id}: {e}")
                task_item['result'] = {'status': 'error', 'error': str(e)}
                task_item['completed_at'] = timezone.now()
    
    def _record_execution(self, integration_name: str, event_data: Dict[str, Any], result: Dict[str, Any]):
        """Record integration execution"""
        try:
            SecurityLog.objects.create(
                security_type='integration_execution',
                severity='info' if result.get('status') == 'success' else 'error',
                description=f"Integration execution: {integration_name} - {result.get('status', 'unknown')}",
                metadata={
                    'integration_name': integration_name,
                    'event_type': event_data.get('event_type', 'unknown'),
                    'result_status': result.get('status', 'unknown'),
                    'execution_id': SecurityUtils.generate_uuid()
                }
            )
        except Exception as e:
            logger.error(f"Error recording integration execution: {e}")
    
    def get_active_handlers(self) -> List[str]:
        """Get list of active handlers"""
        return list(self.active_handlers.keys())
    
    def get_handler_status(self, integration_name: str) -> Dict[str, Any]:
        """Get handler status"""
        handler = self.active_handlers.get(integration_name)
        
        if not handler:
            return {
                'status': 'inactive',
                'error_count': self.error_counts.get(integration_name, 0)
            }
        
        return {
            'status': 'active',
            'error_count': self.error_counts.get(integration_name, 0),
            'config': self.handler_configs.get(integration_name, {}),
            'health': handler.get_health() if hasattr(handler, 'get_health') else 'unknown'
        }
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all integrations"""
        status = {
            'total_integrations': len(self.integrations),
            'active_handlers': len(self.active_handlers),
            'processing_enabled': self.processing_enabled,
            'queue_size': len(self.execution_queue),
            'integrations': {}
        }
        
        for integration_name in self.integrations:
            status['integrations'][integration_name] = self.get_handler_status(integration_name)
        
        return status
    
    def enable_processing(self):
        """Enable integration processing"""
        self.processing_enabled = True
        logger.info("Integration processing enabled")
    
    def disable_processing(self):
        """Disable integration processing"""
        self.processing_enabled = False
        logger.info("Integration processing disabled")
    
    def reset_error_counts(self, integration_name: str = None):
        """Reset error counts"""
        if integration_name:
            self.error_counts[integration_name] = 0
            logger.info(f"Reset error count for: {integration_name}")
        else:
            for name in self.error_counts:
                self.error_counts[name] = 0
            logger.info("Reset all error counts")
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get execution queue status"""
        return {
            'queue_size': len(self.execution_queue),
            'max_queue_size': self.max_queue_size,
            'processing_enabled': self.processing_enabled,
            'pending_tasks': len([t for t in self.execution_queue if 'result' not in t]),
            'completed_tasks': len([t for t in self.execution_queue if 'result' in t])
        }
    
    def clear_queue(self):
        """Clear execution queue"""
        self.execution_queue.clear()
        logger.info("Integration execution queue cleared")


class BaseIntegrationHandler:
    """Base class for integration handlers"""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.config = {}
        self.initialized = False
        self.health_status = 'unknown'
    
    def configure(self, config: Dict[str, Any]):
        """Configure handler"""
        self.config = config
    
    def initialize(self) -> bool:
        """Initialize handler"""
        try:
            self.initialized = True
            self.health_status = 'healthy'
            return True
        except Exception as e:
            logger.error(f"Error initializing {self.name}: {e}")
            self.health_status = 'unhealthy'
            return False
    
    def handle(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle integration event - override in subclasses"""
        raise NotImplementedError("Subclasses must implement handle method")
    
    def cleanup(self):
        """Clean up handler resources"""
        try:
            self.initialized = False
            self.health_status = 'stopped'
        except Exception as e:
            logger.error(f"Error cleaning up {self.name}: {e}")
    
    def get_health(self) -> str:
        """Get handler health status"""
        return self.health_status
    
    def validate_config(self) -> bool:
        """Validate handler configuration"""
        return True
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary"""
        return {
            'name': self.name,
            'initialized': self.initialized,
            'health': self.health_status,
            'config_keys': list(self.config.keys())
        }


# Global integration handler
integration_handler = IntegrationHandler()


# Export symbols
__all__ = [
    'IntegrationHandler',
    'BaseIntegrationHandler',
    'integration_handler'
]