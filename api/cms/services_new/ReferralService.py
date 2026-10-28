# api/cms/services_new/ReferralService.py
"""
Referral Service — Professional grade.
Atomic transactions, select_for_update, cache dedup, type hints.
CPAlead: 5% bonus on every referral's earning for 6 months.
"""
import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List
from django.utils import timezone
from django.db import transaction as db_transaction
from django.db.models import F, Sum, Count
from django.core.cache import cache
from datetime import timedelta

logger = logging.getLogger(__name__)

REFERRAL_BONUS_RATE = Decimal('0.05')  # CPAlead official: 5%
REFERRAL_ACTIVE_MONTHS = 6             # CPAlead: 6 months active


class ReferralService:

    # ── Code Management ──────────────────────────────────────────

    @staticmethod
    def get_or_create_code(user) -> str:
        from api.cms.models_new.referral import ReferralCode
        rc = ReferralCode.get_or_create_for_user(user)
        return rc.code

    # ── Apply Referral (on registration) ─────────────────────────

    @staticmethod
    def apply_referral(referred_user, code: str) -> Dict[str, Any]:
        """
        Link referred_user to referrer via code.
        Thread-safe: uses cache dedup + atomic transaction.
        """
        from api.cms.models_new.referral import ReferralCode, ReferralRelationship

        if not code:
            return {'success': False, 'reason': 'no_code'}

        # Fast dedup via cache (prevents race on double-submit)
        dedup_key = f"referral_apply_{referred_user.id}"
        if not cache.add(dedup_key, 1, timeout=60):
            return {'success': False, 'reason': 'already_processing'}

        try:
            # Validate code
            try:
                rc = ReferralCode.objects.select_related('user').get(
                    code=code.upper().strip(), is_active=True
                )
            except ReferralCode.DoesNotExist:
                return {'success': False, 'reason': 'invalid_code'}

            if rc.user_id == referred_user.id:
                return {'success': False, 'reason': 'self_referral'}

            # Check if user was already referred
            if ReferralRelationship.objects.filter(referred=referred_user).exists():
                return {'success': False, 'reason': 'already_referred'}

            # Create relationship atomically
            with db_transaction.atomic():
                rel = ReferralRelationship.objects.create(
                    referrer=rc.user,
                    referred=referred_user,
                    referral_code=rc,
                    bonus_rate=REFERRAL_BONUS_RATE,
                    expires_at=timezone.now() + timedelta(days=30 * REFERRAL_ACTIVE_MONTHS),
                )
                ReferralCode.objects.filter(pk=rc.pk).update(
                    total_referrals=F('total_referrals') + 1
                )

            logger.info(f"[Referral] {rc.user.username} → {referred_user.username} (code: {code})")
            return {
                'success': True,
                'referrer_username': rc.user.username,
                'relationship_id': rel.id,
                'bonus_rate': float(REFERRAL_BONUS_RATE),
                'expires_at': rel.expires_at.isoformat() if rel.expires_at else None,
            }
        finally:
            cache.delete(dedup_key)

    # ── Award Referral Bonus ──────────────────────────────────────

    @staticmethod
    @db_transaction.atomic
    def award_referral_bonus(referred_user, original_amount_usd: Decimal,
                              source: str = 'offer_complete',
                              lead_id: str = '') -> Optional[Decimal]:
        """
        Award 5% referral bonus to referrer when referred user earns.
        Atomic + select_for_update prevents double-award on concurrent calls.
        """
        from api.cms.models_new.referral import (
            ReferralRelationship, ReferralEarning, ReferralCode
        )

        # Dedup: one bonus per lead_id
        if lead_id:
            dedup_key = f"ref_bonus_dedup_{lead_id}"
            if not cache.add(dedup_key, 1, timeout=86400):
                logger.info(f"[Referral] Bonus already awarded for lead_id={lead_id}")
                return None

        try:
            rel = ReferralRelationship.objects.select_for_update().select_related(
                'referrer'
            ).get(referred=referred_user, is_active=True)
        except ReferralRelationship.DoesNotExist:
            return None

        if not rel.is_still_active():
            rel.is_active = False
            rel.save(update_fields=['is_active'])
            return None

        bonus_usd = (original_amount_usd * rel.bonus_rate).quantize(Decimal('0.0001'))
        if bonus_usd <= 0:
            return None

        # Award virtual coins to referrer — use the referrer's existing balance currency
        bonus_coins = Decimal('0')
        try:
            from api.cms.models_new.cpalead import UserVirtualBalance, VirtualCurrency
            from django.db.models import F
            # Prefer existing referrer balance; fall back to active currency
            referrer_bal = UserVirtualBalance.objects.filter(user=rel.referrer).first()
            if not referrer_bal:
                vc = VirtualCurrency.get_active()
                if vc:
                    referrer_bal, _ = UserVirtualBalance.objects.get_or_create(
                        user=rel.referrer, currency=vc, defaults={'balance': Decimal('0')}
                    )
            if referrer_bal:
                vc = referrer_bal.currency
                bonus_coins = vc.usd_to_virtual(bonus_usd)
                rows = UserVirtualBalance.objects.filter(pk=referrer_bal.pk).update(
                    balance=F('balance') + bonus_coins,
                    total_earned=F('total_earned') + bonus_coins,
                )
                logger.debug(f"[Referral] Awarded {bonus_coins} coins to {rel.referrer} (pk={referrer_bal.pk})")
        except Exception as e:
            logger.warning(f"[Referral] Virtual bonus failed: {e}")

        # Log earning
        ReferralEarning.objects.create(
            referrer=rel.referrer,
            referred=referred_user,
            relationship=rel,
            source=source,
            original_amount_usd=original_amount_usd,
            bonus_rate=rel.bonus_rate,
            bonus_usd=bonus_usd,
            bonus_coins=bonus_coins,
            lead_id=lead_id,
        )

        # Update relationship totals
        ReferralRelationship.objects.filter(pk=rel.pk).update(
            total_bonus_earned_usd=F('total_bonus_earned_usd') + bonus_usd,
            total_bonus_earned_coins=F('total_bonus_earned_coins') + bonus_coins,
        )
        ReferralCode.objects.filter(user=rel.referrer).update(
            total_bonus_usd=F('total_bonus_usd') + bonus_usd,
            total_bonus_coins=F('total_bonus_coins') + bonus_coins,
        )

        # Notify referrer
        try:
            from api.cms.services_new.NotificationService import NotificationService
            NotificationService.notify_referral_bonus(
                user=rel.referrer,
                referred_username=referred_user.username,
                bonus_amount=float(bonus_coins if bonus_coins > 0 else bonus_usd),
                currency='Coins' if bonus_coins > 0 else 'USD',
            )
        except Exception:
            pass

        logger.info(
            f"[Referral] Bonus awarded: ${bonus_usd} ({bonus_coins} coins) "
            f"to {rel.referrer.username} from {referred_user.username}"
        )
        return bonus_usd

    # ── Stats & Dashboard ─────────────────────────────────────────

    @staticmethod
    def get_referral_stats(user) -> Dict[str, Any]:
        """Get complete referral stats for user dashboard."""
        from api.cms.models_new.referral import ReferralCode, ReferralRelationship, ReferralEarning

        try:
            rc = ReferralCode.objects.get(user=user)
            code = rc.code
        except ReferralCode.DoesNotExist:
            code = ReferralService.get_or_create_code(user)

        # Use DB aggregation — no N+1
        rel_stats = ReferralRelationship.objects.filter(referrer=user).aggregate(
            total=Count('id'),
            active=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(is_active=True)),
        )
        earning_stats = ReferralEarning.objects.filter(referrer=user).aggregate(
            total_usd=Sum('bonus_usd'),
            total_coins=Sum('bonus_coins'),
            total_events=Count('id'),
        )

        return {
            'referral_code': code,
            'referral_link': f"/join?ref={code}",
            'total_referrals': rel_stats['total'] or 0,
            'active_referrals': rel_stats['active'] or 0,
            'total_bonus_usd': float(earning_stats['total_usd'] or 0),
            'total_bonus_coins': float(earning_stats['total_coins'] or 0),
            'total_bonus_events': earning_stats['total_events'] or 0,
            'bonus_rate_pct': float(REFERRAL_BONUS_RATE * 100),
            'active_months': REFERRAL_ACTIVE_MONTHS,
        }

    @staticmethod
    def get_referred_users(user, limit: int = 50) -> List[Dict]:
        from api.cms.models_new.referral import ReferralRelationship
        rels = (ReferralRelationship.objects
                .filter(referrer=user)
                .select_related('referred')
                .order_by('-joined_at')[:limit])
        return [{
            'username': r.referred.username,
            'joined_at': r.joined_at.isoformat(),
            'is_active': r.is_still_active(),
            'total_bonus_coins': float(r.total_bonus_earned_coins),
            'total_bonus_usd': float(r.total_bonus_earned_usd),
            'expires_at': r.expires_at.isoformat() if r.expires_at else None,
        } for r in rels]
