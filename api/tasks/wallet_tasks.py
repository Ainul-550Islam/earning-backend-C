"""
tasks/wallet_tasks.py
Wallet system Celery tasks:
  - balance_sync
  - process_withdrawal_batch
  - detect_suspicious_transactions
  - recalculate_wallet_totals
"""
from datetime import timedelta
from django.db import models
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from api.wallet.models_webhook import WalletWebhookLog
from api.wallet.models.withdrawal import UserPaymentMethod

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# balance_sync
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name='tasks.wallet_tasks.balance_sync',
)
def balance_sync(self, user_ids: list = None, batch_size: int = 100) -> dict:
    """
    Recalculate and sync wallet balances by summing WalletTransaction rows.
    If user_ids is provided, only sync those accounts; otherwise sync all.
    Prevents balance drift caused by partial failures in transaction chains.
    """
    try:
        logger.info(f"💼 Starting balance sync (user_ids={user_ids}, batch={batch_size})...")
        synced  = 0
        skipped = 0
        errors  = 0

        try:
            from wallet.models import Wallet, WalletTransaction
            from django.db.models import Sum, Q

            qs = Wallet.objects.all()
            if user_ids:
                qs = qs.filter(user_id__in=user_ids)

            for wallet in qs.iterator(chunk_size=batch_size):
                try:
                    with transaction.atomic():
                        # Sum completed credit transactions
                        credits = WalletTransaction.objects.filter(
                            wallet=wallet,
                            transaction_type__in=['credit', 'task_reward', 'referral_commission', 'bonus'],
                            status='completed',
                        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

                        # Sum completed debit transactions
                        debits = WalletTransaction.objects.filter(
                            wallet=wallet,
                            transaction_type__in=['debit', 'withdrawal', 'fee'],
                            status='completed',
                        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

                        expected = credits - debits
                        if wallet.balance != expected:
                            logger.warning(
                                f"[DRIFT] User {wallet.user_id}: "
                                f"stored={wallet.balance} expected={expected}. Correcting."
                            )
                            wallet.balance = expected
                            wallet.save(update_fields=['balance'])

                        synced += 1
                except Exception as row_err:
                    logger.error(f"[ERROR] Wallet sync for user {wallet.user_id}: {row_err}")
                    errors += 1

        except ImportError as e:
            logger.warning(f"[WARN] Wallet models not available: {e}")

        result = {
            'status': 'success',
            'synced': synced,
            'skipped': skipped,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Balance sync done: {result}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] balance_sync failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# process_withdrawal_batch
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    name='tasks.wallet_tasks.process_withdrawal_batch',
)
def process_withdrawal_batch(self, batch_size: int = 20) -> dict:
    """
    Process a batch of approved, pending withdrawal requests.
    1. Fetch approved withdrawals not yet sent to gateway.
    2. Send to payment gateway.
    3. Update withdrawal status.
    4. Debit wallet.
    """
    try:
        logger.info(f"🏧 Processing withdrawal batch (size={batch_size})...")
        processed = 0
        failed    = 0

        try:
            from wallet.models import Withdrawal
            from api.tasks.services import WalletService

            pending = Withdrawal.objects.filter(
                status='approved',
                gateway_sent=False,
            ).select_related('user', 'wallet')[:batch_size]

            for withdrawal in pending:
                try:
                    with transaction.atomic():
                        wallet_service = WalletService()
                        success = wallet_service.process_withdrawal(withdrawal)
                        if success:
                            processed += 1
                        else:
                            failed += 1
                except Exception as row_err:
                    logger.error(f"[ERROR] Withdrawal {withdrawal.pk}: {row_err}")
                    failed += 1

        except ImportError as e:
            logger.warning(f"[WARN] Wallet withdrawal models not available: {e}")

        result = {
            'status': 'success',
            'processed': processed,
            'failed': failed,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Withdrawal batch done: {result}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] process_withdrawal_batch failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# detect_suspicious_transactions
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.wallet_tasks.detect_suspicious_transactions',
)
def detect_suspicious_transactions(self, lookback_hours: int = 1) -> dict:
    """
    Flag wallet transactions that match suspicious patterns:
    - Large single credits (> threshold)
    - Rapid repeated credits (>N in X minutes)
    - Credits immediately followed by withdrawal
    """
    try:
        from datetime import timedelta
        logger.info(f"🔍 Detecting suspicious transactions (lookback={lookback_hours}h)...")

        flagged = 0
        window  = timezone.now() - timedelta(hours=lookback_hours)

        LARGE_CREDIT_THRESHOLD = Decimal('500')
        RAPID_COUNT_THRESHOLD  = 10
        RAPID_WINDOW_MINUTES   = 10

        try:
            from wallet.models import WalletTransaction, SuspiciousTransactionFlag

            recent = WalletTransaction.objects.filter(
                created_at__gte=window,
                transaction_type='task_reward',
                is_suspicious_checked=False,
            ).select_related('user')

            for txn in recent:
                reasons = []

                # Rule 1: large single credit
                if txn.amount and Decimal(str(txn.amount)) > LARGE_CREDIT_THRESHOLD:
                    reasons.append(f'large_credit:{txn.amount}')

                # Rule 2: rapid repeated credits
                rapid_window = txn.created_at - timedelta(minutes=RAPID_WINDOW_MINUTES)
                rapid_count = WalletTransaction.objects.filter(
                    user=txn.user,
                    transaction_type='task_reward',
                    created_at__gte=rapid_window,
                    created_at__lte=txn.created_at,
                ).count()
                if rapid_count > RAPID_COUNT_THRESHOLD:
                    reasons.append(f'rapid_credit_count:{rapid_count}')

                if reasons:
                    SuspiciousTransactionFlag.objects.get_or_create(
                        transaction=txn,
                        defaults={
                            'reasons': reasons,
                            'flagged_at': timezone.now(),
                            'status': 'pending_review',
                        },
                    )
                    flagged += 1

                txn.is_suspicious_checked = True
                txn.save(update_fields=['is_suspicious_checked'])

        except ImportError as e:
            logger.warning(f"[WARN] Wallet models not available: {e}")

        result = {
            'status': 'success',
            'flagged': flagged,
            'lookback_hours': lookback_hours,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Suspicious transaction detection done: {result}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] detect_suspicious_transactions failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# recalculate_wallet_totals
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.wallet_tasks.recalculate_wallet_totals',
)
def recalculate_wallet_totals(self) -> dict:
    """
    Compute platform-wide wallet totals and store in cache for admin dashboard.
    """
    try:
        logger.info("📈 Recalculating wallet totals...")
        totals = {}

        try:
            from wallet.models import Wallet, WalletTransaction
            from django.db.models import Sum, Count

            totals['total_wallets']      = Wallet.objects.count()
            totals['total_balance']      = str(
                Wallet.objects.aggregate(total=Sum('balance'))['total'] or Decimal('0')
            )
            totals['total_paid_out']     = str(
                WalletTransaction.objects.filter(
                    transaction_type='withdrawal', status='completed'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            )
            totals['total_task_rewards'] = str(
                WalletTransaction.objects.filter(
                    transaction_type='task_reward', status='completed'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            )

            cache.set('wallet_platform_totals', totals, timeout=1800)
            logger.info(f"[OK] Wallet totals cached: {totals}")

        except ImportError as e:
            logger.warning(f"[WARN] Wallet models not available: {e}")

        return {
            'status': 'success',
            'totals': totals,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] recalculate_wallet_totals failed: {exc}")
        raise self.retry(exc=exc)


# ══════════════════════════════════════════════════════════════
# MIGRATED FROM: api/wallet/tasks.py (original code preserved)
# ══════════════════════════════════════════════════════════════
def task_with_retry(max_retries=3, default_retry_delay=60):
    """
    Decorator for adding automatic retry to tasks
    """
    def decorator(task_func):
        def wrapper(*args, **kwargs):
            task_name = task_func.__name__
            task_id = f"{task_name}_{timezone.now().timestamp()}"
            
            # Check circuit breaker
            circuit_key = f"circuit_breaker_{task_name}"
            if cache.get(circuit_key) == 'open':
                logger.warning(f"Circuit breaker open for {task_name}, skipping")
                return {"status": "skipped", "reason": "circuit_breaker_open"}
            
            retry_count = 0
            while retry_count < max_retries:
                try:
                    result = task_func(*args, **kwargs)
                    # Success - reset circuit breaker
                    cache.delete(circuit_key)
                    return result
                    
                except Exception as e:
                    retry_count += 1
                    logger.error(
                        f"Task {task_name} failed (attempt {retry_count}/{max_retries}): {e}",
                        exc_info=True
                    )
                    
                    if retry_count == max_retries:
                        # Trip circuit breaker
                        cache.set(circuit_key, 'open', 300)  # 5 minutes
                        logger.error(f"Circuit breaker tripped for {task_name}")
                        return {
                            "status": "failed",
                            "error": str(e),
                            "retries": retry_count
                        }
                    
                    # Exponential backoff
                    delay = default_retry_delay * (2 ** (retry_count - 1))
                    timezone.sleep(min(delay, 300))  # Max 5 minutes
            
            return {"status": "max_retries_exceeded"}
        return wrapper
    return decorator


# ============================================
# SCHEDULED TASKS (Android থেকে কল করার জন্য API তৈরি হবে)
# ============================================

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
@task_with_retry(max_retries=3)
def expire_bonus_balances(self):
    """
    টাস্ক: মেয়াদোত্তীর্ণ বোনাস ব্যালেন্স expire করা
    Android API: POST /api/wallet/tasks/expire-bonus/
    """
    try:
        expired_count = 0
        refunded_amount = Decimal('0')
        
        now = timezone.now()
        wallets_to_expire = Wallet.objects.filter(
            bonus_balance__gt=0,
            bonus_expires_at__lt=now
        ).select_for_update()  # Prevent race conditions
        
        with transaction.atomic():
            for wallet in wallets_to_expire:
                if wallet.bonus_balance > 0:
                    # Create expiration transaction
                    trans = WalletTransaction.objects.create(
                        wallet=wallet,
                        type='bonus',
                        amount=-wallet.bonus_balance,  # Negative for expiration
                        status='approved',
                        description=f"Bonus expired (was valid until {wallet.bonus_expires_at})",
                        balance_before=wallet.current_balance,
                        created_by=None,  # System action
                        approved_by=None
                    )
                    
                    # Update wallet
                    refunded_amount += wallet.bonus_balance
                    wallet.bonus_balance = Decimal('0')
                    wallet.bonus_expires_at = None
                    wallet.save()
                    
                    trans.balance_after = wallet.current_balance
                    trans.save()
                    
                    expired_count += 1
        
        logger.info(f"Expired {expired_count} bonus wallets, total: {refunded_amount}")
        
        return {
            "status": "success",
            "expired_count": expired_count,
            "refunded_amount": float(refunded_amount),
            "timestamp": now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to expire bonus balances: {e}", exc_info=True)
        raise


@shared_task(bind=True, max_retries=3)
@task_with_retry(max_retries=3)
def process_pending_withdrawals(self):
    """
    টাস্ক: পেন্ডিং উইথড্রয়াল প্রসেস করা
    Android API: POST /api/wallet/tasks/process-withdrawals/
    """
    try:
        processed_count = 0
        failed_count = 0
        
        # Get pending withdrawals
        pending_withdrawals = Withdrawal.objects.filter(
            status='pending'
        ).select_related(
            'wallet', 'payment_method', 'transaction'
        )[:50]  # Process in batches
        
        if not pending_withdrawals.exists():
            return {
                "status": "success",
                "message": "No pending withdrawals to process",
                "processed": 0,
                "failed": 0
            }
        
        with transaction.atomic():
            for withdrawal in pending_withdrawals:
                try:
                    # Simulate payment gateway processing
                    with CircuitBreaker(failure_threshold=3, recovery_timeout=300) as cb:
                        # Update status
                        withdrawal.status = 'processing'
                        withdrawal.save()
                        
                        # Here you would integrate with actual payment gateway
                        # For example: bKash, Nagad, etc.
                        timezone.sleep(1)  # Simulate processing time
                        
                        # Mark as completed (simulate success)
                        withdrawal.status = 'completed'
                        withdrawal.processed_at = timezone.now()
                        
                        # Update transaction
                        withdrawal.transaction.status = 'completed'
                        withdrawal.transaction.approved_at = timezone.now()
                        
                        withdrawal.save()
                        withdrawal.transaction.save()
                        
                        logger.info(f"Processed withdrawal {withdrawal.id}")
                        processed_count += 1
                        
                except ConnectionError:
                    # Circuit breaker open
                    withdrawal.status = 'failed'
                    withdrawal.save()
                    failed_count += 1
                    logger.warning(f"Withdrawal {withdrawal.id} failed due to service outage")
                    
                except Exception as e:
                    withdrawal.status = 'failed'
                    withdrawal.save()
                    failed_count += 1
                    logger.error(f"Failed to process withdrawal {withdrawal.id}: {e}")
        
        return {
            "status": "success",
            "processed": processed_count,
            "failed": failed_count,
            "total": len(pending_withdrawals)
        }
        
    except Exception as e:
        logger.error(f"Batch withdrawal processing failed: {e}", exc_info=True)
        raise


@shared_task(bind=True, max_retries=3)
@task_with_retry(max_retries=3)
def cleanup_old_webhook_logs(self, days_to_keep=30):
    """
    টাস্ক: পুরাতন ওয়েবহুক লগ ডিলিট করা
    Android API: POST /api/wallet/tasks/cleanup-logs/?days=30
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Get count before deletion
        total_count = WalletWebhookLog.objects.count()
        to_delete = WalletWebhookLog.objects.filter(received_at__lt=cutoff_date)
        delete_count = to_delete.count()
        
        # Delete in chunks to avoid large transactions
        chunk_size = 1000
        deleted_total = 0
        
        while True:
            chunk = to_delete[:chunk_size]
            if not chunk.exists():
                break
            
            ids = list(chunk.values_list('id', flat=True))
            deleted, _ = WalletWebhookLog.objects.filter(id__in=ids).delete()
            deleted_total += deleted
            
            if deleted < chunk_size:
                break
        
        remaining = total_count - deleted_total
        
        logger.info(f"Cleaned up {deleted_total} old webhook logs (older than {days_to_keep} days)")
        
        return {
            "status": "success",
            "deleted": deleted_total,
            "remaining": remaining,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup webhook logs: {e}", exc_info=True)
        raise


@shared_task(bind=True, max_retries=3)
@task_with_retry(max_retries=3)
def generate_wallet_reports(self, report_date=None):
    """
    টাস্ক: ওয়ালেট রিপোর্ট জেনারেট করা
    Android API: POST /api/wallet/tasks/generate-report/?date=2024-01-15
    """
    try:
        if not report_date:
            report_date = timezone.now().date()
        else:
            from django.utils.dateparse import parse_date
            report_date = parse_date(report_date) if isinstance(report_date, str) else report_date
        
        start_date = timezone.datetime.combine(report_date, timezone.datetime.min.time())
        end_date = timezone.datetime.combine(report_date, timezone.datetime.max.time())
        
        # Collect report data
        report_data = {
            "report_date": report_date.isoformat(),
            "generated_at": timezone.now().isoformat(),
            "summary": {},
            "transactions": [],
            "withdrawals": []
        }
        
        # Wallet summary
        total_wallets = Wallet.objects.count()
        active_wallets = Wallet.objects.filter(
            transactions__created_at__date=report_date
        ).distinct().count()
        
        total_balance = Wallet.objects.aggregate(
            total=models.Sum('current_balance')
        )['total'] or Decimal('0')
        
        total_pending = Wallet.objects.aggregate(
            total=models.Sum('pending_balance')
        )['total'] or Decimal('0')
        
        report_data["summary"] = {
            "total_wallets": total_wallets,
            "active_today": active_wallets,
            "total_balance": float(total_balance),
            "total_pending": float(total_pending)
        }
        
        # Daily transactions
        daily_transactions = WalletTransaction.objects.filter(
            created_at__date=report_date,
            status='approved'
        ).select_related('wallet', 'wallet__user')
        
        trans_summary = daily_transactions.aggregate(
            total_credit=models.Sum('amount', filter=models.Q(amount__gt=0)),
            total_debit=models.Sum('amount', filter=models.Q(amount__lt=0)),
            count=models.Count('id')
        )
        
        report_data["transactions"] = {
            "total_credit": float(trans_summary['total_credit'] or Decimal('0')),
            "total_debit": float(abs(trans_summary['total_debit'] or Decimal('0'))),
            "count": trans_summary['count']
        }
        
        # Daily withdrawals
        daily_withdrawals = Withdrawal.objects.filter(
            created_at__date=report_date
        ).select_related('user', 'payment_method')
        
        withdrawal_summary = daily_withdrawals.aggregate(
            total_amount=models.Sum('amount'),
            total_fee=models.Sum('fee'),
            count=models.Count('id')
        )
        
        report_data["withdrawals"] = {
            "total_amount": float(withdrawal_summary['total_amount'] or Decimal('0')),
            "total_fee": float(withdrawal_summary['total_fee'] or Decimal('0')),
            "count": withdrawal_summary['count']
        }
        
        # Cache the report
        cache_key = f"wallet_report_{report_date}"
        cache.set(cache_key, report_data, 3600)  # Cache for 1 hour
        
        logger.info(f"Generated wallet report for {report_date}")
        
        return {
            "status": "success",
            "report_date": report_date.isoformat(),
            "data": report_data
        }
        
    except Exception as e:
        logger.error(f"Failed to generate wallet report: {e}", exc_info=True)
        raise


@shared_task(bind=True, max_retries=3)
@task_with_retry(max_retries=3)
def sync_payment_gateway_status(self):
    """
    টাস্ক: পেমেন্ট গেটওয়েতে পেন্ডিং ট্রানজেকশন sync করা
    Android API: POST /api/wallet/tasks/sync-payments/
    """
    try:
        synced_count = 0
        failed_count = 0
        
        # Find transactions that might need syncing
        pending_transactions = WalletTransaction.objects.filter(
            status='pending',
            type__in=['withdrawal', 'earning'],
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).select_related('wallet')[:100]
        
        for transaction in pending_transactions:
            try:
                # Check with payment gateway (simulated)
                # In real implementation, this would call bKash/Nagad API
                with CircuitBreaker(failure_threshold=3, recovery_timeout=300) as cb:
                    gateway_status = self._check_gateway_status(transaction)
                    
                    if gateway_status == 'completed':
                        transaction.approve(approved_by=None)
                        synced_count += 1
                    elif gateway_status == 'failed':
                        transaction.reject(reason="Payment gateway reported failure")
                        failed_count += 1
                    # If still pending, leave as is
                    
            except ConnectionError:
                logger.warning(f"Gateway unavailable for transaction {transaction.id}")
            except Exception as e:
                logger.error(f"Failed to sync transaction {transaction.id}: {e}")
                failed_count += 1
        
        return {
            "status": "success",
            "synced": synced_count,
            "failed": failed_count,
            "total_checked": len(pending_transactions)
        }
        
    except Exception as e:
        logger.error(f"Payment gateway sync failed: {e}", exc_info=True)
        raise
    
    def _check_gateway_status(self, transaction):
        """
        Simulated gateway status check
        In production, replace with actual API calls
        """
        # Simulate API call
        import random
        timezone.sleep(0.5)
        
        statuses = ['completed', 'failed', 'pending']
        weights = [0.7, 0.1, 0.2]  # 70% completed, 10% failed, 20% pending
        
        return random.choices(statuses, weights=weights)[0]


# ============================================
# USER-FACING TASKS (Android থেকে সরাসরি কল করা যাবে)
# ============================================

@shared_task(bind=True, max_retries=3)
@task_with_retry(max_retries=3)
def user_request_withdrawal(self, user_id, amount, payment_method_id):
    """
    টাস্ক: ইউজারের জন্য উইথড্রয়াল রিকোয়েস্ট তৈরি
    Android API: POST /api/wallet/withdraw/request/
    """
    try:
        user = User.objects.get(id=user_id)
        payment_method = UserPaymentMethod.objects.get(
            id=payment_method_id,
            user=user,
            is_verified=True
        )
        
        # Get user's wallet
        wallet, created = Wallet.objects.get_or_create(
            user=user,
            defaults={'currency': 'BDT'}
        )
        
        # Validate
        if wallet.is_locked:
            return {
                "status": "error",
                "code": "WALLET_LOCKED",
                "message": "Your wallet is locked. Please contact support."
            }
        
        if amount > wallet.available_balance:
            return {
                "status": "error",
                "code": "INSUFFICIENT_BALANCE",
                "message": f"Insufficient balance. Available: {wallet.available_balance}"
            }
        
        # Create withdrawal with transaction safety
        with transaction.atomic():
            # Create debit transaction
            trans = WalletTransaction.objects.create(
                wallet=wallet,
                type='withdrawal',
                amount=-amount,
                status='pending',
                description=f"Withdrawal to {payment_method.get_method_type_display()}",
                balance_before=wallet.current_balance,
                created_by=user
            )
            
            # Update wallet
            wallet.current_balance -= amount
            wallet.total_withdrawn += amount
            wallet.save()
            
            trans.balance_after = wallet.current_balance
            trans.save()
            
            # Calculate fee
            fee = max(amount * Decimal('0.015'), Decimal('10'))
            net_amount = amount - fee
            
            # Create withdrawal record
            withdrawal = Withdrawal.objects.create(
                user=user,
                wallet=wallet,
                payment_method=payment_method,
                amount=amount,
                fee=fee,
                net_amount=net_amount,
                status='pending',
                transaction=trans
            )
        
        logger.info(f"Withdrawal request created: {user.username} - {amount}")
        
        return {
            "status": "success",
            "withdrawal_id": str(withdrawal.withdrawal_id),
            "amount": float(amount),
            "fee": float(fee),
            "net_amount": float(net_amount),
            "estimated_processing": "24-48 hours"
        }
        
    except UserPaymentMethod.DoesNotExist:
        return {
            "status": "error",
            "code": "INVALID_PAYMENT_METHOD",
            "message": "Payment method not found or not verified"
        }
    except Exception as e:
        logger.error(f"Withdrawal request failed for user {user_id}: {e}", exc_info=True)
        return {
            "status": "error",
            "code": "INTERNAL_ERROR",
            "message": "Failed to process withdrawal request"
        }


@shared_task(bind=True, max_retries=3)
@task_with_retry(max_retries=3)
def user_add_funds(self, user_id, amount, reference_id, source='manual'):
    """
    টাস্ক: ইউজারের ওয়ালেটে ফান্ড যোগ করা
    Android API: POST /api/wallet/funds/add/
    """
    try:
        user = User.objects.get(id=user_id)
        
        # Get user's wallet
        wallet, created = Wallet.objects.get_or_create(
            user=user,
            defaults={'currency': 'BDT'}
        )
        
        if wallet.is_locked:
            return {
                "status": "error",
                "code": "WALLET_LOCKED",
                "message": "Your wallet is locked. Please contact support."
            }
        
        # Create credit transaction
        with transaction.atomic():
            trans = WalletTransaction.objects.create(
                wallet=wallet,
                type='earning',
                amount=amount,
                status='approved',
                reference_id=reference_id,
                reference_type=source,
                description=f"Funds added via {source}",
                balance_before=wallet.current_balance,
                created_by=user,
                approved_by=user
            )
            
            # Update wallet
            wallet.current_balance += amount
            wallet.total_earned += amount
            wallet.save()
            
            trans.balance_after = wallet.current_balance
            trans.save()
        
        logger.info(f"Funds added: {user.username} - {amount} via {source}")
        
        return {
            "status": "success",
            "new_balance": float(wallet.current_balance),
            "transaction_id": str(trans.transaction_id),
            "added_amount": float(amount)
        }
        
    except Exception as e:
        logger.error(f"Add funds failed for user {user_id}: {e}", exc_info=True)
        return {
            "status": "error",
            "code": "INTERNAL_ERROR",
            "message": "Failed to add funds"
        }


@shared_task(bind=True, max_retries=3)
def send_wallet_notification(self, user_id, notification_type, data):
    """
    টাস্ক: ওয়ালেট নোটিফিকেশন পাঠানো (Email/SMS/Push)
    Android API: POST /api/wallet/notifications/send/
    """
    try:
        user = User.objects.get(id=user_id)
        
        # Prepare notification based on type
        notifications = {
            'low_balance': {
                'subject': 'Low Wallet Balance Alert',
                'message': f'Your wallet balance is low: {data.get("balance", 0)}'
            },
            'withdrawal_success': {
                'subject': 'Withdrawal Successful',
                'message': f'Your withdrawal of {data.get("amount", 0)} has been processed.'
            },
            'withdrawal_failed': {
                'subject': 'Withdrawal Failed',
                'message': f'Your withdrawal of {data.get("amount", 0)} failed. Reason: {data.get("reason", "Unknown")}'
            },
            'bonus_added': {
                'subject': 'Bonus Added to Your Wallet',
                'message': f'You received a bonus of {data.get("amount", 0)}. Valid until {data.get("expires", "N/A")}'
            }
        }
        
        notification = notifications.get(notification_type, {
            'subject': 'Wallet Notification',
            'message': str(data)
        })
        
        # Here you would integrate with your notification system
        # For example: send email, SMS, push notification
        
        # Simulate sending
        timezone.sleep(0.5)
        
        logger.info(f"Sent {notification_type} notification to {user.email}")
        
        return {
            "status": "success",
            "user_id": user_id,
            "notification_type": notification_type,
            "sent_at": timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to send notification to user {user_id}: {e}")
        return {
            "status": "error",
            "message": "Failed to send notification"
        }
