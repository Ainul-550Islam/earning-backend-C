# api/referral/services.py — Complete Multi-Level Referral Service
# পুরনো services.py replace করো
# ============================================================

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
import logging

from .models import Referral, ReferralSettings, ReferralEarning, ReferralChain

logger = logging.getLogger(__name__)


def _get_settings() -> ReferralSettings:
    """Active referral settings পাও — cache করা থাকে।"""
    cached = cache.get('referral_settings')
    if cached:
        return cached
    s = ReferralSettings.objects.first()
    if not s:
        s = ReferralSettings.objects.create()
    cache.set('referral_settings', s, timeout=300)
    return s


class ReferralService:
    """
    পুরনো ReferralService এর সব method রাখা আছে।
    নতুন multi-level + anti-fraud + team bonus add করা হয়েছে।
    """

    # ─── পুরনো method (unchanged interface) ──────────────────

    @staticmethod
    def process_signup_bonus(user, referrer):
        """
        পুরনো method — backward compatible।
        Signup এ bonus দাও।
        """
        return ReferralService.process_signup_with_fraud_check(
            new_user=user,
            referrer=referrer,
            new_user_ip=None,
            referrer_ip=None,
        )

    @staticmethod
    def process_lifetime_commission(referred_user, coins_earned, source_task=None):
        """
        পুরনো method — backward compatible।
        Earning এ Level 1 commission দাও।
        """
        return ReferralService.process_multilevel_commission(
            earner=referred_user,
            earned_amount=Decimal(str(coins_earned)),
            source_type='task',
            source_id=str(source_task.id) if source_task else '',
            source_task=source_task,
        )

    # ─── নতুন methods ─────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def process_signup_with_fraud_check(new_user, referrer, new_user_ip=None, referrer_ip=None) -> dict:
        """
        Registration এ referral process করো।
        ১. Fraud check (same IP/device block)
        ২. Signup bonus দাও
        ৩. Multi-level chain তৈরি করো
        """
        settings = _get_settings()

        if not settings.is_active:
            return {'success': False, 'reason': 'Referral program inactive'}

        if referrer.id == new_user.id:
            return {'success': False, 'reason': 'Self-referral blocked'}

        # ── Anti-fraud: same IP check ──────────────────────────
        if new_user_ip and referrer_ip and new_user_ip == referrer_ip:
            # Suspicious কিন্তু block করো না — flag করো
            logger.warning(f"Suspicious referral: same IP {new_user_ip} for {referrer.username} → {new_user.username}")
            suspicious = True
            suspicious_reason = f"Same IP: {new_user_ip}"
        else:
            suspicious = False
            suspicious_reason = ''

        # ── Duplicate check ────────────────────────────────────
        if Referral.objects.filter(referred_user=new_user).exists():
            return {'success': False, 'reason': 'User already has a referrer'}

        # ── Referral relationship তৈরি করো ───────────────────
        referral = Referral.objects.create(
            referrer=referrer,
            referred_user=new_user,
            level=1,
            signup_bonus_given=False,
            registration_ip=new_user_ip,
            referrer_ip=referrer_ip,
            is_suspicious=suspicious,
            suspicious_reason=suspicious_reason,
        )

        # ── Multi-level chain তৈরি করো ───────────────────────
        ReferralService._build_chain(new_user, referrer)

        # ── Suspicious হলে bonus দেওয়া skip করো ──────────────
        if suspicious:
            logger.info(f"Referral created but bonus skipped (suspicious): {referral.id}")
            return {
                'success': True,
                'referral_id': referral.id,
                'bonus_given': False,
                'note': 'Flagged for review'
            }

        # ── Signup bonus দাও ──────────────────────────────────
        try:
            from api.wallet.services import WalletService
            from api.wallet.models import Wallet

            # নতুন user এর bonus
            new_wallet, _ = Wallet.objects.get_or_create(user=new_user)
            WalletService.add_earnings(
                wallet=new_wallet,
                amount=settings.direct_signup_bonus,
                description=f"Signup bonus (referred by {referrer.username})",
                source_type='referral_signup',
                source_id=str(referrer.id),
            )

            # Referrer এর bonus
            ref_wallet, _ = Wallet.objects.get_or_create(user=referrer)
            WalletService.add_earnings(
                wallet=ref_wallet,
                amount=settings.referrer_signup_bonus,
                description=f"Referral signup bonus ({new_user.username} joined)",
                source_type='referral_signup',
                source_id=str(new_user.id),
            )

            referral.signup_bonus_given = True
            referral.save(update_fields=['signup_bonus_given'])

            # User statistics update
            ReferralService._update_referrer_stats(referrer)

            logger.info(f"Signup bonus given: referrer={referrer.id}, new_user={new_user.id}")
            return {
                'success': True,
                'referral_id': referral.id,
                'bonus_given': True,
                'new_user_bonus': float(settings.direct_signup_bonus),
                'referrer_bonus': float(settings.referrer_signup_bonus),
            }

        except Exception as e:
            logger.error(f"Signup bonus error: {e}")
            return {'success': True, 'referral_id': referral.id, 'bonus_given': False, 'error': str(e)}

    @staticmethod
    @transaction.atomic
    def process_multilevel_commission(earner, earned_amount: Decimal,
                                      source_type: str = 'task', source_id: str = '',
                                      source_task=None) -> list:
        """
        Earner যখন কিছু earn করে → সব ancestor দের commission দাও।

        Example:
        A refers B, B refers C, C refers D
        D earns ৳100:
          C (L1) gets ৳10 (10%)
          B (L2) gets ৳5 (5%)
          A (L3) gets ৳2 (2%)
        """
        settings = _get_settings()
        if not settings.is_active:
            return []

        # Earner এর সব ancestor খোঁজো
        chains = ReferralChain.objects.filter(
            earner=earner,
            level__lte=settings.max_referral_depth
        ).select_related('beneficiary').order_by('level')

        if not chains.exists():
            return []

        results = []

        try:
            from api.wallet.services import WalletService
            from api.wallet.models import Wallet

            for chain in chains:
                beneficiary = chain.beneficiary
                level = chain.level
                rate = settings.get_rate_for_level(level)

                if rate <= 0:
                    continue

                commission = (earned_amount * rate / 100).quantize(Decimal('0.01'))
                if commission <= 0:
                    continue

                # Wallet এ add করো
                wallet, _ = Wallet.objects.get_or_create(user=beneficiary)
                wallet_txn = WalletService.add_earnings(
                    wallet=wallet,
                    amount=commission,
                    description=f"Level {level} referral commission from {earner.username}",
                    source_type='referral_commission',
                    source_id=str(earner.id),
                    metadata={
                        'referral_level': level,
                        'earner_id': str(earner.id),
                        'earned_amount': str(earned_amount),
                        'commission_rate': str(rate),
                    }
                )

                # Log করো
                direct_referral = Referral.objects.filter(
                    referrer=beneficiary, referred_user=earner
                ).first() if level == 1 else None

                earning = ReferralEarning.objects.create(
                    referral=direct_referral,
                    referrer=beneficiary,
                    referred_user=earner,
                    level=level,
                    amount=commission,
                    commission_rate=rate,
                    source_amount=earned_amount,
                    source_type=source_type,
                    source_id=source_id,
                    source_task=source_task,
                    wallet_transaction_id=str(wallet_txn.walletTransaction_id) if wallet_txn else '',
                )

                # Level 1 এর total_commission_earned update করো
                if level == 1 and direct_referral:
                    direct_referral.total_commission_earned += commission
                    direct_referral.save(update_fields=['total_commission_earned'])

                results.append({
                    'beneficiary': beneficiary.username,
                    'level': level,
                    'commission': float(commission),
                    'rate': float(rate),
                })

                logger.info(f"L{level} commission: {beneficiary.username} +{commission} (from {earner.username})")

        except Exception as e:
            logger.error(f"Commission processing error for earner {earner.id}: {e}")

        return results

    @staticmethod
    def get_referral_stats(user) -> dict:
        """User এর complete referral stats"""
        from django.db.models import Sum, Count

        # Direct referrals (Level 1)
        direct_refs = Referral.objects.filter(referrer=user)
        total_direct = direct_refs.count()

        # Level 2 referrals
        level2 = ReferralChain.objects.filter(beneficiary=user, level=2).count()

        # Level 3 referrals
        level3 = ReferralChain.objects.filter(beneficiary=user, level=3).count()

        # Total earnings from referrals
        earnings = ReferralEarning.objects.filter(referrer=user).aggregate(
            total=Sum('amount'),
            l1=Sum('amount', filter=__import__('django.db.models', fromlist=['Q']).Q(level=1)),
            l2=Sum('amount', filter=__import__('django.db.models', fromlist=['Q']).Q(level=2)),
            l3=Sum('amount', filter=__import__('django.db.models', fromlist=['Q']).Q(level=3)),
        )

        # This month
        from django.utils import timezone
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0)
        this_month = ReferralEarning.objects.filter(
            referrer=user,
            created_at__gte=month_start
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        return {
            'referral_code': getattr(user, 'referral_code', ''),
            'total_referrals': total_direct + level2 + level3,
            'level1_count': total_direct,
            'level2_count': level2,
            'level3_count': level3,
            'total_commission': float(earnings['total'] or 0),
            'level1_commission': float(earnings['l1'] or 0),
            'level2_commission': float(earnings['l2'] or 0),
            'level3_commission': float(earnings['l3'] or 0),
            'this_month_commission': float(this_month),
            'active_referrals': direct_refs.filter(referred_user__is_active=True).count(),
        }

    @staticmethod
    def get_my_referrals(user, level: int = 1) -> list:
        """Referral list দেখাও"""
        if level == 1:
            refs = Referral.objects.filter(
                referrer=user
            ).select_related('referred_user').order_by('-created_at')

            return [{
                'id': r.id,
                'username': r.referred_user.username,
                'joined': r.created_at.strftime('%Y-%m-%d'),
                'total_commission': float(r.total_commission_earned),
                'is_active': r.referred_user.is_active,
                'bonus_given': r.signup_bonus_given,
            } for r in refs]

        chains = ReferralChain.objects.filter(
            beneficiary=user, level=level
        ).select_related('earner').order_by('-created_at')

        return [{
            'username': c.earner.username,
            'joined': c.created_at.strftime('%Y-%m-%d'),
            'level': c.level,
            'is_active': c.earner.is_active,
        } for c in chains]

    # ─── Private helpers ───────────────────────────────────────

    @staticmethod
    def _build_chain(new_user, direct_referrer):
        """
        নতুন user join করলে তার ancestor chain তৈরি করো।
        new_user এর earner হিসেবে সব ancestor এ ReferralChain record করো।
        """
        try:
            # Level 1 — direct referrer
            ReferralChain.objects.get_or_create(
                beneficiary=direct_referrer,
                earner=new_user,
                defaults={'level': 1}
            )

            # Level 2 — direct referrer এর referrer
            l1_referral = Referral.objects.filter(referred_user=direct_referrer).first()
            if l1_referral:
                l2_beneficiary = l1_referral.referrer
                ReferralChain.objects.get_or_create(
                    beneficiary=l2_beneficiary,
                    earner=new_user,
                    defaults={'level': 2}
                )

                # Level 3 — আরো একধাপ উপরে
                l2_referral = Referral.objects.filter(referred_user=l2_beneficiary).first()
                if l2_referral:
                    l3_beneficiary = l2_referral.referrer
                    ReferralChain.objects.get_or_create(
                        beneficiary=l3_beneficiary,
                        earner=new_user,
                        defaults={'level': 3}
                    )
        except Exception as e:
            logger.error(f"Chain build error for new_user {new_user.id}: {e}")

    @staticmethod
    def _update_referrer_stats(referrer):
        """Referrer এর UserStatistics update করো"""
        try:
            from api.users.models import UserStatistics
            stats, _ = UserStatistics.objects.get_or_create(user=referrer)
            stats.total_referrals = Referral.objects.filter(referrer=referrer).count()
            stats.active_referrals = Referral.objects.filter(
                referrer=referrer, referred_user__is_active=True
            ).count()
            stats.save(update_fields=['total_referrals', 'active_referrals'])
        except Exception as e:
            logger.warning(f"Referrer stats update failed: {e}")