"""
signals_cap.py – Signal capture and processing capabilities.

Provides advanced signal capture, processing, and routing capabilities
for the postback module. Handles complex signal workflows and
provides a unified interface for signal management.
"""
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from functools import wraps

from django.dispatch import Signal, receiver
from django.db.models.signals import post_save, post_delete, pre_save
from django.utils import timezone
from django.core.cache import cache

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .signals import postback_received, postback_processed, postback_failed

logger = logging.getLogger(__name__)


class SignalCapture:
    """
    Advanced signal capture and processing system.
    
    Provides capabilities for:
    - Signal interception and modification
    - Conditional signal processing
    - Signal aggregation and batching
    - Signal performance monitoring
    """
    
    def __init__(self):
        self._captured_signals = {}
        self._signal_handlers = {}
        self._performance_stats = {}
        self._enabled = True
    
    def capture_signal(self, signal_name: str, signal: Signal, handler_func: Callable = None):
        """
        Capture a signal for processing.
        
        Args:
            signal_name: Name identifier for the signal
            signal: Django Signal instance
            handler_func: Optional custom handler function
        """
        if signal_name in self._captured_signals:
            logger.warning(f"Signal {signal_name} already captured")
            return
        
        # Store signal reference
        self._captured_signals[signal_name] = {
            'signal': signal,
            'handler': handler_func,
            'captured_at': timezone.now(),
            'call_count': 0,
            'total_time': 0.0,
        }
        
        # Connect default handler if none provided
        if handler_func is None:
            handler_func = self._default_signal_handler
        
        # Connect the signal
        signal.connect(handler_func, weak=False)
        
        logger.info(f"Captured signal: {signal_name}")
    
    def release_signal(self, signal_name: str):
        """Release a captured signal."""
        if signal_name not in self._captured_signals:
            logger.warning(f"Signal {signal_name} not captured")
            return
        
        signal_info = self._captured_signals[signal_name]
        signal = signal_info['signal']
        handler_func = signal_info['handler']
        
        # Disconnect the signal
        signal.disconnect(handler_func)
        
        # Remove from captured signals
        del self._captured_signals[signal_name]
        
        logger.info(f"Released signal: {signal_name}")
    
    def _default_signal_handler(self, sender, **kwargs):
        """Default signal handler for captured signals."""
        signal_name = self._get_signal_name_by_sender(sender)
        
        if signal_name and signal_name in self._captured_signals:
            start_time = timezone.now()
            
            try:
                # Process the signal
                self._process_signal_data(signal_name, sender, **kwargs)
                
                # Update performance stats
                processing_time = (timezone.now() - start_time).total_seconds()
                self._update_performance_stats(signal_name, processing_time)
                
            except Exception as e:
                logger.error(f"Error processing signal {signal_name}: {str(e)}")
    
    def _process_signal_data(self, signal_name: str, sender, **kwargs):
        """Process signal data based on signal type."""
        signal_data = {
            'signal_name': signal_name,
            'sender': sender,
            'kwargs': kwargs,
            'processed_at': timezone.now(),
        }
        
        # Store signal data for analysis
        cache_key = f"signal_capture_{signal_name}_{timezone.now().timestamp()}"
        cache.set(cache_key, signal_data, timeout=3600)  # 1 hour
        
        # Log signal processing
        logger.debug(f"Processed signal: {signal_name} from {sender}")
    
    def _get_signal_name_by_sender(self, sender) -> Optional[str]:
        """Get signal name by sender model."""
        sender_name = sender.__class__.__name__
        
        # Map sender classes to signal names
        signal_mapping = {
            'PostbackLog': 'postback_log_signal',
            'PostbackInsight': 'postback_insight_signal',
            'NetworkPostbackConfig': 'network_config_signal',
        }
        
        return signal_mapping.get(sender_name)
    
    def _update_performance_stats(self, signal_name: str, processing_time: float):
        """Update performance statistics for a signal."""
        if signal_name not in self._captured_signals:
            return
        
        signal_info = self._captured_signals[signal_name]
        signal_info['call_count'] += 1
        signal_info['total_time'] += processing_time
        
        # Calculate average time
        avg_time = signal_info['total_time'] / signal_info['call_count']
        signal_info['avg_time'] = avg_time
    
    def get_signal_stats(self) -> Dict[str, Any]:
        """Get performance statistics for all captured signals."""
        stats = {}
        
        for signal_name, signal_info in self._captured_signals.items():
            stats[signal_name] = {
                'call_count': signal_info['call_count'],
                'total_time': signal_info['total_time'],
                'avg_time': signal_info.get('avg_time', 0.0),
                'captured_at': signal_info['captured_at'].isoformat(),
            }
        
        return stats
    
    def enable(self):
        """Enable signal capture."""
        self._enabled = True
        logger.info("Signal capture enabled")
    
    def disable(self):
        """Disable signal capture."""
        self._enabled = False
        logger.info("Signal capture disabled")
    
    def is_enabled(self) -> bool:
        """Check if signal capture is enabled."""
        return self._enabled


class ConditionalSignalProcessor:
    """
    Conditional signal processor for complex signal workflows.
    
    Provides capabilities for:
    - Conditional signal processing based on criteria
    - Signal chaining and workflows
    - Dynamic signal routing
    """
    
    def __init__(self):
        self._conditions = {}
        self._workflows = {}
        self._active_workflows = {}
    
    def add_condition(self, condition_name: str, condition_func: Callable):
        """
        Add a conditional processing rule.
        
        Args:
            condition_name: Name identifier for the condition
            condition_func: Function that returns True/False for processing
        """
        self._conditions[condition_name] = condition_func
        logger.info(f"Added condition: {condition_name}")
    
    def add_workflow(self, workflow_name: str, steps: List[Dict[str, Any]]):
        """
        Add a signal processing workflow.
        
        Args:
            workflow_name: Name identifier for the workflow
            steps: List of workflow steps with conditions and actions
        """
        self._workflows[workflow_name] = {
            'steps': steps,
            'created_at': timezone.now(),
            'execution_count': 0,
        }
        logger.info(f"Added workflow: {workflow_name}")
    
    def process_signal_workflow(self, workflow_name: str, signal_data: Dict[str, Any]) -> bool:
        """
        Process a signal through a workflow.
        
        Args:
            workflow_name: Name of the workflow to execute
            signal_data: Signal data to process
            
        Returns:
            True if workflow completed successfully
        """
        if workflow_name not in self._workflows:
            logger.error(f"Workflow {workflow_name} not found")
            return False
        
        workflow = self._workflows[workflow_name]
        steps = workflow['steps']
        
        try:
            for step in steps:
                if not self._execute_workflow_step(step, signal_data):
                    logger.warning(f"Workflow {workflow_name} failed at step: {step.get('name', 'unnamed')}")
                    return False
            
            # Update workflow stats
            workflow['execution_count'] += 1
            
            logger.info(f"Workflow {workflow_name} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error executing workflow {workflow_name}: {str(e)}")
            return False
    
    def _execute_workflow_step(self, step: Dict[str, Any], signal_data: Dict[str, Any]) -> bool:
        """Execute a single workflow step."""
        step_name = step.get('name', 'unnamed')
        conditions = step.get('conditions', [])
        actions = step.get('actions', [])
        
        # Check conditions
        for condition_name in conditions:
            if condition_name not in self._conditions:
                logger.error(f"Condition {condition_name} not found")
                return False
            
            condition_func = self._conditions[condition_name]
            if not condition_func(signal_data):
                logger.debug(f"Condition {condition_name} failed for step {step_name}")
                return True  # Skip this step but continue workflow
        
        # Execute actions
        for action in actions:
            if not self._execute_action(action, signal_data):
                logger.error(f"Action failed in step {step_name}")
                return False
        
        return True
    
    def _execute_action(self, action: Dict[str, Any], signal_data: Dict[str, Any]) -> bool:
        """Execute a workflow action."""
        action_type = action.get('type')
        
        if action_type == 'log':
            message = action.get('message', 'Signal processed')
            logger.info(f"Workflow action: {message}")
            return True
        
        elif action_type == 'cache':
            cache_key = action.get('cache_key')
            cache_value = action.get('cache_value', signal_data)
            timeout = action.get('timeout', 3600)
            
            if cache_key:
                cache.set(cache_key, cache_value, timeout=timeout)
                return True
        
        elif action_type == 'signal':
            # Emit another signal
            signal_name = action.get('signal_name')
            if signal_name:
                # This would emit the signal (implementation depends on specific needs)
                logger.info(f"Emitting signal: {signal_name}")
                return True
        
        elif action_type == 'function':
            # Call a custom function
            func_name = action.get('function')
            if func_name:
                # This would call the function (implementation depends on specific needs)
                logger.info(f"Calling function: {func_name}")
                return True
        
        else:
            logger.error(f"Unknown action type: {action_type}")
            return False
        
        return True


class SignalAggregator:
    """
    Signal aggregation and batching system.
    
    Provides capabilities for:
    - Signal batching and aggregation
    - Periodic signal processing
    - Signal deduplication
    """
    
    def __init__(self):
        self._batch_size = 100
        self._batch_timeout = 300  # 5 minutes
        self._signal_batches = {}
        self._aggregation_rules = {}
    
    def add_signal_to_batch(self, signal_type: str, signal_data: Dict[str, Any]):
        """
        Add a signal to a batch for aggregation.
        
        Args:
            signal_type: Type of signal
            signal_data: Signal data to batch
        """
        if signal_type not in self._signal_batches:
            self._signal_batches[signal_type] = {
                'signals': [],
                'created_at': timezone.now(),
                'last_updated': timezone.now(),
            }
        
        batch = self._signal_batches[signal_type]
        batch['signals'].append(signal_data)
        batch['last_updated'] = timezone.now()
        
        # Check if batch should be processed
        if len(batch['signals']) >= self._batch_size:
            self._process_batch(signal_type)
        
        logger.debug(f"Added signal to batch {signal_type}: {len(batch['signals'])} signals")
    
    def _process_batch(self, signal_type: str):
        """Process a batch of signals."""
        if signal_type not in self._signal_batches:
            return
        
        batch = self._signal_batches[signal_type]
        signals = batch['signals']
        
        if not signals:
            return
        
        try:
            # Apply aggregation rules
            aggregated_data = self._aggregate_signals(signal_type, signals)
            
            # Process aggregated data
            self._process_aggregated_data(signal_type, aggregated_data)
            
            # Clear the batch
            batch['signals'] = []
            batch['created_at'] = timezone.now()
            batch['last_updated'] = timezone.now()
            
            logger.info(f"Processed batch for {signal_type}: {len(signals)} signals")
            
        except Exception as e:
            logger.error(f"Error processing batch for {signal_type}: {str(e)}")
    
    def _aggregate_signals(self, signal_type: str, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate signals based on rules."""
        if signal_type not in self._aggregation_rules:
            # Default aggregation: count and timestamp
            return {
                'signal_type': signal_type,
                'count': len(signals),
                'first_signal': signals[0],
                'last_signal': signals[-1],
                'aggregated_at': timezone.now(),
            }
        
        # Apply custom aggregation rules
        rule = self._aggregation_rules[signal_type]
        aggregation_func = rule.get('function')
        
        if aggregation_func:
            return aggregation_func(signals)
        else:
            # Default aggregation
            return {
                'signal_type': signal_type,
                'count': len(signals),
                'first_signal': signals[0],
                'last_signal': signals[-1],
                'aggregated_at': timezone.now(),
            }
    
    def _process_aggregated_data(self, signal_type: str, aggregated_data: Dict[str, Any]):
        """Process aggregated signal data."""
        # This would implement custom processing based on signal type
        logger.info(f"Processed aggregated data for {signal_type}: {aggregated_data}")
    
    def add_aggregation_rule(self, signal_type: str, rule: Dict[str, Any]):
        """
        Add aggregation rule for a signal type.
        
        Args:
            signal_type: Type of signal
            rule: Aggregation rule configuration
        """
        self._aggregation_rules[signal_type] = rule
        logger.info(f"Added aggregation rule for {signal_type}")
    
    def process_all_batches(self):
        """Process all pending batches."""
        for signal_type in list(self._signal_batches.keys()):
            self._process_batch(signal_type)


# Global instances
signal_capture = SignalCapture()
conditional_processor = ConditionalSignalProcessor()
signal_aggregator = SignalAggregator()


# Decorators for signal handling
def signal_handler(signal_name: str):
    """
    Decorator for signal handlers with automatic capture.
    
    Args:
        signal_name: Name of the signal to handle
    """
    def decorator(func):
        @wraps(func)
        def wrapper(sender, **kwargs):
            if signal_capture.is_enabled():
                start_time = timezone.now()
                
                try:
                    result = func(sender, **kwargs)
                    
                    # Update performance stats
                    processing_time = (timezone.now() - start_time).total_seconds()
                    signal_capture._update_performance_stats(signal_name, processing_time)
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"Error in signal handler {signal_name}: {str(e)}")
                    raise
            else:
                return func(sender, **kwargs)
        
        return wrapper
    return decorator


def conditional_signal_handler(condition_name: str):
    """
    Decorator for conditional signal handlers.
    
    Args:
        condition_name: Name of the condition to check
    """
    def decorator(func):
        @wraps(func)
        def wrapper(sender, **kwargs):
            if condition_name in conditional_processor._conditions:
                condition_func = conditional_processor._conditions[condition_name]
                signal_data = {'sender': sender, 'kwargs': kwargs}
                
                if condition_func(signal_data):
                    return func(sender, **kwargs)
                else:
                    logger.debug(f"Condition {condition_name} failed, skipping handler")
                    return None
            else:
                logger.warning(f"Condition {condition_name} not found")
                return func(sender, **kwargs)
        
        return wrapper
    return decorator


# Built-in signal handlers
@signal_handler('postback_received')
def handle_postback_received_capture(sender, **kwargs):
    """Handle postback received signal with capture."""
    signal_data = {
        'sender': sender,
        'kwargs': kwargs,
        'timestamp': timezone.now(),
    }
    
    # Add to aggregation batch
    signal_aggregator.add_signal_to_batch('postback_received', signal_data)


@signal_handler('postback_processed')
def handle_postback_processed_capture(sender, **kwargs):
    """Handle postback processed signal with capture."""
    signal_data = {
        'sender': sender,
        'kwargs': kwargs,
        'timestamp': timezone.now(),
    }
    
    # Add to aggregation batch
    signal_aggregator.add_signal_to_batch('postback_processed', signal_data)


@signal_handler('postback_failed')
def handle_postback_failed_capture(sender, **kwargs):
    """Handle postback failed signal with capture."""
    signal_data = {
        'sender': sender,
        'kwargs': kwargs,
        'timestamp': timezone.now(),
    }
    
    # Add to aggregation batch
    signal_aggregator.add_signal_to_batch('postback_failed', signal_data)


# Initialize signal capture system
def initialize_signal_capture():
    """Initialize the signal capture system."""
    try:
        # Capture core postback signals
        signal_capture.capture_signal('postback_received', postback_received)
        signal_capture.capture_signal('postback_processed', postback_processed)
        signal_capture.capture_signal('postback_failed', postback_failed)
        
        # Add default conditions
        conditional_processor.add_condition('is_postback_log', lambda data: 
            hasattr(data.get('sender'), '__class__') and 
            data['sender'].__class__.__name__ == 'PostbackLog')
        
        conditional_processor.add_condition('is_failed_postback', lambda data:
            data.get('kwargs', {}).get('status') == 'FAILED')
        
        # Add aggregation rules
        signal_aggregator.add_aggregation_rule('postback_received', {
            'function': lambda signals: {
                'count': len(signals),
                'unique_networks': len(set(s['kwargs'].get('network_key') for s in signals)),
                'time_range': {
                    'first': min(s['timestamp'] for s in signals),
                    'last': max(s['timestamp'] for s in signals),
                },
                'aggregated_at': timezone.now(),
            }
        })
        
        logger.info("Signal capture system initialized")
        
    except Exception as e:
        logger.error(f"Error initializing signal capture: {str(e)}")


# Cleanup function
def cleanup_signal_capture():
    """Clean up signal capture system."""
    try:
        # Release all captured signals
        for signal_name in list(signal_capture._captured_signals.keys()):
            signal_capture.release_signal(signal_name)
        
        # Process remaining batches
        signal_aggregator.process_all_batches()
        
        logger.info("Signal capture system cleaned up")
        
    except Exception as e:
        logger.error(f"Error cleaning up signal capture: {str(e)}")


# Get statistics
def get_signal_capture_stats() -> Dict[str, Any]:
    """Get comprehensive signal capture statistics."""
    return {
        'capture_stats': signal_capture.get_signal_stats(),
        'workflow_stats': {
            name: workflow['execution_count']
            for name, workflow in conditional_processor._workflows.items()
        },
        'batch_stats': {
            signal_type: len(batch['signals'])
            for signal_type, batch in signal_aggregator._signal_batches.items()
        },
        'system_enabled': signal_capture.is_enabled(),
    }
