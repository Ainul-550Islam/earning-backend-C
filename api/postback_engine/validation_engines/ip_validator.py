"""
validation_engines/ip_validator.py
────────────────────────────────────
IP address validation and whitelist checking.
"""
from __future__ import annotations
import ipaddress
from ..exceptions import IPNotWhitelistedException


class IPValidator:

    def validate_format(self, ip: str) -> bool:
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def is_in_whitelist(self, ip: str, whitelist: list) -> bool:
        if not whitelist:
            return True
        if not ip:
            return False
        try:
            ip_obj = ipaddress.ip_address(ip)
            for entry in whitelist:
                s = str(entry)
                if "/" in s:
                    if ip_obj in ipaddress.ip_network(s, strict=False):
                        return True
                else:
                    if ip_obj == ipaddress.ip_address(s):
                        return True
        except ValueError:
            pass
        return False

    def assert_whitelisted(self, ip: str, whitelist: list) -> None:
        if whitelist and not self.is_in_whitelist(ip, whitelist):
            raise IPNotWhitelistedException(f"IP {ip} not in whitelist.")

    def is_private(self, ip: str) -> bool:
        try:
            return ipaddress.ip_address(ip).is_private
        except ValueError:
            return False

    def is_loopback(self, ip: str) -> bool:
        try:
            return ipaddress.ip_address(ip).is_loopback
        except ValueError:
            return False


ip_validator = IPValidator()
