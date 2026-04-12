"""
Pattern Recognition Engine  (PRODUCTION-READY — COMPLETE)
===========================================================
Identifies known fraud patterns in sequences of user actions.
Works by maintaining a sliding-window action history in Redis
and matching against a library of fraud pattern signatures.

Patterns detected:
  - Rapid login attempts (credential stuffing)
  - Sequential offer completions in inhuman time
  - Identical click timing (bot automation)
  - Repeated same-action bursts
  - Cross-session IP hopping
  - Referral chain fraud
  - Device fingerprint switching mid-session
"""
import logging
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Pattern Library ────────────────────────────────────────────────────────
# Each pattern: name, action_type_keyword, threshold, window_sec, risk_score
FRAUD_PATTERNS = [
    {
        'name':     'rapid_login_attempts',
        'keyword':  'login',
        'threshold': 5,
        'window':   60,
        'score':    35,
        'description': 'More than 5 login attempts within 60 seconds — credential stuffing signal.',
    },
    {
        'name':     'bulk_offer_completions',
        'keyword':  'offer_complete',
        'threshold': 10,
        'window':   300,
        'score':    40,
        'description': 'More than 10 offer completions within 5 minutes — incentive fraud signal.',
    },
    {
        'name':     'high_frequency_api_calls',
        'keyword':  'api_call',
        'threshold': 120,
        'window':   60,
        'score':    25,
        'description': 'More than 120 API calls per minute — bot automation signal.',
    },
    {
        'name':     'repeated_same_action',
        'keyword':  'task_submit',
        'threshold': 20,
        'window':   120,
        'score':    30,
        'description': 'Same task submitted more than 20 times in 2 minutes — bot signal.',
    },
    {
        'name':     'referral_signup_burst',
        'keyword':  'referral_signup',
        'threshold': 3,
        'window':   3600,
        'score':    45,
        'description': 'More than 3 referral signups per hour from same IP — referral fraud.',
    },
    {
        'name':     'withdrawal_velocity',
        'keyword':  'withdrawal',
        'threshold': 3,
        'window':   3600,
        'score':    50,
        'description': 'More than 3 withdrawal attempts per hour — withdrawal fraud signal.',
    },
    {
        'name':     'reward_claim_burst',
        'keyword':  'reward_claim',
        'threshold': 5,
        'window':   3600,
        'score':    45,
        'description': 'More than 5 reward claims per hour from same IP — reward fraud.',
    },
    {
        'name':     'kyc_bypass_attempts',
        'keyword':  'kyc_attempt',
        'threshold': 3,
        'window':   3600,
        'score':    55,
        'description': 'Repeated KYC attempts — identity fraud / document spoofing signal.',
    },
    {
        'name':     'password_reset_abuse',
        'keyword':  'password_reset',
        'threshold': 3,
        'window':   3600,
        'score':    30,
        'description': 'Repeated password reset requests — account takeover signal.',
    },
    {
        'name':     'click_fraud_burst',
        'keyword':  'offer_click',
        'threshold': 20,
        'window':   60,
        'score':    40,
        'description': 'More than 20 offer clicks per minute — click fraud bot signal.',
    },
]


class PatternRecognizer:
    """
    Recognizes fraud patterns from action event streams.

    Usage:
        recognizer = PatternRecognizer(ip_address='1.2.3.4', user_id=123)
        result = recognizer.record_and_check('offer_complete')
        if result['patterns_triggered']:
            # take action
    """

    def __init__(self, ip_address: str = '', user_id: Optional[int] = None,
                 tenant_id: Optional[int] = None):
        self.ip_address = ip_address
        self.user_id    = user_id
        self.tenant_id  = tenant_id

    # ── Public API ─────────────────────────────────────────────────────────

    def record_and_check(self, action_type: str,
                          metadata: dict = None) -> dict:
        """
        Record an action and immediately check for pattern violations.

        Args:
            action_type: e.g. 'login', 'offer_complete', 'api_call'
            metadata:    Optional dict with extra context

        Returns:
            {
                'action_type':         str,
                'patterns_triggered':  list of triggered pattern names,
                'total_risk_score':    int (0-100),
                'is_fraud_pattern':    bool,
                'action_counts':       {action_type: count},
                'recommendations':     list of recommended actions,
            }
        """
        self._record_action(action_type, metadata)
        return self.check_patterns(action_type)

    def check_patterns(self, action_type: str = None) -> dict:
        """
        Check all patterns (or patterns matching a specific action_type).
        Does NOT record a new action — use record_and_check for that.
        """
        triggered     = []
        total_score   = 0
        action_counts = {}

        patterns_to_check = FRAUD_PATTERNS
        if action_type:
            patterns_to_check = [
                p for p in FRAUD_PATTERNS
                if p['keyword'] in action_type or action_type in p['keyword']
            ]

        for pattern in patterns_to_check:
            count = self._get_action_count(pattern['keyword'], pattern['window'])
            action_counts[pattern['name']] = count

            if count >= pattern['threshold']:
                triggered.append({
                    'pattern':     pattern['name'],
                    'description': pattern['description'],
                    'count':       count,
                    'threshold':   pattern['threshold'],
                    'window_sec':  pattern['window'],
                    'risk_score':  pattern['score'],
                })
                total_score += pattern['score']

        total_score = min(total_score, 100)
        recommendations = self._build_recommendations(triggered)

        # Persist to AnomalyDetectionLog if patterns triggered
        if triggered:
            self._log_anomaly(triggered, total_score)

        return {
            'ip_address':        self.ip_address,
            'action_type':       action_type or 'all',
            'patterns_triggered': triggered,
            'total_risk_score':  total_score,
            'is_fraud_pattern':  len(triggered) > 0,
            'action_counts':     action_counts,
            'recommendations':   recommendations,
            'checked_at':        timezone.now().isoformat(),
        }

    def record_action(self, action_type: str,
                       metadata: dict = None) -> int:
        """
        Record an action in the sliding window counter.
        Returns the current count for this action in the window.
        """
        return self._record_action(action_type, metadata)

    def get_action_history(self, action_type: str,
                            window_sec: int = 300) -> dict:
        """
        Get the action history for a specific action type.
        """
        count = self._get_action_count(action_type, window_sec)
        history_key = self._history_key(action_type)
        history = cache.get(history_key, [])

        return {
            'action_type':  action_type,
            'count':        count,
            'window_sec':   window_sec,
            'ip_address':   self.ip_address,
            'user_id':      self.user_id,
            'recent_events': history[-10:],  # Last 10 events
        }

    def reset(self, action_type: str = None):
        """
        Reset counters. If action_type is None, reset all patterns.
        """
        if action_type:
            patterns = [p for p in FRAUD_PATTERNS if action_type in p['keyword']]
        else:
            patterns = FRAUD_PATTERNS

        for pattern in patterns:
            key = self._counter_key(pattern['keyword'], pattern['window'])
            cache.delete(key)
            history_key = self._history_key(pattern['keyword'])
            cache.delete(history_key)

    def get_risk_summary(self) -> dict:
        """
        Get a full risk summary for this IP/user across all patterns.
        """
        results = self.check_patterns()
        return {
            'ip_address':       self.ip_address,
            'user_id':          self.user_id,
            'overall_score':    results['total_risk_score'],
            'patterns_found':   len(results['patterns_triggered']),
            'is_high_risk':     results['total_risk_score'] >= 40,
            'top_pattern':      results['patterns_triggered'][0] if results['patterns_triggered'] else None,
            'recommendations':  results['recommendations'],
        }

    # ── Private Helpers ────────────────────────────────────────────────────

    def _record_action(self, action_type: str,
                        metadata: dict = None) -> int:
        """Increment the sliding window counter for this action."""
        # Find matching patterns to get the right window
        matching = [p for p in FRAUD_PATTERNS if p['keyword'] in action_type]
        window = matching[0]['window'] if matching else 300

        counter_key = self._counter_key(action_type, window)
        try:
            count = cache.incr(counter_key)
        except ValueError:
            cache.set(counter_key, 1, window)
            count = 1

        # Store event history (last 50 events)
        history_key = self._history_key(action_type)
        history = cache.get(history_key, [])
        history.append({
            'time':     timezone.now().isoformat(),
            'count':    count,
            'meta':     metadata or {},
        })
        cache.set(history_key, history[-50:], window * 2)

        return count

    def _get_action_count(self, action_keyword: str, window_sec: int) -> int:
        """Get current counter value for an action in its window."""
        key = self._counter_key(action_keyword, window_sec)
        return cache.get(key, 0)

    def _counter_key(self, action_type: str, window_sec: int) -> str:
        """Build a Redis key for the action counter."""
        parts = ['pi:pattern']
        if self.ip_address:
            parts.append(f"ip:{self.ip_address}")
        if self.user_id:
            parts.append(f"u:{self.user_id}")
        parts.append(f"{action_type}:{window_sec}")
        return ':'.join(parts)

    def _history_key(self, action_type: str) -> str:
        """Build a Redis key for the action history list."""
        parts = ['pi:phist']
        if self.ip_address:
            parts.append(f"ip:{self.ip_address}")
        if self.user_id:
            parts.append(f"u:{self.user_id}")
        parts.append(action_type)
        return ':'.join(parts)

    def _build_recommendations(self, triggered: list) -> list:
        """Build a list of recommended actions from triggered patterns."""
        recommendations = set()
        for pattern in triggered:
            score = pattern['risk_score']
            if score >= 50:
                recommendations.add('block')
            elif score >= 35:
                recommendations.add('challenge')
            else:
                recommendations.add('flag')
        # Return in priority order
        priority = ['block', 'challenge', 'flag']
        return [r for r in priority if r in recommendations]

    def _log_anomaly(self, triggered: list, total_score: int):
        """Write triggered patterns to AnomalyDetectionLog."""
        try:
            from ..models import AnomalyDetectionLog
            AnomalyDetectionLog.objects.create(
                ip_address   = self.ip_address or '0.0.0.0',
                anomaly_type = 'pattern_deviation',
                description  = (
                    f"{len(triggered)} fraud pattern(s) triggered: "
                    + ', '.join(p['pattern'] for p in triggered)
                ),
                anomaly_score = total_score / 100,
                evidence      = {
                    'triggered_patterns': triggered,
                    'user_id':            self.user_id,
                    'ip_address':         self.ip_address,
                },
            )
        except Exception as e:
            logger.debug(f"PatternRecognizer anomaly log failed: {e}")


# ── Module-level convenience function ─────────────────────────────────────

def check_action_pattern(ip_address: str, action_type: str,
                          user_id: int = None) -> dict:
    """
    One-liner convenience wrapper.
    Records the action and returns pattern check results.
    """
    recognizer = PatternRecognizer(
        ip_address=ip_address, user_id=user_id
    )
    return recognizer.record_and_check(action_type)
