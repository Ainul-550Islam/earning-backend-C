"""
Reward Fraud Detector  (PRODUCTION-READY — COMPLETE)
======================================================
Detects fake task/survey completions to earn platform rewards.
Specifically built for CPAlead/CPAgrip-style earning platforms
where users complete offers, surveys, and tasks for rewards.

Fraud patterns:
  1. Instant task completion (bot automation)
  2. Duplicate task claims (same offer, different accounts)
  3. VPN/proxy/Tor usage during reward claim
  4. Device fingerprint switching between claims
  5. IP velocity — too many claims from one IP
  6. Cross-account reward accumulation patterns
  7. Reward-to-withdrawal circular fraud
  8. Fake survey completions (page load → immediate submit)
  9. High-value reward claim anomaly
  10. Platform-specific rule violations (offer wall abuse)
"""
import logging
from typing import Optional

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class RewardFraudDetector:
    """
    Detects reward fraud on earning/CPA platforms.

    Usage:
        detector = RewardFraudDetector(
            ip_address='1.2.3.4',
            user=request.user,
            tenant=request.tenant,
        )
        result = detector.check_reward_claim(
            task_id='task_survey_001',
            reward_amount=2.50,
            completion_time_sec=15.0,
            offer_wall='cpalead',
        )
    """

    SIGNAL_SCORES = {
        'instant_completion':       45,
        'duplicate_task_claim':     50,
        'vpn_during_claim':         30,
        'tor_during_claim':         45,
        'proxy_during_claim':       25,
        'ip_velocity_high':         40,
        'ip_velocity_moderate':     20,
        'device_fingerprint_change': 30,
        'high_value_anomaly':       25,
        'circular_withdrawal':      40,
        'cross_account_pattern':    35,
        'offer_wall_abuse':         30,
        'blacklisted_ip':           55,
        'no_referrer':              20,
    }

    # Min completion times per task type (seconds)
    MIN_COMPLETION_TIMES = {
        'survey':        45,
        'short_survey':  20,
        'video':         15,
        'offer':         20,
        'install':       30,
        'signup':        30,
        'quiz':          30,
        'task':          10,
        'click':          3,
        'default':       10,
    }

    # Max reward claims per IP per hour before flagging
    IP_HOURLY_LIMIT = 10
    IP_DAILY_LIMIT  = 30

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

    def check_reward_claim(
        self,
        task_id: str,
        reward_amount: float        = 0.0,
        completion_time_sec: Optional[float] = None,
        task_type: str              = 'default',
        offer_wall: str             = '',
        referrer_url: str           = '',
        has_prior_clicks: bool      = True,
    ) -> dict:
        """
        Run all fraud checks for a reward/task completion claim.

        Args:
            task_id:             Unique task/offer ID
            reward_amount:       Dollar value of the reward being claimed
            completion_time_sec: Time from page load to completion
            task_type:           'survey', 'video', 'install', etc.
            offer_wall:          Name of the offer wall (cpalead, cpx, etc.)
            referrer_url:        HTTP Referrer header
            has_prior_clicks:    Whether the user clicked into the task first

        Returns:
            {
                'is_fraud':         bool,
                'fraud_score':      int,
                'flags':            list,
                'should_reward':    bool,
                'recommendation':   str,
                'claim_count_hour': int,
                'claim_count_day':  int,
                'fraud_types':      list,
            }
        """
        self.flags = []
        self.score = 0

        hourly, daily = self._check_ip_velocity()
        self._check_completion_time(task_type, completion_time_sec)
        self._check_duplicate_claim(task_id)
        self._check_vpn_proxy_tor()
        self._check_blacklist()
        self._check_device_consistency(task_id)
        self._check_circular_withdrawal()
        self._check_high_value_reward(reward_amount, task_type)
        self._check_offer_wall_abuse(offer_wall)
        self._check_referrer(referrer_url, has_prior_clicks)
        self._check_cross_account_pattern(task_id)

        self.score = min(self.score, 100)
        is_fraud   = self.score >= 40

        if is_fraud:
            self._save_fraud_attempt(task_id, reward_amount, task_type)

        return {
            'ip_address':       self.ip_address,
            'task_id':          task_id,
            'task_type':        task_type,
            'reward_amount':    reward_amount,
            'is_fraud':         is_fraud,
            'fraud_score':      self.score,
            'flags':            self.flags,
            'should_reward':    not is_fraud,
            'recommendation':   self._get_recommendation(),
            'claim_count_hour': hourly,
            'claim_count_day':  daily,
            'fraud_types':      self._get_fraud_types(),
            'checked_at':       timezone.now().isoformat(),
        }

    # ── Signal Checks ──────────────────────────────────────────────────────

    def _check_ip_velocity(self):
        """Signal 1: Too many reward claims from this IP."""
        hour_key = f"pi:reward_vel_h:{self.ip_address}"
        day_key  = f"pi:reward_vel_d:{self.ip_address}"

        hourly = cache.get(hour_key, 0) + 1
        daily  = cache.get(day_key, 0) + 1
        cache.set(hour_key, hourly, 3600)
        cache.set(day_key,  daily,  86400)

        if hourly > self.IP_HOURLY_LIMIT:
            self._add_flag('ip_velocity_high',
                           f'{hourly} reward claims this hour from one IP (limit={self.IP_HOURLY_LIMIT})')
        elif hourly > self.IP_HOURLY_LIMIT // 2:
            self._add_flag('ip_velocity_moderate',
                           f'{hourly} reward claims this hour — approaching limit')

        if daily > self.IP_DAILY_LIMIT:
            self._add_flag('ip_velocity_high',
                           f'{daily} reward claims today from one IP (limit={self.IP_DAILY_LIMIT})')

        return hourly, daily

    def _check_completion_time(self, task_type: str,
                                elapsed: Optional[float]):
        """Signal 2: Task completed faster than humanly possible."""
        if elapsed is None:
            return

        min_time = self.MIN_COMPLETION_TIMES.get(
            task_type, self.MIN_COMPLETION_TIMES['default']
        )

        if elapsed <= 0:
            self._add_flag('instant_completion',
                           f'Instant completion (elapsed={elapsed:.2f}s) — bot signal')
        elif elapsed < min_time:
            self._add_flag('instant_completion',
                           f'Completed {task_type} in {elapsed:.1f}s (min={min_time}s for humans)')

    def _check_duplicate_claim(self, task_id: str):
        """Signal 3: Same task claimed multiple times from this IP or user."""
        # Per-IP per-task check
        ip_task_key = f"pi:reward_claim:{self.ip_address}:{task_id}"
        ip_count    = cache.get(ip_task_key, 0) + 1
        cache.set(ip_task_key, ip_count, 86400)

        if ip_count > 1:
            self._add_flag('duplicate_task_claim',
                           f'Task {task_id!r} claimed {ip_count}x from this IP')

        # Per-user per-task check
        if self.user:
            user_task_key = f"pi:reward_user:{self.user.pk}:{task_id}"
            user_count    = cache.get(user_task_key, 0) + 1
            cache.set(user_task_key, user_count, 86400)
            if user_count > 1:
                self._add_flag('duplicate_task_claim',
                               f'User already claimed task {task_id!r}')

    def _check_vpn_proxy_tor(self):
        """Signal 4: VPN/proxy/Tor usage during reward claim."""
        try:
            from ..models import IPIntelligence
            intel = IPIntelligence.objects.filter(
                ip_address=self.ip_address
            ).values('is_vpn', 'is_proxy', 'is_tor').first()
            if intel:
                if intel.get('is_tor'):
                    self._add_flag('tor_during_claim',
                                   'Reward claimed via Tor — anonymization signal')
                elif intel.get('is_vpn'):
                    self._add_flag('vpn_during_claim',
                                   'Reward claimed while using VPN')
                elif intel.get('is_proxy'):
                    self._add_flag('proxy_during_claim',
                                   'Reward claimed via proxy')
        except Exception:
            pass

    def _check_blacklist(self):
        """Signal 5: IP is on the active blacklist."""
        try:
            from ..models import IPBlacklist
            is_bl = IPBlacklist.objects.filter(
                ip_address=self.ip_address, is_active=True
            ).exists()
            if is_bl:
                self._add_flag('blacklisted_ip',
                               'IP is on the active blacklist — automatic block')
        except Exception:
            pass

    def _check_device_consistency(self, task_id: str):
        """Signal 6: Device fingerprint changed between reward claims."""
        if not self.fingerprint_hash or not self.user:
            return

        key = f"pi:reward_fp:{self.user.pk}"
        stored = cache.get(key)
        if stored is None:
            cache.set(key, self.fingerprint_hash, 86400)
        elif stored != self.fingerprint_hash:
            self._add_flag('device_fingerprint_change',
                           'Device fingerprint changed between reward claims — identity switch')
            cache.set(key, self.fingerprint_hash, 86400)

    def _check_circular_withdrawal(self):
        """Signal 7: Recent withdrawal before reward claim (circular fraud)."""
        if not self.user:
            return
        key = f"pi:withdrawal_recent:{self.user.pk}"
        if cache.get(key):
            self._add_flag('circular_withdrawal',
                           'Recent withdrawal detected — claim-withdraw circular pattern')

    def _check_high_value_reward(self, amount: float, task_type: str):
        """Signal 8: Unusually high reward for the task type."""
        TYPICAL_MAX = {
            'click':        0.10,
            'survey':       5.00,
            'short_survey': 1.50,
            'video':        0.50,
            'install':      3.00,
            'signup':       2.00,
            'offer':        10.00,
            'task':         5.00,
        }
        typical_max = TYPICAL_MAX.get(task_type, 5.00)

        if amount > typical_max * 5:
            self._add_flag('high_value_anomaly',
                           f'Reward ${amount:.2f} is {amount/typical_max:.1f}× typical max for {task_type}')

        # Track daily reward total from this IP
        day_total_key = f"pi:reward_total:{self.ip_address}"
        total_today   = cache.get(day_total_key, 0.0) + amount
        cache.set(day_total_key, total_today, 86400)
        if total_today > 100:
            self._add_flag('high_value_anomaly',
                           f'Total rewards from this IP today: ${total_today:.2f}')

    def _check_offer_wall_abuse(self, offer_wall: str):
        """Signal 9: Offer wall being abused (repeated submissions)."""
        if not offer_wall:
            return
        key   = f"pi:offer_wall:{self.ip_address}:{offer_wall}"
        count = cache.get(key, 0) + 1
        cache.set(key, count, 3600)

        if count > 20:
            self._add_flag('offer_wall_abuse',
                           f'IP submitted {count} tasks on {offer_wall} in 1 hour')

    def _check_referrer(self, referrer_url: str, has_prior_clicks: bool):
        """Signal 10: No referrer and no prior clicks = direct bot POST."""
        if not referrer_url and not has_prior_clicks:
            self._add_flag('no_referrer',
                           'No referrer URL and no prior click recorded — direct POST (bot)')

    def _check_cross_account_pattern(self, task_id: str):
        """Signal 11: Multiple accounts claiming the same task from this IP."""
        key      = f"pi:task_accounts:{self.ip_address}:{task_id}"
        accounts = cache.get(key, set())
        if self.user:
            accounts.add(str(self.user.pk))
        cache.set(key, accounts, 86400)

        if len(accounts) > 2:
            self._add_flag('cross_account_pattern',
                           f'{len(accounts)} accounts claimed task {task_id!r} from this IP')

    # ── Helpers ────────────────────────────────────────────────────────────

    def _add_flag(self, signal: str, description: str):
        score = self.SIGNAL_SCORES.get(signal, 10)
        self.flags.append({'signal': signal, 'description': description, 'score': score})
        self.score += score

    def _get_recommendation(self) -> str:
        if self.score >= 75: return 'block'
        if self.score >= 50: return 'hold_for_review'
        if self.score >= 30: return 'flag'
        return 'allow'

    def _get_fraud_types(self) -> list:
        types = set()
        for f in self.flags:
            s = f['signal']
            if 'instant' in s or 'duplicate' in s:
                types.add('bot_automation')
            if 'vpn' in s or 'tor' in s or 'proxy' in s:
                types.add('anonymous_claim')
            if 'circular' in s:
                types.add('circular_fraud')
            if 'cross_account' in s or 'device_fingerprint' in s:
                types.add('multi_account_fraud')
            if 'velocity' in s or 'offer_wall' in s:
                types.add('velocity_fraud')
            if 'high_value' in s:
                types.add('value_manipulation')
        return sorted(types)

    def _save_fraud_attempt(self, task_id: str, amount: float, task_type: str):
        try:
            from ..models import FraudAttempt
            FraudAttempt.objects.create(
                ip_address  = self.ip_address,
                user        = self.user,
                tenant      = self.tenant,
                fraud_type  = 'offer_fraud',
                status      = 'detected',
                risk_score  = self.score,
                description = (
                    f'Reward fraud: task={task_id}, type={task_type}, amount=${amount:.2f}'
                ),
                flags       = [f['signal'] for f in self.flags],
                evidence    = {
                    'task_id':   task_id,
                    'amount':    amount,
                    'task_type': task_type,
                    'signals':   self.flags,
                },
            )
        except Exception as e:
            logger.error(f"RewardFraudDetector save failed: {e}")
