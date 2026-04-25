# api/payment_gateways/tasks.py
# Root tasks file — full Celery task registry for payment_gateways
# All tasks imported here for Celery autodiscovery

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

# ── Gateway Health Tasks ───────────────────────────────────────────────────────
from api.payment_gateways.tasks.gateway_health_tasks import (
    check_all_gateways,
    check_gateway_alerts,
)

# ── Deposit Tasks ──────────────────────────────────────────────────────────────
from api.payment_gateways.tasks.deposit_verification_tasks import (
    verify_pending_deposits,
    expire_old_deposits,
)

# ── Withdrawal Tasks ───────────────────────────────────────────────────────────
from api.payment_gateways.tasks.withdrawal_processing_tasks import (
    process_approved_payouts,
    retry_failed_payout,
)

# ── Reconciliation Tasks ───────────────────────────────────────────────────────
from api.payment_gateways.tasks.reconciliation_tasks import (
    nightly_reconciliation,
    reconcile_gateway,
)

# ── Analytics Tasks ────────────────────────────────────────────────────────────
from api.payment_gateways.tasks.analytics_tasks import (
    aggregate_daily_analytics,
    update_success_rates,
    auto_blacklist_low_quality_publishers,
    update_offer_quality_scores,
)

# ── Webhook Tasks ──────────────────────────────────────────────────────────────
from api.payment_gateways.tasks.webhook_retry_tasks import (
    retry_failed_webhook,
    retry_all_failed_webhooks,
)

# ── Alert Tasks ────────────────────────────────────────────────────────────────
from api.payment_gateways.tasks.alert_tasks import (
    check_failure_rate_alerts,
    credential_expiry_reminder,
    cleanup_old_logs,
)

# ── Refund Tasks ───────────────────────────────────────────────────────────────
from api.payment_gateways.tasks.refund_tasks import (
    process_approved_refunds,
    check_pending_refunds_timeout,
)

# ── Fee Tasks ──────────────────────────────────────────────────────────────────
from api.payment_gateways.tasks.fee_calculation_tasks import (
    recalculate_gateway_fees,
    sync_gateway_fee_rules,
)

# ── Cleanup Tasks ─────────────────────────────────────────────────────────────
from api.payment_gateways.tasks.cleanup_tasks import (
    cleanup_old_webhook_logs,
    cleanup_health_logs,
    cleanup_expired_deposits,
    cleanup_old_callbacks,
)

# ── Statement Import Tasks ─────────────────────────────────────────────────────
from api.payment_gateways.tasks.statement_import_tasks import (
    auto_import_gateway_statement,
)

# ── USDT Fast Pay Tasks ────────────────────────────────────────────────────────
from api.payment_gateways.tasks.usdt_fastpay_tasks import (
    process_usdt_fastpay_requests,
    process_daily_fastpay,
)

# ── Capacity Tasks ─────────────────────────────────────────────────────────────
from api.payment_gateways.tasks_cap import (
    reset_daily_offer_caps,
    check_queue_depths,
    reprocess_dlq_messages,
)


# ── Convenience tasks (called from signals/events) ─────────────────────────────
@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def async_credit_wallet(self, user_id: int, amount: str, gateway: str, reference_id: str):
    """
    Async task: credit user wallet after deposit.
    Called by DepositService after completing a deposit.
    Uses WalletAdapter to credit your existing api.wallet app.
    """
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from api.payment_gateways.integrations_adapters.WalletAdapter import WalletAdapter

    try:
        User   = get_user_model()
        user   = User.objects.get(id=user_id)
        result = WalletAdapter().credit_deposit(user, Decimal(amount), gateway, reference_id)
        logger.info(f'Wallet credited: user={user_id} amount={amount} gateway={gateway} result={result}')
        return {'success': result}
    except Exception as e:
        logger.error(f'async_credit_wallet failed: user={user_id} error={e}')
        self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def async_send_notification(self, user_id: int, template: str, context: dict):
    """
    Async task: send notification to user after payment event.
    Delegates to your existing api.notifications app via NotificationAdapter.
    """
    from django.contrib.auth import get_user_model
    from api.payment_gateways.integrations_adapters.NotificationAdapter import NotificationAdapter

    try:
        User   = get_user_model()
        user   = User.objects.get(id=user_id)
        adapter= NotificationAdapter()

        if template == 'deposit_completed':
            result = adapter._fallback_email(
                user,
                subject=f'Deposit Confirmed — {context.get("currency")} {context.get("amount")}',
                message=f'Your deposit has been credited to your account.\n\nReference: {context.get("reference_id", "")}'
            )
        elif template == 'withdrawal_processed':
            result = adapter._fallback_email(
                user,
                subject=f'Withdrawal Processed — {context.get("currency")} {context.get("amount")}',
                message=f'Your withdrawal request has been processed.\n\nReference: {context.get("reference_id", "")}'
            )
        else:
            logger.warning(f'Unknown notification template: {template}')
            return {'sent': False, 'reason': 'unknown_template'}

        logger.info(f'Notification sent: user={user_id} template={template}')
        return {'sent': True}
    except Exception as e:
        logger.error(f'async_send_notification failed: user={user_id} template={template} error={e}')
        self.retry(exc=e)


@shared_task(bind=True, max_retries=5, default_retry_delay=10)
def async_fire_postback(self, conversion_id: str):
    """
    Async task: fire publisher postback after conversion approval.
    Delegates to your existing api.postback_engine via PostbackAdapter.
    """
    from api.payment_gateways.integrations_adapters.PostbackAdapter import PostbackAdapter

    try:
        from api.payment_gateways.tracking.models import Conversion
        conversion = Conversion.objects.get(conversion_id=conversion_id)
        result     = PostbackAdapter().fire_publisher_postback(conversion)
        logger.info(f'Postback fired: conversion_id={conversion_id}')
        return result
    except Exception as e:
        logger.error(f'async_fire_postback failed: {conversion_id} error={e}')
        self.retry(exc=e)


@shared_task
def sync_exchange_rates():
    """
    Hourly task: sync exchange rates from external API.
    Updates Currency.exchange_rate in DB and refreshes cache.
    """
    from api.payment_gateways.services.MultiCurrencyEngine import MultiCurrencyEngine

    try:
        engine = MultiCurrencyEngine()
        # Try to update rates from external API
        import requests
        from django.conf import settings

        api_key = getattr(settings, 'EXCHANGE_RATE_API_KEY', '')
        if not api_key:
            logger.debug('EXCHANGE_RATE_API_KEY not set, skipping live rate sync')
            return {'synced': False, 'reason': 'no_api_key'}

        resp  = requests.get(
            f'https://v6.exchangerate-api.com/v6/{api_key}/latest/USD',
            timeout=10
        )
        data  = resp.json()
        rates = data.get('conversion_rates', {})

        from api.payment_gateways.models.core import Currency
        from django.utils import timezone
        from decimal import Decimal

        updated = 0
        for code, rate in rates.items():
            Currency.objects.filter(code=code).update(
                exchange_rate=Decimal(str(rate)),
                last_updated=timezone.now(),
            )
            updated += 1

        # Clear rate cache
        from django.core.cache import cache
        cache.delete('all_exchange_rates')

        logger.info(f'Exchange rates synced: {updated} currencies updated')
        return {'synced': True, 'updated': updated}

    except Exception as e:
        logger.error(f'sync_exchange_rates failed: {e}')
        return {'synced': False, 'error': str(e)}


@shared_task
def aggregate_daily_stats():
    """
    Daily task: aggregate publisher tracking stats into PublisherDailyStats.
    Called at midnight for yesterday's data.
    """
    from api.payment_gateways.services.GatewayAnalyticsService import GatewayAnalyticsService
    from datetime import date, timedelta

    yesterday = date.today() - timedelta(days=1)
    try:
        result = GatewayAnalyticsService().aggregate_daily(yesterday)
        logger.info(f'Daily stats aggregated for {yesterday}')
        return result
    except Exception as e:
        logger.error(f'aggregate_daily_stats failed: {e}')
        return {'error': str(e)}


@shared_task
def pay_pending_commissions():
    """Daily task: pay pending referral commissions."""
    from api.payment_gateways.referral.ReferralEngine import ReferralEngine
    try:
        result = ReferralEngine().pay_pending_commissions()
        logger.info(f'Referral commissions paid: {result}')
        return result
    except Exception as e:
        logger.error(f'pay_pending_commissions failed: {e}')
        return {'error': str(e)}


@shared_task
def expire_inactive_referrals():
    """Daily task: mark expired referral relationships."""
    from api.payment_gateways.referral.ReferralEngine import ReferralEngine
    try:
        result = ReferralEngine().expire_inactive()
        return result
    except Exception as e:
        logger.error(f'expire_inactive_referrals: {e}')
        return {'error': str(e)}


@shared_task
def update_offer_metrics():
    """Hourly task: update offer EPC and conversion rate metrics."""
    from api.payment_gateways.offers.models import Offer
    from api.payment_gateways.tracking.models import Conversion, Click
    from django.db.models import Sum, Count, Avg
    from decimal import Decimal

    updated = 0
    for offer in Offer.objects.filter(status='active'):
        try:
            clicks = Click.objects.filter(offer=offer).count() or 1
            convs  = Conversion.objects.filter(offer=offer, status='approved')
            agg    = convs.aggregate(
                total_payout=Sum('payout'),
                count=Count('id'),
            )
            total_payout   = agg['total_payout'] or Decimal('0')
            conversion_count = agg['count'] or 0
            epc = total_payout / clicks if clicks else Decimal('0')
            cr  = Decimal(str(conversion_count / clicks))

            Offer.objects.filter(id=offer.id).update(
                epc=epc.quantize(Decimal('0.0001')),
                conversion_rate=cr.quantize(Decimal('0.0001')),
                total_conversions=conversion_count,
                total_clicks=clicks,
            )
            updated += 1
        except Exception as e:
            logger.warning(f'update_offer_metrics failed for offer {offer.id}: {e}')

    logger.info(f'Offer metrics updated: {updated} offers')
    return {'updated': updated}


# ── Exports ────────────────────────────────────────────────────────────────────
__all__ = [
    # Gateway health
    'check_all_gateways', 'check_gateway_alerts',
    # Deposits
    'verify_pending_deposits', 'expire_old_deposits',
    # Withdrawals
    'process_approved_payouts', 'retry_failed_payout',
    # Reconciliation
    'nightly_reconciliation', 'reconcile_gateway',
    # Analytics
    'aggregate_daily_analytics', 'update_success_rates',
    # Webhooks
    'retry_failed_webhook', 'retry_all_failed_webhooks',
    # Alerts
    'check_failure_rate_alerts', 'credential_expiry_reminder', 'cleanup_old_logs',
    # Refunds
    'process_approved_refunds',
    # Fees
    'recalculate_gateway_fees', 'sync_gateway_fee_rules',
    # Cleanup
    'cleanup_old_webhook_logs', 'cleanup_health_logs', 'cleanup_expired_deposits',
    # USDT Fast Pay
    'process_usdt_fastpay_requests', 'process_daily_fastpay',
    # Capacity
    'reset_daily_offer_caps', 'check_queue_depths', 'reprocess_dlq_messages',
    # Inline tasks
    'async_credit_wallet', 'async_send_notification', 'async_fire_postback',
    'sync_exchange_rates', 'aggregate_daily_stats', 'pay_pending_commissions',
    'expire_inactive_referrals', 'update_offer_metrics',
]
