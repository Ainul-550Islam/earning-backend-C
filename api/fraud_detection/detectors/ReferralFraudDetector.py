# =============================================================================
# fraud_detection/detectors/ReferralFraudDetector.py
# =============================================================================
"""
Referral Fraud Detector.

Detects:
  - Self-referral (user refers themselves via alt accounts)
  - Referral ring / farm (coordinated fake referrals)
  - IP-based referral clustering (same IP generates many referrals)
  - Device-based referral clustering
  - Velocity abuse (too many referrals in short window)
  - Fake account referral (referred user never converts)
  - Bonus farming (refer → collect bonus → never use platform)
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class ReferralFraudDetector:
    """
    Detects referral fraud using multi-signal analysis.

    Usage:
        detector = ReferralFraudDetector()
        result = detector.detect({
            'referrer_user_id': 42,
            'referred_user_id': 99,
            'referral_code':    'REF123',
            'ip_address':       '1.2.3.4',
            'device_id':        'dev_abc',
            'timestamp':        '2025-01-01T12:00:00Z',
        })
        # result = {'risk_score': 0-100, 'is_fraud': bool, 'reasons': [...], ...}
    """

    # Risk score thresholds
    HIGH_RISK   = 70
    MEDIUM_RISK = 40

    # Config keys (read from settings.REFERRAL_FRAUD_CONFIG or defaults)
    _DEFAULT_CONFIG = {
        'max_referrals_per_hour':       5,
        'max_referrals_per_day':        20,
        'max_referrals_per_ip_hour':    3,
        'max_referrals_per_device_day': 10,
        'min_account_age_days':         1,
        'ring_min_cluster_size':        3,
        'bonus_farm_inactivity_days':   7,
        'self_referral_score':          95,
        'ring_score':                   85,
        'ip_cluster_score':             70,
        'device_cluster_score':         65,
        'velocity_score':               60,
        'bonus_farm_score':             55,
        'new_account_score':            30,
        'cache_ttl':                    3600,
    }

    def __init__(self):
        cfg = getattr(settings, 'REFERRAL_FRAUD_CONFIG', {})
        self._cfg = {**self._DEFAULT_CONFIG, **cfg}

    # =========================================================================
    # Public API
    # =========================================================================

    def detect(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run all referral fraud checks on a single referral event.

        Args:
            data: dict with keys:
                referrer_user_id  (int)       — user giving the referral
                referred_user_id  (int|None)  — user being referred (may not exist yet)
                referral_code     (str)        — the code used
                ip_address        (str|None)
                device_id         (str|None)
                timestamp         (str|None)  — ISO-8601; defaults to now
                metadata          (dict|None)

        Returns:
            {
              'risk_score':   0-100,
              'is_fraud':     bool,
              'is_suspicious': bool,
              'reasons':      [str],
              'signals':      {signal_name: score},
              'recommendation': 'allow' | 'review' | 'block',
              'checked_at':   str,
            }
        """
        referrer_id  = data.get('referrer_user_id')
        referred_id  = data.get('referred_user_id')
        referral_code = data.get('referral_code', '')
        ip_address   = data.get('ip_address', '')
        device_id    = data.get('device_id', '')

        reasons: List[str] = []
        signals: Dict[str, int] = {}
        extra_score = 0

        # 1. Self-referral check
        self_score = self._check_self_referral(referrer_id, referred_id, ip_address, device_id)
        if self_score:
            signals['self_referral'] = self_score
            extra_score = max(extra_score, self_score)
            reasons.append(f'Self-referral detected (score={self_score})')

        # 2. Referral ring check
        ring_score = self._check_referral_ring(referrer_id, ip_address, device_id)
        if ring_score:
            signals['referral_ring'] = ring_score
            extra_score = max(extra_score, ring_score)
            reasons.append(f'Referral ring detected (score={ring_score})')

        # 3. IP clustering
        ip_score = self._check_ip_clustering(ip_address, referrer_id)
        if ip_score:
            signals['ip_clustering'] = ip_score
            extra_score = max(extra_score, ip_score)
            reasons.append(f'IP referral cluster (score={ip_score})')

        # 4. Device clustering
        dev_score = self._check_device_clustering(device_id, referrer_id)
        if dev_score:
            signals['device_clustering'] = dev_score
            extra_score = max(extra_score, dev_score)
            reasons.append(f'Device referral cluster (score={dev_score})')

        # 5. Velocity check (too many referrals too fast)
        vel_score = self._check_referral_velocity(referrer_id, ip_address)
        if vel_score:
            signals['velocity'] = vel_score
            extra_score = max(extra_score, vel_score)
            reasons.append(f'Referral velocity exceeded (score={vel_score})')

        # 6. Bonus farming (referred user never active after signup)
        farm_score = self._check_bonus_farming(referred_id)
        if farm_score:
            signals['bonus_farming'] = farm_score
            extra_score += farm_score // 3
            reasons.append(f'Bonus farming pattern detected (score={farm_score})')

        # 7. New account used as referral vehicle
        new_acc_score = self._check_new_account(referrer_id)
        if new_acc_score:
            signals['new_account'] = new_acc_score
            extra_score += new_acc_score // 4

        risk_score = min(100, extra_score)
        is_fraud      = risk_score >= self.HIGH_RISK
        is_suspicious = risk_score >= self.MEDIUM_RISK

        if is_fraud:
            recommendation = 'block'
        elif is_suspicious:
            recommendation = 'review'
        else:
            recommendation = 'allow'

        # Update velocity cache
        if referrer_id:
            self._record_referral(referrer_id, ip_address, device_id)

        return {
            'risk_score':     risk_score,
            'is_fraud':       is_fraud,
            'is_suspicious':  is_suspicious,
            'reasons':        reasons,
            'signals':        signals,
            'recommendation': recommendation,
            'referrer_id':    referrer_id,
            'referred_id':    referred_id,
            'referral_code':  referral_code,
            'checked_at':     timezone.now().isoformat(),
        }

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Alias for detect() — consistent with other detectors."""
        return self.detect(data)

    def batch_detect(self, referrals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run detect() on a list of referral events."""
        return [self.detect(r) for r in referrals]

    # =========================================================================
    # Individual signal checks
    # =========================================================================

    def _check_self_referral(
        self,
        referrer_id: Optional[int],
        referred_id: Optional[int],
        ip_address: str,
        device_id: str,
    ) -> int:
        """
        Detect self-referral: same user across multiple signals.
        Returns 0-95 score.
        """
        if not referrer_id:
            return 0

        score = 0

        # Direct: same user ID
        if referred_id and referrer_id == referred_id:
            return self._cfg['self_referral_score']

        # Indirect: referred user shares IP with referrer's recent activity
        if ip_address:
            cache_key = f'ref_ip:{referrer_id}'
            known_ips = cache.get(cache_key, set())
            if ip_address in known_ips and referred_id:
                score = max(score, 75)

        # Indirect: referred user shares device with referrer
        if device_id:
            cache_key = f'ref_dev:{referrer_id}'
            known_devices = cache.get(cache_key, set())
            if device_id in known_devices and referred_id:
                score = max(score, 80)

        # Database check: does referred user share IP/device with referrer's attempts?
        if referred_id and referrer_id:
            try:
                from api.fraud_detection.models import DeviceFingerprint
                referrer_ips = set(
                    DeviceFingerprint.objects.filter(user_id=referrer_id)
                    .values_list('ip_address', flat=True)
                )
                referred_ips = set(
                    DeviceFingerprint.objects.filter(user_id=referred_id)
                    .values_list('ip_address', flat=True)
                )
                shared_ips = referrer_ips & referred_ips
                if shared_ips:
                    score = max(score, 70)
            except Exception as exc:
                logger.debug("_check_self_referral DB check failed: %s", exc)

        return score

    def _check_referral_ring(
        self,
        referrer_id: Optional[int],
        ip_address: str,
        device_id: str,
    ) -> int:
        """
        Detect referral rings: A→B→C→A circular patterns.
        Returns 0-85 score.
        """
        if not referrer_id:
            return 0

        score = 0
        cfg = self._cfg

        try:
            # Get users the referrer has referred
            from django.contrib.auth import get_user_model
            User = get_user_model()

            # Check how many users share this referral code / IP cluster
            ip_cluster_key = f'ring_ip:{ip_address}' if ip_address else None
            if ip_cluster_key:
                cluster_members = cache.get(ip_cluster_key, set())
                cluster_members.add(referrer_id)
                cache.set(ip_cluster_key, cluster_members, timeout=cfg['cache_ttl'])

                if len(cluster_members) >= cfg['ring_min_cluster_size']:
                    score = cfg['ring_score']

        except Exception as exc:
            logger.debug("_check_referral_ring failed: %s", exc)

        return score

    def _check_ip_clustering(
        self,
        ip_address: str,
        referrer_id: Optional[int],
    ) -> int:
        """
        Detect many referrals from the same IP in a short window.
        Returns 0-70 score.
        """
        if not ip_address:
            return 0

        cache_key = f'ref_ip_count:{ip_address}'
        count = cache.get(cache_key, 0)

        limit = self._cfg['max_referrals_per_ip_hour']
        if count >= limit:
            excess_ratio = min(count / limit, 3)
            return int(self._cfg['ip_cluster_score'] * (excess_ratio / 3))

        return 0

    def _check_device_clustering(
        self,
        device_id: str,
        referrer_id: Optional[int],
    ) -> int:
        """
        Detect many referrals from the same device in a day window.
        Returns 0-65 score.
        """
        if not device_id:
            return 0

        cache_key = f'ref_dev_count:{device_id}'
        count = cache.get(cache_key, 0)

        limit = self._cfg['max_referrals_per_device_day']
        if count >= limit:
            excess_ratio = min(count / limit, 3)
            return int(self._cfg['device_cluster_score'] * (excess_ratio / 3))

        return 0

    def _check_referral_velocity(
        self,
        referrer_id: Optional[int],
        ip_address: str,
    ) -> int:
        """
        Detect burst referrals in short windows.
        Returns 0-60 score.
        """
        if not referrer_id:
            return 0

        # Per-user hourly check
        hourly_key = f'ref_vel_1h:{referrer_id}'
        hourly_count = cache.get(hourly_key, 0)
        hourly_limit = self._cfg['max_referrals_per_hour']

        if hourly_count >= hourly_limit:
            ratio = min(hourly_count / hourly_limit, 4)
            return int(self._cfg['velocity_score'] * min(ratio / 4, 1.0))

        # Per-user daily check
        daily_key = f'ref_vel_24h:{referrer_id}'
        daily_count = cache.get(daily_key, 0)
        daily_limit = self._cfg['max_referrals_per_day']

        if daily_count >= daily_limit:
            ratio = min(daily_count / daily_limit, 3)
            return int(self._cfg['velocity_score'] * 0.7 * min(ratio / 3, 1.0))

        return 0

    def _check_bonus_farming(self, referred_id: Optional[int]) -> int:
        """
        Detect bonus farming: referred user signs up, collects bonus, then goes inactive.
        Returns 0-55 score.
        """
        if not referred_id:
            return 0

        try:
            from django.contrib.auth import get_user_model
            from api.fraud_detection.models import OfferCompletion
            User = get_user_model()

            user = User.objects.filter(pk=referred_id).first()
            if not user:
                return 0

            # User created recently?
            account_age = (timezone.now() - user.date_joined).days
            if account_age > self._cfg['bonus_farm_inactivity_days'] * 2:
                return 0  # Account too old to be a fresh farm account

            # Has offer completions but no login in the last N days?
            inactivity_cutoff = timezone.now() - timedelta(
                days=self._cfg['bonus_farm_inactivity_days']
            )
            has_completions = OfferCompletion.objects.filter(user_id=referred_id).exists()
            last_login = getattr(user, 'last_login', None)

            if has_completions and last_login and last_login < inactivity_cutoff:
                return self._cfg['bonus_farm_score']

        except Exception as exc:
            logger.debug("_check_bonus_farming failed: %s", exc)

        return 0

    def _check_new_account(self, referrer_id: Optional[int]) -> int:
        """
        New accounts used as referral vehicles (account age < min_account_age_days).
        Returns 0-30 score.
        """
        if not referrer_id:
            return 0

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()

            user = User.objects.filter(pk=referrer_id).only('date_joined').first()
            if not user:
                return 0

            age_days = (timezone.now() - user.date_joined).days
            if age_days < self._cfg['min_account_age_days']:
                return self._cfg['new_account_score']

        except Exception as exc:
            logger.debug("_check_new_account failed: %s", exc)

        return 0

    # =========================================================================
    # Cache management
    # =========================================================================

    def _record_referral(
        self,
        referrer_id: int,
        ip_address: str,
        device_id: str,
    ) -> None:
        """Update velocity + clustering counters after a referral event."""
        ttl = self._cfg['cache_ttl']

        # Per-user hourly counter
        key = f'ref_vel_1h:{referrer_id}'
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=3600)

        # Per-user daily counter
        key = f'ref_vel_24h:{referrer_id}'
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=86400)

        # Per-IP hourly counter
        if ip_address:
            key = f'ref_ip_count:{ip_address}'
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=3600)

            # Store referrer's IPs for self-referral detection
            key = f'ref_ip:{referrer_id}'
            ips: set = cache.get(key, set())
            ips.add(ip_address)
            cache.set(key, ips, timeout=ttl)

        # Per-device daily counter
        if device_id:
            key = f'ref_dev_count:{device_id}'
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=86400)

            # Store referrer's devices
            key = f'ref_dev:{referrer_id}'
            devices: set = cache.get(key, set())
            devices.add(device_id)
            cache.set(key, devices, timeout=ttl)
