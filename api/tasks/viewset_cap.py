"""
api/tasks/viewset_cap.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ViewSet for CAP management (offer caps, campaign budgets).
Admin-only endpoints to view and manage capacity limits.
"""

import logging
from django.utils import timezone
from django.core.cache import cache
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser

logger = logging.getLogger(__name__)


class OfferCapViewSet(viewsets.ViewSet):
    """
    Admin ViewSet for offer CAP management.
    GET  /offers/caps/              — All offers with cap status
    POST /offers/caps/reset/        — Reset daily caps
    POST /offers/caps/{id}/pause/   — Manually pause capped offer
    """

    def get_permissions(self):
        return [IsAdminUser()]

    def list(self, request):
        """List all offers with their cap status."""
        try:
            from ad_networks.models import SmartlinkOffer
            offers = SmartlinkOffer.objects.filter(
                daily_cap__isnull=False
            ).values('id', 'external_id', 'name', 'daily_cap',
                      'daily_clicks_used', 'is_active', 'paused_reason')
            result = []
            for o in offers:
                pct = round(
                    (o['daily_clicks_used'] or 0) / max(o['daily_cap'] or 1, 1) * 100, 1
                )
                result.append({**o, 'cap_pct': pct, 'is_capped': pct >= 100})
            return Response({'results': result, 'count': len(result)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'])
    def reset_daily(self, request):
        """Reset all daily cap counters (usually runs at midnight)."""
        from api.tasks.tasks_cap import reset_daily_caps
        result = reset_daily_caps.apply_async()
        return Response({'status': 'queued', 'task_id': result.id})

    @action(detail=False, methods=['get'])
    def warnings(self, request):
        """List offers at 90%+ cap usage."""
        warnings = []
        try:
            from ad_networks.models import SmartlinkOffer
            for o in SmartlinkOffer.objects.filter(
                is_active=True, daily_cap__isnull=False
            ).values('external_id', 'name', 'daily_cap', 'daily_clicks_used'):
                daily_cap  = o['daily_cap'] or 0
                daily_used = o['daily_clicks_used'] or 0
                if daily_cap and daily_used >= daily_cap * 0.90:
                    warnings.append({
                        'offer_id': o['external_id'],
                        'name':     o['name'],
                        'pct':      round(daily_used / daily_cap * 100, 1),
                    })
        except ImportError:
            pass
        return Response({'warnings': warnings, 'count': len(warnings)})


__all__ = ['OfferCapViewSet']
