# api/payment_gateways/integration_system/sync_manager.py
# Data conflict resolver — handles sync conflicts between payment_gateways and external apps

import logging
from decimal import Decimal
from typing import Optional, Tuple, Any
from django.utils import timezone
from .integ_exceptions import SyncConflictError

logger = logging.getLogger(__name__)


class SyncManager:
    """
    Resolves data conflicts when payment_gateways and external apps
    have different versions of the same data.

    Conflict scenarios:
        1. Double credit: Deposit credited twice (webhook retry)
        2. Balance mismatch: payment_gateways balance ≠ api.wallet balance
        3. Conversion double-count: Postback received twice
        4. Payout duplicate: Two payout requests for same earnings
        5. Stale cache: Cached exchange rate differs from DB

    Resolution strategies:
        - last_write_wins: Most recent update wins
        - source_of_truth: Designated system always wins (usually api.wallet)
        - manual_review: Flag for human review if conflict too large
        - idempotent_check: Check if already processed (reference_id lookup)
    """

    BALANCE_TOLERANCE = Decimal('0.01')  # 1 paisa tolerance

    def check_deposit_duplicate(self, reference_id: str, gateway_ref: str) -> bool:
        """
        Check if a deposit was already processed.
        Prevents double-crediting from webhook retries.

        Returns True if duplicate (already processed).
        """
        from api.payment_gateways.models.deposit import DepositRequest

        # Check by our reference ID
        if DepositRequest.objects.filter(
            reference_id=reference_id, status='completed'
        ).exists():
            logger.warning(f'Duplicate deposit detected: ref={reference_id}')
            return True

        # Check by gateway reference
        if gateway_ref and DepositRequest.objects.filter(
            gateway_ref=gateway_ref, status='completed'
        ).exists():
            logger.warning(f'Duplicate deposit detected: gw_ref={gateway_ref}')
            return True

        return False

    def check_conversion_duplicate(self, click_id: str) -> bool:
        """
        Check if a conversion was already recorded for this click.
        Prevents double-paying publishers.
        """
        try:
            from api.payment_gateways.tracking.models import Conversion
            return Conversion.objects.filter(
                click_id_raw=click_id,
                status__in=('approved', 'pending', 'processing')
            ).exists()
        except Exception:
            return False

    def resolve_balance_conflict(self, user) -> Tuple[Decimal, str]:
        """
        Resolve balance mismatch between payment_gateways and api.wallet.

        Returns:
            (correct_balance, resolution_strategy)
        """
        # Get balance from both sources
        pg_balance   = Decimal(str(getattr(user, 'balance', '0') or '0'))
        wallet_balance = self._get_wallet_balance(user)

        if wallet_balance is None:
            return pg_balance, 'payment_gateways_only'

        diff = abs(pg_balance - wallet_balance)

        if diff <= self.BALANCE_TOLERANCE:
            # Balances match (within tolerance)
            return wallet_balance, 'no_conflict'

        if diff <= Decimal('1.00'):
            # Small difference — use wallet as source of truth
            logger.warning(
                f'Balance mismatch for user {user.id}: '
                f'pg={pg_balance} wallet={wallet_balance} diff={diff} — using wallet'
            )
            return wallet_balance, 'wallet_wins'

        # Large difference — flag for manual review
        logger.error(
            f'LARGE balance mismatch for user {user.id}: '
            f'pg={pg_balance} wallet={wallet_balance} diff={diff} — MANUAL REVIEW REQUIRED'
        )
        self._flag_for_review(user, pg_balance, wallet_balance)
        return wallet_balance, 'manual_review_flagged'

    def sync_conversion_earnings(self, publisher, force: bool = False) -> dict:
        """
        Sync publisher's total earnings between payment_gateways
        tracking and api.wallet transaction history.
        """
        from api.payment_gateways.tracking.models import Conversion
        from django.db.models import Sum

        pg_total = Conversion.objects.filter(
            publisher=publisher, status='approved'
        ).aggregate(t=Sum('payout'))['t'] or Decimal('0')

        wallet_total = self._get_wallet_earning_total(publisher)

        if wallet_total is None:
            return {'synced': False, 'reason': 'wallet_unavailable'}

        diff = abs(pg_total - wallet_total)

        if diff <= Decimal('0.01'):
            return {'synced': True, 'difference': float(diff)}

        logger.warning(
            f'Earnings sync mismatch for publisher {publisher.id}: '
            f'pg_total={pg_total} wallet_total={wallet_total} diff={diff}'
        )

        if force and diff <= Decimal('100.00'):
            # Auto-resolve small differences
            self._create_adjustment_entry(publisher, diff)
            return {'synced': True, 'adjusted': float(diff), 'auto_resolved': True}

        return {
            'synced':    False,
            'pg_total':  float(pg_total),
            'wallet_total': float(wallet_total) if wallet_total else None,
            'difference':float(diff),
            'action':    'manual_review' if diff > 100 else 'auto_resolvable',
        }

    def idempotent_process(self, key: str, processor_func, ttl: int = 86400):
        """
        Idempotent processing wrapper — ensures an operation runs exactly once.

        Args:
            key:            Unique key for this operation (e.g. 'deposit_ABC123')
            processor_func: Function to call if not already processed
            ttl:            How long to remember this key (seconds)

        Returns:
            Result of processor_func, or cached result if already run
        """
        from django.core.cache import cache
        import json

        cache_key = f'idempotent:{key}'
        existing  = cache.get(cache_key)

        if existing is not None:
            logger.debug(f'Idempotent: skipping duplicate processing of {key}')
            try:
                return json.loads(existing)
            except Exception:
                return existing

        result = processor_func()

        try:
            cache.set(cache_key, json.dumps(result, default=str), ttl)
        except Exception:
            cache.set(cache_key, str(result), ttl)

        return result

    def _get_wallet_balance(self, user) -> Optional[Decimal]:
        try:
            from api.payment_gateways.integration_system.data_bridge import DataBridgeSync
            return DataBridgeSync().pull_user_balance(user)
        except Exception:
            return None

    def _get_wallet_earning_total(self, user) -> Optional[Decimal]:
        try:
            from api.wallet.models import WalletTransaction
            from django.db.models import Sum
            total = WalletTransaction.objects.filter(
                user=user, transaction_type='earning'
            ).aggregate(t=Sum('amount'))['t']
            return total or Decimal('0')
        except ImportError:
            return None
        except Exception:
            return None

    def _create_adjustment_entry(self, publisher, amount: Decimal):
        """Create adjustment wallet entry to reconcile difference."""
        try:
            from api.wallet.models import WalletTransaction
            WalletTransaction.objects.create(
                user=publisher,
                transaction_type='adjustment',
                amount=amount,
                description='Auto-sync adjustment by SyncManager',
            )
        except Exception as e:
            logger.error(f'Could not create adjustment entry: {e}')

    def _flag_for_review(self, user, pg_balance: Decimal, wallet_balance: Decimal):
        """Flag balance conflict for admin review."""
        from django.core.cache import cache
        flags = cache.get('balance_conflicts', [])
        flags.append({
            'user_id':       user.id,
            'pg_balance':    float(pg_balance),
            'wallet_balance':float(wallet_balance),
            'diff':          float(abs(pg_balance - wallet_balance)),
            'timestamp':     timezone.now().isoformat(),
        })
        cache.set('balance_conflicts', flags[-100:], 86400 * 7)


# Singleton
sync_manager = SyncManager()
