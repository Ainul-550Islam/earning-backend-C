"""Tor Exit Node List model helpers."""
from django.db import models
from django.utils import timezone
from datetime import timedelta


class TorExitNodeManager(models.Manager):
    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)

    def recently_seen(self, hours: int = 24):
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.active().filter(last_seen__gte=cutoff)

    def is_tor_exit(self, ip_address: str) -> bool:
        return self.active().filter(ip_address=ip_address).exists()

    def get_by_fingerprint(self, fingerprint: str):
        return self.filter(fingerprint=fingerprint).first()

    def deactivate_old(self, hours: int = 72) -> int:
        """Deactivate nodes not seen in N hours."""
        cutoff = timezone.now() - timedelta(hours=hours)
        qs     = self.filter(is_active=True, last_seen__lt=cutoff)
        count  = qs.count()
        qs.update(is_active=False)
        return count

    def get_ip_set(self) -> set:
        """Return a Python set of all active Tor exit IPs — fast O(1) lookup."""
        return set(
            self.active().values_list('ip_address', flat=True)
        )

    def bulk_upsert(self, ip_list: list) -> dict:
        """
        Upsert a list of Tor exit node IPs.
        Returns {added, updated, total} counts.
        """
        from ..models import TorExitNode
        added   = 0
        updated = 0
        now     = timezone.now()

        for ip in ip_list:
            ip = ip.strip()
            if not ip:
                continue
            _, created = TorExitNode.objects.update_or_create(
                ip_address=ip,
                defaults={'is_active': True, 'last_seen': now}
            )
            if created:
                added += 1
            else:
                updated += 1

        return {'added': added, 'updated': updated, 'total': len(ip_list)}

    def stats(self) -> dict:
        return {
            'total_active':     self.active().count(),
            'total_all':        self.count(),
            'recently_seen_24h': self.recently_seen(24).count(),
            'recently_seen_6h': self.recently_seen(6).count(),
        }
