# api/cms/services_new/TaskManagementService.py
"""
Service layer for Task Management and Scheduling
Provides comprehensive task scheduling, execution, and monitoring capabilities
"""
from django.db import models
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.contrib.auth import get_user_model

from ..models_new.task_management import (
    TaskSchedule, TaskExecution, TaskQueue, TaskLock
)

logger = logging.getLogger(__name__)
User = get_user_model()


class TaskManagementService:
    """
    Main service for task management and scheduling
    """
    
    def __init__(self):
        self.cache_timeout = 600  # 10 minutes
    
    def get_ready_tasks(self) -> List[TaskSchedule]:
        """Get tasks that are ready to run"""
        cache_key = "ready_tasks"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        ready_tasks = TaskSchedule.objects.filter(
            status='active'
        ).filter(
            Q(next_run__lte=timezone.now()) | Q(next_run__isnull=True)
        ).select_related('created_by').prefetch_related('depends_on')
        
        # Filter by dependencies
        actually_ready = []
        for task in ready_tasks:
            if task.is_ready_to_run():
                actually_ready.append(task)
        
        cache.set(cache_key, actually_ready, self.cache_timeout)
        return actually_ready
    
    def schedule_task(self, task_data: Dict[str, Any]) -> TaskSchedule:
        """Schedule a new task"""
        task = TaskSchedule.objects.create(**task_data)
        
        # Calculate next run time
        task.next_run = task.calculate_next_run()
        task.save(update_fields=['next_run'])
        
        # Clear cache
        cache.delete("ready_tasks")
        
        logger.info(f"Task scheduled: {task.name}")
        return task
    
    def execute_task(self, schedule_uuid: str, worker_id: str = None) -> TaskExecution:
        """Execute a scheduled task"""
        try:
            schedule = TaskSchedule.objects.get(uuid=schedule_uuid)
            
            if not schedule.is_ready_to_run():
                raise ValueError("Task is not ready to run")
            
            # Create execution record
            execution = TaskExecution.objects.create(
                schedule=schedule,
                status='running',
                worker_id=worker_id or 'unknown'
            )
            
            logger.info(f"Task execution started: {schedule.name} ({execution.uuid})")
            return execution
            
        except TaskSchedule.DoesNotExist:
            raise ValueError("Task schedule not found")
    
    def complete_execution(self, execution_uuid: str, result: Dict = None, 
                       error_message: str = None) -> TaskExecution:
        """Mark a task execution as completed"""
        try:
            execution = TaskExecution.objects.get(uuid=execution_uuid)
            
            if result:
                execution.result = result
                execution.status = 'success'
            elif error_message:
                execution.error_message = error_message
                execution.status = 'failure'
            
            execution.completed_at = timezone.now()
            execution.save()
            
            # Update schedule statistics
            execution.schedule.update_statistics(
                runtime_seconds=execution.runtime_seconds,
                success=execution.status == 'success'
            )
            
            logger.info(f"Task execution completed: {execution.uuid} ({execution.status})")
            return execution
            
        except TaskExecution.DoesNotExist:
            raise ValueError("Task execution not found")
    
    def queue_task(self, task_data: Dict[str, Any], priority: str = 'normal') -> TaskQueue:
        """Queue a background task"""
        task = TaskQueue.objects.create(
            task_name=task_data.get('task_name', 'unknown'),
            task_path=task_data.get('task_path', ''),
            task_args=task_data.get('args', []),
            task_kwargs=task_data.get('kwargs', {}),
            priority=priority,
            queue_name=task_data.get('queue_name', 'default')
        )
        
        logger.info(f"Task queued: {task.task_name} ({task.uuid})")
        return task
    
    def process_queue(self, queue_name: str = 'default', limit: int = 10) -> List[TaskQueue]:
        """Process tasks from queue"""
        tasks = TaskQueue.objects.filter(
            status='queued',
            queue_name=queue_name,
            next_retry_at__lte=timezone.now()
        ).order_by('priority', 'queued_at')[:limit]
        
        processed_tasks = []
        for task in tasks:
            # Mark as processing
            task.status = 'processing'
            task.started_at = timezone.now()
            task.save(update_fields=['status', 'started_at'])
            processed_tasks.append(task)
        
        logger.info(f"Processed {len(processed_tasks)} tasks from queue: {queue_name}")
        return processed_tasks
    
    def acquire_lock(self, lock_key: str, owner: str, timeout_seconds: int = 3600) -> Optional[TaskLock]:
        """Acquire a distributed lock"""
        created, lock = TaskLock.acquire(lock_key, owner, timeout_seconds)
        
        if created:
            logger.info(f"Lock acquired: {lock_key} by {owner}")
            return lock
        else:
            logger.warning(f"Lock acquisition failed: {lock_key} by {owner}")
            return None
    
    def release_lock(self, lock_key: str, owner: str) -> bool:
        """Release a distributed lock"""
        released = TaskLock.release(lock_key, owner)
        
        if released:
            logger.info(f"Lock released: {lock_key} by {owner}")
        else:
            logger.warning(f"Lock release failed: {lock_key} by {owner}")
        
        return released
    
    def get_task_statistics(self, schedule_uuid: str = None) -> Dict[str, Any]:
        """Get comprehensive task statistics"""
        if schedule_uuid:
            # Statistics for specific task
            try:
                schedule = TaskSchedule.objects.get(uuid=schedule_uuid)
                executions = schedule.executions.all()
                
                return {
                    'task': {
                        'uuid': str(schedule.uuid),
                        'name': schedule.name,
                        'frequency': schedule.frequency,
                        'status': schedule.status,
                        'total_runs': schedule.total_runs,
                        'success_rate': (schedule.successful_runs / schedule.total_runs * 100) if schedule.total_runs > 0 else 0
                    },
                    'executions': {
                        'total': executions.count(),
                        'success_rate': round(
                            executions.filter(status='success').count() /
                            max(executions.count(), 1) * 100, 2
                        ),
                        'by_status': list(
                            executions.values('status')
                            .annotate(count=Count('id'))
                            .order_by('status')
                        ),
                        'avg_runtime': float(executions.aggregate(
                            avg=Avg('runtime_seconds')
                        )['avg'] or 0),
                        'last_24h': executions.filter(
                            started_at__gte=timezone.now() - timedelta(hours=24)
                        ).count()
                    }
                }
            except TaskSchedule.DoesNotExist:
                return {'error': 'Task not found'}
        
        else:
            # Overall system statistics
            schedules = TaskSchedule.objects.all()
            executions = TaskExecution.objects.all()
            queues = TaskQueue.objects.all()
            locks = TaskLock.objects.all()
            
            return {
                'overview': {
                    'total_schedules': schedules.count(),
                    'active_schedules': schedules.filter(status='active').count(),
                    'total_executions': executions.count(),
                    'total_queued': queues.filter(status='queued').count(),
                    'active_locks': locks.filter(expires_at__gt=timezone.now()).count()
                },
                'schedules': {
                    'by_frequency': list(
                        schedules.values('frequency')
                        .annotate(count=Count('id'))
                        .order_by('frequency')
                    ),
                    'by_status': list(
                        schedules.values('status')
                        .annotate(count=Count('id'))
                        .order_by('status')
                    )
                },
                'executions': {
                    'by_status': list(
                        executions.values('status')
                        .annotate(count=Count('id'))
                        .order_by('status')
                    ),
                    'avg_runtime': float(executions.aggregate(
                        avg=Avg('runtime_seconds')
                    )['avg'] or 0),
                    'success_rate': round(
                        executions.filter(status='success').count() /
                        max(executions.count(), 1) * 100, 2
                    ),
                    'total_executions': executions.count(),
                    'success_rate': self._calculate_success_rate(executions)
                },
                'queues': {
                    'by_status': list(
                        queues.values('status')
                        .annotate(count=Count('id'))
                        .order_by('status')
                    ),
                    'by_priority': list(
                        queues.values('priority')
                        .annotate(count=Count('id'))
                        .order_by('priority')
                    )
                }
            }
    
    def _calculate_success_rate(self, executions) -> float:
        """Calculate success rate for executions"""
        total = executions.count()
        if total == 0:
            return 0.0
        
        successful = executions.filter(status='success').count()
        return round((successful / total * 100), 2)
    
    def cleanup_expired_locks(self) -> int:
        """Clean up expired locks"""
        return TaskLock.cleanup_expired()
    
    def reschedule_failed_tasks(self) -> int:
        """Reschedule tasks that have failed but can be retried"""
        retry_count = 0
        
        for task in TaskQueue.objects.filter(
            status='failed',
            retry_count__lt=models.F('max_retries')
        ):
            if task.schedule_retry(delay_seconds=300):  # 5 minute delay
                retry_count += 1
        
        return retry_count


class TaskScheduler:
    """
    Advanced task scheduling utilities
    """
    
    @staticmethod
    def parse_cron_expression(cron_expr: str) -> Dict[str, Any]:
        """Parse cron expression into components"""
        # Basic cron parsing - would need a more sophisticated implementation
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError("Invalid cron expression")
        
        return {
            'minute': parts[0],
            'hour': parts[1],
            'day': parts[2],
            'month': parts[3],
            'day_of_week': parts[4]
        }
    
    @staticmethod
    def get_next_run_time(schedule: TaskSchedule) -> Optional[datetime]:
        """Calculate next run time for a schedule"""
        if schedule.frequency == 'once':
            return schedule.start_time if schedule.start_time > timezone.now() else None
        
        elif schedule.frequency == 'minutely':
            return timezone.now() + timedelta(minutes=1)
        
        elif schedule.frequency == 'hourly':
            return timezone.now() + timedelta(hours=1)
        
        elif schedule.frequency == 'daily':
            return timezone.now() + timedelta(days=1)
        
        elif schedule.frequency == 'weekly':
            return timezone.now() + timedelta(weeks=1)
        
        elif schedule.frequency == 'monthly':
            return timezone.now() + timedelta(days=30)
        
        elif schedule.frequency == 'custom' and schedule.cron_expression:
            # Would need full cron parser implementation
            return timezone.now() + timedelta(hours=1)  # Placeholder
        
        return None


class TaskMonitor:
    """
    Task monitoring and alerting
    """
    
    def __init__(self):
        self.alert_thresholds = {
            'failure_rate': 20,  # Alert if failure rate > 20%
            'avg_runtime': 3600,  # Alert if avg runtime > 1 hour
            'queue_size': 1000,  # Alert if queue size > 1000
        }
    
    def check_system_health(self) -> Dict[str, Any]:
        """Check overall system health"""
        service = TaskManagementService()
        stats = service.get_task_statistics()
        
        health_status = 'healthy'
        alerts = []
        
        # Check failure rate
        if stats['executions']['success_rate'] > self.alert_thresholds['failure_rate']:
            health_status = 'warning'
            alerts.append({
                'type': 'high_failure_rate',
                'message': f"Failure rate: {stats['executions']['success_rate']}%"
            })
        
        # Check average runtime
        if stats['executions']['avg_runtime'] > self.alert_thresholds['avg_runtime']:
            health_status = 'warning'
            alerts.append({
                'type': 'high_runtime',
                'message': f"Average runtime: {stats['executions']['avg_runtime']}s"
            })
        
        # Check queue size
        queued_count = stats['queues']['by_status'][0]['count'] if stats['queues']['by_status'] else 0
        if queued_count > self.alert_thresholds['queue_size']:
            health_status = 'critical'
            alerts.append({
                'type': 'large_queue',
                'message': f"Queue size: {queued_count}"
            })
        
        return {
            'status': health_status,
            'alerts': alerts,
            'timestamp': timezone.now().isoformat(),
            'statistics': stats
        }
    
    def get_task_performance_metrics(self, task_uuid: str) -> Dict[str, Any]:
        """Get detailed performance metrics for a specific task"""
        try:
            schedule = TaskSchedule.objects.get(uuid=task_uuid)
            executions = schedule.executions.all().order_by('-started_at')[:100]  # Last 100 executions
            
            if not executions.exists():
                return {'error': 'No executions found'}
            
            # Calculate metrics
            runtimes = [e.runtime_seconds for e in executions if e.runtime_seconds]
            success_count = executions.filter(status='success').count()
            
            return {
                'task_info': {
                    'uuid': str(schedule.uuid),
                    'name': schedule.name,
                    'frequency': schedule.frequency
                },
                'performance': {
                    'total_executions': executions.count(),
                    'success_count': success_count,
                    'success_rate': round((success_count / executions.count() * 100), 2),
                    'avg_runtime': float(sum(runtimes) / len(runtimes)) if runtimes else 0,
                    'min_runtime': float(min(runtimes)) if runtimes else 0,
                    'max_runtime': float(max(runtimes)) if runtimes else 0,
                    'last_execution': executions.first().started_at.isoformat() if executions.first() else None
                },
                'recent_trends': {
                    'last_24h': executions.filter(
                        started_at__gte=timezone.now() - timedelta(hours=24)
                    ).count(),
                    'last_7d': executions.filter(
                        started_at__gte=timezone.now() - timedelta(days=7)
                    ).count(),
                    'last_30d': executions.filter(
                        started_at__gte=timezone.now() - timedelta(days=30)
                    ).count()
                }
            }
            
        except TaskSchedule.DoesNotExist:
            return {'error': 'Task not found'}
