# api/admin_panel/fraud_rules_engine.py
"""Rule-based fraud detection engine — complements fraud_ml.py with explicit rules."""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Tuple
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class FraudRulesEngine:
    """Evaluate explicit fraud detection rules against events."""

    @classmethod
    def evaluate_submission(cls, user_id: Any, campaign_id: Any,
                             ip: str, metadata: Dict = None) -> Dict:
        """Evaluate a task submission for fraud."""
        score = 0
        triggered_rules = []
        metadata = metadata or {}

        # Rule 1: Too fast (bot-like speed)
        last_sub_time = metadata.get('last_submission_seconds_ago', 9999)
        if last_sub_time < 5:
            score += 40
            triggered_rules.append({'rule': 'too_fast', 'detail': f'{last_sub_time}s since last sub', 'weight': 40})

        # Rule 2: Duplicate same campaign
        try:
            from api.promotions.models import TaskSubmission
            from django.db.models import Count
            today_count = TaskSubmission.objects.filter(
                worker_id=user_id, campaign_id=campaign_id,
                created_at__date=timezone.now().date()
            ).count()
            if today_count >= 3:
                score += 50
                triggered_rules.append({'rule': 'duplicate_same_day', 'detail': f'{today_count} subs today', 'weight': 50})
        except Exception:
            pass

        # Rule 3: Known VPN/Proxy IP
        try:
            from api.proxy_intelligence.models import VPNDetectionLog
            is_vpn = VPNDetectionLog.objects.filter(ip_address=ip, is_vpn=True).exists()
            if is_vpn:
                score += 30
                triggered_rules.append({'rule': 'vpn_detected', 'detail': f'IP {ip}', 'weight': 30})
        except Exception:
            pass

        # Rule 4: Blocked IP
        try:
            from api.fraud_detection.models import BlockedIP
            if BlockedIP.objects.filter(ip_address=ip).exists():
                score = 100
                triggered_rules.append({'rule': 'blocked_ip', 'detail': f'IP {ip} is blocked', 'weight': 100})
        except Exception:
            pass

        # Rule 5: New account with many submissions
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
            age_hours = (timezone.now() - user.date_joined).total_seconds() / 3600
            if age_hours < 24:
                try:
                    from api.promotions.models import TaskSubmission
                    recent_count = TaskSubmission.objects.filter(
                        worker_id=user_id,
                        created_at__gte=timezone.now() - timedelta(hours=24)
                    ).count()
                    if recent_count > 10:
                        score += 35
                        triggered_rules.append({'rule': 'new_account_high_volume',
                                                 'detail': f'{recent_count} subs in 24h, account {age_hours:.0f}h old', 'weight': 35})
                except Exception:
                    pass
        except Exception:
            pass

        score = min(100, score)
        level = 'critical' if score >= 90 else 'high' if score >= 70 else 'medium' if score >= 40 else 'low'

        result = {'score': score, 'level': level, 'rules_triggered': triggered_rules,
                  'user_id': user_id, 'campaign_id': campaign_id, 'ip': ip}

        # Auto-create fraud attempt if high score
        if score >= 70:
            cls._log_fraud_attempt(user_id, score, triggered_rules)

        return result

    @classmethod
    def _log_fraud_attempt(cls, user_id: Any, score: int, rules: List[Dict]) -> None:
        try:
            from api.fraud_detection.models import FraudAttempt
            FraudAttempt.objects.create(
                user_id=user_id,
                attempt_type='offer_abuse',
                fraud_score=score,
                description=f"Rules triggered: {[r['rule'] for r in rules]}",
                status='detected',
            )
        except Exception as e:
            logger.debug(f"[FraudRulesEngine._log] {e}")

    @classmethod
    def get_active_rules(cls) -> List[Dict]:
        """Get all active fraud rules from api.fraud_detection."""
        try:
            from api.fraud_detection.models import FraudRule
            return list(FraudRule.objects.filter(is_active=True).values(
                'id', 'name', 'rule_type', 'severity', 'weight', 'threshold', 'action_on_trigger'
            ).order_by('-weight'))
        except Exception:
            return []


fraud_rules_engine = FraudRulesEngine()