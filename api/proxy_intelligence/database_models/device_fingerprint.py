"""Device Fingerprint model helpers."""
from django.db import models
from django.utils import timezone
from datetime import timedelta


class DeviceFingerprintManager(models.Manager):
    def suspicious(self, tenant=None):
        qs = self.filter(is_suspicious=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-risk_score')

    def by_hash(self, fingerprint_hash: str):
        return self.filter(fingerprint_hash=fingerprint_hash).first()

    def for_user(self, user, limit: int = 20):
        return self.filter(user=user).order_by('-last_seen')[:limit]

    def by_ip(self, ip_address: str, limit: int = 20):
        return self.filter(
            ip_addresses__contains=ip_address
        ).order_by('-last_seen')[:limit]

    def shared_fingerprints(self, min_users: int = 2, tenant=None):
        from django.db.models import Count
        qs = self.exclude(user=None)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return (
            qs.values('fingerprint_hash')
            .annotate(user_count=Count('user', distinct=True))
            .filter(user_count__gte=min_users)
            .order_by('-user_count')
        )

    def stale(self, days: int = 90):
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(last_seen__lt=cutoff)

    def high_risk(self, threshold: int = 61, tenant=None):
        qs = self.filter(risk_score__gte=threshold)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-risk_score')

    def spoofing_detected(self, tenant=None):
        qs = self.filter(spoofing_detected=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def update_risk(self, fingerprint_hash: str, risk_score: int,
                    is_suspicious: bool) -> int:
        return self.filter(fingerprint_hash=fingerprint_hash).update(
            risk_score=risk_score, is_suspicious=is_suspicious
        )

    def stats(self, tenant=None) -> dict:
        from django.db.models import Count, Avg
        qs = self.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return {
            'total':             qs.count(),
            'suspicious':        qs.filter(is_suspicious=True).count(),
            'spoofing_detected': qs.filter(spoofing_detected=True).count(),
            'avg_risk_score':    round(qs.aggregate(a=Avg('risk_score'))['a'] or 0, 1),
            'desktop':           qs.filter(device_type='desktop').count(),
            'mobile':            qs.filter(device_type='mobile').count(),
        }
