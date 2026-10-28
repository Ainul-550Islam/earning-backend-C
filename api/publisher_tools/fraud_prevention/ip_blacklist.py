# api/publisher_tools/fraud_prevention/ip_blacklist.py
"""IP Blacklist — IP address blocking and reputation management."""
from datetime import timedelta
from typing import Dict

from django.core.cache import cache
from django.utils import timezone

from api.publisher_tools.models import BlockedIP


def is_ip_blocked(ip_address: str) -> bool:
    if cache.get(f"blocked_ip:{ip_address}"):
        return True
    blocked = BlockedIP.objects.filter(ip_address=ip_address).first()
    return blocked is not None and blocked.is_active_block


def block_ip(ip_address: str, reason: str, fraud_score: int = 80, hours: int = 24, publisher=None) -> BlockedIP:
    entry, _ = BlockedIP.objects.update_or_create(
        ip_address=ip_address,
        defaults={
            "reason": reason,
            "fraud_score": fraud_score,
            "is_auto_blocked": True,
            "expires_at": timezone.now() + timedelta(hours=hours),
            "unblocked_at": None,
            "publisher": publisher,
        },
    )
    cache.set(f"blocked_ip:{ip_address}", True, 86400)
    return entry


def unblock_ip(ip_address: str) -> bool:
    updated = BlockedIP.objects.filter(ip_address=ip_address).update(
        unblocked_at=timezone.now()
    )
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
