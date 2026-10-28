"""
PublisherTierViewSet
Exposes PublisherTier read + evaluation + admin override.
Service: PublisherTierService
Model:   PublisherTier (models/extensions/smartlink_schedule.py)
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from api.smartlink.models.extensions.smartlink_schedule import PublisherTier
from api.smartlink.serializers.PublisherTierSerializer import (
    PublisherTierSerializer,
    PublisherTierSummarySerializer,
    ManualTierOverrideSerializer,
    TierEvaluationResultSerializer,
)
from api.smartlink.services.publisher.PublisherTierService import PublisherTierService

import logging
logger = logging.getLogger('smartlink.viewsets.tier')


class PublisherTierViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Publisher quality tier management.

    Publisher endpoints (own tier only):
      GET  /api/smartlink/publisher/tier/my-tier/
      GET  /api/smartlink/publisher/tier/my-benefits/

    Admin endpoints:
      GET    /api/smartlink/admin/tiers/
      GET    /api/smartlink/admin/tiers/{id}/
      POST   /api/smartlink/admin/tiers/{id}/evaluate/
      POST   /api/smartlink/admin/tiers/{id}/override/
      GET    /api/smartlink/admin/tiers/leaderboard/
    """
    serializer_class = PublisherTierSerializer
    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tier_svc = PublisherTierService()

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return PublisherTier.objects.all().select_related('publisher').order_by('-last_quality_score')
        return PublisherTier.objects.filter(publisher=user).select_related('publisher')

    # ── Publisher-facing actions ───────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='my-tier')
    def my_tier(self, request):
        """
        GET /api/smartlink/publisher/tier/my-tier/
        Return the requesting publisher's current tier and full details.
        """
        try:
            tier_obj = PublisherTier.objects.get(publisher=request.user)
            return Response(PublisherTierSerializer(tier_obj).data)
        except PublisherTier.DoesNotExist:
            return Response({
                'tier': 'standard',
                'tier_display': 'Standard — New Publisher',
                'tier_emoji': '⚪',
                'benefits': self._tier_svc.TIER_BENEFITS['standard'],
                'note': 'No tier record yet. You start as Standard.',
            })

    @action(detail=False, methods=['get'], url_path='my-benefits')
    def my_benefits(self, request):
        """
        GET /api/smartlink/publisher/tier/my-benefits/
        Return current tier benefits (SmartLink quota, feature flags, bonus payout).
        """
        benefits = self._tier_svc.get_benefits(request.user)
        tier = self._tier_svc.get_tier(request.user)
        return Response({
            'tier': tier,
            'benefits': benefits,
            'thresholds_for_upgrade': self._next_tier_thresholds(tier),
        })

    # ── Admin actions ──────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='evaluate')
    def evaluate(self, request, pk=None):
        """
        POST /api/smartlink/admin/tiers/{id}/evaluate/
        Force an immediate tier evaluation for this publisher.
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        tier_obj = self.get_object()
        result = self._tier_svc.evaluate_publisher(tier_obj.publisher)
        logger.info(
            f"Manual tier evaluation: publisher={tier_obj.publisher.username} "
            f"new_tier={result['tier']} by admin={request.user.username}"
        )
        return Response(TierEvaluationResultSerializer(result).data)

    @action(detail=True, methods=['post'], url_path='override')
    def override(self, request, pk=None):
        """
        POST /api/smartlink/admin/tiers/{id}/override/
        Manually set a publisher's tier, bypassing quality evaluation.
        Body: {"tier": "gold", "reason": "VIP partner agreement"}
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        tier_obj = self.get_object()
        serializer = ManualTierOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_tier = serializer.validated_data['tier']
        reason = serializer.validated_data['reason']
        benefits = self._tier_svc.TIER_BENEFITS[new_tier]

        old_tier = tier_obj.tier
        PublisherTier.objects.filter(pk=tier_obj.pk).update(
            tier=new_tier,
            max_smartlinks=benefits['max_smartlinks'],
            max_custom_domains=benefits['max_domains'],
            can_use_ml_rotation=benefits['ml_rotation'],
            can_use_ab_testing=benefits['ab_test'],
            can_use_pre_landers=benefits['pre_landers'],
            payout_bonus_percent=benefits['bonus_pct'],
            notes=f"[Admin override by {request.user.username}]: {reason}",
        )
        tier_obj.refresh_from_db()

        logger.warning(
            f"Tier override: {tier_obj.publisher.username} "
            f"{old_tier} → {new_tier} by admin={request.user.username}. Reason: {reason}"
        )
        return Response(PublisherTierSerializer(tier_obj).data)

    @action(detail=False, methods=['get'], url_path='leaderboard')
    def leaderboard(self, request):
        """
        GET /api/smartlink/admin/tiers/leaderboard/
        Top publishers ranked by quality score. Admin only.
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        qs = PublisherTier.objects.select_related('publisher').order_by(
            '-last_quality_score'
        )[:50]
        return Response(PublisherTierSummarySerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='thresholds')
    def thresholds(self, request):
        """
        GET /api/smartlink/publisher/tier/thresholds/
        Return the criteria required for each tier.
        """
        return Response({
            'thresholds': self._tier_svc.TIER_THRESHOLDS,
            'benefits': self._tier_svc.TIER_BENEFITS,
        })

    # ── Helper ────────────────────────────────────────────────────────────────

    def _next_tier_thresholds(self, current_tier: str) -> dict | None:
        """Return what a publisher needs to reach the next tier."""
        order = ['under_review', 'standard', 'bronze', 'silver', 'gold']
        try:
            idx = order.index(current_tier)
        except ValueError:
            return None
        if idx >= len(order) - 1:
            return {'message': 'Already at the highest tier.'}
        next_tier = order[idx + 1]
        return {
            'next_tier': next_tier,
            'requirements': self._tier_svc.TIER_THRESHOLDS.get(next_tier, {}),
        }
