"""
utils/ip_checker.py

IP address validation utilities for postback security.

Principles:
  • Uses ipaddress stdlib – no third-party deps.
  • Supports both IPv4 and IPv6, CIDR notation.
  • get_client_ip() trusts X-Forwarded-For only when configured.
  • Logs suspicious activity at WARNING without leaking internal network topology.
"""
import ipaddress
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def parse_ip(ip_str: str) -> Optional[ipaddress._BaseAddress]:
    """Parse an IP address string. Returns None if unparseable."""
    try:
        return ipaddress.ip_address(ip_str.strip())
    except ValueError:
        return None


def parse_network(cidr: str) -> Optional[ipaddress._BaseNetwork]:
    """Parse a CIDR network string. Returns None if unparseable."""
    try:
        return ipaddress.ip_network(cidr.strip(), strict=False)
    except ValueError:
        return None


def is_ip_in_whitelist(ip_str: str, whitelist: List[str]) -> bool:
    """
    Return True if ip_str is in the whitelist.
    Each whitelist entry may be a single IP or a CIDR range.
    """
    if not whitelist:
        return False

    client_ip = parse_ip(ip_str)
    if client_ip is None:
        logger.warning("is_ip_in_whitelist: unparseable client IP %r", ip_str)
        return False

    for entry in whitelist:
        entry = entry.strip()
        if not entry:
            continue
        # Try exact IP first
        exact = parse_ip(entry)
        if exact is not None:
            if client_ip == exact:
                return True
            continue
        # Try CIDR range
        network = parse_network(entry)
        if network is not None:
            try:
                if client_ip in network:
                    return True
            except TypeError:
                pass  # IPv4/IPv6 mismatch
        else:
            logger.warning(
                "is_ip_in_whitelist: invalid whitelist entry %r – skipping", entry
            )

    return False


def is_private_ip(ip_str: str) -> bool:
    """Return True if the IP is in a private/loopback range."""
    ip = parse_ip(ip_str)
    if ip is None:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def get_client_ip(request, trust_forwarded: bool = False) -> str:
    """
    Extract the real client IP from a Django request.

    trust_forwarded=True:  use X-Forwarded-For (first entry) when present.
                           Only enable this if behind a trusted reverse proxy.
    trust_forwarded=False: use REMOTE_ADDR only (safer default).
    """
    if trust_forwarded:
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if xff:
            # XFF may contain multiple IPs: "client, proxy1, proxy2"
            # Take the first (leftmost) which is the originating client.
            candidate = xff.split(",")[0].strip()
            ip = parse_ip(candidate)
            if ip is not None:
                return str(ip)
            else:
                logger.warning(
                    "get_client_ip: unparseable X-Forwarded-For value %r; "
                    "falling back to REMOTE_ADDR", candidate
                )

    return request.META.get("REMOTE_ADDR", "")


def validate_ip_whitelist_entries(entries: List[str]) -> List[str]:
    """
    Validate a list of IP/CIDR strings.
    Returns a list of error messages for invalid entries (empty = all valid).
    """
    errors = []
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        if parse_ip(entry) is None and parse_network(entry) is None:
            errors.append(f"Invalid IP address or CIDR: {entry!r}")
    return errors
