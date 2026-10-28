# engagement/integration_system/integ_handler.py
"""
Integration handler system.
Manages execution, routing, and error handling for integrations.
"""
import threading
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import asyncio
import traceback
from datetime import datetime, timedelta

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from .integ_constants import (
    IntegrationStatus, EventPriority, RetryStrategy, ERROR_CODES,
    DEFAULT_CONFIG, CACHE_KEYS, QUEUE_NAMES
)
from .integ_registry import integration_registry, BaseIntegration
from .integ_adapter import AdapterFactory, BaseAdapter

logger = logging.getLogger(__name__)


class HandlerStatus(Enum):
    """Handler execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class ExecutionMode(Enum):
    """Execution modes."""
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    BATCH = "batch"
    STREAMING = "streaming"


@dataclass
class ExecutionContext:
    """Context for integration execution."""
    integration_id: str
    data: Any
    target: Optional[str] = None
    source: Optional[str] = None
    mode: ExecutionMode = ExecutionMode.SYNCHRONOUS
    priority: EventPriority = EventPriority.NORMAL
    timeout: int = 30
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: int = 1
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result: Any = None
    status: HandlerStatus = HandlerStatus.PENDING
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'integration_id': self.integration_id,
            'target': self.target,
            'source': self.source,
            'mode': self.mode.value,
            'priority': self.priority.value,
            'timeout': self.timeout,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'retry_strategy': self.retry_strategy.value,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'status': self.status.value,
        }


@dataclass
class ExecutionResult:
    """Result of integration execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error,
            'execution_time': self.execution_time,
            'retry_count': self.retry_count,
            'metadata': self.metadata,
        }


class BaseHandler(ABC):
    """Base handler class for integrations."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def handle(self, context: ExecutionContext) -> ExecutionResult:
        """Handle integration execution."""
        pass
    
    @abstractmethod
    def validate_context(self, context: ExecutionContext) -> bool:
        """Validate execution context."""
        pass
    
    @abstractmethod
    def prepare_data(self, context: ExecutionContext) -> Any:
        """Prepare data for execution."""
        pass
    
    @abstractmethod
    def process_result(self, result: Any, context: ExecutionContext) -> ExecutionResult:
        """Process execution result."""
        pass
    
    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Execute the handler."""
        start_time = timezone.now()
        
        try:
            # Validate context
            if not self.validate_context(context):
                return ExecutionResult(
                    success=False,
                    error="Invalid execution context",
                    execution_time=(timezone.now() - start_time).total_seconds()
                )
            
            # Prepare data
            prepared_data = self.prepare_data(context)
            
            # Handle execution
            result = self.handle(context.with_data(prepared_data))
            
            # Process result
            processed_result = self.process_result(result, context)
            
            processed_result.execution_time = (timezone.now() - start_time).total_seconds()
            
            return processed_result
            
        except Exception as exc:
            self.logger.error(f"Handler execution failed: {exc}")
            return ExecutionResult(
                success=False,
                error=str(exc),
                execution_time=(timezone.now() - start_time).total_seconds()
            )


class IntegrationHandler(BaseHandler):
    """Handler for integration executions."""
    
    def __init__(self):
        super().__init__("IntegrationHandler")
        self._execution_queue = []
        self._running_executions = {}
        self._lock = threading.Lock()
    
    def handle(self, context: ExecutionContext) -> ExecutionResult:
        """Handle integration execution."""
        integration = integration_registry.get_integration(context.integration_id)
        if not integration:
            return ExecutionResult(
                success=False,
                error=f"Integration {context.integration_id} not found"
            )
        
        try:
            # Execute integration
            result = integration.execute(context.data, context.metadata)
            
            return ExecutionResult(
                success=True,
                data=result,
                metadata={
                    'integration_id': context.integration_id,
                    'execution_mode': context.mode.value,
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Integration execution failed: {exc}")
            return ExecutionResult(
                success=False,
                error=str(exc),
                metadata={
                    'integration_id': context.integration_id,
                    'execution_mode': context.mode.value,
                }
            )
    
    def validate_context(self, context: ExecutionContext) -> bool:
        """Validate execution context."""
        if not context.integration_id:
            return False
        
        integration = integration_registry.get_integration(context.integration_id)
        if not integration:
            return False
        
        if context.timeout <= 0:
            return False
        
        return True
    
    def prepare_data(self, context: ExecutionContext) -> Any:
        """Prepare data for execution."""
        # Add execution metadata
        context.metadata.update({
            'handler_name': self.name,
            'execution_id': str(id(context)),
            'started_at': timezone.now().isoformat(),
        })
        
        return context.data
    
    def process_result(self, result: Any, context: ExecutionContext) -> ExecutionResult:
        """Process execution result."""
        return ExecutionResult(
            success=True,
            data=result,
            metadata={
                'handler_name': self.name,
                'execution_id': str(id(context)),
            }
        )
    
    def execute_async(self, context: ExecutionContext) -> str:
        """Execute integration asynchronously."""
        execution_id = str(id(context))
        
        with self._lock:
            self._execution_queue.append(context)
            self._running_executions[execution_id] = context
        
        # Start async execution
        threading.Thread(
            target=self._execute_async_worker,
            args=(execution_id,),
            daemon=True
        ).start()
        
        return execution_id
    
    def _execute_async_worker(self, execution_id: str):
        """Worker for async execution."""
        context = self._running_executions.get(execution_id)
        if not context:
            return
        
        try:
            context.status = HandlerStatus.RUNNING
            context.started_at = timezone.now()
            
            result = self.execute(context)
            
            context.status = HandlerStatus.COMPLETED
            context.completed_at = timezone.now()
            context.result = result
            
        except Exception as exc:
            context.status = HandlerStatus.FAILED
            context.completed_at = timezone.now()
            context.error_message = str(exc)
            
        finally:
            with self._lock:
                self._running_executions.pop(execution_id, None)
    
    def get_execution_status(self, execution_id: str) -> Optional[ExecutionContext]:
        """Get execution status."""
        with self._lock:
            return self._running_executions.get(execution_id)


class RetryHandler(BaseHandler):
    """Handler for retry logic."""
    
    def __init__(self, max_retries: int = 3, retry_delay: int = 1):
        super().__init__("RetryHandler")
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def handle(self, context: ExecutionContext) -> ExecutionResult:
        """Handle execution with retry logic."""
        last_result = None
        
        for attempt in range(context.max_retries + 1):
            try:
                # Execute integration
                integration = integration_registry.get_integration(context.integration_id)
                if not integration:
                    return ExecutionResult(
                        success=False,
                        error=f"Integration {context.integration_id} not found"
                    )
                
                result = integration.execute(context.data, context.metadata)
                
                return ExecutionResult(
                    success=True,
                    data=result,
                    retry_count=attempt,
                    metadata={
                        'attempt': attempt + 1,
                        'max_attempts': context.max_retries + 1,
                    }
                )
                
            except Exception as exc:
                last_result = ExecutionResult(
                    success=False,
                    error=str(exc),
                    retry_count=attempt,
                    metadata={
                        'attempt': attempt + 1,
                        'max_attempts': context.max_retries + 1,
                    }
                )
                
                if attempt < context.max_retries:
                    # Calculate retry delay based on strategy
                    delay = self._calculate_retry_delay(context.retry_strategy, attempt)
                    time.sleep(delay)
                    context.retry_count = attempt + 1
                else:
                    break
        
        return last_result
    
    def validate_context(self, context: ExecutionContext) -> bool:
        """Validate execution context."""
        return context.max_retries >= 0 and context.retry_delay >= 0
    
    def prepare_data(self, context: ExecutionContext) -> Any:
        """Prepare data for execution."""
        return context.data
    
    def process_result(self, result: Any, context: ExecutionContext) -> ExecutionResult:
        """Process execution result."""
        return result
    
    def _calculate_retry_delay(self, strategy: RetryStrategy, attempt: int) -> float:
        """Calculate retry delay based on strategy."""
        if strategy == RetryStrategy.FIXED_INTERVAL:
            return context.retry_delay
        elif strategy == RetryStrategy.LINEAR_BACKOFF:
            return context.retry_delay * (attempt + 1)
        elif strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            return context.retry_delay * (2 ** attempt)
        else:
            return context.retry_delay


class CircuitBreakerHandler(BaseHandler):
    """Handler with circuit breaker pattern."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        super().__init__("CircuitBreakerHandler")
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self._circuit_states = {}
        self._failure_counts = {}
        self._last_failure_times = {}
    
    def handle(self, context: ExecutionContext) -> ExecutionResult:
        """Handle execution with circuit breaker."""
        circuit_key = f"{context.integration_id}:{context.target or 'default'}"
        
        # Check circuit state
        if self._is_circuit_open(circuit_key):
            return ExecutionResult(
                success=False,
                error="Circuit breaker is open",
                metadata={'circuit_state': 'open'}
            )
        
        try:
            # Execute integration
            integration = integration_registry.get_integration(context.integration_id)
            if not integration:
                return ExecutionResult(
                    success=False,
                    error=f"Integration {context.integration_id} not found"
                )
            
            result = integration.execute(context.data, context.metadata)
            
            # Reset failure count on success
            self._reset_failure_count(circuit_key)
            
            return ExecutionResult(
                success=True,
                data=result,
                metadata={'circuit_state': 'closed'}
            )
            
        except Exception as exc:
            # Record failure
            self._record_failure(circuit_key)
            
            # Check if circuit should open
            if self._should_open_circuit(circuit_key):
                self._open_circuit(circuit_key)
            
            return ExecutionResult(
                success=False,
                error=str(exc),
                metadata={
                    'circuit_state': self._get_circuit_state(circuit_key),
                    'failure_count': self._failure_counts.get(circuit_key, 0)
                }
            )
    
    def validate_context(self, context: ExecutionContext) -> bool:
        """Validate execution context."""
        return True
    
    def prepare_data(self, context: ExecutionContext) -> Any:
        """Prepare data for execution."""
        return context.data
    
    def process_result(self, result: Any, context: ExecutionContext) -> ExecutionResult:
        """Process execution result."""
        return result
    
    def _is_circuit_open(self, circuit_key: str) -> bool:
        """Check if circuit is open."""
        state = self._circuit_states.get(circuit_key, 'closed')
        
        if state == 'open':
            # Check if timeout has passed
            last_failure = self._last_failure_times.get(circuit_key)
            if last_failure and (timezone.now() - last_failure).total_seconds() > self.timeout:
                self._close_circuit(circuit_key)
                return False
            else:
                return True
        
        return False
    
    def _should_open_circuit(self, circuit_key: str) -> bool:
        """Check if circuit should open."""
        return self._failure_counts.get(circuit_key, 0) >= self.failure_threshold
    
    def _open_circuit(self, circuit_key: str):
        """Open circuit."""
        self._circuit_states[circuit_key] = 'open'
        self.logger.warning(f"Circuit opened for {circuit_key}")
    
    def _close_circuit(self, circuit_key: str):
        """Close circuit."""
        self._circuit_states[circuit_key] = 'closed'
        self._failure_counts[circuit_key] = 0
        self.logger.info(f"Circuit closed for {circuit_key}")
    
    def _reset_failure_count(self, circuit_key: str):
        """Reset failure count."""
        self._failure_counts[circuit_key] = 0
    
    def _record_failure(self, circuit_key: str):
        """Record failure."""
        self._failure_counts[circuit_key] = self._failure_counts.get(circuit_key, 0) + 1
        self._last_failure_times[circuit_key] = timezone.now()
    
    def _get_circuit_state(self, circuit_key: str) -> str:
        """Get circuit state."""
        return self._circuit_states.get(circuit_key, 'closed')


class BatchHandler(BaseHandler):
    """Handler for batch processing."""
    
    def __init__(self, batch_size: int = 100):
        super().__init__("BatchHandler")
        self.batch_size = batch_size
    
    def handle(self, context: ExecutionContext) -> ExecutionResult:
        """Handle batch execution."""
        if not isinstance(context.data, list):
            return ExecutionResult(
                success=False,
                error="Batch handler requires list data"
            )
        
        results = []
        total_items = len(context.data)
        
        for i in range(0, total_items, self.batch_size):
            batch = context.data[i:i + self.batch_size]
            
            try:
                # Execute batch
                integration = integration_registry.get_integration(context.integration_id)
                if not integration:
                    return ExecutionResult(
                        success=False,
                        error=f"Integration {context.integration_id} not found"
                    )
                
                batch_result = integration.execute(batch, context.metadata)
                results.append({
                    'batch_index': i // self.batch_size,
                    'batch_size': len(batch),
                    'result': batch_result,
                    'success': True
                })
                
            except Exception as exc:
                results.append({
                    'batch_index': i // self.batch_size,
                    'batch_size': len(batch),
                    'error': str(exc),
                    'success': False
                })
        
        successful_batches = sum(1 for r in results if r['success'])
        
        return ExecutionResult(
            success=successful_batches == len(results),
            data=results,
            metadata={
                'total_items': total_items,
                'batch_size': self.batch_size,
                'total_batches': len(results),
                'successful_batches': successful_batches,
                'failed_batches': len(results) - successful_batches,
            }
        )
    
    def validate_context(self, context: ExecutionContext) -> bool:
        """Validate execution context."""
        return isinstance(context.data, list) and len(context.data) > 0
    
    def prepare_data(self, context: ExecutionContext) -> Any:
        """Prepare data for execution."""
        return context.data
    
    def process_result(self, result: Any, context: ExecutionContext) -> ExecutionResult:
        """Process execution result."""
        return result


class HandlerChain:
    """Chain of handlers for complex processing."""
    
    def __init__(self):
        self.handlers: List[BaseHandler] = []
        self.logger = logging.getLogger(f"{__name__}.HandlerChain")
    
    def add_handler(self, handler: BaseHandler):
        """Add handler to chain."""
        self.handlers.append(handler)
    
    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Execute handler chain."""
        current_context = context
        chain_results = []
        
        for i, handler in enumerate(self.handlers):
            try:
                result = handler.execute(current_context)
                chain_results.append({
                    'handler': handler.name,
                    'step': i + 1,
                    'result': result.to_dict(),
                    'success': result.success
                })
                
                if not result.success:
                    # Stop chain on failure
                    break
                
                # Update context for next handler
                if result.data is not None:
                    current_context = current_context.with_data(result.data)
                
            except Exception as exc:
                self.logger.error(f"Handler {handler.name} failed: {exc}")
                chain_results.append({
                    'handler': handler.name,
                    'step': i + 1,
                    'error': str(exc),
                    'success': False
                })
                break
        
        successful_handlers = sum(1 for r in chain_results if r['success'])
        
        return ExecutionResult(
            success=successful_handlers == len(self.handlers),
            data=chain_results,
            metadata={
                'total_handlers': len(self.handlers),
                'successful_handlers': successful_handlers,
                'failed_handlers': len(self.handlers) - successful_handlers,
            }
        )


class HandlerFactory:
    """Factory for creating handlers."""
    
    @staticmethod
    def create_integration_handler() -> IntegrationHandler:
        """Create integration handler."""
        return IntegrationHandler()
    
    @staticmethod
    def create_retry_handler(max_retries: int = 3, retry_delay: int = 1) -> RetryHandler:
        """Create retry handler."""
        return RetryHandler(max_retries, retry_delay)
    
    @staticmethod
    def create_circuit_breaker_handler(failure_threshold: int = 5, timeout: int = 60) -> CircuitBreakerHandler:
        """Create circuit breaker handler."""
        return CircuitBreakerHandler(failure_threshold, timeout)
    
    @staticmethod
    def create_batch_handler(batch_size: int = 100) -> BatchHandler:
        """Create batch handler."""
        return BatchHandler(batch_size)
    
    @staticmethod
    def create_handler_chain() -> HandlerChain:
        """Create handler chain."""
        return HandlerChain()


# Global handler instances
integration_handler = IntegrationHandler()
retry_handler = RetryHandler()
circuit_breaker_handler = CircuitBreakerHandler()
batch_handler = BatchHandler()


# Handler utilities
class HandlerUtils:
    """Utilities for handler management."""
    
    @staticmethod
    def create_execution_context(integration_id: str, data: Any, **kwargs) -> ExecutionContext:
        """Create execution context."""
        return ExecutionContext(
            integration_id=integration_id,
            data=data,
            **kwargs
        )
    
    @staticmethod
    def execute_with_retry(context: ExecutionContext, max_retries: int = 3) -> ExecutionResult:
        """Execute with retry logic."""
        handler = HandlerFactory.create_retry_handler(max_retries)
        return handler.execute(context)
    
    @staticmethod
    def execute_with_circuit_breaker(context: ExecutionContext, failure_threshold: int = 5) -> ExecutionResult:
        """Execute with circuit breaker."""
        handler = HandlerFactory.create_circuit_breaker_handler(failure_threshold)
        return handler.execute(context)
    
    @staticmethod
    def execute_batch(integration_id: str, data: List[Any], batch_size: int = 100, **kwargs) -> ExecutionResult:
        """Execute batch processing."""
        context = HandlerUtils.create_execution_context(
            integration_id=integration_id,
            data=data,
            mode=ExecutionMode.BATCH,
            **kwargs
        )
        
        handler = HandlerFactory.create_batch_handler(batch_size)
        return handler.execute(context)
    
    @staticmethod
    def execute_with_chain(context: ExecutionContext, handlers: List[BaseHandler]) -> ExecutionResult:
        """Execute with handler chain."""
        chain = HandlerFactory.create_handler_chain()
        
        for handler in handlers:
            chain.add_handler(handler)
        
        return chain.execute(context)
