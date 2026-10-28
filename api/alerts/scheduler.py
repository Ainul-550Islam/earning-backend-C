"""
Task Scheduler for alerts app - Advanced task scheduling and management
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable, Union
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
import asyncio
import logging
import json
import uuid
import time
import threading
from datetime import datetime, timedelta
from enum import Enum
try:
    from croniter import croniter
except ImportError:
    croniter = None

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    TIMEOUT = "timeout"


class TaskPriority(Enum):
    """Task priority enumeration"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class ScheduleType(Enum):
    """Schedule type enumeration"""
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Task:
    """Represents a scheduled task"""
    
    def __init__(self, name: str, func: Callable, schedule_type: ScheduleType,
                 schedule_config: Dict[str, Any], priority: TaskPriority = TaskPriority.NORMAL,
                 max_retries: int = 3, timeout: int = 300, metadata: Dict[str, Any] = None):
        self.id = str(uuid.uuid4())
        self.name = name
        self.func = func
        self.schedule_type = schedule_type
        self.schedule_config = schedule_config
        self.priority = priority
        self.max_retries = max_retries
        self.timeout = timeout
        self.metadata = metadata or {}
        self.created_at = timezone.now()
        self.last_run = None
        self.next_run = self._calculate_next_run()
        self.status = TaskStatus.PENDING
        self.run_count = 0
        self.failure_count = 0
        self.last_error = None
        self.enabled = True
        
    def _calculate_next_run(self) -> Optional[datetime]:
        """Calculate next run time"""
        now = timezone.now()
        
        if self.schedule_type == ScheduleType.ONCE:
            run_at = self.schedule_config.get('run_at')
            if run_at and run_at > now:
                return run_at
            return None
            
        elif self.schedule_type == ScheduleType.INTERVAL:
            interval = self.schedule_config.get('interval', 3600)  # Default 1 hour
            start_from = self.schedule_config.get('start_from', now)
            return start_from + timedelta(seconds=interval)
            
        elif self.schedule_type == ScheduleType.CRON:
            cron_expression = self.schedule_config.get('cron_expression')
            if cron_expression:
                cron = croniter(cron_expression, now)
                return cron.get_next(datetime)
            return None
            
        elif self.schedule_type == ScheduleType.DAILY:
            hour = self.schedule_config.get('hour', 0)
            minute = self.schedule_config.get('minute', 0)
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run
            
        elif self.schedule_type == ScheduleType.WEEKLY:
            day_of_week = self.schedule_config.get('day_of_week', 0)  # 0 = Monday
            hour = self.schedule_config.get('hour', 0)
            minute = self.schedule_config.get('minute', 0)
            
            days_ahead = day_of_week - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            
            next_run = now + timedelta(days=days_ahead)
            next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return next_run
            
        elif self.schedule_type == ScheduleType.MONTHLY:
            day = self.schedule_config.get('day', 1)
            hour = self.schedule_config.get('hour', 0)
            minute = self.schedule_config.get('minute', 0)
            
            if now.day > day:
                # Next month
                if now.month == 12:
                    next_run = now.replace(year=now.year + 1, month=1, day=day, hour=hour, minute=minute, second=0, microsecond=0)
                else:
                    next_run = now.replace(month=now.month + 1, day=day, hour=hour, minute=minute, second=0, microsecond=0)
            else:
                next_run = now.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
            
            return next_run
        
        return None
    
    def update_next_run(self):
        """Update next run time after execution"""
        now = timezone.now()
        
        if self.schedule_type == ScheduleType.ONCE:
            self.next_run = None  # One-time tasks don't run again
            
        elif self.schedule_type == ScheduleType.INTERVAL:
            interval = self.schedule_config.get('interval', 3600)
            self.next_run = now + timedelta(seconds=interval)
            
        elif self.schedule_type == ScheduleType.CRON:
            cron_expression = self.schedule_config.get('cron_expression')
            if cron_expression:
                cron = croniter(cron_expression, now)
                self.next_run = cron.get_next(datetime)
            else:
                self.next_run = None
                
        elif self.schedule_type in [ScheduleType.DAILY, ScheduleType.WEEKLY, ScheduleType.MONTHLY]:
            self.next_run = self._calculate_next_run()
        
        else:
            self.next_run = None
    
    def is_due(self) -> bool:
        """Check if task is due for execution"""
        if not self.enabled or self.next_run is None:
            return False
        
        return timezone.now() >= self.next_run
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'schedule_type': self.schedule_type.value,
            'schedule_config': self.schedule_config,
            'priority': self.priority.value,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'status': self.status.value,
            'run_count': self.run_count,
            'failure_count': self.failure_count,
            'last_error': self.last_error,
            'enabled': self.enabled
        }


class TaskRunner:
    """Task execution runner"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_concurrent_tasks = config.get('max_concurrent_tasks', 10)
        self.default_timeout = config.get('default_timeout', 300)
        self.retry_delay = config.get('retry_delay', 60)
        
    async def execute_task(self, task: Task) -> Dict[str, Any]:
        """Execute a task"""
        if not task.enabled:
            return {
                'success': False,
                'error': 'Task is disabled',
                'task_id': task.id
            }
        
        task.status = TaskStatus.RUNNING
        task.last_run = timezone.now()
        
        try:
            # Execute task with timeout
            if asyncio.iscoroutinefunction(task.func):
                result = await asyncio.wait_for(task.func(**task.metadata), timeout=task.timeout)
            else:
                # Run synchronous function in thread pool
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: task.func(**task.metadata)),
                    timeout=task.timeout
                )
            
            # Task completed successfully
            task.status = TaskStatus.COMPLETED
            task.run_count += 1
            task.failure_count = 0
            task.last_error = None
            
            # Update next run time
            task.update_next_run()
            
            logger.info(f"Task {task.name} ({task.id}) completed successfully")
            
            return {
                'success': True,
                'result': result,
                'task_id': task.id,
                'run_count': task.run_count
            }
            
        except asyncio.TimeoutError:
            task.status = TaskStatus.TIMEOUT
            task.failure_count += 1
            task.last_error = "Task execution timed out"
            
            logger.error(f"Task {task.name} ({task.id}) timed out")
            
            return {
                'success': False,
                'error': 'Task execution timed out',
                'task_id': task.id,
                'timeout': task.timeout
            }
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.failure_count += 1
            task.last_error = str(e)
            
            logger.error(f"Task {task.name} ({task.id}) failed: {e}")
            
            # Check if should retry
            if task.failure_count < task.max_retries:
                task.status = TaskStatus.RETRYING
                task.next_run = timezone.now() + timedelta(seconds=self.retry_delay * task.failure_count)
                
                logger.info(f"Task {task.name} ({task.id}) will retry in {self.retry_delay * task.failure_count} seconds")
            
            return {
                'success': False,
                'error': 'Operation failed',
                'task_id': task.id,
                'failure_count': task.failure_count
            }


class TaskScheduler:
    """Main task scheduler system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tasks = {}
        self.task_runner = TaskRunner(config.get('runner', {}))
        self.enabled = config.get('enabled', True)
        self.check_interval = config.get('check_interval', 60)  # seconds
        self.max_tasks = config.get('max_tasks', 1000)
        self.running = False
        self.scheduler_thread = None
        self.execution_semaphore = asyncio.Semaphore(config.get('max_concurrent_tasks', 10))
        
        # Task statistics
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'running_tasks': 0,
            'pending_tasks': 0
        }
        
    def add_task(self, name: str, func: Callable, schedule_type: ScheduleType,
                 schedule_config: Dict[str, Any], priority: TaskPriority = TaskPriority.NORMAL,
                 max_retries: int = 3, timeout: int = 300, metadata: Dict[str, Any] = None) -> Task:
        """Add a new task to the scheduler"""
        if len(self.tasks) >= self.max_tasks:
            raise Exception(f"Maximum tasks reached: {self.max_tasks}")
        
        task = Task(
            name=name,
            func=func,
            schedule_type=schedule_type,
            schedule_config=schedule_config,
            priority=priority,
            max_retries=max_retries,
            timeout=timeout,
            metadata=metadata or {}
        )
        
        self.tasks[task.id] = task
        self.stats['total_tasks'] += 1
        
        logger.info(f"Added task {task.name} ({task.id}) with schedule type {schedule_type.value}")
        
        return task
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the scheduler"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            logger.info(f"Removed task {task_id}")
            return True
        return False
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return self.tasks.get(task_id)
    
    def get_tasks(self, status: TaskStatus = None, enabled_only: bool = False) -> List[Task]:
        """Get tasks with optional filters"""
        tasks = list(self.tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        if enabled_only:
            tasks = [t for t in tasks if t.enabled]
        
        return sorted(tasks, key=lambda x: (x.priority.value, x.next_run or timezone.now()), reverse=True)
    
    def enable_task(self, task_id: str) -> bool:
        """Enable a task"""
        task = self.tasks.get(task_id)
        if task:
            task.enabled = True
            logger.info(f"Enabled task {task_id}")
            return True
        return False
    
    def disable_task(self, task_id: str) -> bool:
        """Disable a task"""
        task = self.tasks.get(task_id)
        if task:
            task.enabled = False
            task.status = TaskStatus.CANCELLED
            logger.info(f"Disabled task {task_id}")
            return True
        return False
    
    async def run_task(self, task_id: str) -> Dict[str, Any]:
        """Run a specific task immediately"""
        task = self.tasks.get(task_id)
        if not task:
            return {
                'success': False,
                'error': f'Task {task_id} not found'
            }
        
        async with self.execution_semaphore:
            return await self.task_runner.execute_task(task)
    
    def start_scheduler(self):
        """Start the task scheduler"""
        if self.running:
            logger.warning("Task scheduler is already running")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("Task scheduler started")
    
    def stop_scheduler(self):
        """Stop the task scheduler"""
        self.running = False
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        logger.info("Task scheduler stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                # Get due tasks
                due_tasks = [task for task in self.tasks.values() if task.is_due()]
                
                # Sort by priority
                due_tasks.sort(key=lambda x: x.priority.value, reverse=True)
                
                # Execute due tasks
                for task in due_tasks:
                    if not self.running:
                        break
                    
                    try:
                        # Run task in asyncio event loop
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        try:
                            loop.run_until_complete(self.run_task(task.id))
                        finally:
                            loop.close()
                            
                    except Exception as e:
                        logger.error(f"Error executing task {task.id}: {e}")
                
                # Update statistics
                self._update_statistics()
                
                # Wait for next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                time.sleep(self.check_interval)
    
    def _update_statistics(self):
        """Update task statistics"""
        tasks = list(self.tasks.values())
        
        self.stats.update({
            'total_tasks': len(tasks),
            'completed_tasks': len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
            'failed_tasks': len([t for t in tasks if t.status == TaskStatus.FAILED]),
            'running_tasks': len([t for t in tasks if t.status == TaskStatus.RUNNING]),
            'pending_tasks': len([t for t in tasks if t.status == TaskStatus.PENDING]),
            'due_tasks': len([t for t in tasks if t.is_due()])
        })
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get scheduler status"""
        self._update_statistics()
        
        return {
            'scheduler_enabled': self.enabled,
            'scheduler_running': self.running,
            'check_interval': self.check_interval,
            'max_tasks': self.max_tasks,
            'max_concurrent_tasks': self.task_runner.max_concurrent_tasks,
            'statistics': self.stats.copy(),
            'due_tasks_count': len([t for t in self.tasks.values() if t.is_due()]),
            'next_runs': [
                {
                    'task_id': task.id,
                    'name': task.name,
                    'next_run': task.next_run.isoformat() if task.next_run else None,
                    'priority': task.priority.value
                }
                for task in sorted(
                    [t for t in self.tasks.values() if t.next_run],
                    key=lambda x: x.next_run or timezone.now()
                )[:10]
            ],
            'timestamp': timezone.now().isoformat()
        }


class CronJobManager:
    """Cron job management utilities"""
    
    @staticmethod
    def create_daily_task(name: str, func: Callable, hour: int = 0, minute: int = 0,
                         **kwargs) -> Task:
        """Create a daily scheduled task"""
        return Task(
            name=name,
            func=func,
            schedule_type=ScheduleType.DAILY,
            schedule_config={'hour': hour, 'minute': minute},
            **kwargs
        )
    
    @staticmethod
    def create_weekly_task(name: str, func: Callable, day_of_week: int = 0,
                          hour: int = 0, minute: int = 0, **kwargs) -> Task:
        """Create a weekly scheduled task"""
        return Task(
            name=name,
            func=func,
            schedule_type=ScheduleType.WEEKLY,
            schedule_config={'day_of_week': day_of_week, 'hour': hour, 'minute': minute},
            **kwargs
        )
    
    @staticmethod
    def create_monthly_task(name: str, func: Callable, day: int = 1,
                           hour: int = 0, minute: int = 0, **kwargs) -> Task:
        """Create a monthly scheduled task"""
        return Task(
            name=name,
            func=func,
            schedule_type=ScheduleType.MONTHLY,
            schedule_config={'day': day, 'hour': hour, 'minute': minute},
            **kwargs
        )
    
    @staticmethod
    def create_interval_task(name: str, func: Callable, interval_seconds: int,
                            **kwargs) -> Task:
        """Create an interval-based task"""
        return Task(
            name=name,
            func=func,
            schedule_type=ScheduleType.INTERVAL,
            schedule_config={'interval': interval_seconds},
            **kwargs
        )
    
    @staticmethod
    def create_cron_task(name: str, func: Callable, cron_expression: str,
                        **kwargs) -> Task:
        """Create a cron-based task"""
        return Task(
            name=name,
            func=func,
            schedule_type=ScheduleType.CRON,
            schedule_config={'cron_expression': cron_expression},
            **kwargs
        )
    
    @staticmethod
    def create_one_time_task(name: str, func: Callable, run_at: datetime,
                            **kwargs) -> Task:
        """Create a one-time task"""
        return Task(
            name=name,
            func=func,
            schedule_type=ScheduleType.ONCE,
            schedule_config={'run_at': run_at},
            **kwargs
        )


# Global task scheduler
task_scheduler = None


def get_task_scheduler() -> Optional[TaskScheduler]:
    """Get the global task scheduler"""
    return task_scheduler


def initialize_task_scheduler():
    """Initialize task scheduler from settings"""
    from django.conf import settings
    
    global task_scheduler
    
    config = getattr(settings, 'TASK_SCHEDULER_CONFIG', {
        'enabled': True,
        'check_interval': 60,
        'max_tasks': 1000,
        'max_concurrent_tasks': 10,
        'runner': {
            'max_concurrent_tasks': 10,
            'default_timeout': 300,
            'retry_delay': 60
        }
    })
    
    try:
        task_scheduler = TaskScheduler(config)
        
        # Start scheduler if auto_start is enabled
        # Opt-in: TASK_SCHEDULER_CONFIG = {'auto_start': True, ...}. An in-process scheduler runs in
        # EVERY worker, so tasks would execute N times; prefer Celery beat (celery_beat_config.py).
        if config.get('auto_start', False):
            task_scheduler.start_scheduler()
        
        logger.info("Task scheduler initialized")
        
    except Exception as e:
        logger.error(f"Error initializing task scheduler: {e}")


# Decorator for scheduled tasks
def scheduled_task(schedule_type: ScheduleType, schedule_config: Dict[str, Any],
                  priority: TaskPriority = TaskPriority.NORMAL, max_retries: int = 3,
                  timeout: int = 300, name: str = None):
    """Decorator to register a function as a scheduled task"""
    def decorator(func):
        task_name = name or f"{func.__module__}.{func.__name__}"
        
        # Create task when scheduler is available
        def register_task():
            scheduler = get_task_scheduler()
            if scheduler:
                scheduler.add_task(
                    name=task_name,
                    func=func,
                    schedule_type=schedule_type,
                    schedule_config=schedule_config,
                    priority=priority,
                    max_retries=max_retries,
                    timeout=timeout
                )
        
        # Try to register immediately
        try:
            register_task()
        except:
            # Register later when scheduler is available
            import atexit
            atexit.register(register_task)
        
        return func
    
    return decorator


# Convenience decorators
def daily_task(hour: int = 0, minute: int = 0, **kwargs):
    """Decorator for daily tasks"""
    return scheduled_task(ScheduleType.DAILY, {'hour': hour, 'minute': minute}, **kwargs)


def weekly_task(day_of_week: int = 0, hour: int = 0, minute: int = 0, **kwargs):
    """Decorator for weekly tasks"""
    return scheduled_task(ScheduleType.WEEKLY, {'day_of_week': day_of_week, 'hour': hour, 'minute': minute}, **kwargs)


def monthly_task(day: int = 1, hour: int = 0, minute: int = 0, **kwargs):
    """Decorator for monthly tasks"""
    return scheduled_task(ScheduleType.MONTHLY, {'day': day, 'hour': hour, 'minute': minute}, **kwargs)


def interval_task(interval_seconds: int, **kwargs):
    """Decorator for interval tasks"""
    return scheduled_task(ScheduleType.INTERVAL, {'interval': interval_seconds}, **kwargs)


def cron_task(cron_expression: str, **kwargs):
    """Decorator for cron tasks"""
    return scheduled_task(ScheduleType.CRON, {'cron_expression': cron_expression}, **kwargs)


def one_time_task(run_at: datetime, **kwargs):
    """Decorator for one-time tasks"""
    return scheduled_task(ScheduleType.ONCE, {'run_at': run_at}, **kwargs)


# Initialize on module import
try:
    initialize_task_scheduler()
except Exception as e:
    logger.error(f"Error initializing task scheduler: {e}")
