# api/offer_inventory/marketing/referral_program.py
"""
Referral Program Manager.
Multi-level referral tracking, code generation,
commission calculation, and fraud prevention.
"""
import secrets
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

REFERRAL_CODE_LENGTH = 8
MAX_REFERRAL_DEPTH   = 2   # Multi-level depth


class ReferralProgramManager:
    """Complete referral program management."""

    # ── Code generation ────────────────────────────────────────────

    @staticmethod
    def get_or_create_code(user) -> str:
        """Get or generate a user's referral code."""
        cache_key = f'ref_code:{user.id}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        # Try to find existing
        from api.offer_inventory.models import UserReferral
        from django.contrib.auth import get_user_model

        code = ReferralProgramManager._generate_unique_code()
        cache.set(cache_key, code, 86400)
        return code

    @staticmethod
    def _generate_unique_code() -> str:
        """Generate a unique referral code."""
        import string
        charset = string.ascii_uppercase + string.digits
        for _ in range(10):   # Max 10 attempts
            code = ''.join(secrets.choice(charset) for _ in range(REFERRAL_CODE_LENGTH))
            # Check uniqueness in DB
            from api.offer_inventory.models import UserReferral
            if not UserReferral.objects.filter(referral_code=code).exists():
                return code
        return secrets.token_hex(4).upper()

    # ── Registration ───────────────────────────────────────────────

    @classmethod
    @transaction.atomic
    def register_referral(cls, referrer_code: str, new_user) -> bool:
        """
        Link a new user to their referrer.
        Called during registration.
        """
        from api.offer_inventory.models import UserReferral

        # Find referrer
        referrer_ref = UserReferral.objects.filter(
            referral_code=referrer_code
        ).select_related('referrer').first()

        if not referrer_ref:
            # Code might be directly on a user profile
            from django.contrib.auth import get_user_model
            User = get_user_model()
            # Try username as code
            referrer = User.objects.filter(username=referrer_code).first()
            if not referrer:
                logger.warning(f'Referral code not found: {referrer_code}')
                return False
        else:
            referrer = referrer_ref.referrer

        # Prevent self-referral
        if referrer.id == new_user.id:
            return False

        # Prevent duplicate
        if UserReferral.objects.filter(referred=new_user).exists():
            return False

        # Create referral
        code = cls._generate_unique_code()
        UserReferral.objects.create(
            referrer    =referrer,
            referred    =new_user,
            referral_code=code,
        )

        logger.info(f'Referral registered: {referrer.username} → {new_user.username}')
        return True

    @classmethod
    @transaction.atomic
    def mark_converted(cls, referred_user) -> bool:
        """Mark a referral as converted (first successful offer)."""
        from api.offer_inventory.models import UserReferral
        from api.offer_inventory.marketing.loyalty_program import LoyaltyManager

        try:
            ref = UserReferral.objects.get(referred=referred_user, is_converted=False)
        except UserReferral.DoesNotExist:
            return False

        ref.is_converted = True
        ref.converted_at = timezone.now()
        ref.save(update_fields=['is_converted', 'converted_at'])

        # Award referrer bonus for first conversion
        from api.offer_inventory.repository import WalletRepository
        WalletRepository.credit_user(
            user_id    =ref.referrer_id,
            amount     =Decimal('20'),   # Registration bonus
            source     ='referral_bonus',
            source_id  =str(referred_user.id),
            description=f'{referred_user.username} প্রথম অফার সম্পন্ন করেছে',
        )

        # Loyalty points
        LoyaltyManager.award_referral_points(ref.referrer, referred_user)

        # Notify referrer
        from api.offer_inventory.repository import NotificationRepository
        NotificationRepository.create(
            user_id   =ref.referrer_id,
            notif_type='success',
            title     ='🎉 রেফারেল বোনাস পেয়েছেন!',
            body      =f'{referred_user.username} প্রথম অফার করেছে। আপনি ২০ টাকা পেয়েছেন!',
        )

        logger.info(f'Referral converted: {ref.referrer.username} → {referred_user.username}')
        return True

    # ── Analytics ──────────────────────────────────────────────────

    @staticmethod
    def get_referral_tree(user, depth: int = 2) -> dict:
        """Get multi-level referral tree."""
        from api.offer_inventory.models import UserReferral

        def get_children(parent_user, current_depth):
            if current_depth > depth:
                return []
            refs = UserReferral.objects.filter(
                referrer=parent_user
            ).select_related('referred')
            children = []
            for ref in refs:
                children.append({
                    'user'        : ref.referred.username,
                    'is_converted': ref.is_converted,
                    'earnings'    : float(ref.total_earnings_generated),
                    'joined'      : ref.created_at.isoformat(),
                    'children'    : get_children(ref.referred, current_depth + 1),
                })
            return children

        return {
            'user'    : user.username,
            'children': get_children(user, 1),
        }

    @staticmethod
    def get_stats(user) -> dict:
        """Referral program stats for a user."""
        from api.offer_inventory.models import UserReferral, ReferralCommission
        from django.db.models import Sum, Count

        refs  = UserReferral.objects.filter(referrer=user)
        comms = ReferralCommission.objects.filter(referrer=user)

        total_refs     = refs.count()
        converted      = refs.filter(is_converted=True).count()
        total_earnings = comms.aggregate(t=Sum('amount'))['t'] or Decimal('0')

        return {
            'referral_code'  : ReferralProgramManager.get_or_create_code(user),
            'total_referrals': total_refs,
            'converted'      : converted,
            'conversion_rate': round(converted / max(total_refs, 1) * 100, 1),
            'total_earnings' : float(total_earnings),
            'pending_earnings': float(comms.filter(is_paid=False).aggregate(t=Sum('amount'))['t'] or 0),
        }
