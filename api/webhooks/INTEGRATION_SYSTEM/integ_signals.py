"""Integration Signals

This module provides signal handling for integration system
with comprehensive event broadcasting and listening capabilities.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from django.dispatch import Signal, receiver
from django.utils import timezone
from django.conf import settings

from .integ_constants import IntegrationType, SignalType
from .integ_exceptions import SignalError
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class IntegrationSignals:
    """
    Integration signal manager for webhook system.
    Provides comprehensive signal broadcasting and listening.
    """
    
    # Define integration signals
    webhook_received = Signal()
    webhook_processed = Signal()
    webhook_failed = Signal()
    webhook_retried = Signal()
    
    batch_started = Signal()
    batch_completed = Signal()
    batch_failed = Signal()
    
    integration_connected = Signal()
    integration_disconnected = Signal()
    integration_error = Signal()
    
    data_validated = Signal()
    data_transformed = Signal()
    data_routed = Signal()
    
    performance_alert = Signal()
    health_check_failed = Signal()
    system_maintenance = Signal()
    
    def __init__(self):
        """Initialize the integration signals manager."""
        self.logger = logger
        self.monitor = PerformanceMonitor()
        self._listeners = {}
        self._signal_history = []
        self._signal_stats = {}
        
        # Load configuration
        self._load_configuration()
    
    def _load_configuration(self):
        """Load signal configuration from settings."""
        try:
            self.config = getattr(settings, 'WEBHOOK_SIGNAL_CONFIG', {})
            self.enabled_signals = self.config.get('enabled_signals', [])
            self.max_history = self.config.get('max_history', 1000)
            self.stats_enabled = self.config.get('stats_enabled', True)
            
            self.logger.info("Signal configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading signal configuration: {str(e)}")
            self.config = {}
            self.enabled_signals = []
            self.max_history = 1000
            self.stats_enabled = True
    
    def send_signal(self, signal_type: str, sender: Any = None, **kwargs) -> Dict[str, Any]:
        """
        Send an integration signal.
        
        Args:
            signal_type: Type of signal to send
            sender: Signal sender
            **kwargs: Signal arguments
            
        Returns:
            Signal result
        """
        try:
            # Check if signal is enabled
            if self.enabled_signals and signal_type not in self.enabled_signals:
                self.logger.warning(f"Signal {signal_type} not in enabled signals")
                return {'success': False, 'error': 'Signal not enabled'}
            
            # Get signal object
            signal = self._get_signal(signal_type)
            if not signal:
                self.logger.error(f"Signal {signal_type} not found")
                return {'success': False, 'error': 'Signal not found'}
            
            # Start performance monitoring
            with self.monitor.measure_signal(signal_type) as measurement:
                # Prepare signal data
                signal_data = {
                    'signal_type': signal_type,
                    'sender': sender,
                    'timestamp': timezone.now().isoformat(),
                    'data': kwargs
                }
                
                # Send signal
                result = signal.send(sender=sender, **kwargs)
                
                # Record signal in history
                self._record_signal(signal_data, result)
                
                # Update statistics
                if self.stats_enabled:
                    self._update_signal_stats(signal_type, result)
                
                # Compile final result
                final_result = {
                    'signal_type': signal_type,
                    'success': True,
                    'receivers': len(result),
                    'timestamp': signal_data['timestamp'],
                    'performance': measurement.get_metrics()
                }
                
                return final_result
                
        except Exception as e:
            self.logger.error(f"Error sending signal {signal_type}: {str(e)}")
            return {
                'signal_type': signal_type,
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _get_signal(self, signal_type: str) -> Optional[Signal]:
        """Get signal object by type."""
        signal_map = {
            'webhook_received': self.webhook_received,
            'webhook_processed': self.webhook_processed,
            'webhook_failed': self.webhook_failed,
            'webhook_retried': self.webhook_retried,
            'batch_started': self.batch_started,
            'batch_completed': self.batch_completed,
            'batch_failed': self.batch_failed,
            'integration_connected': self.integration_connected,
            'integration_disconnected': self.integration_disconnected,
            'integration_error': self.integration_error,
            'data_validated': self.data_validated,
            'data_transformed': self.data_transformed,
            'data_routed': self.data_routed,
            'performance_alert': self.performance_alert,
            'health_check_failed': self.health_check_failed,
            'system_maintenance': self.system_maintenance,
        }
        
        return signal_map.get(signal_type)
    
    def _record_signal(self, signal_data: Dict[str, Any], result: List) -> None:
        """Record signal in history."""
        try:
            history_entry = {
                'signal_data': signal_data,
                'result': result,
                'receivers_count': len(result),
                'recorded_at': timezone.now()
            }
            
            self._signal_history.append(history_entry)
            
            # Limit history size
            if len(self._signal_history) > self.max_history:
                self._signal_history = self._signal_history[-self.max_history:]
                
        except Exception as e:
            self.logger.error(f"Error recording signal: {str(e)}")
    
    def _update_signal_stats(self, signal_type: str, result: List) -> None:
        """Update signal statistics."""
        try:
            if signal_type not in self._signal_stats:
                self._signal_stats[signal_type] = {
                    'total_sent': 0,
                    'total_received': 0,
                    'last_sent': None,
                    'last_received': None
                }
            
            self._signal_stats[signal_type]['total_sent'] += 1
            self._signal_stats[signal_type]['last_sent'] = timezone.now()
            
            # Count receivers
            receivers_count = len(result)
            self._signal_stats[signal_type]['total_received'] += receivers_count
            
            if receivers_count > 0:
                self._signal_stats[signal_type]['last_received'] = timezone.now()
                
        except Exception as e:
            self.logger.error(f"Error updating signal stats: {str(e)}")
    
    def register_listener(self, signal_type: str, listener: Callable, priority: int = 0) -> bool:
        """
        Register a signal listener.
        
        Args:
            signal_type: Type of signal to listen for
            listener: Listener function
            priority: Listener priority (higher = earlier execution)
            
        Returns:
            True if registration successful
        """
        try:
            if signal_type not in self._listeners:
                self._listeners[signal_type] = []
            
            # Add listener with priority
            self._listeners[signal_type].append({
                'listener': listener,
                'priority': priority,
                'registered_at': timezone.now()
            })
            
            # Sort by priority (highest first)
            self._listeners[signal_type].sort(key=lambda x: x['priority'], reverse=True)
            
            # Connect to Django signal
            signal = self._get_signal(signal_type)
            if signal:
                receiver_func = self._create_receiver_func(signal_type, listener)
                signal.connect(receiver_func)
            
            self.logger.info(f"Listener registered for signal {signal_type}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering listener for {signal_type}: {str(e)}")
            return False
    
    def unregister_listener(self, signal_type: str, listener: Callable) -> bool:
        """
        Unregister a signal listener.
        
        Args:
            signal_type: Type of signal
            listener: Listener function
            
        Returns:
            True if unregistration successful
        """
        try:
            if signal_type in self._listeners:
                # Remove listener from list
                self._listeners[signal_type] = [
                    item for item in self._listeners[signal_type]
                    if item['listener'] != listener
                ]
                
                # Disconnect from Django signal
                signal = self._get_signal(signal_type)
                if signal:
                    receiver_func = self._create_receiver_func(signal_type, listener)
                    signal.disconnect(receiver_func)
                
                self.logger.info(f"Listener unregistered for signal {signal_type}")
                return True
            else:
                self.logger.warning(f"No listeners found for signal {signal_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error unregistering listener for {signal_type}: {str(e)}")
            return False
    
    def _create_receiver_func(self, signal_type: str, listener: Callable) -> Callable:
        """Create receiver function for Django signal."""
        def receiver_func(sender, **kwargs):
            try:
                return listener(sender, signal_type, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in signal listener for {signal_type}: {str(e)")
                return None
        
        return receiver_func
    
    def get_signal_history(self, signal_type: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get signal history.
        
        Args:
            signal_type: Optional signal type filter
            limit: Maximum number of entries to return
            
        Returns:
            Signal history entries
        """
        try:
            history = self._signal_history
            
            # Filter by signal type
            if signal_type:
                history = [
                    entry for entry in history
                    if entry['signal_data']['signal_type'] == signal_type
                ]
            
            # Limit results
            if limit:
                history = history[-limit:]
            
            return history
            
        except Exception as e:
            self.logger.error(f"Error getting signal history: {str(e)}")
            return []
    
    def get_signal_stats(self, signal_type: str = None) -> Dict[str, Any]:
        """
        Get signal statistics.
        
        Args:
            signal_type: Optional signal type filter
            
        Returns:
            Signal statistics
        """
        try:
            if signal_type:
                return self._signal_stats.get(signal_type, {})
            else:
                return self._signal_stats
                
        except Exception as e:
            self.logger.error(f"Error getting signal stats: {str(e)}")
            return {}
    
    def get_listeners(self, signal_type: str = None) -> Dict[str, Any]:
        """
        Get registered listeners.
        
        Args:
            signal_type: Optional signal type filter
            
        Returns:
            Listener information
        """
        try:
            if signal_type:
                if signal_type in self._listeners:
                    return {
                        'signal_type': signal_type,
                        'listeners': [
                            {
                                'priority': item['priority'],
                                'registered_at': item['registered_at'].isoformat()
                            }
                            for item in self._listeners[signal_type]
                        ]
                    }
                else:
                    return {'error': f'No listeners for signal {signal_type}'}
            else:
                return {
                    'total_signals': len(self._listeners),
                    'signals': {
                        signal_type: {
                            'listener_count': len(listeners),
                            'listeners': [
                                {
                                    'priority': item['priority'],
                                    'registered_at': item['registered_at'].isoformat()
                                }
                                for item in listeners
                            ]
                        }
                        for signal_type, listeners in self._listeners.items()
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Error getting listeners: {str(e)}")
            return {'error': str(e)}
    
    def clear_history(self, signal_type: str = None) -> bool:
        """
        Clear signal history.
        
        Args:
            signal_type: Optional signal type filter
            
        Returns:
            True if clear successful
        """
        try:
            if signal_type:
                self._signal_history = [
                    entry for entry in self._signal_history
                    if entry['signal_data']['signal_type'] != signal_type
                ]
            else:
                self._signal_history = []
            
            self.logger.info("Signal history cleared")
            return True
            
        except Exception as e:
            self.logger.error(f"Error clearing signal history: {str(e)}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of signal system.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall': 'healthy',
                'components': {},
                'checks': []
            }
            
            # Check signal configuration
            if not self.config:
                health_status['components']['configuration'] = {
                    'status': 'unhealthy',
                    'error': 'No configuration loaded'
                }
                health_status['overall'] = 'unhealthy'
            else:
                health_status['components']['configuration'] = {
                    'status': 'healthy',
                    'enabled_signals': len(self.enabled_signals),
                    'max_history': self.max_history,
                    'stats_enabled': self.stats_enabled
                }
            
            # Check listeners
            total_listeners = sum(len(listeners) for listeners in self._listeners.values())
            health_status['components']['listeners'] = {
                'status': 'healthy',
                'total_listeners': total_listeners,
                'signals_with_listeners': len(self._listeners)
            }
            
            # Check signal history
            health_status['components']['history'] = {
                'status': 'healthy',
                'history_size': len(self._signal_history),
                'max_history': self.max_history
            }
            
            # Check statistics
            health_status['components']['statistics'] = {
                'status': 'healthy',
                'stats_enabled': self.stats_enabled,
                'tracked_signals': len(self._signal_stats)
            }
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall': 'unhealthy',
                'error': str(e)
            }


# Global signal manager instance
signal_manager = IntegrationSignals()


# Convenience functions for common signal operations
def send_webhook_received(sender, **kwargs):
    """Send webhook received signal."""
    return signal_manager.send_signal('webhook_received', sender=sender, **kwargs)


def send_webhook_processed(sender, **kwargs):
    """Send webhook processed signal."""
    return signal_manager.send_signal('webhook_processed', sender=sender, **kwargs)


def send_webhook_failed(sender, **kwargs):
    """Send webhook failed signal."""
    return signal_manager.send_signal('webhook_failed', sender=sender, **kwargs)


def send_integration_connected(sender, **kwargs):
    """Send integration connected signal."""
    return signal_manager.send_signal('integration_connected', sender=sender, **kwargs)


def send_integration_error(sender, **kwargs):
    """Send integration error signal."""
    return signal_manager.send_signal('integration_error', sender=sender, **kwargs)
