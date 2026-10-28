"""
📡 Advanced Signal Handling Module

This module provides comprehensive signal handling capabilities for the backup system.
It includes advanced signal dispatching, signal chaining, signal filtering, and
signal analytics to support complex event-driven architectures.

Features:
- Advanced signal dispatching with priority support
- Signal chaining and composition
- Signal filtering and routing
- Signal analytics and monitoring
- Signal persistence and replay
- Signal throttling and debouncing
- Signal error handling and recovery
- Signal-based event sourcing
"""

import logging
import json
import time
import threading
from typing import Dict, List, Any, Optional, Union, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from django.dispatch import Signal, receiver
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from concurrent.futures import ThreadPoolExecutor
import queue
import weakref

# Import backup models and services
from .models import Backup, BackupLog, BackupAlert
from .utils import TimeUtils

logger = logging.getLogger(__name__)

T = TypeVar('T')


class SignalPriority(Enum):
    """Enumeration of signal priorities."""
    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100


class SignalStatus(Enum):
    """Enumeration of signal statuses."""
    PENDING = "pending"
    DISPATCHING = "dispatching"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    THROTTLED = "throttled"


class SignalType(Enum):
    """Enumeration of signal types."""
    BACKUP_EVENT = "backup_event"
    SYSTEM_EVENT = "system_event"
    USER_EVENT = "user_event"
    SCHEDULE_EVENT = "schedule_event"
    STORAGE_EVENT = "storage_event"
    SECURITY_EVENT = "security_event"
    PERFORMANCE_EVENT = "performance_event"
    CUSTOM_EVENT = "custom_event"


@dataclass
class SignalMetadata:
    """Signal metadata."""
    signal_id: str
    signal_type: SignalType
    priority: SignalPriority = SignalPriority.NORMAL
    source: Optional[str] = None
    timestamp: datetime = field(default_factory=timezone.now)
    tags: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    timeout: Optional[float] = None
    async_dispatch: bool = False
    persist: bool = False
    chain_id: Optional[str] = None


@dataclass
class SignalResult:
    """Result of signal processing."""
    signal_id: str
    status: SignalStatus
    results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    processing_time_ms: float = 0.0
    handler_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    timestamp: datetime = field(default_factory=timezone.now)


class SignalHandler:
    """Advanced signal handler with metadata and priority support."""
    
    def __init__(self, func: Callable, priority: SignalPriority = SignalPriority.NORMAL,
                 name: Optional[str] = None, condition: Optional[Callable] = None,
                 async_handler: bool = False):
        self.func = func
        self.priority = priority
        self.name = name or func.__name__
        self.condition = condition
        self.async_handler = async_handler
        self.enabled = True
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.last_execution = None
        self.average_execution_time = 0.0
    
    def should_handle(self, sender: Any, **kwargs) -> bool:
        """Check if handler should process the signal."""
        if not self.enabled:
            return False
        
        if self.condition:
            try:
                return self.condition(sender, **kwargs)
            except Exception as e:
                logger.error(f"Error in handler condition for {self.name}: {e}")
                return False
        
        return True
    
    def handle(self, sender: Any, **kwargs) -> Any:
        """Execute the handler."""
        start_time = time.time()
        
        try:
            self.execution_count += 1
            result = self.func(sender, **kwargs)
            self.success_count += 1
            return result
        except Exception as e:
            self.failure_count += 1
            raise
        finally:
            execution_time = (time.time() - start_time) * 1000
            self.last_execution = timezone.now()
            
            # Update average execution time
            if self.execution_count == 1:
                self.average_execution_time = execution_time
            else:
                alpha = 0.1
                self.average_execution_time = (
                    alpha * execution_time + 
                    (1 - alpha) * self.average_execution_time
                )


class SignalFilter:
    """Signal filtering utility."""
    
    @staticmethod
    def by_source(source: str) -> Callable:
        """Filter by signal source."""
        def filter_func(sender: Any, **kwargs) -> bool:
            metadata = kwargs.get('metadata', {})
            return metadata.get('source') == source
        return filter_func
    
    @staticmethod
    def by_tag(tag: str) -> Callable:
        """Filter by signal tag."""
        def filter_func(sender: Any, **kwargs) -> bool:
            metadata = kwargs.get('metadata', {})
            return tag in metadata.get('tags', [])
        return filter_func
    
    @staticmethod
    def by_type(signal_type: SignalType) -> Callable:
        """Filter by signal type."""
        def filter_func(sender: Any, **kwargs) -> bool:
            metadata = kwargs.get('metadata', {})
            return metadata.get('signal_type') == signal_type
        return filter_func
    
    @staticmethod
    def by_priority(min_priority: SignalPriority) -> Callable:
        """Filter by minimum priority."""
        def filter_func(sender: Any, **kwargs) -> bool:
            metadata = kwargs.get('metadata', {})
            priority = metadata.get('priority', SignalPriority.NORMAL)
            return priority.value >= min_priority.value
        return filter_func
    
    @staticmethod
    def custom(condition: Callable) -> Callable:
        """Custom filter condition."""
        return condition


class SignalThrottler:
    """Signal throttling utility."""
    
    def __init__(self):
        self.throttle_cache = {}
        self.throttle_lock = threading.Lock()
    
    def should_throttle(self, key: str, limit: int, period: timedelta) -> bool:
        """Check if signal should be throttled."""
        with self.throttle_lock:
            now = timezone.now()
            
            if key not in self.throttle_cache:
                self.throttle_cache[key] = {
                    'count': 0,
                    'reset_time': now + period,
                    'first_hit': now
                }
            
            throttle_info = self.throttle_cache[key]
            
            # Reset if period has passed
            if now >= throttle_info['reset_time']:
                throttle_info['count'] = 0
                throttle_info['reset_time'] = now + period
                throttle_info['first_hit'] = now
            
            # Check limit
            if throttle_info['count'] >= limit:
                return True
            
            throttle_info['count'] += 1
            return False
    
    def get_throttle_info(self, key: str) -> Dict[str, Any]:
        """Get throttling information for a key."""
        with self.throttle_lock:
            return self.throttle_cache.get(key, {})


class SignalChain:
    """Signal chaining for sequential processing."""
    
    def __init__(self, chain_id: str):
        self.chain_id = chain_id
        self.signals: List[Dict[str, Any]] = []
        self.results: List[SignalResult] = []
        self.current_index = 0
        self.status = SignalStatus.PENDING
        self.created_at = timezone.now()
        self.completed_at = None
    
    def add_signal(self, signal_name: str, sender: Any = None, **kwargs) -> 'SignalChain':
        """Add a signal to the chain."""
        self.signals.append({
            'signal_name': signal_name,
            'sender': sender,
            'kwargs': kwargs
        })
        return self
    
    def execute(self) -> List[SignalResult]:
        """Execute the signal chain."""
        self.status = SignalStatus.DISPATCHING
        results = []
        
        try:
            for i, signal_info in enumerate(self.signals):
                self.current_index = i
                
                # Dispatch signal
                result = SignalDispatcher.dispatch(
                    signal_info['signal_name'],
                    signal_info['sender'],
                    **signal_info['kwargs']
                )
                
                results.append(result)
                
                # Stop on failure
                if result.status == SignalStatus.FAILED:
                    break
            
            self.status = SignalStatus.COMPLETED
            self.completed_at = timezone.now()
            
        except Exception as e:
            self.status = SignalStatus.FAILED
            self.completed_at = timezone.now()
            logger.error(f"Signal chain {self.chain_id} failed: {e}")
        
        self.results = results
        return results


class SignalDispatcher:
    """Advanced signal dispatcher with priority and filtering support."""
    
    def __init__(self):
        self.signals: Dict[str, List[SignalHandler]] = {}
        self.global_handlers: List[SignalHandler] = []
        self.throttler = SignalThrottler()
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.signal_history: List[SignalResult] = []
        self.max_history = getattr(settings, 'BACKUP_SIGNAL_MAX_HISTORY', 1000)
        self.persistence_enabled = getattr(settings, 'BACKUP_SIGNAL_PERSISTENCE', False)
    
    def register(self, signal_name: str, handler: Callable,
                priority: SignalPriority = SignalPriority.NORMAL,
                name: Optional[str] = None,
                condition: Optional[Callable] = None,
                async_handler: bool = False) -> None:
        """Register a signal handler."""
        signal_handler = SignalHandler(
            func=handler,
            priority=priority,
            name=name,
            condition=condition,
            async_handler=async_handler
        )
        
        if signal_name not in self.signals:
            self.signals[signal_name] = []
        
        # Insert handler in priority order
        handlers = self.signals[signal_name]
        inserted = False
        
        for i, existing_handler in enumerate(handlers):
            if signal_handler.priority.value > existing_handler.priority.value:
                handlers.insert(i, signal_handler)
                inserted = True
                break
        
        if not inserted:
            handlers.append(signal_handler)
        
        logger.info(f"Registered signal handler {signal_handler.name} for {signal_name}")
    
    def register_global(self, handler: Callable,
                       priority: SignalPriority = SignalPriority.NORMAL,
                       condition: Optional[Callable] = None) -> None:
        """Register a global signal handler for all signals."""
        signal_handler = SignalHandler(
            func=handler,
            priority=priority,
            condition=condition
        )
        
        self.global_handlers.append(signal_handler)
        self.global_handlers.sort(key=lambda h: h.priority.value, reverse=True)
    
    def dispatch(self, signal_name: str, sender: Any = None,
                async_dispatch: bool = False,
                timeout: Optional[float] = None,
                **kwargs) -> SignalResult:
        """Dispatch a signal with advanced capabilities."""
        start_time = time.time()
        signal_id = f"signal_{int(start_time * 1000)}"
        
        # Create metadata
        metadata = kwargs.pop('metadata', {})
        signal_metadata = SignalMetadata(
            signal_id=signal_id,
            signal_type=metadata.get('signal_type', SignalType.CUSTOM_EVENT),
            source=metadata.get('source'),
            priority=metadata.get('priority', SignalPriority.NORMAL),
            tags=metadata.get('tags', []),
            context=metadata.get('context', {}),
            timeout=timeout,
            async_dispatch=async_dispatch
        )
        
        # Add metadata to kwargs
        kwargs['metadata'] = signal_metadata
        
        # Check throttling
        throttle_key = f"{signal_name}:{signal_metadata.source or 'unknown'}"
        if self.throttler.should_throttle(throttle_key, 100, timedelta(minutes=1)):
            return SignalResult(
                signal_id=signal_id,
                status=SignalStatus.THROTTLED,
                processing_time_ms=(time.time() - start_time) * 1000
            )
        
        # Get handlers
        handlers = self.signals.get(signal_name, [])
        all_handlers = self.global_handlers + handlers
        
        # Filter handlers
        filtered_handlers = [
            h for h in all_handlers 
            if h.should_handle(sender, **kwargs)
        ]
        
        # Sort by priority
        filtered_handlers.sort(key=lambda h: h.priority.value, reverse=True)
        
        result = SignalResult(
            signal_id=signal_id,
            status=SignalStatus.DISPATCHING,
            handler_count=len(filtered_handlers)
        )
        
        try:
            if async_dispatch:
                # Async dispatch
                futures = []
                for handler in filtered_handlers:
                    future = self.executor.submit(self._execute_handler, handler, sender, **kwargs)
                    futures.append(future)
                
                # Wait for completion
                for future in futures:
                    try:
                        handler_result = future.result(timeout=timeout)
                        result.results.append(handler_result)
                        result.success_count += 1
                    except Exception as e:
                        result.errors.append({
                            'handler': 'unknown',
                            'error': str(e)
                        })
                        result.failure_count += 1
            else:
                # Sync dispatch
                for handler in filtered_handlers:
                    try:
                        handler_result = self._execute_handler(handler, sender, **kwargs)
                        result.results.append(handler_result)
                        result.success_count += 1
                    except Exception as e:
                        result.errors.append({
                            'handler': handler.name,
                            'error': str(e)
                        })
                        result.failure_count += 1
            
            result.status = SignalStatus.COMPLETED if result.failure_count == 0 else SignalStatus.FAILED
            
        except Exception as e:
            result.status = SignalStatus.FAILED
            result.errors.append({
                'handler': 'dispatcher',
                'error': str(e)
            })
        
        result.processing_time_ms = (time.time() - start_time) * 1000
        
        # Store in history
        self._store_result(result)
        
        # Persist if enabled
        if self.persistence_enabled and signal_metadata.persist:
            self._persist_signal(signal_name, sender, kwargs, result)
        
        return result
    
    def _execute_handler(self, handler: SignalHandler, sender: Any, **kwargs) -> Dict[str, Any]:
        """Execute a single handler."""
        start_time = time.time()
        
        try:
            result = handler.handle(sender, **kwargs)
            return {
                'handler': handler.name,
                'success': True,
                'result': result,
                'execution_time_ms': (time.time() - start_time) * 1000
            }
        except Exception as e:
            return {
                'handler': handler.name,
                'success': False,
                'error': str(e),
                'execution_time_ms': (time.time() - start_time) * 1000
            }
    
    def _store_result(self, result: SignalResult) -> None:
        """Store signal result in history."""
        self.signal_history.append(result)
        
        # Limit history size
        if len(self.signal_history) > self.max_history:
            self.signal_history = self.signal_history[-self.max_history:]
    
    def _persist_signal(self, signal_name: str, sender: Any, kwargs: Dict[str, Any], result: SignalResult) -> None:
        """Persist signal to database."""
        try:
            # Create backup log entry for signal
            BackupLog.objects.create(
                action='signal_dispatch',
                category='system',
                level='info' if result.status == SignalStatus.COMPLETED else 'error',
                message=f"Signal {signal_name} dispatched",
                metadata={
                    'signal_name': signal_name,
                    'signal_id': result.signal_id,
                    'status': result.status.value,
                    'handler_count': result.handler_count,
                    'success_count': result.success_count,
                    'failure_count': result.failure_count,
                    'processing_time_ms': result.processing_time_ms
                }
            )
        except Exception as e:
            logger.error(f"Failed to persist signal {signal_name}: {e}")
    
    def get_signal_history(self, limit: Optional[int] = None) -> List[SignalResult]:
        """Get signal history."""
        history = sorted(self.signal_history, key=lambda r: r.timestamp, reverse=True)
        return history[:limit] if limit else history
    
    def get_handler_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        stats = {}
        
        for signal_name, handlers in self.signals.items():
            handler_stats = []
            for handler in handlers:
                handler_stats.append({
                    'name': handler.name,
                    'enabled': handler.enabled,
                    'execution_count': handler.execution_count,
                    'success_count': handler.success_count,
                    'failure_count': handler.failure_count,
                    'success_rate': (handler.success_count / handler.execution_count * 100) if handler.execution_count > 0 else 0,
                    'average_execution_time': handler.average_execution_time,
                    'last_execution': handler.last_execution.isoformat() if handler.last_execution else None
                })
            
            stats[signal_name] = handler_stats
        
        return stats
    
    def get_throttle_stats(self) -> Dict[str, Any]:
        """Get throttling statistics."""
        return {
            'active_throttles': len(self.throttler.throttle_cache),
            'throttle_info': {
                key: info for key, info in self.throttler.throttle_cache.items()
            }
        }


class SignalAnalytics:
    """Signal analytics and monitoring."""
    
    def __init__(self, dispatcher: SignalDispatcher):
        self.dispatcher = dispatcher
    
    def get_signal_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get signal metrics for the last N hours."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        recent_signals = [
            s for s in self.dispatcher.signal_history 
            if s.timestamp >= cutoff_time
        ]
        
        if not recent_signals:
            return {}
        
        total_signals = len(recent_signals)
        successful_signals = sum(1 for s in recent_signals if s.status == SignalStatus.COMPLETED)
        failed_signals = total_signals - successful_signals
        
        # Calculate average processing time
        avg_processing_time = sum(s.processing_time_ms for s in recent_signals) / total_signals
        
        # Signal type distribution
        signal_types = {}
        for signal in recent_signals:
            # Extract signal type from results if available
            signal_type = 'unknown'
            if signal.results and signal.results[0].get('metadata'):
                signal_type = signal.results[0]['metadata'].get('signal_type', 'unknown')
            
            signal_types[signal_type] = signal_types.get(signal_type, 0) + 1
        
        return {
            'total_signals': total_signals,
            'successful_signals': successful_signals,
            'failed_signals': failed_signals,
            'success_rate': (successful_signals / total_signals * 100) if total_signals > 0 else 0,
            'average_processing_time_ms': avg_processing_time,
            'signal_types': signal_types,
            'period_hours': hours
        }
    
    def get_handler_performance(self, hours: int = 24) -> Dict[str, Any]:
        """Get handler performance metrics."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        recent_signals = [
            s for s in self.dispatcher.signal_history 
            if s.timestamp >= cutoff_time
        ]
        
        handler_performance = {}
        
        for signal in recent_signals:
            for result in signal.results:
                handler_name = result.get('handler', 'unknown')
                
                if handler_name not in handler_performance:
                    handler_performance[handler_name] = {
                        'executions': 0,
                        'successes': 0,
                        'failures': 0,
                        'total_time': 0.0,
                        'avg_time': 0.0
                    }
                
                perf = handler_performance[handler_name]
                perf['executions'] += 1
                perf['total_time'] += result.get('execution_time_ms', 0)
                
                if result.get('success', False):
                    perf['successes'] += 1
                else:
                    perf['failures'] += 1
                
                perf['avg_time'] = perf['total_time'] / perf['executions']
        
        return handler_performance
    
    def get_signal_trends(self, days: int = 7) -> Dict[str, Any]:
        """Get signal trends over time."""
        trends = {}
        
        for day in range(days):
            date = timezone.now() - timedelta(days=day)
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            day_signals = [
                s for s in self.dispatcher.signal_history 
                if day_start <= s.timestamp < day_end
            ]
            
            trends[date.strftime('%Y-%m-%d')] = {
                'total_signals': len(day_signals),
                'successful_signals': sum(1 for s in day_signals if s.status == SignalStatus.COMPLETED),
                'failed_signals': sum(1 for s in day_signals if s.status == SignalStatus.FAILED),
                'avg_processing_time': sum(s.processing_time_ms for s in day_signals) / len(day_signals) if day_signals else 0
            }
        
        return trends


# Global signal dispatcher instance
_signal_dispatcher: Optional[SignalDispatcher] = None
_signal_analytics: Optional[SignalAnalytics] = None


def get_signal_dispatcher() -> SignalDispatcher:
    """Get the global signal dispatcher instance."""
    global _signal_dispatcher
    if _signal_dispatcher is None:
        _signal_dispatcher = SignalDispatcher()
    return _signal_dispatcher


def get_signal_analytics() -> SignalAnalytics:
    """Get the global signal analytics instance."""
    global _signal_analytics
    if _signal_analytics is None:
        _signal_analytics = SignalAnalytics(get_signal_dispatcher())
    return _signal_analytics


def register_signal_handler(signal_name: str, handler: Callable,
                           priority: SignalPriority = SignalPriority.NORMAL,
                           condition: Optional[Callable] = None,
                           async_handler: bool = False) -> None:
    """Register a signal handler."""
    dispatcher = get_signal_dispatcher()
    dispatcher.register(signal_name, handler, priority, condition=condition, async_handler=async_handler)


def register_global_signal_handler(handler: Callable,
                                 priority: SignalPriority = SignalPriority.NORMAL,
                                 condition: Optional[Callable] = None) -> None:
    """Register a global signal handler."""
    dispatcher = get_signal_dispatcher()
    dispatcher.register_global(handler, priority, condition)


def dispatch_signal(signal_name: str, sender: Any = None,
                   async_dispatch: bool = False,
                   timeout: Optional[float] = None,
                   **kwargs) -> SignalResult:
    """Dispatch a signal."""
    dispatcher = get_signal_dispatcher()
    return dispatcher.dispatch(signal_name, sender, async_dispatch, timeout, **kwargs)


def create_signal_chain(chain_id: str) -> SignalChain:
    """Create a new signal chain."""
    return SignalChain(chain_id)


# Decorators for easy signal registration
def backup_signal(signal_name: str, priority: SignalPriority = SignalPriority.NORMAL):
    """Decorator for backup signal handlers."""
    def decorator(func):
        register_signal_handler(signal_name, func, priority)
        return func
    return decorator


def system_signal(signal_name: str, priority: SignalPriority = SignalPriority.NORMAL):
    """Decorator for system signal handlers."""
    def decorator(func):
        register_signal_handler(signal_name, func, priority)
        return func
    return decorator


def global_signal_handler(priority: SignalPriority = SignalPriority.NORMAL):
    """Decorator for global signal handlers."""
    def decorator(func):
        register_global_signal_handler(func, priority)
        return func
    return decorator


# Example signal handlers
@backup_signal('backup_created', SignalPriority.HIGH)
def handle_backup_created(sender, **kwargs):
    """Handle backup created signal."""
    backup = kwargs.get('backup')
    if backup:
        logger.info(f"Backup created: {backup.backup_id}")
        # Additional backup creation logic


@backup_signal('backup_completed', SignalPriority.NORMAL)
def handle_backup_completed(sender, **kwargs):
    """Handle backup completed signal."""
    backup = kwargs.get('backup')
    if backup:
        logger.info(f"Backup completed: {backup.backup_id}")
        # Post-completion logic


@backup_signal('backup_failed', SignalPriority.HIGH)
def handle_backup_failed(sender, **kwargs):
    """Handle backup failed signal."""
    backup = kwargs.get('backup')
    error = kwargs.get('error')
    if backup:
        logger.error(f"Backup failed: {backup.backup_id} - {error}")
        # Failure handling logic


@system_signal('system_alert', SignalPriority.HIGHEST)
def handle_system_alert(sender, **kwargs):
    """Handle system alert signal."""
    alert_type = kwargs.get('alert_type')
    message = kwargs.get('message')
    logger.warning(f"System alert: {alert_type} - {message}")
    # Alert handling logic


@global_signal_handler(SignalPriority.NORMAL)
def log_all_signals(sender, **kwargs):
    """Log all signals for debugging."""
    metadata = kwargs.get('metadata', {})
    signal_name = metadata.get('signal_name', 'unknown')
    logger.debug(f"Signal received: {signal_name} from {sender}")


# Signal filters for common use cases
backup_source_filter = SignalFilter.by_source('backup_system')
security_tag_filter = SignalFilter.by_tag('security')
high_priority_filter = SignalFilter.by_priority(SignalPriority.HIGH)
