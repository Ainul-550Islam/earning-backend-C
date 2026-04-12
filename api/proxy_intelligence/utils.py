"""
Proxy Intelligence Utilities
==============================
General-purpose helper functions used across the module.
"""
import hashlib
import socket
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def hash_string(s: str) -> str:
    """SHA-256 hash a string."""
    return hashlib.sha256(s.encode()).hexdigest()


def reverse_dns(ip_address: str) -> Optional[str]:
    """Perform reverse DNS lookup. Returns hostname or None."""
    try:
        return socket.gethostbyaddr(ip_address)[0]
    except Exception:
        return None


def get_ip_from_request(request) -> str:
    """Extract the real client IP from a Django request object."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip


def mask_ip(ip_address: str) -> str:
    """Mask an IP for privacy (e.g., for logs): 192.168.1.100 -> 192.168.1.***"""
    parts = ip_address.split('.')
    if len(parts) == 4:
        return '.'.join(parts[:3]) + '.***'
    return ip_address[:len(ip_address)//2] + '***'


def format_risk_badge(risk_level: str) -> str:
    """Returns an emoji badge for a risk level (for notifications)."""
    badges = {
        'very_low': '🟢',
        'low': '🟡',
        'medium': '🟠',
        'high': '🔴',
        'critical': '☠️',
    }
    return badges.get(risk_level, '⚪')


def chunk_list(lst: list, size: int) -> list:
    """Split a list into chunks of given size."""
    return [lst[i:i+size] for i in range(0, len(lst), size)]
