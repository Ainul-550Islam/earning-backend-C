"""
Integration Signals Module
Signal handling for integration system
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.dispatch import Signal, receiver
from django.conf import settings

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_handler import integration_handler

User = get_user_model()
logger = logging.getLogger('security.integration.signals')


# Define integration signals
integration_event = Signal()
integration_success = Signal()
integration_error = Signal()
integration_health_check = Signal()
integration_config_changed = Signal()


class IntegrationSignalHandler:
    """Handler for integration signals"""
    
    def __init__(self):
        self.signal_handlers = {}
        self.signal_history = []
        self.max_history = 1000
        self.enabled = True
        self._setup_signal_connections()
    
    def _setup_signal_connections(self):
        """Setup signal connections"""
        integration_event.connect(self._handle_integration_event, sender=None)
        integration_success.connect(self._handle_integration_success, sender=None)
        integration_error.connect(self._handle_integration_error, sender=None)
        integration_health_check.connect(self._handle_health_check, sender=None)
        integration_config_changed.connect(self._handle_config_changed, sender=None)
    
    def register_signal_handler(self, signal_name: str, handler: Callable):
        """Register a signal handler"""
        if signal_name not in self.signal_handlers:
            self.signal_handlers[signal_name] = []
        
        self.signal_handlers[signal_name].append(handler)
        logger.info(f"Registered signal handler for: {signal_name}")
    
    def unregister_signal_handler(self, signal_name: str, handler: Callable):
        """Unregister a signal handler"""
        if signal_name in self.signal_handlers:
            try:
                self.signal_handlers[signal_name].remove(handler)
                logger.info(f"Unregistered signal handler for: {signal_name}")
            except ValueError:
                logger.warning(f"Handler not found for signal: {signal_name}")
    
    def emit_signal(self, signal_name: str, **kwargs):
        """Emit a signal"""
        if not self.enabled:
            return
        
        try:
            # Record signal emission
            signal_record = {
                'signal_name': signal_name,
                'timestamp': timezone.now(),
                'kwargs': kwargs,
                'id': SecurityUtils.generate_uuid()
            }
            
            self.signal_history.append(signal_record)
            if len(self.signal_history) > self.max_history:
                self.signal_history.pop(0)
            
            # Emit Django signal
            if signal_name == 'integration_event':
                integration_event.send(sender=None, **kwargs)
            elif signal_name == 'integration_success':
                integration_success.send(sender=None, **kwargs)
            elif signal_name == 'integration_error':
                integration_error.send(sender=None, **kwargs)
            elif signal_name == 'integration_health_check':
                integration_health_check.send(sender=None, **kwargs)
            elif signal_name == 'integration_config_changed':
                integration_config_changed.send(sender=None, **kwargs)
            
            logger.debug(f"Emitted signal: {signal_name}")
            
        except Exception as e:
            logger.error(f"Error emitting signal {signal_name}: {e}")
    
    def _handle_integration_event(self, sender, **kwargs):
        """Handle integration event signal"""
        try:
            integration_name = kwargs.get('integration_name')
            event_data = kwargs.get('event_data', {})
            
            if integration_name:
                # Execute integration
                result = integration_handler.execute_integration(integration_name, event_data)
                
                # Emit result signal
                if result.get('status') == 'success':
                    self.emit_signal('integration_success', 
                                   integration_name=integration_name,
                                   result=result)
                else:
                    self.emit_signal('integration_error',
                                   integration_name=integration_name,
                                   error=result.get('message', 'Unknown error'),
                                   result=result)
            
            # Call registered handlers
            self._call_signal_handlers('integration_event', **kwargs)
            
        except Exception as e:
            logger.error(f"Error handling integration event signal: {e}")
    
    def _handle_integration_success(self, sender, **kwargs):
        """Handle integration success signal"""
        try:
            integration_name = kwargs.get('integration_name')
            result = kwargs.get('result', {})
            
            # Log success
            SecurityLog.objects.create(
                security_type='integration_success',
                severity='info',
                description=f"Integration success: {integration_name}",
                metadata={
                    'integration_name': integration_name,
                    'result': result
                }
            )
            
            # Update monitoring
            monitoring_manager.record_event('integration_success', 'info')
            
            # Call registered handlers
            self._call_signal_handlers('integration_success', **kwargs)
            
        except Exception as e:
            logger.error(f"Error handling integration success signal: {e}")
    
    def _handle_integration_error(self, sender, **kwargs):
        """Handle integration error signal"""
        try:
            integration_name = kwargs.get('integration_name')
            error = kwargs.get('error', 'Unknown error')
            result = kwargs.get('result', {})
            
            # Log error
            SecurityLog.objects.create(
                security_type='integration_error',
                severity='error',
                description=f"Integration error: {integration_name} - {error}",
                metadata={
                    'integration_name': integration_name,
                    'error': error,
                    'result': result
                }
            )
            
            # Update monitoring
            monitoring_manager.record_event('integration_error', 'error')
            
            # Create incident for critical errors
            if result.get('error_count', 0) >= 5:
                SecurityIncident.objects.create(
                    title=f"Integration Failure: {integration_name}",
                    incident_type='integration_failure',
                    severity='medium',
                    priority='medium',
                    description=f"Multiple integration failures detected: {integration_name}",
                    metadata={
                        'integration_name': integration_name,
                        'error_count': result.get('error_count', 0),
                        'last_error': error
                    }
                )
            
            # Call registered handlers
            self._call_signal_handlers('integration_error', **kwargs)
            
        except Exception as e:
            logger.error(f"Error handling integration error signal: {e}")
    
    def _handle_health_check(self, sender, **kwargs):
        """Handle health check signal"""
        try:
            integration_name = kwargs.get('integration_name')
            health_status = kwargs.get('health_status', 'unknown')
            
            # Log health check
            SecurityLog.objects.create(
                security_type='health_check',
                severity='info',
                description=f"Health check: {integration_name} - {health_status}",
                metadata={
                    'integration_name': integration_name,
                    'health_status': health_status
                }
            )
            
            # Call registered handlers
            self._call_signal_handlers('health_check', **kwargs)
            
        except Exception as e:
            logger.error(f"Error handling health check signal: {e}")
    
    def _handle_config_changed(self, sender, **kwargs):
        """Handle config changed signal"""
        try:
            integration_name = kwargs.get('integration_name')
            config = kwargs.get('config', {})
            
            # Log config change
            SecurityLog.objects.create(
                security_type='config_changed',
                severity='info',
                description=f"Configuration changed: {integration_name}",
                metadata={
                    'integration_name': integration_name,
                    'config_keys': list(config.keys())
                }
            )
            
            # Reactivate handler if needed
            if integration_name in integration_handler.active_handlers:
                integration_handler.deactivate_handler(integration_name)
                integration_handler.activate_handler(integration_name, config)
            
            # Call registered handlers
            self._call_signal_handlers('config_changed', **kwargs)
            
        except Exception as e:
            logger.error(f"Error handling config changed signal: {e}")
    
    def _call_signal_handlers(self, signal_name: str, **kwargs):
        """Call registered signal handlers"""
        handlers = self.signal_handlers.get(signal_name, [])
        
        for handler in handlers:
            try:
                handler(**kwargs)
            except Exception as e:
                logger.error(f"Error in signal handler {handler.__name__}: {e}")
    
    def get_signal_history(self, signal_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get signal history"""
        history = self.signal_history
        
        if signal_name:
            history = [s for s in history if s['signal_name'] == signal_name]
        
        return history[-limit:]
    
    def get_signal_statistics(self) -> Dict[str, Any]:
        """Get signal statistics"""
        total_signals = len(self.signal_history)
        
        # Count by signal type
        signal_counts = {}
        for signal in self.signal_history:
            signal_counts[signal['signal_name']] = signal_counts.get(signal['signal_name'], 0) + 1
        
        # Count by time period
        now = timezone.now()
        recent_signals = len([s for s in self.signal_history if s['timestamp'] >= now - timedelta(hours=1)])
        
        return {
            'total_signals': total_signals,
            'recent_signals': recent_signals,
            'signal_counts': signal_counts,
            'enabled': self.enabled,
            'registered_handlers': {
                name: len(handlers) for name, handlers in self.signal_handlers.items()
            }
        }
    
    def enable(self):
        """Enable signal handling"""
        self.enabled = True
        logger.info("Integration signal handling enabled")
    
    def disable(self):
        """Disable signal handling"""
        self.enabled = False
        logger.info("Integration signal handling disabled")
    
    def clear_history(self, signal_name: str = None):
        """Clear signal history"""
        if signal_name:
            self.signal_history = [
                s for s in self.signal_history 
                if s['signal_name'] != signal_name
            ]
            logger.info(f"Cleared signal history for: {signal_name}")
        else:
            self.signal_history.clear()
            logger.info("Cleared all signal history")


# Global signal handler
integration_signal_handler = IntegrationSignalHandler()


# Decorator for signal handlers
def integration_signal_handler_decorator(signal_name: str):
    """Decorator for registering signal handlers"""
    def decorator(func):
        integration_signal_handler.register_signal_handler(signal_name, func)
        return func
    return decorator


# Export symbols
__all__ = [
    'integration_event',
    'integration_success',
    'integration_error',
    'integration_health_check',
    'integration_config_changed',
    'IntegrationSignalHandler',
    'integration_signal_handler',
    'integration_signal_handler_decorator'
]