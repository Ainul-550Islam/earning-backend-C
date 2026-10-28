"""
tasks_cap.py – Advanced task management and capabilities for postback module.

Provides enhanced task management features including:
- Task chaining and workflows
- Conditional task execution
- Task performance monitoring
- Task retry and failure handling
- Dynamic task scheduling
"""
import logging
import json
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime, timedelta
from functools import wraps
from enum import Enum

from celery import Task as CeleryTask
from celery.result import AsyncResult
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .exceptions import PostbackException

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 15


class TaskCapability:
    """
    Base class for advanced task capabilities.
    
    Provides common functionality for enhanced task management
    including monitoring, retry logic, and performance tracking.
    """
    
    def __init__(self, task_name: str, max_retries: int = 3, retry_delay: int = 60):
        self.task_name = task_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.execution_history = []
        self.performance_metrics = {}
    
    def execute_with_monitoring(self, task_func: Callable, *args, **kwargs) -> Any:
        """
        Execute a task with comprehensive monitoring.
        
        Args:
            task_func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Result of task execution
        """
        start_time = timezone.now()
        execution_id = self._generate_execution_id()
        
        try:
            # Log task start
            self._log_task_start(execution_id, args, kwargs)
            
            # Execute the task
            result = task_func(*args, **kwargs)
            
            # Calculate execution time
            execution_time = (timezone.now() - start_time).total_seconds()
            
            # Record successful execution
            self._record_execution(execution_id, TaskStatus.SUCCESS, execution_time, None)
            
            # Update performance metrics
            self._update_performance_metrics(execution_time, True)
            
            # Log task completion
            self._log_task_completion(execution_id, TaskStatus.SUCCESS, execution_time)
            
            return result
            
        except Exception as e:
            execution_time = (timezone.now() - start_time).total_seconds()
            
            # Record failed execution
            self._record_execution(execution_id, TaskStatus.FAILURE, execution_time, str(e))
            
            # Update performance metrics
            self._update_performance_metrics(execution_time, False)
            
            # Log task failure
            self._log_task_completion(execution_id, TaskStatus.FAILURE, execution_time, str(e))
            
            # Check if retry should be attempted
            if self._should_retry(e):
                return self._retry_task(task_func, execution_id, args, kwargs)
            
            # Re-raise exception if no retry
            raise
    
    def _generate_execution_id(self) -> str:
        """Generate unique execution ID."""
        import uuid
        return f"{self.task_name}_{uuid.uuid4().hex[:8]}"
    
    def _log_task_start(self, execution_id: str, args: tuple, kwargs: dict):
        """Log task start."""
        logger.info(f"Task {self.task_name} started: {execution_id}")
        
        # Cache execution start
        cache_key = f"task_execution_{execution_id}"
        cache.set(cache_key, {
            'status': TaskStatus.RUNNING.value,
            'started_at': timezone.now().isoformat(),
            'task_name': self.task_name,
        }, timeout=3600)
    
    def _log_task_completion(self, execution_id: str, status: TaskStatus, execution_time: float, error: str = None):
        """Log task completion."""
        logger.info(f"Task {self.task_name} {status.value}: {execution_id} ({execution_time:.2f}s)")
        
        # Update cache
        cache_key = f"task_execution_{execution_id}"
        cache_data = cache.get(cache_key) or {}
        cache_data.update({
            'status': status.value,
            'completed_at': timezone.now().isoformat(),
            'execution_time': execution_time,
            'error': error,
        })
        cache.set(cache_key, cache_data, timeout=3600)
    
    def _record_execution(self, execution_id: str, status: TaskStatus, execution_time: float, error: str = None):
        """Record task execution details."""
        execution_record = {
            'execution_id': execution_id,
            'status': status.value,
            'execution_time': execution_time,
            'error': error,
            'timestamp': timezone.now().isoformat(),
        }
        
        self.execution_history.append(execution_record)
        
        # Keep only last 100 executions
        if len(self.execution_history) > 100:
            self.execution_history = self.execution_history[-100:]
    
    def _update_performance_metrics(self, execution_time: float, success: bool):
        """Update performance metrics."""
        if 'total_executions' not in self.performance_metrics:
            self.performance_metrics = {
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
                'total_execution_time': 0.0,
                'avg_execution_time': 0.0,
                'min_execution_time': float('inf'),
                'max_execution_time': 0.0,
            }
        
        metrics = self.performance_metrics
        metrics['total_executions'] += 1
        metrics['total_execution_time'] += execution_time
        
        if success:
            metrics['successful_executions'] += 1
        else:
            metrics['failed_executions'] += 1
        
        metrics['avg_execution_time'] = metrics['total_execution_time'] / metrics['total_executions']
        metrics['min_execution_time'] = min(metrics['min_execution_time'], execution_time)
        metrics['max_execution_time'] = max(metrics['max_execution_time'], execution_time)
    
    def _should_retry(self, exception: Exception) -> bool:
        """Determine if task should be retried."""
        # Check retry count
        recent_failures = [e for e in self.execution_history[-5:] if e['status'] == TaskStatus.FAILURE.value]
        
        if len(recent_failures) >= self.max_retries:
            return False
        
        # Check exception type
        retryable_exceptions = (
            ConnectionError,
            TimeoutError,
            PostbackException,
        )
        
        return isinstance(exception, retryable_exceptions)
    
    def _retry_task(self, task_func: Callable, execution_id: str, args: tuple, kwargs: dict) -> Any:
        """Retry task execution with delay."""
        import time
        
        logger.warning(f"Retrying task {self.task_name} after {self.retry_delay}s: {execution_id}")
        
        # Wait before retry
        time.sleep(self.retry_delay)
        
        # Retry execution
        return self.execute_with_monitoring(task_func, *args, **kwargs)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for the task."""
        metrics = self.performance_metrics
        
        if not metrics:
            return {'message': 'No performance data available'}
        
        success_rate = (metrics['successful_executions'] / metrics['total_executions']) * 100 if metrics['total_executions'] > 0 else 0
        
        return {
            'task_name': self.task_name,
            'total_executions': metrics['total_executions'],
            'successful_executions': metrics['successful_executions'],
            'failed_executions': metrics['failed_executions'],
            'success_rate': f"{success_rate:.2f}%",
            'avg_execution_time': f"{metrics['avg_execution_time']:.2f}s",
            'min_execution_time': f"{metrics['min_execution_time']:.2f}s",
            'max_execution_time': f"{metrics['max_execution_time']:.2f}s",
            'last_executions': self.execution_history[-10:],
        }


class TaskChain:
    """
    Task chaining system for complex workflows.
    
    Provides capabilities for:
    - Sequential task execution
    - Conditional task routing
    - Parallel task execution
    - Task dependency management
    """
    
    def __init__(self, chain_name: str):
        self.chain_name = chain_name
        self.tasks = []
        self.conditions = {}
        self.dependencies = {}
        self.execution_history = []
    
    def add_task(self, task_name: str, task_func: Callable, depends_on: List[str] = None, condition: str = None):
        """
        Add a task to the chain.
        
        Args:
            task_name: Name identifier for the task
            task_func: Function to execute
            depends_on: List of task names this task depends on
            condition: Condition name for conditional execution
        """
        self.tasks.append({
            'name': task_name,
            'function': task_func,
            'depends_on': depends_on or [],
            'condition': condition,
            'status': TaskStatus.PENDING.value,
            'result': None,
            'error': None,
            'execution_time': 0.0,
        })
        
        # Store dependencies
        if depends_on:
            self.dependencies[task_name] = depends_on
        
        # Store condition
        if condition:
            self.conditions[task_name] = condition
        
        logger.info(f"Added task to chain {self.chain_name}: {task_name}")
    
    def execute_chain(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute the entire task chain.
        
        Args:
            context: Execution context passed to all tasks
            
        Returns:
            Chain execution results
        """
        if context is None:
            context = {}
        
        chain_start_time = timezone.now()
        chain_id = self._generate_chain_id()
        
        try:
            logger.info(f"Starting task chain {self.chain_name}: {chain_id}")
            
            # Execute tasks in dependency order
            executed_tasks = set()
            
            while len(executed_tasks) < len(self.tasks):
                progress_made = False
                
                for task in self.tasks:
                    task_name = task['name']
                    
                    if task_name in executed_tasks:
                        continue
                    
                    # Check dependencies
                    if not self._dependencies_satisfied(task_name, executed_tasks):
                        continue
                    
                    # Check condition
                    if task['condition'] and not self._condition_satisfied(task['condition'], context):
                        task['status'] = TaskStatus.REVOKED.value
                        logger.info(f"Task {task_name} revoked due to condition: {task['condition']}")
                        executed_tasks.add(task_name)
                        progress_made = True
                        continue
                    
                    # Execute task
                    self._execute_chain_task(task, context)
                    executed_tasks.add(task_name)
                    progress_made = True
                
                if not progress_made:
                    # Circular dependency or unsatisfied dependencies
                    raise PostbackException(f"Cannot complete chain {self.chain_name}: unsatisfied dependencies")
            
            # Calculate chain execution time
            chain_execution_time = (timezone.now() - chain_start_time).total_seconds()
            
            # Record chain execution
            self._record_chain_execution(chain_id, TaskStatus.SUCCESS, chain_execution_time, context)
            
            # Prepare results
            results = {
                'chain_id': chain_id,
                'chain_name': self.chain_name,
                'status': TaskStatus.SUCCESS.value,
                'execution_time': chain_execution_time,
                'tasks': {task['name']: self._get_task_summary(task) for task in self.tasks},
                'context': context,
            }
            
            logger.info(f"Task chain {self.chain_name} completed successfully: {chain_id}")
            return results
            
        except Exception as e:
            chain_execution_time = (timezone.now() - chain_start_time).total_seconds()
            
            # Record chain failure
            self._record_chain_execution(chain_id, TaskStatus.FAILURE, chain_execution_time, context, str(e))
            
            results = {
                'chain_id': chain_id,
                'chain_name': self.chain_name,
                'status': TaskStatus.FAILURE.value,
                'execution_time': chain_execution_time,
                'error': str(e),
                'tasks': {task['name']: self._get_task_summary(task) for task in self.tasks},
                'context': context,
            }
            
            logger.error(f"Task chain {self.chain_name} failed: {chain_id} - {str(e)}")
            return results
    
    def _generate_chain_id(self) -> str:
        """Generate unique chain execution ID."""
        import uuid
        return f"{self.chain_name}_{uuid.uuid4().hex[:8]}"
    
    def _dependencies_satisfied(self, task_name: str, executed_tasks: set) -> bool:
        """Check if task dependencies are satisfied."""
        if task_name not in self.dependencies:
            return True
        
        dependencies = self.dependencies[task_name]
        return all(dep in executed_tasks for dep in dependencies)
    
    def _condition_satisfied(self, condition: str, context: Dict[str, Any]) -> bool:
        """Check if execution condition is satisfied."""
        # This would implement custom condition logic
        # For now, return True (no condition checking)
        return True
    
    def _execute_chain_task(self, task: Dict[str, Any], context: Dict[str, Any]):
        """Execute a single task in the chain."""
        task_name = task['name']
        task_func = task['function']
        
        start_time = timezone.now()
        task['status'] = TaskStatus.RUNNING.value
        
        try:
            logger.info(f"Executing task {task_name} in chain {self.chain_name}")
            
            # Execute task with context
            result = task_func(context)
            
            # Update task status
            task['status'] = TaskStatus.SUCCESS.value
            task['result'] = result
            task['execution_time'] = (timezone.now() - start_time).total_seconds()
            
            # Update context with task result
            context[task_name] = result
            
            logger.info(f"Task {task_name} completed successfully")
            
        except Exception as e:
            task['status'] = TaskStatus.FAILURE.value
            task['error'] = str(e)
            task['execution_time'] = (timezone.now() - start_time).total_seconds()
            
            logger.error(f"Task {task_name} failed: {str(e)}")
            raise
    
    def _get_task_summary(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Get task execution summary."""
        return {
            'status': task['status'],
            'execution_time': task['execution_time'],
            'error': task.get('error'),
            'depends_on': task.get('depends_on', []),
            'condition': task.get('condition'),
        }
    
    def _record_chain_execution(self, chain_id: str, status: TaskStatus, execution_time: float, context: Dict[str, Any], error: str = None):
        """Record chain execution details."""
        execution_record = {
            'chain_id': chain_id,
            'chain_name': self.chain_name,
            'status': status.value,
            'execution_time': execution_time,
            'context': context,
            'error': error,
            'timestamp': timezone.now().isoformat(),
        }
        
        self.execution_history.append(execution_record)
        
        # Keep only last 50 executions
        if len(self.execution_history) > 50:
            self.execution_history = self.execution_history[-50:]
        
        # Cache execution record
        cache_key = f"chain_execution_{chain_id}"
        cache.set(cache_key, execution_record, timeout=3600)


class ConditionalTask:
    """
    Conditional task execution system.
    
    Provides capabilities for:
    - Conditional task execution based on criteria
    - Dynamic task routing
    - Rule-based task selection
    """
    
    def __init__(self):
        self.conditions = {}
        self.rules = {}
        self.task_registry = {}
    
    def register_condition(self, condition_name: str, condition_func: Callable):
        """
        Register a condition function.
        
        Args:
            condition_name: Name identifier for the condition
            condition_func: Function that returns True/False
        """
        self.conditions[condition_name] = condition_func
        logger.info(f"Registered condition: {condition_name}")
    
    def register_task(self, task_name: str, task_func: Callable):
        """
        Register a task function.
        
        Args:
            task_name: Name identifier for the task
            task_func: Function to execute
        """
        self.task_registry[task_name] = task_func
        logger.info(f"Registered task: {task_name}")
    
    def add_rule(self, rule_name: str, conditions: List[str], task_name: str, priority: int = 5):
        """
        Add a conditional execution rule.
        
        Args:
            rule_name: Name identifier for the rule
            conditions: List of condition names that must be satisfied
            task_name: Task to execute if conditions are satisfied
            priority: Rule priority (higher = more important)
        """
        self.rules[rule_name] = {
            'conditions': conditions,
            'task_name': task_name,
            'priority': priority,
            'execution_count': 0,
        }
        logger.info(f"Added rule: {rule_name}")
    
    def execute_conditional_task(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task based on conditions and rules.
        
        Args:
            context: Execution context
            
        Returns:
            Task execution results
        """
        start_time = timezone.now()
        execution_id = self._generate_execution_id()
        
        try:
            # Find matching rules
            matching_rules = self._find_matching_rules(context)
            
            if not matching_rules:
                return {
                    'execution_id': execution_id,
                    'status': TaskStatus.REVOKED.value,
                    'message': 'No matching rules found',
                    'execution_time': (timezone.now() - start_time).total_seconds(),
                }
            
            # Execute highest priority rule
            rule = matching_rules[0]
            task_name = rule['task_name']
            
            # Check if task exists
            if task_name not in self.task_registry:
                raise PostbackException(f"Task {task_name} not registered")
            
            # Execute task
            task_func = self.task_registry[task_name]
            result = task_func(context)
            
            # Update rule execution count
            rule['execution_count'] += 1
            
            execution_time = (timezone.now() - start_time).total_seconds()
            
            return {
                'execution_id': execution_id,
                'status': TaskStatus.SUCCESS.value,
                'rule_name': max(self.rules.keys(), key=lambda k: self.rules[k]['priority']),
                'task_name': task_name,
                'result': result,
                'execution_time': execution_time,
            }
            
        except Exception as e:
            execution_time = (timezone.now() - start_time).total_seconds()
            
            return {
                'execution_id': execution_id,
                'status': TaskStatus.FAILURE.value,
                'error': str(e),
                'execution_time': execution_time,
            }
    
    def _find_matching_rules(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find rules that match the current context."""
        matching_rules = []
        
        for rule_name, rule in self.rules.items():
            if self._rule_conditions_satisfied(rule, context):
                matching_rules.append(rule)
        
        # Sort by priority (highest first)
        matching_rules.sort(key=lambda r: r['priority'], reverse=True)
        
        return matching_rules
    
    def _rule_conditions_satisfied(self, rule: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Check if all rule conditions are satisfied."""
        for condition_name in rule['conditions']:
            if condition_name not in self.conditions:
                logger.warning(f"Condition {condition_name} not found")
                return False
            
            condition_func = self.conditions[condition_name]
            if not condition_func(context):
                return False
        
        return True
    
    def _generate_execution_id(self) -> str:
        """Generate unique execution ID."""
        import uuid
        return f"conditional_task_{uuid.uuid4().hex[:8]}"
    
    def get_rule_statistics(self) -> Dict[str, Any]:
        """Get execution statistics for all rules."""
        return {
            rule_name: {
                'priority': rule['priority'],
                'execution_count': rule['execution_count'],
                'conditions': rule['conditions'],
                'task_name': rule['task_name'],
            }
            for rule_name, rule in self.rules.items()
        }


# Decorators for task capabilities
def task_capability(task_name: str, max_retries: int = 3, retry_delay: int = 60):
    """
    Decorator for adding task capabilities to functions.
    
    Args:
        task_name: Name of the task
        max_retries: Maximum number of retries
        retry_delay: Delay between retries in seconds
    """
    def decorator(func):
        capability = TaskCapability(task_name, max_retries, retry_delay)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return capability.execute_with_monitoring(func, *args, **kwargs)
        
        # Attach capability to wrapper for access to metrics
        wrapper._capability = capability
        wrapper.get_performance_summary = capability.get_performance_summary
        
        return wrapper
    return decorator


def conditional_task_execution(conditions: List[str]):
    """
    Decorator for conditional task execution.
    
    Args:
        conditions: List of condition names that must be satisfied
    """
    def decorator(func):
        @wraps(func)
        def wrapper(context: Dict[str, Any], *args, **kwargs):
            conditional_system = ConditionalTask()
            
            # Register the function as a task
            task_name = func.__name__
            conditional_system.register_task(task_name, func)
            
            # Add rule for this task
            rule_name = f"{task_name}_rule"
            conditional_system.add_rule(rule_name, conditions, task_name)
            
            # Execute conditional task
            return conditional_system.execute_conditional_task(context)
        
        return wrapper
    return decorator


# Global instances
task_capabilities = {}
task_chains = {}
conditional_tasks = ConditionalTask()


def get_task_capability(task_name: str) -> TaskCapability:
    """Get or create task capability instance."""
    if task_name not in task_capabilities:
        task_capabilities[task_name] = TaskCapability(task_name)
    
    return task_capabilities[task_name]


def create_task_chain(chain_name: str) -> TaskChain:
    """Create a new task chain."""
    chain = TaskChain(chain_name)
    task_chains[chain_name] = chain
    return chain


def get_task_statistics() -> Dict[str, Any]:
    """Get comprehensive task statistics."""
    return {
        'task_capabilities': {
            name: capability.get_performance_summary()
            for name, capability in task_capabilities.items()
        },
        'task_chains': {
            name: {
                'total_executions': len(chain.execution_history),
                'total_tasks': len(chain.tasks),
                'last_execution': chain.execution_history[-1] if chain.execution_history else None,
            }
            for name, chain in task_chains.items()
        },
        'conditional_tasks': conditional_tasks.get_rule_statistics(),
    }


# Built-in conditions for conditional tasks
def is_business_hours(context: Dict[str, Any]) -> bool:
    """Check if current time is within business hours."""
    from datetime import datetime
    current_hour = datetime.now().hour
    return 9 <= current_hour <= 17


def is_high_priority(context: Dict[str, Any]) -> bool:
    """Check if context indicates high priority."""
    return context.get('priority', 'normal') == 'high'


def has_error(context: Dict[str, Any]) -> bool:
    """Check if context contains an error."""
    return 'error' in context and context['error'] is not None


def is_weekend(context: Dict[str, Any]) -> bool:
    """Check if current day is weekend."""
    from datetime import datetime
    current_day = datetime.now().weekday()
    return current_day >= 5  # Saturday=5, Sunday=6


# Register built-in conditions
conditional_tasks.register_condition('is_business_hours', is_business_hours)
conditional_tasks.register_condition('is_high_priority', is_high_priority)
conditional_tasks.register_condition('has_error', has_error)
conditional_tasks.register_condition('is_weekend', is_weekend)
