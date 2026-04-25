# earning_backend/api/notifications/tasks/unsubscribe_tasks.py
"""
Unsubscribe tasks — process opt-out requests, handle unsubscribe link clicks,
sync opt-outs from provider webhook data, and run bulk unsubscribe jobs.
"""
import logging
from datetime import timedelta
from typing import List

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue='notifications_optout',
    name='notifications.process_unsubscribe_request',
)
def process_unsubscribe_request_task(
    self,
    user_id: int,
    channel: str,
    reason: str = 'user_request',
    notification_id: int = None,
    notes: str = '',
):
    """
    Process a single user unsubscribe request.

    Args:
        user_id:         User PK.
        channel:         Channel to opt out of ('email', 'sms', 'push', 'all', etc.).
        reason:          Opt-out reason code.
        notification_id: Notification that triggered the opt-out (if any).
        notes:           Free-text reason from the user.
    """
    from django.contrib.auth import get_user_model
    from notifications.services.OptOutService import opt_out_service

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
        triggered_by = None

        if notification_id:
            from notifications.models import Notification
            try:
                triggered_by = Notification.objects.get(pk=notification_id)
            except Notification.DoesNotExist:
                pass

        result = opt_out_service.opt_out(
            user=user,
            channel=channel,
            reason=reason,
            notes=notes,
            triggered_by=triggered_by,
            actioned_by=user,
        )

        logger.info(
            f'process_unsubscribe_request_task: '
            f'user #{user_id} opted out of {channel} (reason={reason})'
        )
        return result

    except User.DoesNotExist:
        logger.warning(f'process_unsubscribe_request_task: user #{user_id} not found')
        return {'success': False, 'user_id': user_id, 'error': 'User not found'}
    except Exception as exc:
        logger.error(f'process_unsubscribe_request_task user #{user_id}: {exc}')
        try:
            self.retry(exc=exc)
        except Exception:
            return {'success': False, 'user_id': user_id, 'error': str(exc)}


@shared_task(
    queue='notifications_optout',
    name='notifications.process_bulk_unsubscribe',
)
def process_bulk_unsubscribe_task(
    user_ids: List[int],
    channel: str,
    reason: str = 'admin_action',
):
    """
    Opt-out multiple users from a channel in a single task.
    Used for GDPR bulk opt-outs or admin bulk unsubscribe operations.

    Args:
        user_ids: List of user PKs.
        channel:  Channel to opt out of.
        reason:   Reason code.
    """
    from notifications.services.OptOutService import opt_out_service

    result = opt_out_service.bulk_opt_out(
        user_ids=user_ids,
        channel=channel,
        reason=reason,
    )
    logger.info(
        f'process_bulk_unsubscribe_task: '
        f'channel={channel} opted_out={result.get("opted_out_count")} '
        f'errors={result.get("errors")}'
    )
    return result


@shared_task(
    queue='notifications_optout',
    name='notifications.sync_sendgrid_unsubscribes',
)
def sync_sendgrid_unsubscribes():
    """
    Pull the global unsubscribe list from SendGrid and create OptOutTracking
    records for matching users. Runs weekly.
    """
    from notifications.services.providers.SendGridProvider import sendgrid_provider
    from notifications.services.OptOutService import opt_out_service

    if not sendgrid_provider.is_available():
        return {'skipped': True, 'reason': 'SendGridProvider not available'}

    synced = 0
    errors = 0

    try:
        # Fetch global unsubscribes via SendGrid API
        response = sendgrid_provider._client.asm.suppressions.global_.get()
        if response.status_code != 200:
            return {'success': False, 'error': f'SendGrid API error: {response.status_code}'}

        import json
        unsubscribes = json.loads(response.body)

        from django.contrib.auth import get_user_model
        User = get_user_model()

        for item in unsubscribes:
            email = item.get('email', '')
            if not email:
                continue
            try:
                user = User.objects.filter(email=email).first()
                if user:
                    opt_out_service.opt_out(
                        user=user,
                        channel='email',
                        reason='spam',
                        notes=f'Synced from SendGrid global unsubscribes',
                    )
                    synced += 1
            except Exception as exc:
                logger.warning(f'sync_sendgrid_unsubscribes email={email}: {exc}')
                errors += 1

    except Exception as exc:
        logger.error(f'sync_sendgrid_unsubscribes failed: {exc}')
        return {'success': False, 'error': str(exc)}

    logger.info(f'sync_sendgrid_unsubscribes: synced={synced} errors={errors}')
    return {'success': True, 'synced': synced, 'errors': errors}


@shared_task(
    queue='notifications_optout',
    name='notifications.process_one_click_unsubscribe',
)
def process_one_click_unsubscribe_task(token: str):
    """
    Process a one-click unsubscribe from an email link.
    The token encodes the user and channel.

    Token format (base64-encoded JSON): {"user_id": int, "channel": str, "ts": int}
    """
    import base64
    import json as _json
    from django.contrib.auth import get_user_model
    from notifications.services.OptOutService import opt_out_service

    User = get_user_model()

    try:
        # Decode token
        padding = 4 - len(token) % 4
        padded = token + '=' * padding
        decoded = base64.urlsafe_b64decode(padded).decode('utf-8')
        data = _json.loads(decoded)

        user_id = data.get('user_id')
        channel = data.get('channel', 'email')
        ts = data.get('ts', 0)

        # Validate token age (max 7 days)
        from time import time
        if time() - ts > 7 * 24 * 3600:
            return {'success': False, 'error': 'Token expired'}

        user = User.objects.get(pk=user_id)
        result = opt_out_service.opt_out(
            user=user,
            channel=channel,
            reason='user_request',
            notes='One-click unsubscribe via email link',
            actioned_by=user,
        )

        logger.info(f'process_one_click_unsubscribe_task: user #{user_id} channel={channel}')
        return result

    except (ValueError, KeyError, TypeError) as exc:
        return {'success': False, 'error': f'Invalid token: {exc}'}
    except Exception as exc:
        logger.error(f'process_one_click_unsubscribe_task: {exc}')
        return {'success': False, 'error': str(exc)}


@shared_task(
    queue='notifications_optout',
    name='notifications.cleanup_old_opt_out_records',
)
def cleanup_old_opt_out_records(months: int = 12):
    """
    Delete OptOutTracking records where the user has since re-subscribed
    and the record is older than `months` months.
    Keeps active (is_active=True) records indefinitely for compliance.
    """
    from notifications.models.analytics import OptOutTracking

    cutoff = timezone.now() - timedelta(days=months * 30)
    try:
        deleted, _ = OptOutTracking.objects.filter(
            is_active=False,  # re-subscribed
            updated_at__lt=cutoff,
        ).delete()
        logger.info(f'cleanup_old_opt_out_records: deleted={deleted}')
        return {'success': True, 'deleted': deleted}
    except Exception as exc:
        logger.error(f'cleanup_old_opt_out_records: {exc}')
        return {'success': False, 'error': str(exc)}
