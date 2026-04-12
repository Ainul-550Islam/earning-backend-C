"""Fraud Rule — model helpers and rule evaluation engine."""
import logging
from django.db import models

logger = logging.getLogger(__name__)


class FraudRuleManager(models.Manager):
    def active(self, tenant=None):
        qs = self.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by("priority")

    def by_condition(self, condition_type: str, tenant=None):
        qs = self.active(tenant).filter(condition_type=condition_type)
        return qs

    def evaluate_all(self, context: dict, tenant=None) -> list:
        """
        Evaluate all active rules against a context dict.
        context keys: is_vpn, is_tor, risk_score, velocity_exceeded, etc.
        Returns list of triggered rule names with actions.
        """
        triggered = []
        for rule in self.active(tenant):
            if self._matches(rule, context):
                triggered.append({
                    "rule": rule.name,
                    "action": rule.action,
                    "priority": rule.priority,
                })
                try:
                    from ..models import FraudRule
                    FraudRule.objects.filter(pk=rule.pk).update(
                        trigger_count=models.F("trigger_count") + 1
                    )
                except Exception:
                    pass
        return triggered

    @staticmethod
    def _matches(rule, context: dict) -> bool:
        ct = rule.condition_type
        val = rule.condition_value or {}
        if ct == "ip_risk_score_gt":
            return context.get("risk_score", 0) > val.get("threshold", 60)
        if ct == "vpn_detected":
            return bool(context.get("is_vpn"))
        if ct == "proxy_detected":
            return bool(context.get("is_proxy"))
        if ct == "tor_detected":
            return bool(context.get("is_tor"))
        if ct == "velocity_exceeded":
            return bool(context.get("velocity_exceeded"))
        if ct == "multi_account":
            return bool(context.get("multi_account"))
        if ct == "blacklisted":
            return bool(context.get("is_blacklisted"))
        return False
