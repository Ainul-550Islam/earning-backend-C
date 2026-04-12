# api/offer_inventory/misc_features/system_recovery.py
"""
System Recovery — Recovery procedures for common failure scenarios.
Handles: stuck conversions, failed payouts, corrupted caps, cache issues.
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class SystemRecovery:
    """Auto-recovery from common platform failure scenarios."""

    @staticmethod
    def recover_stuck_conversions(hours: int = 2,
                                   limit: int = 100) -> dict:
        """
        Find and auto-approve conversions stuck in 'pending' from S2S networks.
        These should have been auto-approved but weren't due to errors.
        """
        from api.offer_inventory.models import Conversion, ConversionStatus
        from api.offer_inventory.services import ConversionService

        cutoff   = timezone.now() - timedelta(hours=hours)
        stuck_qs = Conversion.objects.filter(
            status__name='pending',
            created_at__lt=cutoff,
            offer__network__is_s2s_enabled=True,
            approved_at__isnull=True,
        ).select_related('offer', 'offer__network')[:limit]

        stuck_count  = stuck_qs.count()
        approved_cnt = 0
        failed_cnt   = 0

        for conv in stuck_qs:
            try:
                ConversionService.approve_conversion(str(conv.id))
                approved_cnt += 1
            except Exception as e:
                failed_cnt += 1
                logger.error(f'Recovery failed for conv {conv.id}: {e}')

        logger.info(f'Stuck conversion recovery: found={stuck_count} approved={approved_cnt} failed={failed_cnt}')
        return {
            'stuck_found' : stuck_count,
            'recovered'   : approved_cnt,
            'failed'      : failed_cnt,
        }

    @staticmethod
    def recover_failed_payouts(limit: int = 200) -> dict:
        """Re-queue payout tasks for approved conversions that weren't paid."""
        from api.offer_inventory.models import Conversion
        from api.offer_inventory.tasks import process_approved_conversion_payout

        approved = list(
            Conversion.objects.filter(
                status__name='approved',
                approved_at__isnull=True,
            ).values_list('id', flat=True)[:limit]
        )

        requeued = 0
        for conv_id in approved:
            payout_cache = f'payout_done:{conv_id}'
            if not cache.get(payout_cache):
                process_approved_conversion_payout.delay(str(conv_id))
                requeued += 1

        logger.info(f'Failed payout recovery: requeued={requeued}')
        return {'requeued': requeued, 'total_checked': len(approved)}

    @staticmethod
    @transaction.atomic
    def rebuild_offer_caps() -> dict:
        """
        Recalculate offer cap counts from actual conversion data.
        Fixes cap counts that drifted due to errors.
        """
        from api.offer_inventory.models import Offer, OfferCap, Conversion
        from django.db.models import Count

        fixed   = 0
        checked = 0

        for offer in Offer.objects.filter(status__in=['active', 'paused']):
            actual = Conversion.objects.filter(
                offer=offer, status__name='approved'
            ).count()
            caps_updated = OfferCap.objects.filter(
                offer=offer, cap_type='total'
            ).update(current_count=actual)
            if caps_updated:
                fixed += 1
                cache.delete(f'offer_avail:{offer.id}')
            checked += 1

        logger.info(f'Offer caps rebuilt: {fixed}/{checked} updated')
        return {'offers_checked': checked, 'caps_fixed': fixed}

    @staticmethod
    def clear_caches(tenant=None) -> dict:
        """Clear all application caches (use with caution!)."""
        patterns_cleared = 0
        patterns = [
            'offers:*', 'offer_*', 'user:profile:*',
            'ip_bl:*', 'feature:*', 'notif:unread:*',
            'dashboard:*', 'kpi_*', 'network_*',
        ]
        for pattern in patterns:
            try:
                if hasattr(cache, 'delete_pattern'):
                    cache.delete_pattern(pattern)
                    patterns_cleared += 1
            except Exception:
                pass

        logger.warning(f'Caches cleared: {patterns_cleared} patterns | tenant={tenant}')
        return {'patterns_cleared': patterns_cleared}

    @staticmethod
    def fix_wallet_balances(limit: int = 100) -> dict:
        """
        Recalculate wallet balances from WalletTransaction history.
        Fixes drift caused by partial failures.
        """
        from django.db.models import Sum

        fixed   = 0
        errors  = 0
        try:
            from api.wallet.models import Wallet, WalletTransaction
        except ImportError:
            return {'error': 'Wallet app not available'}

        for wallet in Wallet.objects.all()[:limit]:
            try:
                credits = WalletTransaction.objects.filter(
                    user=wallet.user, tx_type='credit'
                ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
                debits  = WalletTransaction.objects.filter(
                    user=wallet.user, tx_type='debit'
                ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
                expected = credits - debits

                if abs(expected - wallet.current_balance) > Decimal('0.001'):
                    Wallet.objects.filter(id=wallet.id).update(
                        current_balance=expected
                    )
                    fixed += 1
                    cache.delete(f'wallet:{wallet.user_id}')
            except Exception as e:
                errors += 1
                logger.error(f'Wallet fix error {wallet.user_id}: {e}')

        logger.info(f'Wallet balance fix: {fixed} fixed, {errors} errors')
        return {'fixed': fixed, 'errors': errors}

    @staticmethod
    def recovery_report() -> dict:
        """Generate a health report with recovery recommendations."""
        from api.offer_inventory.models import Conversion, WithdrawalRequest, Offer
        now = timezone.now()

        stuck_convs   = Conversion.objects.filter(
            status__name='pending',
            created_at__lt=now - timedelta(hours=2),
            offer__network__is_s2s_enabled=True,
        ).count()

        unpaid_convs  = Conversion.objects.filter(
            status__name='approved',
            approved_at__isnull=True,
        ).count()

        pending_wd    = WithdrawalRequest.objects.filter(status='pending').count()
        paused_offers = Offer.objects.filter(status='paused').count()

        recommendations = []
        if stuck_convs > 0:
            recommendations.append(f'Run recover_stuck_conversions(): {stuck_convs} stuck')
        if unpaid_convs > 0:
            recommendations.append(f'Run recover_failed_payouts(): {unpaid_convs} unpaid')
        if pending_wd > 50:
            recommendations.append(f'Process withdrawal queue: {pending_wd} pending')

        return {
            'stuck_conversions'  : stuck_convs,
            'unpaid_conversions' : unpaid_convs,
            'pending_withdrawals': pending_wd,
            'paused_offers'      : paused_offers,
            'health'             : 'ok' if not recommendations else 'needs_attention',
            'recommendations'    : recommendations,
            'checked_at'         : now.isoformat(),
        }
