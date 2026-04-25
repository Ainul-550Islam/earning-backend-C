# api/payment_gateways/background_jobs.py
# Background job registry — all Celery tasks organized by category
# "Do not summarize or skip any logic. Provide the full code."

import logging
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# DEPOSIT JOBS
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=5, default_retry_delay=60, name='pg.deposit.verify')
def job_verify_deposit(self, deposit_id: int):
    """Verify a pending deposit by polling the gateway API."""
    from api.payment_gateways.models.deposit import DepositRequest
    try:
        deposit = DepositRequest.objects.get(id=deposit_id)
        if deposit.status == 'completed':
            return {'status': 'already_completed'}
        if deposit.status == 'expired':
            return {'status': 'expired'}
        from api.payment_gateways.interactors import DepositFlowInteractor
        result = DepositFlowInteractor().verify(deposit.reference_id)
        logger.info(f'Deposit verification: {deposit.reference_id} → {result}')
        return result
    except Exception as e:
        logger.error(f'job_verify_deposit failed: deposit_id={deposit_id}: {e}')
        self.retry(exc=e)


@shared_task(name='pg.deposit.expire_old')
def job_expire_old_deposits():
    """Expire deposits stuck in pending state > 1 hour."""
    from api.payment_gateways.repositories import DepositRepository
    count = DepositRepository().mark_expired(older_than_minutes=60)
    logger.info(f'Expired {count} old deposits')
    return {'expired': count}


@shared_task(name='pg.deposit.verify_all_pending')
def job_verify_all_pending():
    """Verify all deposits pending > 5 minutes."""
    from api.payment_gateways.models.deposit import DepositRequest
    from datetime import timedelta
    from django.utils import timezone
    stuck = DepositRequest.objects.filter(
        status='pending', initiated_at__lte=timezone.now() - timedelta(minutes=5)
    ).values_list('id', flat=True)[:50]
    for deposit_id in stuck:
        job_verify_deposit.apply_async(args=[deposit_id], countdown=2)
    return {'queued': len(stuck)}


# ══════════════════════════════════════════════════════════════════════════════
# PAYOUT JOBS
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=300, name='pg.payout.process')
def job_process_payout(self, payout_id: int):
    """Process a single approved payout via gateway."""
    from api.payment_gateways.use_cases import ProcessPayoutUseCase
    try:
        result = ProcessPayoutUseCase().execute(payout_id)
        logger.info(f'Payout processed: {payout_id} → {result.get("success")}')
        return result
    except Exception as e:
        logger.error(f'job_process_payout failed: {payout_id}: {e}')
        self.retry(exc=e)


@shared_task(name='pg.payout.process_all_approved')
def job_process_all_approved_payouts():
    """Process all approved payouts in batch."""
    from api.payment_gateways.models.core import PayoutRequest
    approved_ids = list(
        PayoutRequest.objects.filter(status='approved').values_list('id', flat=True)[:100]
    )
    for pid in approved_ids:
        job_process_payout.apply_async(args=[pid], countdown=1)
    logger.info(f'Queued {len(approved_ids)} payouts for processing')
    return {'queued': len(approved_ids)}


@shared_task(name='pg.payout.usdt_fastpay')
def job_usdt_fastpay():
    """Process USDT fast pay requests."""
    from api.payment_gateways.models.core import PayoutRequest
    from django.utils import timezone
    today = timezone.now().date()
    requests = PayoutRequest.objects.filter(
        payout_method='crypto', status='approved',
        metadata__fast_pay=True,
    )
    processed = 0
    for req in requests[:50]:
        try:
            job_process_payout.apply_async(args=[req.id])
            processed += 1
        except Exception as e:
            logger.error(f'USDT fast pay failed: {req.id}: {e}')
    return {'processed': processed}


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSION JOBS
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=30, name='pg.conversion.approve')
def job_approve_conversion(self, conversion_id: str):
    """Approve a single pending conversion."""
    from api.payment_gateways.use_cases import ApproveConversionUseCase
    try:
        return ApproveConversionUseCase().execute(conversion_id)
    except Exception as e:
        logger.error(f'job_approve_conversion failed: {conversion_id}: {e}')
        self.retry(exc=e)


@shared_task(name='pg.conversion.auto_approve_old')
def job_auto_approve_old_conversions():
    """Auto-approve conversions pending > 24 hours (configurable)."""
    from api.payment_gateways.models.core import PaymentGateway
    from api.payment_gateways.tracking.models import Conversion
    from django.utils import timezone
    from datetime import timedelta
    from django.conf import settings
    hours   = getattr(settings, 'AUTO_APPROVE_CONVERSION_HOURS', 48)
    cutoff  = timezone.now() - timedelta(hours=hours)
    pending = Conversion.objects.filter(status='pending', created_at__lte=cutoff)[:100]
    approved = 0
    for conv in pending:
        job_approve_conversion.apply_async(args=[conv.conversion_id])
        approved += 1
    return {'queued_for_approval': approved}


@shared_task(bind=True, max_retries=3, name='pg.postback.fire')
def job_fire_postback(self, conversion_id: str):
    """Fire publisher postback for an approved conversion."""
    from api.payment_gateways.integrations_adapters.PostbackAdapter import PostbackAdapter
    from api.payment_gateways.tracking.models import Conversion
    try:
        conv   = Conversion.objects.get(conversion_id=conversion_id)
        result = PostbackAdapter().fire_publisher_postback(conv)
        return result
    except Exception as e:
        logger.error(f'job_fire_postback failed: {conversion_id}: {e}')
        self.retry(exc=e)


# ══════════════════════════════════════════════════════════════════════════════
# GATEWAY HEALTH JOBS
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(name='pg.health.check_all')
def job_check_all_gateways():
    """Health check all active gateways."""
    from api.payment_gateways.services.GatewayHealthService import GatewayHealthService
    try:
        results = GatewayHealthService().check_all()
        logger.info(f'Gateway health checked: {len(results)} gateways')
        return results
    except Exception as e:
        logger.error(f'job_check_all_gateways failed: {e}')
        return {}


@shared_task(name='pg.health.alert_failures')
def job_alert_gateway_failures():
    """Send alerts for gateways with high failure rates."""
    from api.payment_gateways.services.GatewayAnalyticsService import GatewayAnalyticsService
    from api.payment_gateways.monitoring import payment_monitor
    try:
        analytics = GatewayAnalyticsService()
        for gateway in ['bkash', 'nagad', 'sslcommerz', 'stripe', 'paypal']:
            stats = analytics.get_stats(gateway)
            if stats.get('success_rate', 100) < 80:
                payment_monitor.add_alert(
                    f'gateway_low_success_{gateway}',
                    f'{gateway} success rate: {stats["success_rate"]}%',
                    severity='critical' if stats.get('success_rate', 100) < 60 else 'warning',
                )
    except Exception as e:
        logger.error(f'job_alert_gateway_failures: {e}')


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS & REPORTING JOBS
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(name='pg.analytics.daily_aggregate')
def job_daily_analytics():
    """Aggregate daily analytics stats."""
    from api.payment_gateways.analytics import PaymentAnalyticsEngine
    try:
        engine = PaymentAnalyticsEngine()
        stats  = engine.get_admin_summary()
        from django.core.cache import cache
        cache.set('pg:analytics:daily', stats, 3600)
        return {'status': 'aggregated'}
    except Exception as e:
        logger.error(f'job_daily_analytics: {e}')


@shared_task(name='pg.analytics.update_offer_metrics')
def job_update_offer_metrics():
    """Recalculate EPC and CR for all active offers."""
    from api.payment_gateways.offers.models import Offer
    from api.payment_gateways.tracking.models import Conversion, Click
    from django.db.models import Sum, Count, Avg
    updated = 0
    for offer in Offer.objects.filter(status='active'):
        try:
            clicks = Click.objects.filter(offer=offer).count() or 1
            convs  = Conversion.objects.filter(offer=offer, status='approved')
            agg    = convs.aggregate(total=Sum('payout'), count=Count('id'))
            total  = agg['total'] or 0
            count  = agg['count'] or 0
            Offer.objects.filter(id=offer.id).update(
                epc=round(float(total) / clicks, 4),
                conversion_rate=round(count / clicks * 100, 4) if clicks else 0,
                total_conversions=count,
                total_clicks=clicks,
                total_revenue=total,
            )
            updated += 1
        except Exception:
            pass
    return {'updated': updated}


@shared_task(name='pg.analytics.sync_exchange_rates')
def job_sync_exchange_rates():
    """Sync exchange rates from external API."""
    from api.payment_gateways.tasks import sync_exchange_rates
    return sync_exchange_rates()


# ══════════════════════════════════════════════════════════════════════════════
# WALLET & REFERRAL JOBS
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, name='pg.wallet.credit')
def job_credit_wallet(self, user_id: int, amount_str: str, gateway: str, ref_id: str):
    """Credit user wallet after deposit."""
    from api.payment_gateways.tasks import async_credit_wallet
    return async_credit_wallet(user_id, amount_str, gateway, ref_id)


@shared_task(name='pg.referral.pay_commissions')
def job_pay_referral_commissions():
    """Pay pending referral commissions."""
    from api.payment_gateways.tasks import pay_pending_commissions
    return pay_pending_commissions()


# ══════════════════════════════════════════════════════════════════════════════
# CLEANUP JOBS
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(name='pg.cleanup.webhook_logs')
def job_cleanup_webhook_logs():
    """Delete webhook logs older than 30 days."""
    from api.payment_gateways.models.core import PaymentGatewayWebhookLog
    from django.utils import timezone
    from datetime import timedelta
    deleted, _ = PaymentGatewayWebhookLog.objects.filter(
        created_at__lte=timezone.now() - timedelta(days=30)
    ).delete()
    logger.info(f'Cleaned {deleted} webhook logs')
    return {'deleted': deleted}


@shared_task(name='pg.cleanup.old_clicks')
def job_cleanup_old_clicks():
    """Archive clicks older than 90 days."""
    from api.payment_gateways.tracking.models import Click
    from django.utils import timezone
    from datetime import timedelta
    deleted, _ = Click.objects.filter(
        created_at__lte=timezone.now() - timedelta(days=90),
        is_converted=False, is_fraud=True
    ).delete()
    return {'deleted': deleted}


@shared_task(name='pg.cleanup.cache_flush')
def job_flush_stale_cache():
    """Flush stale cached data."""
    from api.payment_gateways.caching import payment_cache
    count = payment_cache.flush_all('pg:offers:')  # Flush offer lists
    return {'flushed': count}


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION JOBS
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, name='pg.notify.send')
def job_send_notification(self, user_id: int, template: str, context: dict):
    """Send push notification to user."""
    from api.payment_gateways.tasks import async_send_notification
    return async_send_notification(user_id, template, context)


@shared_task(name='pg.notify.low_balance_alerts')
def job_check_low_balance():
    """Alert advertisers with low balance."""
    from api.payment_gateways.publisher.models import AdvertiserProfile
    from api.payment_gateways.notifications_push import push_service
    from decimal import Decimal
    LOW_BALANCE_THRESHOLD = Decimal('50')
    for profile in AdvertiserProfile.objects.filter(status='active'):
        if profile.balance <= LOW_BALANCE_THRESHOLD:
            push_service.send_balance_low_alert(
                profile.user, profile.balance, LOW_BALANCE_THRESHOLD
            )
    return {'checked': AdvertiserProfile.objects.filter(status='active').count()}


# ══════════════════════════════════════════════════════════════════════════════
# RECONCILIATION JOBS
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(name='pg.recon.nightly')
def job_nightly_reconciliation():
    """Run nightly reconciliation for all gateways."""
    from api.payment_gateways.interactors import ReconciliationInteractor
    return ReconciliationInteractor().run_nightly()


@shared_task(name='pg.recon.single_gateway')
def job_reconcile_gateway(gateway_name: str, date_str: str):
    """Reconcile a single gateway for a specific date."""
    from api.payment_gateways.services.ReconciliationService import ReconciliationService
    from datetime import date
    target_date = date.fromisoformat(date_str)
    return ReconciliationService().reconcile(gateway_name, target_date)


# ══════════════════════════════════════════════════════════════════════════════
# CAP MANAGEMENT JOBS
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(name='pg.caps.reset_daily')
def job_reset_daily_caps():
    """Reset daily conversion caps at midnight."""
    from api.payment_gateways.offers.ConversionCapEngine import ConversionCapEngine
    return {'reactivated': ConversionCapEngine().reset_daily_caps()}


@shared_task(name='pg.caps.check_queues')
def job_check_queue_depths():
    """Alert if message queues are filling up."""
    from api.payment_gateways.tasks_cap import check_queue_depths
    return check_queue_depths()


# ══════════════════════════════════════════════════════════════════════════════
# JOB REGISTRY
# ══════════════════════════════════════════════════════════════════════════════
ALL_JOBS = [
    job_verify_deposit, job_expire_old_deposits, job_verify_all_pending,
    job_process_payout, job_process_all_approved_payouts, job_usdt_fastpay,
    job_approve_conversion, job_auto_approve_old_conversions, job_fire_postback,
    job_check_all_gateways, job_alert_gateway_failures,
    job_daily_analytics, job_update_offer_metrics, job_sync_exchange_rates,
    job_credit_wallet, job_pay_referral_commissions,
    job_cleanup_webhook_logs, job_cleanup_old_clicks, job_flush_stale_cache,
    job_send_notification, job_check_low_balance,
    job_nightly_reconciliation, job_reconcile_gateway,
    job_reset_daily_caps, job_check_queue_depths,
]
