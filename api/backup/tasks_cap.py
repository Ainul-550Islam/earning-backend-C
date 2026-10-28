"""
⚡ Advanced Task Management Module

This module provides comprehensive task management capabilities for the backup system.
It includes advanced task scheduling, task chaining, task monitoring, and task
orchestration to support complex background job workflows.

Features:
- Advanced task scheduling with dependencies
- Task chaining and workflows
- Task monitoring and analytics
- Task retry and failure handling
- Task prioritization and queuing
- Task resource management
- Task persistence and recovery
- Distributed task execution
"""

import logging
import json
import time
import threading
from typing import Dict, List, Any, Optional, Union, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from celery import Celery
from celery.result import AsyncResult
from celery.exceptions import Retry, WorkerLostError
from concurrent.futures import ThreadPoolExecutor, Future
import queue
import uuid
import pickle
import hashlib

# Import backup models and services
from .models import Backup, BackupLog, BackupAlert
from .utils import TimeUtils

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TaskStatus(Enum):
    """Enumeration of task statuses."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(Enum):
    """Enumeration of task priorities."""
    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100
    URGENT = 125


class TaskType(Enum):
    """Enumeration of task types."""
    BACKUP_CREATE = "backup_create"
    BACKUP_VERIFY = "backup_verify"
    BACKUP_RESTORE = "backup_restore"
    BACKUP_CLEANUP = "backup_cleanup"
    BACKUP_ENCRYPT = "backup_encrypt"
    BACKUP_COMPRESS = "backup_compress"
    BACKUP_UPLOAD = "backup_upload"
    BACKUP_DOWNLOAD = "backup_download"
    SCHEDULE_EXECUTE = "schedule_execute"
    ANALYTICS_GENERATE = "analytics_generate"
    NOTIFICATION_SEND = "notification_send"
    HEALTH_CHECK = "health_check"
    SYSTEM_MAINTENANCE = "system_maintenance"
    CUSTOM = "custom"


@dataclass
class TaskMetadata:
    """Task metadata."""
    task_id: str
    task_type: TaskType
    priority: TaskPriority = TaskPriority.NORMAL
    source: Optional[str] = None
    created_at: datetime = field(default_factory=timezone.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout: Optional[float] = None
    max_retries: int = 3
    retry_delay: int = 60  # seconds
    retry_backoff: float = 2.0  # exponential backoff factor
    tags: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    workflow_id: Optional[str] = None
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    estimated_duration: Optional[float] = None


@dataclass
class TaskResult:
    """Result of task execution."""
    task_id: str
    status: TaskStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    execution_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    retry_count: int = 0
    worker_id: Optional[str] = None
    timestamp: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskDefinition:
    """Task definition for registration."""
    name: str
    func: Callable
    task_type: TaskType
    default_priority: TaskPriority = TaskPriority.NORMAL
    default_timeout: Optional[float] = None
    default_max_retries: int = 3
    default_retry_delay: int = 60
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    estimated_duration: Optional[float] = None
    description: Optional[str] = None
    enabled: bool = True


class TaskQueue:
    """Advanced task queue with priority support."""
    
    def __init__(self, name: str, max_size: int = 1000):
        self.name = name
        self.max_size = max_size
        self.queue = queue.PriorityQueue(maxsize=max_size)
        self.tasks: Dict[str, TaskMetadata] = {}
        self.lock = threading.Lock()
        self.stats = {
            'total_queued': 0,
            'total_dequeued': 0,
            'current_size': 0,
            'priority_distribution': {p.value: 0 for p in TaskPriority}
        }
    
    def enqueue(self, task_metadata: TaskMetadata) -> bool:
        """Add task to queue."""
        with self.lock:
            if len(self.tasks) >= self.max_size:
                return False
            
            # Priority queue uses negative priority for max-heap behavior
            priority_value = -task_metadata.priority.value
            self.queue.put((priority_value, task_metadata.task_id, task_metadata))
            self.tasks[task_metadata.task_id] = task_metadata
            self.stats['total_queued'] += 1
            self.stats['current_size'] += 1
            self.stats['priority_distribution'][task_metadata.priority.value] += 1
            
            return True
    
    def dequeue(self, timeout: Optional[float] = None) -> Optional[TaskMetadata]:
        """Get next task from queue."""
        try:
            priority_value, task_id, task_metadata = self.queue.get(timeout=timeout)
            
            with self.lock:
                if task_id in self.tasks:
                    del self.tasks[task_id]
                    self.stats['total_dequeued'] += 1
                    self.stats['current_size'] -= 1
                    self.stats['priority_distribution'][task_metadata.priority.value] -= 1
                    return task_metadata
            
            return None
            
        except queue.Empty:
            return None
    
    def get_task(self, task_id: str) -> Optional[TaskMetadata]:
        """Get task by ID."""
        with self.lock:
            return self.tasks.get(task_id)
    
    def size(self) -> int:
        """Get queue size."""
        return self.queue.qsize()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self.lock:
            return {
                'name': self.name,
                'size': self.size(),
                'max_size': self.max_size,
                'current_tasks': len(self.tasks),
                **self.stats
            }


class TaskDependencyManager:
    """Manages task dependencies and execution order."""
    
    def __init__(self):
        self.dependencies: Dict[str, List[str]] = {}
        self.dependents: Dict[str, List[str]] = {}
        self.lock = threading.Lock()
    
    def add_dependency(self, task_id: str, depends_on: str) -> None:
        """Add dependency relationship."""
        with self.lock:
            if task_id not in self.dependencies:
                self.dependencies[task_id] = []
            
            if depends_on not in self.dependents:
                self.dependents[depends_on] = []
            
            self.dependencies[task_id].append(depends_on)
            self.dependents[depends_on].append(task_id)
    
    def remove_dependency(self, task_id: str, depends_on: str) -> None:
        """Remove dependency relationship."""
        with self.lock:
            if task_id in self.dependencies:
                self.dependencies[task_id] = [d for d in self.dependencies[task_id] if d != depends_on]
            
            if depends_on in self.dependents:
                self.dependents[depends_on] = [d for d in self.dependents[depends_on] if d != task_id]
    
    def can_execute(self, task_id: str, completed_tasks: set) -> bool:
        """Check if task can be executed based on dependencies."""
        with self.lock:
            dependencies = self.dependencies.get(task_id, [])
            return all(dep in completed_tasks for dep in dependencies)
    
    def get_ready_tasks(self, pending_tasks: List[str], completed_tasks: set) -> List[str]:
        """Get tasks that are ready to execute."""
        ready_tasks = []
        
        for task_id in pending_tasks:
            if self.can_execute(task_id, completed_tasks):
                ready_tasks.append(task_id)
        
        return ready_tasks
    
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get dependency graph."""
        with self.lock:
            return self.dependencies.copy()


class TaskWorkflow:
    """Task workflow for complex task orchestration."""
    
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.tasks: Dict[str, TaskMetadata] = {}
        self.task_results: Dict[str, TaskResult] = {}
        self.status = TaskStatus.PENDING
        self.created_at = timezone.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
        self.dependency_manager = TaskDependencyManager()
    
    def add_task(self, task_metadata: TaskMetadata) -> 'TaskWorkflow':
        """Add task to workflow."""
        task_metadata.workflow_id = self.workflow_id
        self.tasks[task_metadata.task_id] = task_metadata
        
        # Add dependencies
        for dep_id in task_metadata.dependencies:
            self.dependency_manager.add_dependency(task_metadata.task_id, dep_id)
        
        return self
    
    def get_ready_tasks(self) -> List[str]:
        """Get tasks ready to execute."""
        completed_tasks = {tid for tid, result in self.task_results.items() 
                          if result.status == TaskStatus.SUCCESS}
        pending_tasks = [tid for tid, task in self.tasks.items() 
                       if tid not in self.task_results]
        
        return self.dependency_manager.get_ready_tasks(pending_tasks, completed_tasks)
    
    def update_task_result(self, task_result: TaskResult) -> None:
        """Update task result."""
        self.task_results[task_result.task_id] = task_result
        
        # Update workflow status
        if task_result.status == TaskStatus.FAILURE:
            self.status = TaskStatus.FAILURE
            self.error = f"Task {task_result.task_id} failed: {task_result.error}"
    
    def is_complete(self) -> bool:
        """Check if workflow is complete."""
        return len(self.task_results) == len(self.tasks)
    
    def is_successful(self) -> bool:
        """Check if workflow was successful."""
        if not self.is_complete():
            return False
        
        return all(result.status == TaskStatus.SUCCESS for result in self.task_results.values())


class TaskResourceManager:
    """Manages task resource allocation and monitoring."""
    
    def __init__(self):
        self.resources: Dict[str, Dict[str, Any]] = {}
        self.allocations: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
    
    def register_resource(self, resource_name: str, capacity: Dict[str, Any]) -> None:
        """Register a resource."""
        with self.lock:
            self.resources[resource_name] = {
                'capacity': capacity,
                'allocated': {k: 0 for k in capacity.keys()},
                'available': capacity.copy()
            }
    
    def can_allocate(self, task_id: str, requirements: Dict[str, Any]) -> bool:
        """Check if resources can be allocated."""
        with self.lock:
            for resource_name, required_amount in requirements.items():
                if resource_name not in self.resources:
                    return False
                
                available = self.resources[resource_name]['available'].get(required_amount, 0)
                if available < required_amount:
                    return False
            
            return True
    
    def allocate(self, task_id: str, requirements: Dict[str, Any]) -> bool:
        """Allocate resources to task."""
        with self.lock:
            if not self.can_allocate(task_id, requirements):
                return False
            
            self.allocations[task_id] = {}
            
            for resource_name, required_amount in requirements.items():
                self.resources[resource_name]['allocated'][required_amount] += required_amount
                self.resources[resource_name]['available'][required_amount] -= required_amount
                self.allocations[task_id][resource_name] = required_amount
            
            return True
    
    def release(self, task_id: str) -> None:
        """Release allocated resources."""
        with self.lock:
            if task_id not in self.allocations:
                return
            
            allocations = self.allocations[task_id]
            
            for resource_name, allocated_amount in allocations.items():
                self.resources[resource_name]['allocated'][allocated_amount] -= allocated_amount
                self.resources[resource_name]['available'][allocated_amount] += allocated_amount
            
            del self.allocations[task_id]
    
    def get_resource_status(self) -> Dict[str, Any]:
        """Get resource status."""
        with self.lock:
            return {
                'resources': self.resources,
                'allocations': self.allocations
            }


class AdvancedTaskManager:
    """Advanced task manager with comprehensive capabilities."""
    
    def __init__(self):
        self.task_definitions: Dict[str, TaskDefinition] = {}
        self.queues: Dict[str, TaskQueue] = {}
        self.workflows: Dict[str, TaskWorkflow] = {}
        self.task_results: Dict[str, TaskResult] = {}
        self.resource_manager = TaskResourceManager()
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.running_tasks: Dict[str, Future] = {}
        self.lock = threading.Lock()
        
        # Initialize default queues
        self._initialize_default_queues()
        
        # Register default tasks
        self._register_default_tasks()
        
        # Register system resources
        self._register_system_resources()
    
    def _initialize_default_queues(self) -> None:
        """Initialize default task queues."""
        queue_configs = getattr(settings, 'BACKUP_TASK_QUEUES', {
            'default': {'max_size': 1000},
            'backup': {'max_size': 500},
            'restore': {'max_size': 200},
            'maintenance': {'max_size': 100},
            'analytics': {'max_size': 200}
        })
        
        for queue_name, config in queue_configs.items():
            max_size = config.get('max_size', 1000)
            self.queues[queue_name] = TaskQueue(queue_name, max_size)
    
    def _register_default_tasks(self) -> None:
        """Register default task definitions."""
        # Backup creation task
        self.register_task(TaskDefinition(
            name='backup_create',
            func=self._backup_create_task,
            task_type=TaskType.BACKUP_CREATE,
            default_priority=TaskPriority.NORMAL,
            default_timeout=3600,  # 1 hour
            estimated_duration=300,  # 5 minutes
            resource_requirements={'memory_mb': 512, 'cpu_cores': 2}
        ))
        
        # Backup verification task
        self.register_task(TaskDefinition(
            name='backup_verify',
            func=self._backup_verify_task,
            task_type=TaskType.BACKUP_VERIFY,
            default_priority=TaskPriority.NORMAL,
            default_timeout=1800,  # 30 minutes
            estimated_duration=120,  # 2 minutes
            resource_requirements={'memory_mb': 256, 'cpu_cores': 1}
        ))
        
        # Backup restore task
        self.register_task(TaskDefinition(
            name='backup_restore',
            func=self._backup_restore_task,
            task_type=TaskType.BACKUP_RESTORE,
            default_priority=TaskPriority.HIGH,
            default_timeout=7200,  # 2 hours
            estimated_duration=600,  # 10 minutes
            resource_requirements={'memory_mb': 1024, 'cpu_cores': 4}
        ))
        
        # Backup cleanup task
        self.register_task(TaskDefinition(
            name='backup_cleanup',
            func=self._backup_cleanup_task,
            task_type=TaskType.BACKUP_CLEANUP,
            default_priority=TaskPriority.LOW,
            default_timeout=1800,  # 30 minutes
            estimated_duration=180,  # 3 minutes
            resource_requirements={'memory_mb': 256, 'cpu_cores': 1}
        ))
    
    def _register_system_resources(self) -> None:
        """Register system resources."""
        self.resource_manager.register_resource('memory_mb', {'total': 8192})  # 8GB
        self.resource_manager.register_resource('cpu_cores', {'total': 8})
        self.resource_manager.register_resource('disk_space_gb', {'total': 1000})  # 1TB
    
    def register_task(self, task_definition: TaskDefinition) -> None:
        """Register a task definition."""
        self.task_definitions[task_definition.name] = task_definition
        logger.info(f"Registered task: {task_definition.name}")
    
    def submit_task(self, task_name: str, queue_name: str = 'default',
                   priority: Optional[TaskPriority] = None,
                   scheduled_at: Optional[datetime] = None,
                   dependencies: Optional[List[str]] = None,
                   workflow_id: Optional[str] = None,
                   **kwargs) -> str:
        """Submit a task for execution."""
        if task_name not in self.task_definitions:
            raise ValueError(f"Task {task_name} not registered")
        
        task_def = self.task_definitions[task_name]
        
        if not task_def.enabled:
            raise ValueError(f"Task {task_name} is disabled")
        
        # Create task metadata
        task_id = str(uuid.uuid4())
        task_metadata = TaskMetadata(
            task_id=task_id,
            task_type=task_def.task_type,
            priority=priority or task_def.default_priority,
            scheduled_at=scheduled_at,
            timeout=task_def.default_timeout,
            max_retries=task_def.default_max_retries,
            retry_delay=task_def.default_retry_delay,
            dependencies=dependencies or [],
            workflow_id=workflow_id,
            resource_requirements=task_def.resource_requirements,
            estimated_duration=task_def.estimated_duration,
            context=kwargs
        )
        
        # Add to queue
        queue = self.queues.get(queue_name)
        if not queue:
            raise ValueError(f"Queue {queue_name} not found")
        
        if not queue.enqueue(task_metadata):
            raise ValueError(f"Queue {queue_name} is full")
        
        logger.info(f"Submitted task {task_id} ({task_name}) to queue {queue_name}")
        return task_id
    
    def create_workflow(self, workflow_id: Optional[str] = None) -> TaskWorkflow:
        """Create a new workflow."""
        if workflow_id is None:
            workflow_id = str(uuid.uuid4())
        
        workflow = TaskWorkflow(workflow_id)
        self.workflows[workflow_id] = workflow
        
        return workflow
    
    def execute_workflow(self, workflow: TaskWorkflow) -> Dict[str, TaskResult]:
        """Execute a workflow."""
        workflow.status = TaskStatus.RUNNING
        workflow.started_at = timezone.now()
        
        completed_tasks = set()
        results = {}
        
        try:
            while not workflow.is_complete():
                ready_tasks = workflow.get_ready_tasks()
                
                if not ready_tasks:
                    # Check for deadlock
                    if len(completed_tasks) > 0:
                        break
                    else:
                        raise Exception("Workflow deadlock detected")
                
                # Execute ready tasks
                for task_id in ready_tasks:
                    task_metadata = workflow.tasks[task_id]
                    result = self._execute_task(task_metadata)
                    workflow.update_task_result(result)
                    results[task_id] = result
                    
                    if result.status == TaskStatus.SUCCESS:
                        completed_tasks.add(task_id)
                    elif result.status == TaskStatus.FAILURE:
                        workflow.status = TaskStatus.FAILURE
                        workflow.error = f"Task {task_id} failed: {result.error}"
                        break
            
            workflow.completed_at = timezone.now()
            if workflow.is_successful():
                workflow.status = TaskStatus.SUCCESS
            
        except Exception as e:
            workflow.status = TaskStatus.FAILURE
            workflow.error = str(e)
            workflow.completed_at = timezone.now()
        
        return results
    
    def _execute_task(self, task_metadata: TaskMetadata) -> TaskResult:
        """Execute a single task."""
        start_time = time.time()
        
        # Check resource availability
        if not self.resource_manager.can_allocate(task_metadata.task_id, task_metadata.resource_requirements):
            return TaskResult(
                task_id=task_metadata.task_id,
                status=TaskStatus.FAILURE,
                error="Insufficient resources",
                execution_time_ms=(time.time() - start_time) * 1000
            )
        
        # Allocate resources
        self.resource_manager.allocate(task_metadata.task_id, task_metadata.resource_requirements)
        
        try:
            # Get task definition
            task_def = self.task_definitions.get(f"task_{task_metadata.task_type.value}")
            if not task_def:
                raise ValueError(f"No task definition for {task_metadata.task_type}")
            
            # Execute task
            result = task_def.func(**task_metadata.context)
            
            execution_time = (time.time() - start_time) * 1000
            
            return TaskResult(
                task_id=task_metadata.task_id,
                status=TaskStatus.SUCCESS,
                result=result,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            
            return TaskResult(
                task_id=task_metadata.task_id,
                status=TaskStatus.FAILURE,
                error=str(e),
                execution_time_ms=execution_time
            )
        
        finally:
            # Release resources
            self.resource_manager.release(task_metadata.task_id)
    
    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get task status."""
        return self.task_results.get(task_id)
    
    def get_workflow_status(self, workflow_id: str) -> Optional[TaskWorkflow]:
        """Get workflow status."""
        return self.workflows.get(workflow_id)
    
    def get_queue_stats(self, queue_name: Optional[str] = None) -> Dict[str, Any]:
        """Get queue statistics."""
        if queue_name:
            queue = self.queues.get(queue_name)
            return queue.get_stats() if queue else {}
        
        return {
            'queues': {name: queue.get_stats() for name, queue in self.queues.items()},
            'total_tasks': len(self.task_results),
            'active_workflows': len(self.workflows)
        }
    
    def get_resource_stats(self) -> Dict[str, Any]:
        """Get resource statistics."""
        return self.resource_manager.get_resource_status()
    
    # Default task implementations
    def _backup_create_task(self, **kwargs) -> Dict[str, Any]:
        """Default backup creation task."""
        backup_id = kwargs.get('backup_id')
        logger.info(f"Creating backup {backup_id}")
        
        # This would integrate with the actual backup service
        time.sleep(2)  # Simulate work
        
        return {'backup_id': backup_id, 'status': 'created'}
    
    def _backup_verify_task(self, **kwargs) -> Dict[str, Any]:
        """Default backup verification task."""
        backup_id = kwargs.get('backup_id')
        logger.info(f"Verifying backup {backup_id}")
        
        time.sleep(1)  # Simulate work
        
        return {'backup_id': backup_id, 'verified': True}
    
    def _backup_restore_task(self, **kwargs) -> Dict[str, Any]:
        """Default backup restoration task."""
        backup_id = kwargs.get('backup_id')
        logger.info(f"Restoring backup {backup_id}")
        
        time.sleep(3)  # Simulate work
        
        return {'backup_id': backup_id, 'restored': True}
    
    def _backup_cleanup_task(self, **kwargs) -> Dict[str, Any]:
        """Default backup cleanup task."""
        days_old = kwargs.get('days_old', 30)
        logger.info(f"Cleaning up backups older than {days_old} days")
        
        time.sleep(1)  # Simulate work
        
        return {'cleaned_backups': 5}


# Global task manager instance
_task_manager: Optional[AdvancedTaskManager] = None


def get_task_manager() -> AdvancedTaskManager:
    """Get the global task manager instance."""
    global _task_manager
    if _task_manager is None:
        _task_manager = AdvancedTaskManager()
    return _task_manager


def submit_task(task_name: str, queue_name: str = 'default',
                priority: Optional[TaskPriority] = None,
                scheduled_at: Optional[datetime] = None,
                dependencies: Optional[List[str]] = None,
                **kwargs) -> str:
    """Submit a task for execution."""
    manager = get_task_manager()
    return manager.submit_task(
        task_name, queue_name, priority, scheduled_at, dependencies, **kwargs
    )


def create_backup_workflow(backup_id: str) -> str:
    """Create a backup workflow."""
    manager = get_task_manager()
    workflow = manager.create_workflow()
    
    # Add tasks to workflow
    create_task = TaskMetadata(
        task_id=str(uuid.uuid4()),
        task_type=TaskType.BACKUP_CREATE,
        context={'backup_id': backup_id}
    )
    
    verify_task = TaskMetadata(
        task_id=str(uuid.uuid4()),
        task_type=TaskType.BACKUP_VERIFY,
        context={'backup_id': backup_id},
        dependencies=[create_task.task_id]
    )
    
    workflow.add_task(create_task).add_task(verify_task)
    
    # Execute workflow
    manager.execute_workflow(workflow)
    
    return workflow.workflow_id


def get_task_status(task_id: str) -> Optional[TaskResult]:
    """Get task status."""
    manager = get_task_manager()
    return manager.get_task_status(task_id)


def get_workflow_status(workflow_id: str) -> Optional[TaskWorkflow]:
    """Get workflow status."""
    manager = get_task_manager()
    return manager.get_workflow_status(workflow_id)


def get_task_stats(queue_name: Optional[str] = None) -> Dict[str, Any]:
    """Get task statistics."""
    manager = get_task_manager()
    return manager.get_queue_stats(queue_name)


# Decorators for task registration
def backup_task(name: str, priority: TaskPriority = TaskPriority.NORMAL,
                timeout: Optional[float] = None, **kwargs):
    """Decorator for backup task registration."""
    def decorator(func):
        task_def = TaskDefinition(
            name=name,
            func=func,
            task_type=TaskType.CUSTOM,
            default_priority=priority,
            default_timeout=timeout,
            **kwargs
        )
        
        manager = get_task_manager()
        manager.register_task(task_def)
        return func
    return decorator


def system_task(name: str, priority: TaskPriority = TaskPriority.NORMAL,
               timeout: Optional[float] = None, **kwargs):
    """Decorator for system task registration."""
    def decorator(func):
        task_def = TaskDefinition(
            name=name,
            func=func,
            task_type=TaskType.SYSTEM_MAINTENANCE,
            default_priority=priority,
            default_timeout=timeout,
            **kwargs
        )
        
        manager = get_task_manager()
        manager.register_task(task_def)
        return func
    return decorator
