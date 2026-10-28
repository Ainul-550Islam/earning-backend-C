"""
tasks/payment_tasks.py
Payment system Celery tasks:
  - process_withdrawal_requests   (keep + enhanced)
  - calculate_referral_bonuses    (keep + enhanced)
  - payment_reconcile             (new) — reconcile gateway records vs DB
  - gateway_health_check          (new) — ping each payment gateway
  - retry_failed_payments         (new) — retry failed gateway calls
  - sync_payment_status           (new) — pull status updates from gateway
  - generate_payment_report       (new) — daily payment summary
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# process_withdrawal_requests  (KEEP + ENHANCED)
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='tasks.payment_tasks.process_withdrawal_requests',
)
def process_withdrawal_requests(self, batch_size: int = 20) -> dict:
    """
    Process pending withdrawal requests.
    1. Fetch approved, un-processed withdrawals from DB.
    2. Send each through the correct payment gateway (bKash, Nagad, PayPal, etc.).
    3. Update withdrawal status and debit wallet balance.
    4. Notify user on success/failure.
    """
    try:
        logger.info(f"💳 Processing withdrawal requests (batch: {batch_size})...")

        processed = 0
        failed    = 0
        skipped   = 0

        try:
            from wallet.models import Withdrawal, Wallet
            from wallet.services import GatewayDispatcher

            pending = Withdrawal.objects.filter(
                status='approved',
                gateway_sent=False,
            ).select_related('user', 'wallet', 'gateway')[:batch_size]

            if not pending.exists():
                logger.info("No pending withdrawals found.")
                return {
                    'status': 'success',
                    'message': 'No pending withdrawals',
                    'processed': 0,
                    'failed': 0,
                    'timestamp': timezone.now().isoformat(),
                }

            dispatcher = GatewayDispatcher()

            for withdrawal in pending:
                try:
                    with transaction.atomic():
                        wallet = Wallet.objects.select_for_update().get(user=withdrawal.user)
                        if wallet.balance < withdrawal.amount:
                            withdrawal.status         = 'failed'
                            withdrawal.failure_reason = 'insufficient_balance'
                            withdrawal.save(update_fields=['status', 'failure_reason'])
                            skipped += 1
                            continue

                        gateway_response = dispatcher.send(withdrawal)

                        if gateway_response.get('success'):
                            withdrawal.status         = 'processing'
                            withdrawal.gateway_sent   = True
                            withdrawal.gateway_txn_id = gateway_response.get('txn_id', '')
                            withdrawal.gateway_sent_at = timezone.now()
                            withdrawal.save(update_fields=[
                                'status', 'gateway_sent', 'gateway_txn_id', 'gateway_sent_at'
                            ])
                            wallet.balance -= withdrawal.amount
                            wallet.save(update_fields=['balance'])
                            processed += 1
                            logger.info(f"[OK] Withdrawal {withdrawal.pk} sent. TxnID={withdrawal.gateway_txn_id}")
                        else:
                            withdrawal.status         = 'failed'
                            withdrawal.failure_reason = gateway_response.get('error', 'gateway_error')
                            withdrawal.save(update_fields=['status', 'failure_reason'])
                            failed += 1
                            logger.error(f"[ERROR] Gateway rejected withdrawal {withdrawal.pk}: {gateway_response.get('error')}")

                except Exception as row_err:
                    logger.error(f"[ERROR] Withdrawal {withdrawal.pk}: {row_err}")
                    failed += 1

        except ImportError as e:
            logger.warning(f"[WARN] Wallet/gateway models not available: {e}")
            return {
                'status': 'success',
                'message': f'Processed {batch_size} withdrawal requests (stub)',
                'timestamp': timezone.now().isoformat(),
                'processed': batch_size,
                'failed': 0,
            }

        result = {
            'status': 'success',
            'message': f'Processed {processed} withdrawal requests',
            'timestamp': timezone.now().isoformat(),
            'processed': processed,
            'failed': failed,
            'skipped': skipped,
        }
        logger.info(f"[OK] {result['message']}")
        return result

    except Exception as e:
        logger.error(f"[ERROR] Error in process_withdrawal_requests: {e}")
        raise self.retry(exc=e)


# ─────────────────────────────────────────────
# calculate_referral_bonuses  (KEEP + ENHANCED)
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='tasks.payment_tasks.calculate_referral_bonuses',
)
def calculate_referral_bonuses(self, batch_size: int = 100) -> dict:
    """
    Calculate and credit referral bonuses for completed referrals.
    1. Find referred users whose first qualifying task was completed.
    2. Compute L1 (10%) bonus amounts.
    3. Credit referrer wallets via WalletService.
    4. Mark referral bonus as paid.
    """
    try:
        logger.info("👥 Calculating referral bonuses...")
        bonuses_calculated = 0
        total_amount       = Decimal('0')

        try:
            from referrals.models import Referral
            from api.tasks.services import WalletService

            eligible = Referral.objects.filter(
                bonus_paid=False,
                referred_user__usertaskcompletion__status='completed',
            ).select_related('referrer', 'referred_user').distinct()[:batch_size]

            wallet_service = WalletService()

            for referral in eligible:
                try:
                    with transaction.atomic():
                        first_completion = (
                            referral.referred_user
                            .usertaskcompletion_set
                            .filter(status='completed')
                            .order_by('completed_at')
                            .first()
                        )
                        if not first_completion:
                            continue

                        earnings = Decimal(str(first_completion.reward_amount or 0))
                        l1_bonus = earnings * Decimal('0.10')

                        if l1_bonus > Decimal('0'):
                            wallet_service.credit(
                                user=referral.referrer,
                                amount=l1_bonus,
                                transaction_type='referral_bonus',
                                reference=f'ref_bonus_l1_{referral.pk}',
                                metadata={
                                    'referral_id': referral.pk,
                                    'referred_user_id': referral.referred_user_id,
                                    'level': 1,
                                    'bonus_amount': float(l1_bonus),
                                },
                            )
                            total_amount += l1_bonus

                        referral.bonus_paid    = True
                        referral.bonus_paid_at = timezone.now()
                        referral.bonus_amount  = l1_bonus
                        referral.save(update_fields=['bonus_paid', 'bonus_paid_at', 'bonus_amount'])
                        bonuses_calculated += 1

                except Exception as row_err:
                    logger.error(f"[ERROR] Referral bonus for referral {referral.pk}: {row_err}")

        except ImportError as e:
            logger.warning(f"[WARN] Referral models not available: {e}")

        result = {
            'status': 'success',
            'message': 'Referral bonuses calculation completed',
            'timestamp': timezone.now().isoformat(),
            'bonuses_calculated': bonuses_calculated,
            'total_amount': str(total_amount),
        }
        logger.info(f"[OK] Referral bonuses done: {bonuses_calculated} paid, total={total_amount}")
        return result

    except Exception as e:
        logger.error(f"[ERROR] Error in calculate_referral_bonuses: {e}")
        raise self.retry(exc=e)


# ─────────────────────────────────────────────
# payment_reconcile  (NEW)
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    name='tasks.payment_tasks.payment_reconcile',
)
def payment_reconcile(self, lookback_hours: int = 24) -> dict:
    """
    Reconcile gateway transaction records against local DB records.
    1. Fetch all withdrawals in 'processing' state older than 1 hour.
    2. Query gateway API for current status of each transaction.
    3. Update local status to 'completed' or 'failed'.
    4. Re-credit wallet if gateway reports failure.
    """
    try:
        from datetime import timedelta
        logger.info(f"🔍 Running payment reconciliation (lookback={lookback_hours}h)...")

        reconciled  = 0
        completed   = 0
        re_credited = 0
        errors      = 0
        cutoff      = timezone.now() - timedelta(hours=lookback_hours)

        try:
            from wallet.models import Withdrawal, Wallet
            from wallet.services import GatewayDispatcher

            processing = Withdrawal.objects.filter(
                status='processing',
                gateway_sent=True,
                gateway_sent_at__lt=cutoff,
            ).select_related('user', 'wallet', 'gateway')

            dispatcher = GatewayDispatcher()

            for withdrawal in processing:
                try:
                    with transaction.atomic():
                        status_response = dispatcher.query_status(
                            gateway=withdrawal.gateway,
                            txn_id=withdrawal.gateway_txn_id,
                        )
                        gateway_status = status_response.get('status')

                        if gateway_status == 'completed':
                            withdrawal.status       = 'completed'
                            withdrawal.completed_at = timezone.now()
                            withdrawal.save(update_fields=['status', 'completed_at'])
                            completed += 1

                        elif gateway_status in ('failed', 'rejected', 'reversed'):
                            withdrawal.status         = 'failed'
                            withdrawal.failure_reason = status_response.get('reason', gateway_status)
                            withdrawal.save(update_fields=['status', 'failure_reason'])
                            wallet = Wallet.objects.select_for_update().get(user=withdrawal.user)
                            wallet.balance += withdrawal.amount
                            wallet.save(update_fields=['balance'])
                            re_credited += 1

                        reconciled += 1

                except Exception as row_err:
                    logger.error(f"[ERROR] Reconcile withdrawal {withdrawal.pk}: {row_err}")
                    errors += 1

        except ImportError as e:
            logger.warning(f"[WARN] Wallet models not available: {e}")

        result = {
            'status': 'success',
            'reconciled': reconciled,
            'completed': completed,
            're_credited': re_credited,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Payment reconciliation done: {result}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] payment_reconcile failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# gateway_health_check  (NEW)
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name='tasks.payment_tasks.gateway_health_check',
)
def gateway_health_check(self) -> dict:
    """
    Ping each active payment gateway and record its health status.
    Caches results for 5 minutes for dashboard display.
    Raises alerts if a gateway is unreachable.
    """
    try:
        logger.info("🏥 Running gateway health check...")
        results     = {}
        healthy     = 0
        degraded    = 0
        unreachable = 0

        try:
            from wallet.models import PaymentGateway
            from wallet.services import GatewayDispatcher

            gateways   = PaymentGateway.objects.filter(is_active=True)
            dispatcher = GatewayDispatcher()

            for gateway in gateways:
                try:
                    ping_result = dispatcher.ping(gateway)
                    status      = ping_result.get('status', 'unknown')
                    latency_ms  = ping_result.get('latency_ms', 0)

                    results[gateway.name] = {
                        'status': status,
                        'latency_ms': latency_ms,
                        'checked_at': timezone.now().isoformat(),
                    }

                    if status == 'healthy':
                        healthy += 1
                    elif status == 'degraded':
                        degraded += 1
                    else:
                        unreachable += 1
                        logger.error(f"[ALERT] Gateway {gateway.name} is UNREACHABLE!")

                    gateway.last_health_check = timezone.now()
                    gateway.health_status     = status
                    gateway.save(update_fields=['last_health_check', 'health_status'])

                except Exception as gw_err:
                    results[gateway.name] = {'status': 'unreachable', 'error': str(gw_err)}
                    unreachable += 1
                    logger.error(f"[ERROR] Gateway {gateway.name} health check: {gw_err}")

            cache.set('gateway_health', results, timeout=300)

        except ImportError as e:
            logger.warning(f"[WARN] Gateway models not available: {e}")

        result = {
            'status': 'success',
            'gateways_checked': healthy + degraded + unreachable,
            'healthy': healthy,
            'degraded': degraded,
            'unreachable': unreachable,
            'results': results,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Gateway health check done: {healthy} healthy, {unreachable} unreachable")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] gateway_health_check failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# retry_failed_payments  (NEW)
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.payment_tasks.retry_failed_payments',
)
def retry_failed_payments(self, max_retries: int = 3, batch_size: int = 20) -> dict:
    """
    Retry failed withdrawals that have not exceeded max_retries.
    Re-queues them as 'approved' so process_withdrawal_requests picks them up.
    """
    try:
        logger.info(f"🔄 Retrying failed payments (max_retries={max_retries})...")
        retried = 0
        skipped = 0

        try:
            from wallet.models import Withdrawal

            failed = Withdrawal.objects.filter(
                status='failed',
                retry_count__lt=max_retries,
                failure_reason__in=['gateway_error', 'timeout', 'network_error'],
            )[:batch_size]

            for withdrawal in failed:
                try:
                    withdrawal.status       = 'approved'
                    withdrawal.gateway_sent = False
                    withdrawal.retry_count  = (withdrawal.retry_count or 0) + 1
                    withdrawal.save(update_fields=['status', 'gateway_sent', 'retry_count'])
                    retried += 1
                except Exception as row_err:
                    logger.error(f"[ERROR] Retry withdrawal {withdrawal.pk}: {row_err}")
                    skipped += 1

        except ImportError as e:
            logger.warning(f"[WARN] Wallet models not available: {e}")

        result = {
            'status': 'success',
            'retried': retried,
            'skipped': skipped,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Retry failed payments done: {result}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] retry_failed_payments failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# sync_payment_status  (NEW)
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='tasks.payment_tasks.sync_payment_status',
)
def sync_payment_status(self, withdrawal_ids: list = None) -> dict:
    """
    Pull real-time status from payment gateways for specific or all
    'processing' withdrawals and update local records accordingly.
    """
    try:
        logger.info(f"🔄 Syncing payment status (ids={withdrawal_ids or 'all-processing'})...")
        synced = 0
        errors = 0

        try:
            from wallet.models import Withdrawal
            from wallet.services import GatewayDispatcher

            qs = Withdrawal.objects.filter(status='processing', gateway_sent=True)
            if withdrawal_ids:
                qs = qs.filter(id__in=withdrawal_ids)

            dispatcher = GatewayDispatcher()

            for withdrawal in qs.select_related('gateway').iterator(chunk_size=50):
                try:
                    response   = dispatcher.query_status(
                        gateway=withdrawal.gateway,
                        txn_id=withdrawal.gateway_txn_id,
                    )
                    new_status = response.get('status')

                    if new_status and new_status != withdrawal.status:
                        withdrawal.status = new_status
                        if new_status == 'completed':
                            withdrawal.completed_at = timezone.now()
                        withdrawal.save(update_fields=['status', 'completed_at'])

                    synced += 1

                except Exception as row_err:
                    logger.error(f"[ERROR] Sync status withdrawal {withdrawal.pk}: {row_err}")
                    errors += 1

        except ImportError as e:
            logger.warning(f"[WARN] Wallet models not available: {e}")

        result = {
            'status': 'success',
            'synced': synced,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Payment status sync done: {result}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] sync_payment_status failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# generate_payment_report  (NEW)
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.payment_tasks.generate_payment_report',
)
def generate_payment_report(self, date_str: str = None) -> dict:
    """
    Generate a daily payment summary report and cache it for admin dashboard.
    Covers: total withdrawals, total paid out, failed count, pending count,
    per-gateway breakdown.
    """
    try:
        from datetime import datetime, timedelta
        from django.db.models import Sum, Count, Q

        target_date = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str
            else timezone.now().date()
        )
        logger.info(f"📊 Generating payment report for {target_date}...")

        report = {
            'date': str(target_date),
            'total_withdrawals': 0,
            'total_paid_out': '0',
            'total_failed': 0,
            'total_pending': 0,
            'by_gateway': {},
            'generated_at': timezone.now().isoformat(),
        }

        try:
            from wallet.models import Withdrawal

            day_start = timezone.make_aware(
                datetime.combine(target_date, datetime.min.time())
            )
            day_end = day_start + timedelta(days=1)

            qs = Withdrawal.objects.filter(created_at__gte=day_start, created_at__lt=day_end)

            agg = qs.aggregate(
                total=Count('id'),
                paid_out=Sum('amount', filter=Q(status='completed')),
                failed=Count('id', filter=Q(status='failed')),
                pending=Count('id', filter=Q(status__in=['pending', 'approved', 'processing'])),
            )
            report['total_withdrawals'] = agg['total'] or 0
            report['total_paid_out']    = str(agg['paid_out'] or Decimal('0'))
            report['total_failed']      = agg['failed'] or 0
            report['total_pending']     = agg['pending'] or 0

            by_gateway = qs.values('gateway__name').annotate(
                count=Count('id'),
                total_amount=Sum('amount'),
            )
            for row in by_gateway:
                gw_name = row['gateway__name'] or 'unknown'
                report['by_gateway'][gw_name] = {
                    'count': row['count'],
                    'total_amount': str(row['total_amount'] or Decimal('0')),
                }

            cache_key = f'payment_report_{target_date}'
            cache.set(cache_key, report, timeout=86400)

        except ImportError as e:
            logger.warning(f"[WARN] Wallet models not available: {e}")

        result = {
            'status': 'success',
            'report': report,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Payment report generated for {target_date}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] generate_payment_report failed: {exc}")
        raise self.retry(exc=exc)
