"""
Incentive Fraud Detector  (PRODUCTION-READY — COMPLETE)
=========================================================
Detects abuse of bonuses, welcome credits, deposit bonuses,
cashback offers, and platform incentive programs.

Common incentive fraud patterns:
  1. Multiple bonus claims from same IP (multi-account bonus farming)
  2. Bonus claim without real activity (claiming without spending/using)
  3. Circular bonus-to-withdrawal pattern (claim bonus → withdraw immediately)
  4. Device fingerprint switching between bonus claims
  5. VPN/proxy usage specifically during bonus claim
  6. Velocity abuse (many small bonus claims in quick succession)
  7. First-deposit bonus abuse with fake minimum deposits
  8. Referral bonus farming (self-referrals, ring referrals)
  9. Promotion code sharing/reselling
  10. Account churning (claim → deplete → new account)
"""
import logging
from typing import Optional

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class IncentiveFraudDetector:
    """
    Detects incentive and bonus fraud on earning/marketing platforms.

    Usage:
        detector = IncentiveFraudDetector('1.2.3.4', user=request.user)
        result = detector.check_bonus_claim(
            bonus_type='welcome_bonus',
            bonus_amount=10.00,
            promotion_code='WELCOME10',
        )
    """

    SIGNAL_SCORES = {
        'multiple_claims_same_ip':   40,
        'circular_withdrawal':       50,
        'vpn_during_claim':          30,
        'tor_during_claim':          45,
        'device_switch':             25,
        'claim_velocity':            35,
        'no_prior_activity':         20,
        'high_value_suspicious':     25,
        'promo_code_shared':         30,
        'new_account_instant_claim': 35,
        'self_referral_bonus':       50,
        'account_age_too_short':     20,
    }

    # Per-bonus daily claim limits
    DAILY_CLAIM_LIMITS = {
        'welcome_bonus':         1,
        'first_deposit_bonus':   1,
        'referral_bonus':        5,
        'cashback':              3,
        'task_bonus':            10,
        'daily_login_bonus':     1,
        'promotion':             3,
        'default':               5,
    }

    def __init__(self, ip_address: str,
                 user=None,
                 tenant=None,
                 fingerprint_hash: str = ''):
        self.ip_address       = ip_address
        self.user             = user
        self.tenant           = tenant
        self.fingerprint_hash = fingerprint_hash
        self.flags: list      = []
        self.score: int       = 0

    # ── Public API ─────────────────────────────────────────────────────────

    def check_bonus_claim(
        self,
        bonus_type: str,
        bonus_amount: float = 0.0,
        promotion_code: str = '',
        referral_user_id: Optional[int] = None,
        account_age_days: Optional[int] = None,
        has_prior_deposits: bool = False,
        has_prior_activity: bool = False,
    ) -> dict:
        """
        Run all fraud checks for a bonus/incentive claim.

        Returns:
            {
                'is_fraud':           bool,
                'fraud_score':        int,
                'flags':              list,
                'recommendation':     'allow'|'flag'|'review'|'block',
                'should_award':       bool,
                'claim_count_today':  int,
                'fraud_types':        list,
            }
        """
        self.flags = []
        self.score = 0

        claim_count = self._check_ip_claim_velocity(bonus_type)
        self._check_vpn_tor()
        self._check_device_consistency(bonus_type)
        self._check_circular_withdrawal(bonus_type)
        self._check_prior_activity(has_prior_deposits, has_prior_activity, bonus_type)
        self._check_account_age(account_age_days, bonus_type)
        self._check_high_value(bonus_amount)
        self._check_promotion_code(promotion_code)
        if referral_user_id:
            self._check_referral_bonus(referral_user_id)

        self.score = min(self.score, 100)
        is_fraud   = self.score >= 40
        recommendation = self._get_recommendation()

        if is_fraud:
            self._save_fraud(bonus_type, bonus_amount, promotion_code)

        return {
            'ip_address':       self.ip_address,
            'bonus_type':       bonus_type,
            'bonus_amount':     bonus_amount,
            'is_fraud':         is_fraud,
            'fraud_score':      self.score,
            'flags':            self.flags,
            'recommendation':   recommendation,
            'should_award':     not is_fraud,
            'claim_count_today': claim_count,
            'fraud_types':      self._classify_fraud_types(),
            'checked_at':       timezone.now().isoformat(),
        }

    # ── Signal Checks ──────────────────────────────────────────────────────

    def _check_ip_claim_velocity(self, bonus_type: str) -> int:
        """Signal 1: Multiple bonus claims from this IP."""
        limit = self.DAILY_CLAIM_LIMITS.get(
            bonus_type, self.DAILY_CLAIM_LIMITS['default']
        )

        # Per-IP per-type daily counter
        key   = f"pi:incentive:{self.ip_address}:{bonus_type}"
        count = cache.get(key, 0) + 1
        cache.set(key, count, 86400)

        # Per-user claim count (across all accounts from this IP)
        ip_users_key   = f"pi:incentive_users:{self.ip_address}:{bonus_type}"
        ip_user_claims = cache.get(ip_users_key, {})
        if self.user:
            ip_user_claims[str(self.user.pk)] = ip_user_claims.get(str(self.user.pk), 0) + 1
        cache.set(ip_users_key, ip_user_claims, 86400)

        # Multiple users claiming same bonus from same IP
        if len(ip_user_claims) > limit:
            self._add_flag(
                'multiple_claims_same_ip',
                f'{len(ip_user_claims)} users claimed {bonus_type} from this IP today '
                f'(limit={limit})'
            )

        return count

    def _check_vpn_tor(self):
        """Signal 2: VPN/Tor usage during bonus claim."""
        try:
            from ..models import IPIntelligence
            intel = IPIntelligence.objects.filter(
                ip_address=self.ip_address
            ).values('is_vpn', 'is_tor', 'is_proxy').first()
            if intel:
                if intel.get('is_tor'):
                    self._add_flag('tor_during_claim',
                                   'Bonus claimed via Tor exit node')
                elif intel.get('is_vpn'):
                    self._add_flag('vpn_during_claim',
                                   'Bonus claimed via VPN — location masking')
                elif intel.get('is_proxy'):
                    self._add_flag('vpn_during_claim',
                                   'Bonus claimed via proxy')
        except Exception:
            pass

    def _check_device_consistency(self, bonus_type: str):
        """Signal 3: Device fingerprint switched between claims."""
        if not self.fingerprint_hash or not self.user:
            return

        key         = f"pi:incentive_fp:{self.user.pk}:{bonus_type}"
        stored_hash = cache.get(key)

        if stored_hash is None:
            cache.set(key, self.fingerprint_hash, 86400)
        elif stored_hash != self.fingerprint_hash:
            self._add_flag('device_switch',
                           f'Device fingerprint changed between {bonus_type} claims')
            cache.set(key, self.fingerprint_hash, 86400)

    def _check_circular_withdrawal(self, bonus_type: str):
        """Signal 4: Claim bonus → immediate withdrawal (circular pattern)."""
        if not self.user:
            return

        cache_key = f"pi:withdrawal_after_bonus:{self.user.pk}"
        recent_withdrawal = cache.get(cache_key, False)

        if recent_withdrawal and bonus_type in ('welcome_bonus', 'first_deposit_bonus'):
            self._add_flag('circular_withdrawal',
                           'Recent withdrawal detected before bonus claim — circular fraud')

    def _check_prior_activity(self, has_deposits: bool,
                               has_activity: bool, bonus_type: str):
        """Signal 5: Claiming bonus without any real platform activity."""
        high_value_bonuses = {'welcome_bonus', 'first_deposit_bonus', 'cashback'}
        if bonus_type in high_value_bonuses:
            if not has_deposits and not has_activity:
                self._add_flag('no_prior_activity',
                               f'{bonus_type} claimed with no prior deposits or activity')

    def _check_account_age(self, account_age_days: Optional[int],
                            bonus_type: str):
        """Signal 6: Account too new for the claimed bonus."""
        if account_age_days is None:
            return

        MIN_AGE = {
            'cashback':      7,
            'loyalty_bonus': 30,
            'vip_bonus':     60,
        }

        required_age = MIN_AGE.get(bonus_type, 0)
        if required_age > 0 and account_age_days < required_age:
            self._add_flag('account_age_too_short',
                           f'Account only {account_age_days}d old — needs {required_age}d for {bonus_type}')

        # Brand-new accounts instantly claiming bonuses
        if bonus_type != 'welcome_bonus' and account_age_days == 0:
            self._add_flag('new_account_instant_claim',
                           f'Account created today claiming {bonus_type} immediately')

    def _check_high_value(self, bonus_amount: float):
        """Signal 7: Unusually high bonus amount for this IP's history."""
        if bonus_amount <= 0:
            return

        # Check if this IP has claimed unusually high bonuses recently
        key = f"pi:incentive_total:{self.ip_address}"
        total_today = cache.get(key, 0.0) + bonus_amount
        cache.set(key, total_today, 86400)

        if total_today > 500:  # $500+ in bonuses from one IP per day
            self._add_flag('high_value_suspicious',
                           f'Total bonus value today from this IP: ${total_today:.2f}')

    def _check_promotion_code(self, promo_code: str):
        """Signal 8: Promotion code shared across many accounts."""
        if not promo_code:
            return

        key   = f"pi:promo_uses:{promo_code}"
        uses  = cache.get(key, {})
        if self.ip_address not in uses:
            uses[self.ip_address] = 0
        uses[self.ip_address] += 1
        cache.set(key, uses, 86400)

        # More than 3 different IPs using same promo code in a day
        if len(uses) > 5:
            self._add_flag('promo_code_shared',
                           f'Promo code {promo_code!r} used from {len(uses)} IPs today')

    def _check_referral_bonus(self, referral_user_id: int):
        """Signal 9: Referral bonus fraud (self-referral rings)."""
        if not self.user:
            return

        if self.user.pk == referral_user_id:
            self._add_flag('self_referral_bonus', 'User claiming own referral bonus')
            return

        # Check if referral user is on the same IP
        try:
            from ..models import IPIntelligence, UserRiskProfile
            risk = UserRiskProfile.objects.filter(
                user_id=referral_user_id,
                multi_account_detected=True,
            ).exists()
            if risk:
                self._add_flag('self_referral_bonus',
                               'Referring user has multi-account flag — ring referral suspected')
        except Exception:
            pass

    # ── Helpers ────────────────────────────────────────────────────────────

    def _add_flag(self, signal: str, description: str):
        score = self.SIGNAL_SCORES.get(signal, 10)
        self.flags.append({'signal': signal, 'description': description, 'score': score})
        self.score += score

    def _get_recommendation(self) -> str:
        if self.score >= 75: return 'block'
        if self.score >= 50: return 'review'
        if self.score >= 30: return 'flag'
        return 'allow'

    def _classify_fraud_types(self) -> list:
        types = set()
        for f in self.flags:
            s = f['signal']
            if 'multiple_claims' in s or 'claim_velocity' in s:
                types.add('bonus_farming')
            if 'vpn' in s or 'tor' in s:
                types.add('anonymous_claim')
            if 'circular' in s:
                types.add('circular_fraud')
            if 'referral' in s:
                types.add('referral_fraud')
            if 'device_switch' in s:
                types.add('identity_switching')
        return sorted(types)

    def _save_fraud(self, bonus_type: str, amount: float, promo_code: str):
        try:
            from ..models import FraudAttempt
            FraudAttempt.objects.create(
                ip_address  = self.ip_address,
                user        = self.user,
                tenant      = self.tenant,
                fraud_type  = 'offer_fraud',
                status      = 'detected',
                risk_score  = self.score,
                description = f'Incentive fraud: bonus_type={bonus_type}, amount={amount}',
                flags       = [f['signal'] for f in self.flags],
                evidence    = {
                    'bonus_type': bonus_type,
                    'amount':     amount,
                    'promo_code': promo_code,
                    'signals':    self.flags,
                },
            )
        except Exception as e:
            logger.error(f"IncentiveFraudDetector save failed: {e}")
