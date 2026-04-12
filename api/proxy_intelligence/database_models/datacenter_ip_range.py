"""Datacenter IP Range — model helpers for CIDR management."""
import ipaddress
import logging
from django.db import models

logger = logging.getLogger(__name__)


class DatacenterIPRangeManager(models.Manager):
    def active(self):
        return self.filter(is_active=True)

    def by_provider(self, provider_name: str):
        return self.active().filter(provider_name__icontains=provider_name)

    def contains_ip(self, ip_address: str) -> bool:
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            for cidr in self.active().values_list("cidr", flat=True):
                try:
                    if ip_obj in ipaddress.ip_network(cidr, strict=False):
                        return True
                except ValueError:
                    continue
        except ValueError:
            pass
        return False

    def find_range(self, ip_address: str):
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            for entry in self.active():
                try:
                    if ip_obj in ipaddress.ip_network(entry.cidr, strict=False):
                        return entry
                except ValueError:
                    continue
        except ValueError:
            pass
        return None

    def stats(self):
        from django.db.models import Count
        return {
            "total_ranges": self.active().count(),
            "by_provider": list(
                self.active().values("provider_name")
                .annotate(count=Count("id"))
                .order_by("-count")
            ),
        }
