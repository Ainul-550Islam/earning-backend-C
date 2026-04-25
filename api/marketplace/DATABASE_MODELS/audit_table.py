"""
DATABASE_MODELS/audit_table.py — Audit Trail Reference
"""
from api.marketplace.PRODUCT_MANAGEMENT.product_inventory import InventoryAuditLog
from api.marketplace.WEBHOOKS.webhook_logger import WebhookLog
from django.db import models
from django.conf import settings


class MarketplaceAuditLog(models.Model):
    """Generic audit log for admin actions in the marketplace."""
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="marketplace_audit_logs_tenant")
    action      = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=50)
    entity_id   = models.IntegerField(null=True, blank=True)
    actor       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, related_name="marketplace_audit_actions")
    old_value   = models.JSONField(null=True, blank=True)
    new_value   = models.JSONField(null=True, blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.CharField(max_length=500, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_audit_log"
        ordering  = ["-created_at"]
        indexes   = [models.Index(fields=["entity_type","entity_id"], name='idx_entity_type_entity_id_1115')]

    def __str__(self):
        return f"[{self.entity_type}] {self.action} by {self.actor} @ {self.created_at:%Y-%m-%d %H:%M}"


def log_action(tenant, actor, action: str, entity_type: str, entity_id: int = None,
               old_value=None, new_value=None, ip: str = None, ua: str = ""):
    MarketplaceAuditLog.objects.create(
        tenant=tenant, actor=actor, action=action,
        entity_type=entity_type, entity_id=entity_id,
        old_value=old_value, new_value=new_value,
        ip_address=ip, user_agent=ua,
    )


def recent_actions(tenant, limit: int = 50) -> list:
    return list(
        MarketplaceAuditLog.objects.filter(tenant=tenant)
        .select_related("actor")
        .order_by("-created_at")[:limit]
    )


__all__ = [
    "InventoryAuditLog","WebhookLog","MarketplaceAuditLog",
    "log_action","recent_actions",
]
