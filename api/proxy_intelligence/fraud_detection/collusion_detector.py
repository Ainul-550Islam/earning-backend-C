"""Collusion Detector — detects coordinated multi-account fraud rings."""
import logging
from django.db.models import Count
logger = logging.getLogger(__name__)

class CollusionDetector:
    """Detects groups of accounts working together to defraud the platform."""

    def __init__(self, tenant=None):
        self.tenant = tenant

    def find_rings(self, min_accounts: int = 3, days: int = 30) -> list:
        """Find IP addresses with suspicious shared multi-account activity."""
        from ..models import MultiAccountLink
        from datetime import timedelta
        from django.utils import timezone

        since = timezone.now() - timedelta(days=days)
        qs = MultiAccountLink.objects.filter(
            created_at__gte=since, is_suspicious=True
        )
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        ip_groups = {}
        for link in qs.select_related('primary_user','linked_user'):
            ip = link.shared_identifier
            if ip not in ip_groups:
                ip_groups[ip] = set()
            ip_groups[ip].add(link.primary_user_id)
            ip_groups[ip].add(link.linked_user_id)

        rings = []
        for ip, user_ids in ip_groups.items():
            if len(user_ids) >= min_accounts:
                rings.append({
                    'shared_ip': ip,
                    'account_count': len(user_ids),
                    'user_ids': list(user_ids),
                    'risk': 'critical' if len(user_ids) >= 5 else 'high',
                })
        return sorted(rings, key=lambda x: -x['account_count'])

    def score_collusion(self, user) -> int:
        """Score how likely a user is part of a fraud ring."""
        from ..models import MultiAccountLink
        link_count = MultiAccountLink.objects.filter(
            primary_user=user, is_suspicious=True
        ).count()
        return min(link_count * 15, 100)
