# api/referral/services/ReferralService.py
# Fix: hardcoded 10 bonus → dynamic from ReferralSettings + active campaign
# All original methods preserved for backward compatibility
# ============================================================

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


def _get_settings():
    """Active referral settings পাও — cache করা থাকে।"""
    cached = cache.get('referral_settings')
    if cached:
        return cached
    from api.referral.models import ReferralSettings
    s = ReferralSettings.objects.select_related('active_campaign').first()
    if not s:
        s = ReferralSettings.objects.create()
    cache.set('referral_settings', s, timeout=300)
    return s


class ReferralService:
    """
    Core referral service।
    পুরনো ReferralService এর সব method রাখা আছে।
    Fix: hardcoded bonus removed — dynamic from ReferralSettings।
    New: campaign multiplier, fraud check integration।
    """

    # ─── Backward-compatible methods ──────────────────────────

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
        Earning এ Level 1/2/3 commission দাও।
        FIX: hardcoded 10 removed — dynamic from settings।
        """
        return ReferralService.process_multilevel_commission(
            earner=referred_user,
            earned_amount=Decimal(str(coins_earned)),
            source_type='task',
            source_id=str(source_task.id) if source_task else '',
            source_task=source_task,
        )

    # ─── Main methods ──────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def process_signup_with_fraud_check(
        new_user, referrer, new_user_ip=None, referrer_ip=None,
        device_fingerprint=None, user_agent=None
    ) -> dict:
        """
        Registration এ referral process করো।
        ১. Fraud check (same IP/device/blacklist)
        ২. Signup bonus দাও — DYNAMIC from settings (no hardcoded value)
        ৩. Multi-level chain তৈরি করো
        ৪. Tree update করো
        """
        from api.referral.models import Referral, ReferralSettings
        from api.referral.services.ReferralFraudService import ReferralFraudService
        from api.referral.services.ReferralTreeService import ReferralTreeService

        settings = _get_settings()

        if not settings.is_active:
            return {'success': False, 'reason': 'Referral program inactive'}

        if not settings.allow_self_referral and referrer.id == new_user.id:
            return {'success': False, 'reason': 'Self-referral blocked'}

        # ── Duplicate check ────────────────────────────────────
        if Referral.objects.filter(referred_user=new_user).exists():
            return {'success': False, 'reason': 'User already has a referrer'}

        # ── Fraud check ────────────────────────────────────────
        fraud_result = ReferralFraudService.check_signup(
            new_user=new_user,
            referrer=referrer,
            new_user_ip=new_user_ip,
            referrer_ip=referrer_ip,
            device_fingerprint=device_fingerprint,
        )

        # ── Create Referral ────────────────────────────────────
        referral = Referral.objects.create(
            referrer=referrer,
            referred_user=new_user,
            level=1,
            signup_bonus_given=False,
            registration_ip=new_user_ip,
            referrer_ip=referrer_ip,
            is_suspicious=fraud_result.get('is_suspicious', False),
            suspicious_reason=fraud_result.get('reason', ''),
        )

        # Fraud log create করো
        if fraud_result.get('is_suspicious'):
            from api.referral.models import SuspiciousReferral
            SuspiciousReferral.objects.get_or_create(
                referral=referral,
                defaults={
                    'flags': fraud_result.get('flags', {}),
                    'fraud_score': fraud_result.get('fraud_score', 0),
                    'evidence': fraud_result.get('evidence', {}),
                }
            )

        # ── Build multi-level chain ────────────────────────────
        ReferralService._build_chain(new_user, referrer)

        # ── Update tree ────────────────────────────────────────
        ReferralTreeService.ensure_tree(referrer)
        ReferralTreeService.rebuild_tree(referrer)

        # ── Block fraud referrals from getting bonus ───────────
        fraud_action = fraud_result.get('action', 'allow')
        if fraud_action == 'block':
            logger.warning(
                f"Referral blocked (fraud): "
                f"{referrer.username} → {new_user.username}"
            )
            return {
                'success': False,
                'reason': 'Blocked by fraud detection',
                'referral_id': referral.id,
            }

        # ── Signup bonus — DYNAMIC from settings/campaign ─────
        # FIX: No more hardcoded values. Settings + campaign multiplier used.
        try:
            from api.wallet.services import WalletService
            from api.wallet.models import Wallet

            # Dynamic bonuses from settings (campaign multiplier applied inside)
            new_user_bonus = settings.get_effective_signup_bonus('direct')
            referrer_bonus = settings.get_effective_signup_bonus('referrer')

            # If fraud flagged (but not blocked), hold commission
            if fraud_result.get('is_suspicious') and fraud_action == 'hold_commission':
                logger.info(
                    f"Referral flagged — bonus held: {referral.id}"
                )
                return {
                    'success': True,
                    'referral_id': referral.id,
                    'bonus_given': False,
                    'note': 'Bonus held pending fraud review',
                }

            # New user bonus
            new_wallet, _ = Wallet.objects.get_or_create(user=new_user)
            WalletService.add_earnings(
                wallet=new_wallet,
                amount=new_user_bonus,
                description=f"Signup bonus (referred by {referrer.username})",
                source_type='referral_signup',
                source_id=str(referrer.id),
            )

            # Referrer bonus
            ref_wallet, _ = Wallet.objects.get_or_create(user=referrer)
            WalletService.add_earnings(
                wallet=ref_wallet,
                amount=referrer_bonus,
                description=f"Referral signup bonus ({new_user.username} joined)",
                source_type='referral_signup',
                source_id=str(new_user.id),
            )

            referral.signup_bonus_given = True
            referral.save(update_fields=['signup_bonus_given'])

            # User stats update
            ReferralService._update_referrer_stats(referrer)

            # ReferralCode conversion record
            ReferralService._record_code_conversion(referrer)

            # Campaign spend record
            if settings.active_campaign_id:
                try:
                    settings.active_campaign.record_spend(
                        referrer_bonus + new_user_bonus
                    )
                except Exception:
                    pass

            logger.info(
                f"Signup bonus given: "
                f"referrer={referrer.id} +{referrer_bonus}, "
                f"new_user={new_user.id} +{new_user_bonus}"
            )

            return {
                'success': True,
                'referral_id': referral.id,
                'bonus_given': True,
                'new_user_bonus': float(new_user_bonus),
                'referrer_bonus': float(referrer_bonus),
                'campaign_active': bool(
                    settings.active_campaign_id and
                    settings.active_campaign.is_currently_active()
                ),
            }

        except Exception as e:
            logger.error(f"Signup bonus error: {e}")
            return {
                'success': True,
                'referral_id': referral.id,
                'bonus_given': False,
                'error': str(e)
            }

    @staticmethod
    @transaction.atomic
    def process_multilevel_commission(
        earner, earned_amount: Decimal,
        source_type: str = 'task', source_id: str = '',
        source_task=None
    ) -> list:
        """
        Earner যখন কিছু earn করে → সব ancestor দের commission দাও।
        FIX: rate fully dynamic from settings (no hardcoded 10).

        Example:
          A refers B, B refers C, C refers D
          D earns ৳100:
            C (L1) gets dynamic L1 rate %
            B (L2) gets dynamic L2 rate %
            A (L3) gets dynamic L3 rate %
        """
        from api.referral.models import ReferralChain, ReferralEarning, Referral

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
        campaign_multiplier = Decimal('1')

        # Active campaign multiplier
        if settings.active_campaign_id:
            try:
                if settings.active_campaign.is_currently_active():
                    campaign_multiplier = settings.active_campaign.bonus_multiplier
            except Exception:
                pass

        try:
            from api.wallet.services import WalletService
            from api.wallet.models import Wallet
            from api.referral.services.CommissionService import CommissionService

            for chain in chains:
                beneficiary = chain.beneficiary
                level = chain.level

                # Dynamic rate from settings (no hardcoded values)
                base_rate = settings.get_rate_for_level(level)
                if base_rate <= 0:
                    continue

                commission = (
                    earned_amount * base_rate / 100
                ).quantize(Decimal('0.01'))

                if commission <= 0:
                    continue

                # Commission hold check
                hold_days = settings.commission_hold_days
                should_hold = hold_days > 0

                # CommissionService দিয়ে create করো (with hold if needed)
                log = CommissionService.create_commission_log(
                    user=beneficiary,
                    referred_user=earner,
                    amount=commission,
                    base_amount=earned_amount,
                    commission_rate=base_rate,
                    level=level,
                    action_type=source_type,
                    source_reference=f"{source_type}:{source_id}" if source_id else source_type,
                    hold_days=hold_days if should_hold else 0,
                )

                # If no hold, add to wallet immediately
                if not should_hold:
                    wallet, _ = Wallet.objects.get_or_create(user=beneficiary)
                    # Use add_earnings to bypass wallet's hardcoded rates
                    # commission is already calculated using ReferralSettings rates
                    wallet_txn = WalletService.add_earnings(
                        wallet=wallet,
                        amount=commission,
                        description=f'L{level} referral commission from {earner.username}',
                        source_type='referral',
                        source_id=str(earner.id),
                        reference_id=str(earner.id),
                    )
                    if wallet_txn and log:
                        log.wallet_transaction_id = str(
                            getattr(wallet_txn, 'walletTransaction_id', '')
                        )
                        log.status = 'released'
                        log.save(update_fields=['wallet_transaction_id', 'status'])

                # Log ReferralEarning (backward compat)
                direct_referral = Referral.objects.filter(
                    referrer=beneficiary, referred_user=earner
                ).first() if level == 1 else None

                earning = ReferralEarning.objects.create(
                    referral=direct_referral,
                    referrer=beneficiary,
                    referred_user=earner,
                    level=level,
                    amount=commission,
                    commission_rate=base_rate,
                    source_amount=earned_amount,
                    source_type=source_type,
                    source_id=source_id,
                    source_task=source_task,
                    campaign_multiplier=campaign_multiplier,
                    status='held' if should_hold else 'released',
                )

                # Level 1 direct referral commission update
                if level == 1 and direct_referral:
                    direct_referral.total_commission_earned += commission
                    direct_referral.save(
                        update_fields=['total_commission_earned']
                    )

                results.append({
                    'beneficiary': beneficiary.username,
                    'level': level,
                    'commission': float(commission),
                    'rate': float(base_rate),
                    'held': should_hold,
                    'campaign_multiplier': float(campaign_multiplier),
                })

                logger.info(
                    f"L{level} commission: "
                    f"{beneficiary.username} +{commission} "
                    f"(from {earner.username})"
                    f"{' [HELD]' if should_hold else ''}"
                )

        except Exception as e:
            logger.error(
                f"Commission processing error for earner {earner.id}: {e}"
            )

        return results

    @staticmethod
    def get_referral_stats(user) -> dict:
        """User এর complete referral stats"""
        from django.db.models import Sum, Count, Q
        from api.referral.models import Referral, ReferralChain, ReferralEarning

        direct_refs = Referral.objects.filter(referrer=user)
        total_direct = direct_refs.count()

        level2 = ReferralChain.objects.filter(beneficiary=user, level=2).count()
        level3 = ReferralChain.objects.filter(beneficiary=user, level=3).count()

        earnings = ReferralEarning.objects.filter(referrer=user).aggregate(
            total=Sum('amount'),
            l1=Sum('amount', filter=Q(level=1)),
            l2=Sum('amount', filter=Q(level=2)),
            l3=Sum('amount', filter=Q(level=3)),
        )

        month_start = timezone.now().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
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
            'active_referrals': direct_refs.filter(
                referred_user__is_active=True
            ).count(),
        }

    @staticmethod
    def get_my_referrals(user, level: int = 1) -> list:
        """Referral list দেখাও"""
        from api.referral.models import Referral, ReferralChain

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
                'is_suspicious': r.is_suspicious,
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
        """
        from api.referral.models import ReferralChain, Referral

        try:
            # Level 1 — direct referrer
            ReferralChain.objects.get_or_create(
                beneficiary=direct_referrer,
                earner=new_user,
                defaults={'level': 1}
            )

            # Level 2 — direct referrer এর referrer
            l1_referral = Referral.objects.filter(
                referred_user=direct_referrer
            ).first()
            if l1_referral:
                l2_beneficiary = l1_referral.referrer
                ReferralChain.objects.get_or_create(
                    beneficiary=l2_beneficiary,
                    earner=new_user,
                    defaults={'level': 2}
                )

                # Level 3 — আরো একধাপ উপরে
                l2_referral = Referral.objects.filter(
                    referred_user=l2_beneficiary
                ).first()
                if l2_referral:
                    l3_beneficiary = l2_referral.referrer
                    ReferralChain.objects.get_or_create(
                        beneficiary=l3_beneficiary,
                        earner=new_user,
                        defaults={'level': 3}
                    )
        except Exception as e:
            logger.error(
                f"Chain build error for new_user {new_user.id}: {e}"
            )

    @staticmethod
    def _update_referrer_stats(referrer):
        """Referrer এর UserStatistics update করো"""
        from api.referral.models import Referral

        try:
            from api.users.models import UserStatistics
            stats, _ = UserStatistics.objects.get_or_create(user=referrer)
            stats.total_referrals = Referral.objects.filter(
                referrer=referrer
            ).count()
            stats.active_referrals = Referral.objects.filter(
                referrer=referrer, referred_user__is_active=True
            ).count()
            stats.save(update_fields=['total_referrals', 'active_referrals'])
        except Exception as e:
            logger.warning(f"Referrer stats update failed: {e}")

    @staticmethod
    def _record_code_conversion(referrer):
        """Primary referral code এর conversion record করো।"""
        from api.referral.models import ReferralCode

        try:
            code = ReferralCode.objects.filter(
                user=referrer, is_primary=True, is_active=True
            ).first()
            if code:
                code.record_conversion()
        except Exception as e:
            logger.warning(f"Code conversion record failed: {e}")

    @staticmethod
    def invalidate_settings_cache():
        """Settings cache clear করো।"""
        cache.delete('referral_settings')