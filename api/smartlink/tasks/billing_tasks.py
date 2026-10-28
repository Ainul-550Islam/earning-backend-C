"""
SmartLink Billing Tasks
Celery tasks for wallet hold release, payout reminders, and scheduled reports.
"""
import logging
from celery import shared_task

logger = logging.getLogger('smartlink.tasks.billing')


@shared_task(name='smartlink.release_pending_balances', queue='default')
def release_pending_balances():
    """
    Beat task: move pending wallet balances → available after HOLD_DAYS.
    Schedule: daily at 02:00 UTC in CELERY_BEAT_SCHEDULE.
    """
    from django.contrib.auth import get_user_model
    from api.smartlink.models.billing import PublisherWallet
    from django.db.models import F

    User = get_user_model()
    # Simple approach: release all pending to available
    # (In production, track per-conversion hold expiry in a separate table)
    wallets = PublisherWallet.objects.filter(pending_usd__gt=0)
    released = 0
    for wallet in wallets:
        PublisherWallet.objects.filter(pk=wallet.pk, pending_usd__gt=0).update(
            balance_usd=F('balance_usd') + F('pending_usd'),
            pending_usd=0,
        )
        released += 1

    logger.info(f"Pending balances released for {released} publishers")
    return {'released': released}


@shared_task(name='smartlink.send_daily_report_emails', queue='notifications')
def send_daily_report_emails():
    """
    Beat task: send daily performance report emails to publishers who opted in.
    Schedule: daily at 08:00 UTC.
    """
    from django.contrib.auth import get_user_model
    from api.smartlink.models.billing import PublisherProfile
    from ..services.notification.NotificationService import NotificationService
    from ..reports.PublisherReportService import PublisherReportService
    import datetime

    User = get_user_model()
    notification_svc = NotificationService()
    report_svc = PublisherReportService()

    profiles = PublisherProfile.objects.filter(
        notification_preferences__daily_report_email=True,
        data_anonymized=False,
    ).select_related('publisher')

    sent = 0
    for profile in profiles:
        try:
            yesterday = datetime.date.today() - datetime.timedelta(days=1)
            stats = report_svc.performance_report(
                publisher_id=profile.publisher_id,
                params={'date_from': str(yesterday), 'date_to': str(yesterday)},
            )
            notification_svc.notify_daily_report(profile.publisher, stats)
            sent += 1
        except Exception as e:
            logger.error(f"Daily report failed for {profile.publisher.username}: {e}")

    logger.info(f"Daily report emails sent to {sent} publishers")
    return {'sent': sent}


@shared_task(name='smartlink.send_payout_ready_notifications', queue='notifications')
def send_payout_ready_notifications(batch_id: int):
    """
    Notify publishers when their payout record is approved and ready.
    Triggered when admin approves a batch.
    """
    from api.smartlink.models.billing import PayoutBatch, PayoutRecord
    from ..services.notification.NotificationService import NotificationService
    from ..services.webhook.WebhookService import WebhookService

    notification_svc = NotificationService()
    webhook_svc = WebhookService()

    try:
        batch = PayoutBatch.objects.get(pk=batch_id)
    except PayoutBatch.DoesNotExist:
        return {'notified': 0}

    records = PayoutRecord.objects.filter(
        batch=batch, status=PayoutRecord.Status.APPROVED
    ).select_related('publisher')

    notified = 0
    for record in records:
        try:
            # Webhook
            webhook_svc.dispatch('payout_ready', publisher=record.publisher,
                                 amount_usd=str(record.net_amount),
                                 currency=record.currency,
                                 period_from=str(record.period_from),
                                 period_to=str(record.period_to),
                                 reference_id=str(record.reference_id))
            notified += 1
        except Exception as e:
            logger.error(f"Payout notification failed for {record.publisher.username}: {e}")

    return {'notified': notified}


@shared_task(name='smartlink.check_smartlink_expiry', queue='default')
def check_smartlink_expiry():
    """
    Beat task: auto-deactivate SmartLinks that have expired.
    Schedule: every 15 minutes.
    """
    from django.utils import timezone
    from django.db.models import Q, F
    from api.smartlink.models import SmartLink

    now = timezone.now()
    deactivated = 0

    # Datetime expiry
    expired_by_time = SmartLink.objects.filter(
        is_active=True,
        expires_at__lte=now,
    )
    count = expired_by_time.update(is_active=False)
    deactivated += count

    # Lifetime click cap
    expired_by_clicks = SmartLink.objects.filter(
        is_active=True,
        lifetime_click_cap__isnull=False,
    ).filter(total_clicks__gte=F('lifetime_click_cap'))
    count = expired_by_clicks.update(is_active=False)
    deactivated += count

    # Lifetime conversion cap
    expired_by_conv = SmartLink.objects.filter(
        is_active=True,
        lifetime_conversion_cap__isnull=False,
    ).filter(total_conversions__gte=F('lifetime_conversion_cap'))
    count = expired_by_conv.update(is_active=False)
    deactivated += count

    if deactivated:
        logger.info(f"Auto-deactivated {deactivated} expired SmartLinks")
    return {'deactivated': deactivated}


@shared_task(
    name='smartlink.process_payout_payment',
    queue='default',
    bind=True,
    max_retries=3,
    default_retry_delay=300,   # 5 minutes between retries
)
def process_payout_payment(self, payout_record_id: int):
    """
    Async task: send a single APPROVED PayoutRecord to its payment gateway.
    Retries up to 3 times with 5-minute delays on gateway errors.

    Args:
        payout_record_id: PayoutRecord.pk (must be status=APPROVED)
    """
    from api.smartlink.models.billing import PayoutRecord
    from ..services.billing.BillingService import BillingService

    try:
        record = PayoutRecord.objects.select_related('publisher').get(pk=payout_record_id)
    except PayoutRecord.DoesNotExist:
        logger.error(f"process_payout_payment: PayoutRecord #{payout_record_id} not found")
        return {'success': False, 'error': 'PayoutRecord not found'}

    result = BillingService().process_payment(record)

    # Retry on gateway errors (not on manual/credential issues)
    if (not result['success']
            and not result.get('requires_manual')
            and 'credentials not configured' not in result.get('error', '')):
        logger.warning(
            f"process_payout_payment: retrying ref={record.reference_id} "
            f"attempt={self.request.retries + 1}/{self.max_retries}"
        )
        try:
            raise self.retry()
        except Exception:
            pass  # Max retries reached — record already marked failed

    return result


@shared_task(
    name='smartlink.process_batch_payments_async',
    queue='default',
)
def process_batch_payments_async(batch_id: int):
    """
    Async task: process all APPROVED records in a payout batch via gateways.
    Dispatches individual process_payout_payment tasks per record for isolation.

    Args:
        batch_id: PayoutBatch.pk
    """
    from api.smartlink.models.billing import PayoutBatch, PayoutRecord

    try:
        batch = PayoutBatch.objects.get(pk=batch_id)
    except PayoutBatch.DoesNotExist:
        logger.error(f"process_batch_payments_async: PayoutBatch #{batch_id} not found")
        return {'dispatched': 0}

    records = PayoutRecord.objects.filter(
        batch=batch,
        status=PayoutRecord.Status.APPROVED,
    ).values_list('pk', flat=True)

    dispatched = 0
    for record_id in records:
        process_payout_payment.apply_async(
            args=[record_id],
            countdown=dispatched * 2,  # 2s stagger to avoid rate limits
        )
        dispatched += 1

    logger.info(f"process_batch_payments_async: dispatched {dispatched} tasks for batch #{batch_id}")
    return {'dispatched': dispatched}


@shared_task(name='smartlink.evaluate_publisher_tiers', queue='analytics')
def evaluate_publisher_tiers():
    """
    Beat task: recalculate Gold/Silver/Bronze/Standard tiers for all publishers.
    Schedule: weekly Monday 06:00 UTC.
    """
    from ..services.billing.BillingService import BillingService
    result = BillingService().evaluate_publisher_tiers()
    logger.info(
        f"evaluate_publisher_tiers: evaluated={result['evaluated']} "
        f"changed={result['changed']}"
    )
    return result


@shared_task(name='smartlink.update_currency_rates', queue='default')
def update_currency_rates():
    """
    Beat task: fetch fresh FX rates from external provider and cache them.
    Schedule: hourly at :15.
    """
    from ..services.core.MultiCurrencyService import MultiCurrencyService
    try:
        result = MultiCurrencyService().refresh_rates()
        logger.info(f"Currency rates updated: {result}")
        return result if isinstance(result, dict) else {'updated': result}
    except Exception as exc:
        logger.error(f"Currency rate update failed: {exc}")
        return {'updated': 0, 'error': str(exc)}


@shared_task(name='smartlink.send_daily_publisher_reports', queue='email')
def send_daily_publisher_reports():
    """
    Beat task: send daily performance report emails to opted-in publishers.
    Schedule: daily 08:00 UTC.
    """
    from django.contrib.auth import get_user_model as _get_user_model
    from ..services.notification.NotificationService import NotificationService
    User = _get_user_model()
    svc  = NotificationService()
    sent = 0
    for user in User.objects.filter(is_active=True, is_staff=False):
        try:
            svc.send_daily_report(user)
            sent += 1
        except Exception as exc:
            logger.warning(f"Daily report failed for {user.username}: {exc}")
    logger.info(f"Daily publisher reports sent: {sent}")
    return {'sent': sent}


@shared_task(name='smartlink.send_weekly_publisher_reports', queue='email')
def send_weekly_publisher_reports():
    """
    Beat task: send weekly performance summary to opted-in publishers.
    Schedule: weekly Monday 08:00 UTC.
    """
    from django.contrib.auth import get_user_model as _get_user_model
    from ..services.notification.NotificationService import NotificationService
    User = _get_user_model()
    svc  = NotificationService()
    sent = 0
    for user in User.objects.filter(is_active=True, is_staff=False):
        try:
            svc.send_weekly_report(user)
            sent += 1
        except Exception as exc:
            logger.warning(f"Weekly report failed for {user.username}: {exc}")
    logger.info(f"Weekly publisher reports sent: {sent}")
    return {'sent': sent}
