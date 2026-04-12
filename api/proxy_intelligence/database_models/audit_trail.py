"""Audit Trail — model helpers and compliance queries."""
from django.db import models
from django.utils import timezone
from datetime import timedelta


class SystemAuditTrailManager(models.Manager):
    def recent(self, hours=24, tenant=None):
        since = timezone.now() - timedelta(hours=hours)
        qs = self.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by("-created_at")

    def by_action(self, action: str, tenant=None):
        qs = self.filter(action=action)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by("-created_at")

    def by_user(self, user, days=30):
        since = timezone.now() - timedelta(days=days)
        return self.filter(user=user, created_at__gte=since).order_by("-created_at")

    def by_model(self, model_name: str, tenant=None):
        qs = self.filter(model_name=model_name)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by("-created_at")

    def blacklist_actions(self, tenant=None):
        return self.by_action("blacklist", tenant)

    def config_changes(self, days=7, tenant=None):
        since = timezone.now() - timedelta(days=days)
        qs = self.filter(
            action__in=["config_change", "rule_change"],
            created_at__gte=since,
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by("-created_at")

    def compliance_export(self, days=90, tenant=None) -> list:
        since = timezone.now() - timedelta(days=days)
        qs = self.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.values(
            "created_at", "user__email", "action",
            "model_name", "object_repr", "ip_address", "notes"
        ).order_by("-created_at"))
