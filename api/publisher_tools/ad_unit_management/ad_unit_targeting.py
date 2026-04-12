# api/publisher_tools/ad_unit_management/ad_unit_targeting.py
"""Ad Unit Targeting — Advanced targeting rules and management."""
from typing import Dict, List
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AdUnitTargetingRule(TimeStampedModel):
    """Individual targeting rule for ad units."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_targetingrule_tenant", db_index=True)
    ad_unit         = models.ForeignKey("publisher_tools.AdUnit", on_delete=models.CASCADE, related_name="targeting_rules")
    rule_type       = models.CharField(max_length=20, choices=[
        ("geo","Geographic"),("device","Device"),("os","Operating System"),
        ("browser","Browser"),("time","Time Schedule"),("frequency","Frequency Cap"),
        ("audience","Audience Segment"),("keyword","Keyword"),
    ], db_index=True)
    rule_action     = models.CharField(max_length=10, choices=[("include","Include"),("exclude","Exclude")], default="include")
    rule_values     = models.JSONField(default=list)
    operator        = models.CharField(max_length=10, choices=[("and","AND"),("or","OR")], default="or")
    priority        = models.IntegerField(default=0)
    is_active       = models.BooleanField(default=True, db_index=True)
    description     = models.CharField(max_length=300, blank=True)
    starts_at       = models.DateTimeField(null=True, blank=True)
    ends_at         = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "publisher_tools_ad_unit_targeting_rules"
        verbose_name = _("Targeting Rule")
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["ad_unit", "rule_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.ad_unit.unit_id} — {self.rule_type} {self.rule_action}: {str(self.rule_values)[:40]}"

    @property
    def is_scheduled(self):
        now = timezone.now()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True

    @property
    def is_effective(self):
        return self.is_active and self.is_scheduled


def apply_targeting_rules(ad_unit, request_context: Dict) -> bool:
    """Request context-এ targeting rules apply করে। True = show ad."""
    rules = AdUnitTargetingRule.objects.filter(ad_unit=ad_unit, is_active=True).order_by("-priority")
    for rule in rules:
        if not rule.is_effective:
            continue
        if rule.rule_type == "geo":
            country = request_context.get("country", "")
            match = country in rule.rule_values or "ALL" in rule.rule_values
            if rule.rule_action == "exclude" and match:
                return False
            if rule.rule_action == "include" and not match and "ALL" not in rule.rule_values:
                return False
        elif rule.rule_type == "device":
            device = request_context.get("device_type", "")
            match = device in rule.rule_values or "all" in rule.rule_values
            if rule.rule_action == "exclude" and match:
                return False
    return True
