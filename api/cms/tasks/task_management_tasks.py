# api/cms/tasks/task_management_tasks.py
"""Background tasks for task management system"""
import logging
from celery import shared_task

from api.cms.services_new.TaskManagementService import TaskManagementService

logger = logging.getLogger(__name__)


@shared_task(name='cms.tasks.process_ready_tasks', bind=True, max_retries=3)
def process_ready_tasks(self):
    """Process tasks that are ready to run"""
    try:
        service = TaskManagementService()
        ready_tasks = service.get_ready_tasks()
        
        processed_count = 0
        for task in ready_tasks:
            try:
                # Execute the task
                execution = service.execute_task(str(task.uuid), worker_id=f"worker_{self.request.id}")
                processed_count += 1
                logger.info(f"Task {task.name} executed successfully: {execution.uuid}")
            except Exception as e:
                logger.error(f"Failed to execute task {task.name}: {e}")
        
        return {
            'status': 'success',
            'processed_count': processed_count,
            'message': f'Processed {processed_count} ready tasks'
        }
    except Exception as exc:
        logger.error(f"Task processing failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name='cms.tasks.cleanup_expired_locks', bind=True, max_retries=2)
def cleanup_expired_locks(self):
    """Clean up expired task locks"""
    try:
        service = TaskManagementService()
        cleaned_count = service.cleanup_expired_locks()
        
        logger.info(f"Cleaned up {cleaned_count} expired locks")
        return {
            'status': 'success',
            'cleaned_count': cleaned_count,
            'message': f'Cleaned {cleaned_count} expired locks'
        }
    except Exception as exc:
        logger.error(f"Lock cleanup failed: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='cms.tasks.update_task_statistics', bind=True, max_retries=2)
def update_task_statistics(self):
    """Update statistics for all task schedules"""
    try:
        service = TaskManagementService()
        schedules = service.get_all_schedules()
        
        updated_count = 0
        for schedule in schedules:
            try:
                schedule.update_statistics()
                updated_count += 1
            except Exception as e:
                logger.error(f"Failed to update statistics for {schedule.name}: {e}")
        
        logger.info(f"Updated statistics for {updated_count} task schedules")
        return {
            'status': 'success',
            'updated_count': updated_count,
            'message': f'Updated statistics for {updated_count} schedules'
        }
    except Exception as exc:
        logger.error(f"Task statistics update failed: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='cms.tasks.process_task_queue', bind=True, max_retries=3)
def process_task_queue(self, queue_name='default', limit=10):
    """Process tasks from a specific queue"""
    try:
        service = TaskManagementService()
        processed_tasks = service.process_queue(queue_name, limit)
        
        processed_count = len(processed_tasks)
        logger.info(f"Processed {processed_count} tasks from queue: {queue_name}")
        
        return {
            'status': 'success',
            'processed_count': processed_count,
            'queue_name': queue_name,
            'message': f'Processed {processed_count} tasks from {queue_name}'
        }
    except Exception as exc:
        logger.error(f"Queue processing failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name='cms.tasks.monitor_task_performance', bind=True, max_retries=2)
def monitor_task_performance(self):
    """Monitor task performance and send alerts"""
    try:
        service = TaskManagementService()
        monitor = TaskMonitor()
        
        health_status = monitor.check_system_health()
        
        if health_status['status'] != 'healthy':
            # Send notification to admins
            from api.cms.tasks.notification_tasks import send_notification
            for admin_email in ['admin@example.com']:  # Would get from settings
                send_notification(
                    user_id=None,  # System notification
                    notification_type='system_alert',
                    title='Task System Alert',
                    message=f"Task system health: {health_status['status']}",
                    metadata=health_status
                )
        
        return {
            'status': 'success',
            'health_status': health_status,
            'message': f"Health check completed: {health_status['status']}"
        }
    except Exception as exc:
        logger.error(f"Task monitoring failed: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='cms.tasks.archive_old_executions', bind=True, max_retries=2)
def archive_old_executions(self, days=90):
    """Archive old task execution records"""
    try:
        from django.utils import timezone
        from api.cms.models_new.task_management import TaskExecution
        
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        old_executions = TaskExecution.objects.filter(
            started_at__lt=cutoff_date
        )
        
        # Archive logic would depend on archival system
        # For now, just log the count
        archived_count = old_executions.count()
        
        logger.info(f"Found {archived_count} old task executions to archive")
        return {
            'status': 'success',
            'archived_count': archived_count,
            'days': days,
            'message': f'Identified {archived_count} executions older than {days} days'
        }
    except Exception as exc:
        logger.error(f"Task archiving failed: {exc}")
        raise self.retry(exc=exc, countdown=600)
