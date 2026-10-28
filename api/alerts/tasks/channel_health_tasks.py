"""
channel_health_tasks — Celery tasks that periodically check the health of
every AlertChannel, log results to ChannelHealthLog, update channel status,
and alert the team when a channel degrades or recovers.
"""
import logging
import time
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-channel health check logic
# ---------------------------------------------------------------------------

def _check_email_channel(channel) -> dict:
    """
    Verify SMTP connectivity by opening a connection to the configured
    SMTP server.  Does NOT send a message.
    """
    import socket
    config = channel.config
    host = config.get('smtp_server', 'localhost')
    port = int(config.get('smtp_port', 587))
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=5):
            pass
        response_ms = round((time.monotonic() - start) * 1000, 2)
        return {'status': 'healthy', 'response_time_ms': response_ms, 'error_message': ''}
    except Exception:
        logger.exception("Unhandled error in _check_email_channel")
        response_ms = round((time.monotonic() - start) * 1000, 2)
        return {'status': 'critical', 'response_time_ms': response_ms, 'error_message': 'Operation failed'}


def _check_telegram_channel(channel) -> dict:
    """
    Call the Telegram getMe API to verify the bot token is valid.
    """
    import requests
    config = channel.config
    bot_token = config.get('bot_token', '')
    start = time.monotonic()
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getMe",
            timeout=8,
        )
        response_ms = round((time.monotonic() - start) * 1000, 2)
        if resp.status_code == 200 and resp.json().get('ok'):
            return {'status': 'healthy', 'response_time_ms': response_ms, 'error_message': ''}
        return {
            'status': 'critical',
            'response_time_ms': response_ms,
            'error_message': f"HTTP {resp.status_code}: {resp.text[:100]}",
        }
    except Exception:
        logger.exception("Unhandled error in _check_telegram_channel")
        response_ms = round((time.monotonic() - start) * 1000, 2)
        return {'status': 'critical', 'response_time_ms': response_ms, 'error_message': 'Operation failed'}


def _check_slack_channel(channel) -> dict:
    """
    Send a HEAD request to the Slack webhook URL to verify reachability.
    """
    import requests
    config = channel.config
    webhook_url = config.get('webhook_url', '')
    start = time.monotonic()
    try:
        # A HEAD request to the webhook URL returns 405 (Method Not Allowed)
        # which still confirms the endpoint is reachable.
        resp = requests.head(webhook_url, timeout=8)
        response_ms = round((time.monotonic() - start) * 1000, 2)
        if resp.status_code in (200, 405):
            return {'status': 'healthy', 'response_time_ms': response_ms, 'error_message': ''}
        return {
            'status': 'warning',
            'response_time_ms': response_ms,
            'error_message': f"Unexpected HTTP {resp.status_code}",
        }
    except Exception:
        logger.exception("Unhandled error in _check_slack_channel")
        response_ms = round((time.monotonic() - start) * 1000, 2)
        return {'status': 'critical', 'response_time_ms': response_ms, 'error_message': 'Operation failed'}


def _check_discord_channel(channel) -> dict:
    """Same approach as Slack — HEAD request to the webhook URL."""
    return _check_slack_channel(channel)


def _check_webhook_channel(channel) -> dict:
    """
    Send a HEAD (or GET) request to the configured webhook URL.
    """
    import requests
    config = channel.config
    url = config.get('url', '')
    if not url:
        return {'status': 'critical', 'response_time_ms': 0, 'error_message': 'No URL configured'}
    start = time.monotonic()
    try:
        resp = requests.head(url, timeout=8)
        response_ms = round((time.monotonic() - start) * 1000, 2)
        if resp.status_code < 500:
            return {'status': 'healthy', 'response_time_ms': response_ms, 'error_message': ''}
        return {
            'status': 'critical',
            'response_time_ms': response_ms,
            'error_message': f"HTTP {resp.status_code}",
        }
    except Exception:
        logger.exception("Unhandled error in _check_webhook_channel")
        response_ms = round((time.monotonic() - start) * 1000, 2)
        return {'status': 'critical', 'response_time_ms': response_ms, 'error_message': 'Operation failed'}


def _check_pagerduty_channel(channel) -> dict:
    """
    Verify PagerDuty API reachability by hitting the status endpoint.
    """
    import requests
    start = time.monotonic()
    try:
        resp = requests.get('https://status.pagerduty.com/api/v2/status.json', timeout=8)
        response_ms = round((time.monotonic() - start) * 1000, 2)
        if resp.status_code == 200:
            return {'status': 'healthy', 'response_time_ms': response_ms, 'error_message': ''}
        return {
            'status': 'warning',
            'response_time_ms': response_ms,
            'error_message': f"HTTP {resp.status_code}",
        }
    except Exception:
        logger.exception("Unhandled error in _check_pagerduty_channel")
        response_ms = round((time.monotonic() - start) * 1000, 2)
        return {'status': 'critical', 'response_time_ms': response_ms, 'error_message': 'Operation failed'}


def _check_opsgenie_channel(channel) -> dict:
    """
    Verify OpsGenie API reachability by hitting the heartbeat endpoint.
    """
    import requests
    config = channel.config
    api_key = config.get('api_key', '')
    start = time.monotonic()
    try:
        resp = requests.get(
            'https://api.opsgenie.com/v2/heartbeats',
            headers={'Authorization': f'GenieKey {api_key}'},
            timeout=8,
        )
        response_ms = round((time.monotonic() - start) * 1000, 2)
        if resp.status_code in (200, 401):
            # 401 means the key is wrong but the API is reachable
            status = 'healthy' if resp.status_code == 200 else 'warning'
            return {
                'status': status,
                'response_time_ms': response_ms,
                'error_message': '' if resp.status_code == 200 else 'Invalid API key',
            }
        return {
            'status': 'critical',
            'response_time_ms': response_ms,
            'error_message': f"HTTP {resp.status_code}",
        }
    except Exception:
        logger.exception("Unhandled error in _check_opsgenie_channel")
        response_ms = round((time.monotonic() - start) * 1000, 2)
        return {'status': 'critical', 'response_time_ms': response_ms, 'error_message': 'Operation failed'}


def _check_sms_channel(channel) -> dict:
    """
    For SMS channels, verify the provider API is reachable.
    Twilio: check account SID endpoint.
    Others: generic HTTP check.
    """
    import requests
    config = channel.config
    provider = config.get('provider', '')
    start = time.monotonic()
    try:
        if provider == 'twilio':
            account_sid = config.get('account_sid', '')
            auth_token = config.get('auth_token', '')
            resp = requests.get(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json",
                auth=(account_sid, auth_token),
                timeout=8,
            )
            response_ms = round((time.monotonic() - start) * 1000, 2)
            if resp.status_code in (200, 401):
                status = 'healthy' if resp.status_code == 200 else 'warning'
                return {
                    'status': status,
                    'response_time_ms': response_ms,
                    'error_message': '' if resp.status_code == 200 else 'Invalid credentials',
                }
            return {
                'status': 'critical',
                'response_time_ms': response_ms,
                'error_message': f"HTTP {resp.status_code}",
            }
        else:
            # Generic: just confirm the provider key exists
            response_ms = round((time.monotonic() - start) * 1000, 2)
            if config.get('api_key') or config.get('auth_token'):
                return {'status': 'healthy', 'response_time_ms': response_ms, 'error_message': ''}
            return {
                'status': 'warning',
                'response_time_ms': response_ms,
                'error_message': 'No API credentials configured',
            }
    except Exception:
        logger.exception("Unhandled error in _check_sms_channel")
        response_ms = round((time.monotonic() - start) * 1000, 2)
        return {'status': 'critical', 'response_time_ms': response_ms, 'error_message': 'Operation failed'}


# Dispatch table
_CHECKERS = {
    'email': _check_email_channel,
    'telegram': _check_telegram_channel,
    'slack': _check_slack_channel,
    'discord': _check_discord_channel,
    'webhook': _check_webhook_channel,
    'pagerduty': _check_pagerduty_channel,
    'opsgenie': _check_opsgenie_channel,
    'sms': _check_sms_channel,
}


def _run_health_check(channel) -> dict:
    """
    Run the appropriate health check for a channel and return the result dict.
    Falls back to a generic 'unknown' result for unsupported channel types.
    """
    checker = _CHECKERS.get(channel.channel_type)
    if checker:
        try:
            return checker(channel)
        except Exception:
            logger.exception("Unhandled error in _run_health_check")
            return {
                'status': 'critical',
                'response_time_ms': 0,
                'error_message': 'Checker raised',
            }
    return {
        'status': 'unknown',
        'response_time_ms': 0,
        'error_message': f"No health checker for type '{channel.channel_type}'",
    }


def _persist_health_log(channel, result: dict):
    """Write a ChannelHealthLog record for the check result."""
    from ..models.channel import ChannelHealthLog
    ChannelHealthLog.log_health_check(
        channel=channel,
        status=result['status'],
        check_type='connectivity',
        response_time_ms=result.get('response_time_ms'),
        error_message=result.get('error_message', ''),
        details=result,
    )


def _update_channel_status(channel, result: dict, previous_status: str):
    """
    Update channel.status based on the health check result and fire
    recovery/failure notifications if the status changed.
    """
    new_status = result['status']

    if new_status == 'critical':
        channel.consecutive_failures += 1
        channel.last_failure = timezone.now()
        if channel.consecutive_failures >= 3:
            channel.status = 'error'
    elif new_status == 'healthy':
        channel.consecutive_failures = 0
        channel.last_success = timezone.now()
        if channel.status == 'error':
            channel.status = 'active'
    elif new_status == 'warning':
        channel.last_success = timezone.now()
        # Don't flip to error on a single warning

    channel.save(update_fields=[
        'status', 'consecutive_failures', 'last_success', 'last_failure'
    ])

    # Fire notifications on state transitions
    if previous_status != 'error' and channel.status == 'error':
        _notify_channel_failure(channel, result.get('error_message', ''))
    elif previous_status == 'error' and channel.status == 'active':
        _notify_channel_recovery(channel)


def _notify_channel_failure(channel, error_message: str):
    """Create a pending Notification to alert the team about a channel failure."""
    try:
        from ..models.core import Notification
        Notification.objects.create(
            alert_log=None,
            notification_type='email',
            recipient='ops-team',  # resolved by routing in production
            subject=f"Channel Failure: {channel.name} ({channel.channel_type})",
            message=(
                f"Alert channel '{channel.name}' has failed and is now in ERROR state.\n\n"
                f"Channel type: {channel.channel_type}\n"
                f"Consecutive failures: {channel.consecutive_failures}\n"
                f"Error: {error_message}\n"
                f"Time: {timezone.now().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                f"Notifications through this channel are currently suspended."
            ),
            status='pending',
        )
        from .notification import send_pending_notifications
        send_pending_notifications.delay()
    except Exception as e:
        logger.error(f"_notify_channel_failure: {e}")


def _notify_channel_recovery(channel):
    """Create a pending Notification to alert the team about a channel recovery."""
    try:
        from ..models.core import Notification
        Notification.objects.create(
            alert_log=None,
            notification_type='email',
            recipient='ops-team',
            subject=f"Channel Recovered: {channel.name} ({channel.channel_type})",
            message=(
                f"Alert channel '{channel.name}' has recovered and is now ACTIVE.\n\n"
                f"Channel type: {channel.channel_type}\n"
                f"Recovered at: {timezone.now().strftime('%Y-%m-%d %H:%M UTC')}"
            ),
            status='pending',
        )
        from .notification import send_pending_notifications
        send_pending_notifications.delay()
    except Exception as e:
        logger.error(f"_notify_channel_recovery: {e}")


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------

@shared_task(
    name='alerts.check_all_channel_health',
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    soft_time_limit=280,
    time_limit=300,
)
def check_all_channel_health(self):
    """
    Run health checks on every enabled AlertChannel and persist results.

    Scheduled every 5 minutes via Celery Beat:
        CELERY_BEAT_SCHEDULE = {
            'check-all-channel-health': {
                'task': 'alerts.check_all_channel_health',
                'schedule': crontab(minute='*/5'),
            },
        }

    Returns:
        dict with counts of healthy / warning / critical / unknown channels.
    """
    try:
        from ..models.channel import AlertChannel

        channels = AlertChannel.objects.filter(is_enabled=True)
        counts = {'healthy': 0, 'warning': 0, 'critical': 0, 'unknown': 0, 'total': 0}

        for channel in channels:
            counts['total'] += 1
            previous_status = channel.status
            result = _run_health_check(channel)
            _persist_health_log(channel, result)
            _update_channel_status(channel, result, previous_status)
            status_key = result['status'] if result['status'] in counts else 'unknown'
            counts[status_key] += 1

            logger.debug(
                f"check_all_channel_health: channel='{channel.name}' "
                f"type={channel.channel_type} status={result['status']} "
                f"response_ms={result.get('response_time_ms', 0)}"
            )

        logger.info(
            f"check_all_channel_health: {counts}"
        )
        return counts

    except Exception as exc:
        logger.error(f"check_all_channel_health error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'error': 'Operation failed'}


@shared_task(
    name='alerts.check_single_channel_health',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def check_single_channel_health(self, channel_id: int):
    """
    Run a health check on a single AlertChannel by ID.
    Used by admin actions and the API test endpoint.

    Args:
        channel_id: PK of the AlertChannel to check.

    Returns:
        Health check result dict.
    """
    try:
        from ..models.channel import AlertChannel
        channel = AlertChannel.objects.get(id=channel_id)
        previous_status = channel.status
        result = _run_health_check(channel)
        _persist_health_log(channel, result)
        _update_channel_status(channel, result, previous_status)

        logger.info(
            f"check_single_channel_health: channel_id={channel_id} "
            f"status={result['status']}"
        )
        return {
            'channel_id': channel_id,
            'channel_name': channel.name,
            'channel_type': channel.channel_type,
            **result,
        }

    except Exception as exc:
        logger.error(f"check_single_channel_health error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'channel_id': channel_id, 'status': 'error', 'error_message': 'Operation failed'}


@shared_task(
    name='alerts.compute_channel_delivery_rates',
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=280,
    time_limit=300,
)
def compute_channel_delivery_rates(self, hours: int = 24):
    """
    Compute delivery success rates for every AlertChannel over the last
    `hours` hours and update channel.success_rate.

    Scheduled hourly via Celery Beat:
        CELERY_BEAT_SCHEDULE = {
            'compute-channel-delivery-rates': {
                'task': 'alerts.compute_channel_delivery_rates',
                'schedule': crontab(minute=30),  # half-past every hour
            },
        }

    Args:
        hours: look-back window in hours (default 24).

    Returns:
        dict mapping channel_id → success_rate.
    """
    try:
        from ..models.channel import AlertChannel
        from ..models.core import Notification
        from django.db.models import Count, Q

        cutoff = timezone.now() - timedelta(hours=hours)
        channels = AlertChannel.objects.filter(is_enabled=True)
        rates = {}

        for channel in channels:
            stats = Notification.objects.filter(
                notification_type=channel.channel_type,
                created_at__gte=cutoff,
            ).aggregate(
                total=Count('id'),
                sent=Count('id', filter=Q(status='sent')),
                delivered=Count('id', filter=Q(status='delivered')),
                failed=Count('id', filter=Q(status='failed')),
            )

            total = stats['total'] or 0
            success = (stats['sent'] or 0) + (stats['delivered'] or 0)
            rate = round((success / total * 100), 2) if total > 0 else 100.0

            channel.success_rate = rate
            channel.total_sent = (channel.total_sent or 0) + (stats['sent'] or 0)
            channel.total_failed = (channel.total_failed or 0) + (stats['failed'] or 0)
            channel.save(update_fields=['success_rate', 'total_sent', 'total_failed'])

            rates[channel.id] = rate

            logger.debug(
                f"compute_channel_delivery_rates: channel='{channel.name}' "
                f"total={total} success={success} rate={rate}%"
            )

        logger.info(
            f"compute_channel_delivery_rates: updated {len(rates)} channels "
            f"over last {hours}h"
        )
        return rates

    except Exception as exc:
        logger.error(f"compute_channel_delivery_rates error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {}


@shared_task(
    name='alerts.cleanup_old_channel_health_logs',
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def cleanup_old_channel_health_logs(self, days_to_keep: int = 30):
    """
    Delete ChannelHealthLog records older than `days_to_keep` days.

    Scheduled daily at 03:00 via Celery Beat:
        CELERY_BEAT_SCHEDULE = {
            'cleanup-channel-health-logs': {
                'task': 'alerts.cleanup_old_channel_health_logs',
                'schedule': crontab(hour=3, minute=0),
            },
        }

    Args:
        days_to_keep: logs older than this are deleted (default 30).

    Returns:
        Number of records deleted.
    """
    try:
        from ..models.channel import ChannelHealthLog
        cutoff = timezone.now() - timedelta(days=days_to_keep)
        deleted, _ = ChannelHealthLog.objects.filter(checked_at__lt=cutoff).delete()
        logger.info(
            f"cleanup_old_channel_health_logs: deleted {deleted} records "
            f"older than {days_to_keep} days"
        )
        return deleted

    except Exception as exc:
        logger.error(f"cleanup_old_channel_health_logs error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return 0
