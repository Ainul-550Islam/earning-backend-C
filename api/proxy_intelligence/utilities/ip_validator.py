"""
IP Validator Utility
====================
Validation, parsing, and classification helpers for IP addresses.
"""
import ipaddress
import re
from typing import Optional


class IPValidator:
    """Utility class for IP address validation and analysis."""

    @staticmethod
    def is_valid(ip_str: str) -> bool:
        try:
            ipaddress.ip_address(ip_str)
            return True
        except ValueError:
            return False

    @staticmethod
    def is_private(ip_str: str) -> bool:
        try:
            return ipaddress.ip_address(ip_str).is_private
        except ValueError:
            return False

    @staticmethod
    def is_loopback(ip_str: str) -> bool:
        try:
            return ipaddress.ip_address(ip_str).is_loopback
        except ValueError:
            return False

    @staticmethod
    def is_reserved(ip_str: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip_str)
            return addr.is_reserved or addr.is_multicast or addr.is_link_local
        except ValueError:
            return False

    @staticmethod
    def get_version(ip_str: str) -> Optional[int]:
        try:
            return ipaddress.ip_address(ip_str).version
        except ValueError:
            return None

    @staticmethod
    def is_in_cidr(ip_str: str, cidr: str) -> bool:
        """Check if an IP is within a CIDR range."""
        try:
            return ipaddress.ip_address(ip_str) in ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            return False

    @staticmethod
    def normalize(ip_str: str) -> str:
        """Normalize IP (e.g. expand IPv6 abbreviations)."""
        try:
            return str(ipaddress.ip_address(ip_str))
        except ValueError:
            return ip_str

    @staticmethod
    def extract_from_request(request) -> str:
        """Extract real client IP from Django request, handling proxies."""
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded_for:
            # Take the first (leftmost) IP - it's the original client
            ip = forwarded_for.split(',')[0].strip()
            if IPValidator.is_valid(ip) and not IPValidator.is_private(ip):
                return ip

        real_ip = request.META.get('HTTP_X_REAL_IP', '')
        if real_ip and IPValidator.is_valid(real_ip):
            return real_ip

        return request.META.get('REMOTE_ADDR', '0.0.0.0')

    @staticmethod
    def is_should_skip(ip_str: str) -> bool:
        """Return True if this IP should be skipped (private, loopback, etc.)."""
        return (IPValidator.is_private(ip_str) or
                IPValidator.is_loopback(ip_str) or
                IPValidator.is_reserved(ip_str))
