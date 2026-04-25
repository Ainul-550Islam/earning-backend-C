# api/publisher_tools/fraud_prevention/ip_blacklist.py
"""IP Blacklist — IP address blocking and reputation management."""
import ipaddress
from typing import Dict, List
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
from core.models import TimeStampedModel


class BlockedIP(TimeStampedModel):
    """Blocked IP addresses."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_blockedip_tenant", db_index=True)
    ip_address   = models.GenericIPAddressField(unique=True, db_index=True)
    ip_range     = models.CharField(max_length=20, blank=True, verbose_name=_("CIDR Range"))
    reason       = models.TextField(blank=True)
    fraud_score  = models.IntegerField(default=0)
    block_type   = models.CharField(max_length=20, choices=[
        ("manual","Manual"),("auto","Automated"),("abuse_db","Abuse Database"),
    ], default="auto")
    is_active    = models.BooleanField(default=True, db_index=True)
    expires_at   = models.DateTimeField(null=True, blank=True)
    blocked_count= models.IntegerField(default=0)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    country_code = models.CharField(max_length=5, blank=True)
    publisher    = models.ForeignKey("publisher_tools.Publisher", on_delete=models.SET_NULL, null=True, blank=True, related_name="blocked_ips")

    class Meta:
        db_table = "publisher_tools_blocked_ips"
        verbose_name = _("Blocked IP")
        verbose_name_plural = _("Blocked IPs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["ip_address", "is_active"], name='idx_ip_address_is_active_1589'),
            models.Index(fields=["publisher", "is_active"], name='idx_publisher_is_active_1590'),
        ]

    def __str__(self):
        return f"{self.ip_address} — {self.block_type} [{self.reason[:50]}]"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update cache
        if self.is_active:
            cache.set(f"blocked_ip:{self.ip_address}", True, 86400)
        else:
            cache.delete(f"blocked_ip:{self.ip_address}")

    @property
    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at)


def is_ip_blocked(ip_address: str) -> bool:
    return bool(cache.get(f"blocked_ip:{ip_address}")) or BlockedIP.objects.filter(ip_address=ip_address, is_active=True).exists()


def block_ip(ip_address: str, reason: str, fraud_score: int = 80, hours: int = 24, publisher=None) -> BlockedIP:
    entry, _ = BlockedIP.objects.update_or_create(
        ip_address=ip_address,
        defaults={
            "reason": reason, "fraud_score": fraud_score,
            "is_active": True, "block_type": "auto",
            "expires_at": timezone.now() + __import__("datetime").timedelta(hours=hours),
            "publisher": publisher,
        },
    )
    return entry


def unblock_ip(ip_address: str) -> bool:
    updated = BlockedIP.objects.filter(ip_address=ip_address).update(is_active=False)
    cache.delete(f"blocked_ip:{ip_address}")
    return bool(updated)


def get_ip_reputation(ip_address: str) -> Dict:
    blocked = BlockedIP.objects.filter(ip_address=ip_address).first()
    from .bot_detector import is_datacenter_ip
    return {
        "ip": ip_address,
        "is_blocked": is_ip_blocked(ip_address),
        "is_datacenter": is_datacenter_ip(ip_address),
        "fraud_score": blocked.fraud_score if blocked else 0,
        "block_reason": blocked.reason if blocked else None,
    }
