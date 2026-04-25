# earning_backend/api/notifications/tasks/batch_send_tasks.py
"""
Batch send processor tasks — process NotificationBatch records,
split large recipient lists into sub-tasks, and track overall progress.
"""
import logging
from datetime import timedelta
from typing import List

from celery import shared_task, group, chord
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)

# Max users per Celery sub-task chunk
CHUNK_SIZE = 100


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue='notifications_batch',
    name='notifications.process_batch',
)
def process_batch_task(self, batch_id: int):
    """
    Process a NotificationBatch — evaluates its segment, splits into
    chunks, and dispatches send sub-tasks via Celery group.

    Called by the admin UI or campaign_tasks when a batch is created.
    """
    from notifications.models.schedule import NotificationBatch
    from notifications.services.SegmentService import segment_service
    from notifications.services.OptOutService import opt_out_service
    from notifications.services.FatigueService import fatigue_service

    try:
        batch = NotificationBatch.objects.select_related(
            'template', 'segment'
        ).get(pk=batch_id)

        if batch.status not in ('draft', 'queued'):
            return {
                'success': False,
                'batch_id': batch_id,
                'error': f'Cannot process batch in status: {batch.status}',
            }

        batch.start()

        # Get target users via segment
        user_ids: List[int] = []
        if batch.segment:
            user_ids = segment_service.evaluate_segment(batch.segment)
        else:
            # No segment — cannot determine recipients
            batch.status = 'failed'
            batch.save(update_fields=['status', 'updated_at'])
            return {
                'success': False,
                'batch_id': batch_id,
                'error': 'No segment assigned to batch',
            }

        # Determine channel from template
        channel = 'in_app'
        priority = 'medium'
        if batch.template:
            channel = getattr(batch.template, 'channel', 'in_app') or 'in_app'
            priority = getattr(batch.template, 'priority', 'medium') or 'medium'

        # Filter opted-out users
        user_ids = opt_out_service.filter_opted_out_users(user_ids, channel)
        # Filter fatigued users
        user_ids = fatigue_service.filter_fatigued_users(user_ids, priority)

        batch.total_count = len(user_ids)
        batch.save(update_fields=['total_count', 'updated_at'])

        if not user_ids:
            batch.complete()
            return {
                'success': True,
                'batch_id': batch_id,
                'total': 0,
                'message': 'No eligible users after opt-out and fatigue filtering',
            }

        # Split into chunks and dispatch
        chunks = [user_ids[i: i + CHUNK_SIZE] for i in range(0, len(user_ids), CHUNK_SIZE)]
        template_id = batch.template.pk if batch.template else None
        context = batch.context or {}

        sub_tasks = group(
            send_batch_chunk_task.s(
                batch_id=batch_id,
                chunk_user_ids=chunk,
                template_id=template_id,
                context=context,
                channel=channel,
                priority=priority,
            )
            for chunk in chunks
        )
        sub_tasks.apply_async()

        logger.info(
            f'process_batch_task #{batch_id}: '
            f'total={len(user_ids)} chunks={len(chunks)}'
        )
        return {
            'success': True,
            'batch_id': batch_id,
            'total_users': len(user_ids),
            'chunks': len(chunks),
        }

    except NotificationBatch.DoesNotExist:
        logger.error(f'process_batch_task: batch #{batch_id} not found')
        return {'success': False, 'batch_id': batch_id, 'error': 'Batch not found'}
    except Exception as exc:
        logger.error(f'process_batch_task #{batch_id}: {exc}')
        try:
            from notifications.models.schedule import NotificationBatch
            NotificationBatch.objects.filter(pk=batch_id).update(
                status='failed', updated_at=timezone.now()
            )
        except Exception:
            pass
        try:
            self.retry(exc=exc)
        except Exception:
            return {'success': False, 'batch_id': batch_id, 'error': str(exc)}


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue='notifications_batch',
    name='notifications.send_batch_chunk',
)
def send_batch_chunk_task(
    self,
    batch_id: int,
    chunk_user_ids: List[int],
    template_id: int,
    context: dict,
    channel: str = 'in_app',
    priority: str = 'medium',
):
    """
    Send notifications to a single chunk of users for a batch.
    Updates batch progress counters after each chunk completes.
    """
    from django.contrib.auth import get_user_model
    from notifications.models.schedule import NotificationBatch
    from notifications.services import notification_service
    from notifications.services.FatigueService import fatigue_service

    User = get_user_model()
    sent = 0
    failed = 0
    skipped = 0

    try:
        batch = NotificationBatch.objects.get(pk=batch_id)
        if batch.status == 'cancelled':
            return {'success': False, 'batch_id': batch_id, 'error': 'Batch cancelled'}

        template_name = None
        if template_id:
            from notifications.models import NotificationTemplate
            try:
                tpl = NotificationTemplate.objects.get(pk=template_id)
                template_name = tpl.name
            except NotificationTemplate.DoesNotExist:
                pass

        users = User.objects.filter(pk__in=chunk_user_ids, is_active=True)

        for user in users:
            try:
                if template_name:
                    notification = notification_service.create_from_template(
                        template_name=template_name,
                        user=user,
                        context=context,
                    )
                else:
                    skipped += 1
                    continue

                if notification:
                    success = notification_service.send_notification(notification)
                    if success:
                        sent += 1
                        fatigue_service.record_send(user, priority=priority)
                    else:
                        failed += 1
                else:
                    failed += 1

            except Exception as exc:
                logger.warning(f'send_batch_chunk_task user #{user.pk}: {exc}')
                failed += 1

        # Update batch counters atomically
        from django.db.models import F
        NotificationBatch.objects.filter(pk=batch_id).update(
            sent_count=F('sent_count') + sent,
            failed_count=F('failed_count') + failed,
            skipped_count=F('skipped_count') + skipped,
            updated_at=timezone.now(),
        )

        return {
            'success': True,
            'batch_id': batch_id,
            'chunk_size': len(chunk_user_ids),
            'sent': sent,
            'failed': failed,
            'skipped': skipped,
        }

    except NotificationBatch.DoesNotExist:
        return {'success': False, 'batch_id': batch_id, 'error': 'Batch not found'}
    except Exception as exc:
        logger.error(f'send_batch_chunk_task #{batch_id}: {exc}')
        try:
            self.retry(exc=exc)
        except Exception:
            return {'success': False, 'batch_id': batch_id, 'error': str(exc)}


@shared_task(
    queue='notifications_batch',
    name='notifications.finalize_batch',
)
def finalize_batch_task(batch_id: int):
    """
    Mark a batch as completed after all chunks have been processed.
    Called after the Celery chord of chunk tasks completes.
    """
    from notifications.models.schedule import NotificationBatch

    try:
        batch = NotificationBatch.objects.get(pk=batch_id)
        if batch.status == 'processing':
            batch.complete()
        logger.info(
            f'finalize_batch_task #{batch_id}: '
            f'status={batch.status} sent={batch.sent_count} failed={batch.failed_count}'
        )
        return {
            'success': True,
            'batch_id': batch_id,
            'status': batch.status,
            'sent_count': batch.sent_count,
            'failed_count': batch.failed_count,
        }
    except NotificationBatch.DoesNotExist:
        return {'success': False, 'batch_id': batch_id, 'error': 'Batch not found'}
    except Exception as exc:
        logger.error(f'finalize_batch_task #{batch_id}: {exc}')
        return {'success': False, 'batch_id': batch_id, 'error': str(exc)}


@shared_task(
    queue='notifications_batch',
    name='notifications.cancel_batch',
)
def cancel_batch_task(batch_id: int):
    """Cancel a batch (marks it cancelled so chunk tasks check and skip)."""
    from notifications.models.schedule import NotificationBatch

    try:
        updated = NotificationBatch.objects.filter(
            pk=batch_id,
            status__in=('draft', 'queued', 'processing'),
        ).update(status='cancelled', updated_at=timezone.now())
        return {'success': bool(updated), 'batch_id': batch_id}
    except Exception as exc:
        return {'success': False, 'batch_id': batch_id, 'error': str(exc)}
