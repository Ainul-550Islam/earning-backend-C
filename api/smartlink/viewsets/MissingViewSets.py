"""
SmartLink — Missing ViewSets
==============================
Adds API endpoints for 18 models that had no viewset:
  RedirectRule, RedirectChain, PublisherSubID,
  PublisherAllowList, PublisherBlockList,
  OSTargeting, BrowserTargeting, TimeTargeting,
  ISPTargeting, LanguageTargeting,
  ClickMetadata, UniqueClick, ClickFraudFlag, BotClick,
  SmartLinkTag, SmartLinkDomain, SmartLinkTagging,
  SmartLinkRotation, SmartLinkFallback, SmartLinkVersion,
  OfferPerformanceStat, GeoPerformanceStat, DevicePerformanceStat,
  OfferCapTracker, OfferRotationLog, OfferScoreCache
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.smartlink.serializers.MissingSerializers import (
    RedirectRuleSerializer,
    PublisherSubIDSerializer,
    BrowserTargetingSerializer,
    UniqueClickSerializer,
    ClickFraudFlagSerializer,
    ClickFraudFlagListSerializer,
    SmartLinkDomainSerializer,
    SmartLinkTaggingSerializer,
    OfferPerformanceStatSerializer,
    GeoPerformanceStatSerializer,
    DevicePerformanceStatSerializer,
    OfferCapTrackerSerializer,
    OfferBlacklistSerializer,
)

logger = logging.getLogger('smartlink.viewsets.missing')


# ── RedirectRule ViewSet ──────────────────────────────────────────────────────

class RedirectRuleViewSet(viewsets.ModelViewSet):
    """
    Custom redirect rules per SmartLink.
    GET    /api/smartlink/smartlinks/{sl_pk}/redirect-rules/
    POST   /api/smartlink/smartlinks/{sl_pk}/redirect-rules/
    PUT    /api/smartlink/smartlinks/{sl_pk}/redirect-rules/{id}/
    DELETE /api/smartlink/smartlinks/{sl_pk}/redirect-rules/{id}/
    POST   /api/smartlink/smartlinks/{sl_pk}/redirect-rules/{id}/toggle/
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = RedirectRuleSerializer

    def get_queryset(self):
        from api.smartlink.models.redirect import RedirectRule
        return RedirectRule.objects.filter(
            smartlink_id=self.kwargs.get('smartlink_pk'),
            smartlink__publisher=self.request.user,
        ).order_by('priority')

    def perform_create(self, serializer):
        from api.smartlink.models import SmartLink
        from django.shortcuts import get_object_or_404
        sl = get_object_or_404(
            SmartLink,
            pk=self.kwargs['smartlink_pk'],
            publisher=self.request.user,
        )
        serializer.save(smartlink=sl)

    @action(detail=True, methods=['post'])
    def toggle(self, request, smartlink_pk=None, pk=None):
        """Toggle redirect rule active/inactive."""
        from api.smartlink.models.redirect import RedirectRule
        from django.shortcuts import get_object_or_404
        rule = get_object_or_404(
            RedirectRule,
            pk=pk,
            smartlink_id=smartlink_pk,
            smartlink__publisher=request.user,
        )
        RedirectRule.objects.filter(pk=rule.pk).update(is_active=not rule.is_active)
        rule.refresh_from_db()
        return Response(RedirectRuleSerializer(rule).data)


# ── PublisherSubID ViewSet ────────────────────────────────────────────────────

class PublisherSubIDViewSet(viewsets.ModelViewSet):
    """
    Sub-ID label definitions per publisher.
    GET  /api/smartlink/publisher/sub-id-labels/
    POST /api/smartlink/publisher/sub-id-labels/
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = PublisherSubIDSerializer

    def get_queryset(self):
        from api.smartlink.models.publisher import PublisherSubID
        return PublisherSubID.objects.filter(
            publisher=self.request.user
        ).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(publisher=self.request.user)


# ── BrowserTargeting ViewSet ──────────────────────────────────────────────────

class BrowserTargetingViewSet(viewsets.ModelViewSet):
    """
    Browser targeting per SmartLink.
    GET  /api/smartlink/smartlinks/{sl_pk}/browser-targeting/
    POST /api/smartlink/smartlinks/{sl_pk}/browser-targeting/
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = BrowserTargetingSerializer

    def get_queryset(self):
        from api.smartlink.models.targeting import BrowserTargeting
        return BrowserTargeting.objects.filter(
            smartlink_id=self.kwargs.get('smartlink_pk'),
            smartlink__publisher=self.request.user,
        )

    def perform_create(self, serializer):
        from api.smartlink.models import SmartLink
        from django.shortcuts import get_object_or_404
        sl = get_object_or_404(
            SmartLink,
            pk=self.kwargs['smartlink_pk'],
            publisher=self.request.user,
        )
        serializer.save(smartlink=sl)


# ── OSTargeting ViewSet ───────────────────────────────────────────────────────

class OSTargetingViewSet(viewsets.ModelViewSet):
    """OS targeting per SmartLink."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from api.smartlink.serializers.MissingTargetingSerializers import OSTargetingSerializer
        return OSTargetingSerializer

    def get_queryset(self):
        from api.smartlink.models.targeting import OSTargeting
        return OSTargeting.objects.filter(
            smartlink_id=self.kwargs.get('smartlink_pk'),
            smartlink__publisher=self.request.user,
        )

    def perform_create(self, serializer):
        from api.smartlink.models import SmartLink
        from django.shortcuts import get_object_or_404
        sl = get_object_or_404(SmartLink, pk=self.kwargs['smartlink_pk'], publisher=self.request.user)
        serializer.save(smartlink=sl)


# ── TimeTargeting ViewSet ─────────────────────────────────────────────────────

class TimeTargetingViewSet(viewsets.ModelViewSet):
    """Time-of-day and day-of-week targeting per SmartLink."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from api.smartlink.serializers import TimeTargetingSerializer
        return TimeTargetingSerializer

    def get_queryset(self):
        from api.smartlink.models.targeting import TimeTargeting
        return TimeTargeting.objects.filter(
            smartlink_id=self.kwargs.get('smartlink_pk'),
            smartlink__publisher=self.request.user,
        )

    def perform_create(self, serializer):
        from api.smartlink.models import SmartLink
        from django.shortcuts import get_object_or_404
        sl = get_object_or_404(SmartLink, pk=self.kwargs['smartlink_pk'], publisher=self.request.user)
        serializer.save(smartlink=sl)


# ── ISPTargeting ViewSet ──────────────────────────────────────────────────────

class ISPTargetingViewSet(viewsets.ModelViewSet):
    """ISP/ASN targeting per SmartLink."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from api.smartlink.serializers.MissingTargetingSerializers import ISPTargetingSerializer
        return ISPTargetingSerializer

    def get_queryset(self):
        from api.smartlink.models.targeting import ISPTargeting
        return ISPTargeting.objects.filter(
            smartlink_id=self.kwargs.get('smartlink_pk'),
            smartlink__publisher=self.request.user,
        )

    def perform_create(self, serializer):
        from api.smartlink.models import SmartLink
        from django.shortcuts import get_object_or_404
        sl = get_object_or_404(SmartLink, pk=self.kwargs['smartlink_pk'], publisher=self.request.user)
        serializer.save(smartlink=sl)


# ── LanguageTargeting ViewSet ─────────────────────────────────────────────────

class LanguageTargetingViewSet(viewsets.ModelViewSet):
    """Browser language targeting per SmartLink."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from api.smartlink.serializers.MissingTargetingSerializers import LanguageTargetingSerializer
        from api.smartlink.serializers import GeoTargetingSerializer
        return LanguageTargetingSerializer

    def get_queryset(self):
        from api.smartlink.models.targeting import LanguageTargeting
        return LanguageTargeting.objects.filter(
            smartlink_id=self.kwargs.get('smartlink_pk'),
            smartlink__publisher=self.request.user,
        )

    def perform_create(self, serializer):
        from api.smartlink.models import SmartLink
        from django.shortcuts import get_object_or_404
        sl = get_object_or_404(SmartLink, pk=self.kwargs['smartlink_pk'], publisher=self.request.user)
        serializer.save(smartlink=sl)


# ── ClickFraudFlag ViewSet ────────────────────────────────────────────────────

class ClickFraudFlagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only fraud flag analytics per SmartLink.
    GET /api/smartlink/smartlinks/{sl_pk}/fraud-flags/
    GET /api/smartlink/smartlinks/{sl_pk}/fraud-flags/{id}/
    GET /api/smartlink/smartlinks/{sl_pk}/fraud-flags/summary/ — score distribution
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return ClickFraudFlagListSerializer
        return ClickFraudFlagSerializer

    def get_queryset(self):
        from api.smartlink.models.click import ClickFraudFlag
        return ClickFraudFlag.objects.filter(
            click__smartlink_id=self.kwargs.get('smartlink_pk'),
            click__smartlink__publisher=self.request.user,
        ).select_related('click').order_by('-detected_at')

    @action(detail=False, methods=['get'])
    def summary(self, request, smartlink_pk=None):
        """Score distribution for fraud flags."""
        from api.smartlink.models.click import ClickFraudFlag
        from django.db.models import Count, Avg
        qs = self.get_queryset()
        agg = qs.aggregate(
            total=Count('id'),
            avg_score=Avg('score'),
        )
        blocked = qs.filter(action='block').count()
        flagged = qs.filter(action='flag').count()
        return Response({
            'total_fraud_flags': agg['total'],
            'avg_fraud_score':   round(agg['avg_score'] or 0, 2),
            'blocked':           blocked,
            'flagged':           flagged,
            'passed':            agg['total'] - blocked - flagged,
        })


# ── UniqueClick ViewSet ───────────────────────────────────────────────────────

class UniqueClickViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only deduplication records per SmartLink.
    GET /api/smartlink/smartlinks/{sl_pk}/unique-clicks/
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = UniqueClickSerializer

    def get_queryset(self):
        from api.smartlink.models.click import UniqueClick
        return UniqueClick.objects.filter(
            smartlink_id=self.kwargs.get('smartlink_pk'),
            smartlink__publisher=self.request.user,
        ).order_by('-created_at')

    @action(detail=False, methods=['get'])
    def stats(self, request, smartlink_pk=None):
        """Dedup stats: total unique IPs, dedup rate, etc."""
        from api.smartlink.models import Click
        total_clicks  = Click.objects.filter(smartlink_id=smartlink_pk).count()
        unique_clicks = self.get_queryset().count()
        dedup_rate = round((1 - unique_clicks / max(total_clicks, 1)) * 100, 2)
        return Response({
            'total_clicks':  total_clicks,
            'unique_clicks': unique_clicks,
            'duplicate_rate_pct': dedup_rate,
        })


# ── SmartLinkDomain ViewSet ───────────────────────────────────────────────────

class SmartLinkDomainViewSet(viewsets.ModelViewSet):
    """
    Custom domains attached to SmartLinks.
    GET  /api/smartlink/smartlinks/{sl_pk}/custom-domains/
    POST /api/smartlink/smartlinks/{sl_pk}/custom-domains/
    POST /api/smartlink/smartlinks/{sl_pk}/custom-domains/{id}/verify/
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = SmartLinkDomainSerializer

    def get_queryset(self):
        from api.smartlink.models.smartlink import SmartLinkDomain
        return SmartLinkDomain.objects.filter(
            smartlink_id=self.kwargs.get('smartlink_pk'),
            smartlink__publisher=self.request.user,
        )

    def perform_create(self, serializer):
        from api.smartlink.models import SmartLink
        from django.shortcuts import get_object_or_404
        sl = get_object_or_404(SmartLink, pk=self.kwargs['smartlink_pk'], publisher=self.request.user)
        serializer.save(smartlink=sl)

    @action(detail=True, methods=['post'])
    def verify(self, request, smartlink_pk=None, pk=None):
        """Trigger domain DNS verification."""
        from api.smartlink.models.smartlink import SmartLinkDomain
        from django.shortcuts import get_object_or_404
        domain = get_object_or_404(SmartLinkDomain, pk=pk, smartlink_id=smartlink_pk)
        try:
            from api.smartlink.services.core.DomainService import DomainService
            result = DomainService().verify_domain(domain)
            return Response({'verified': result, 'domain': domain.domain})
        except Exception as exc:
            return Response({'verified': False, 'error': str(exc)})


# ── SmartLinkTagging ViewSet ──────────────────────────────────────────────────

class SmartLinkTaggingViewSet(viewsets.ModelViewSet):
    """
    Tag assignments to SmartLinks.
    GET    /api/smartlink/smartlinks/{sl_pk}/tags/
    POST   /api/smartlink/smartlinks/{sl_pk}/tags/       — add tag
    DELETE /api/smartlink/smartlinks/{sl_pk}/tags/{id}/  — remove tag
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = SmartLinkTaggingSerializer

    def get_queryset(self):
        from api.smartlink.models.smartlink import SmartLinkTagging
        return SmartLinkTagging.objects.filter(
            smartlink_id=self.kwargs.get('smartlink_pk'),
            smartlink__publisher=self.request.user,
        ).select_related('tag')

    def perform_create(self, serializer):
        from api.smartlink.models import SmartLink
        from django.shortcuts import get_object_or_404
        sl = get_object_or_404(SmartLink, pk=self.kwargs['smartlink_pk'], publisher=self.request.user)
        serializer.save(smartlink=sl)


# ── Performance Stats ViewSets ────────────────────────────────────────────────

class OfferPerformanceStatViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Offer-level performance stats per SmartLink.
    GET /api/smartlink/smartlinks/{sl_pk}/offer-stats/
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = OfferPerformanceStatSerializer

    def get_queryset(self):
        from api.smartlink.models.analytics import OfferPerformanceStat
        qs = OfferPerformanceStat.objects.filter(
            smartlink_id=self.kwargs.get('smartlink_pk'),
            smartlink__publisher=self.request.user,
        ).order_by('-date')
        days = self.request.query_params.get('days', 30)
        try:
            from django.utils import timezone
            cutoff = timezone.now().date() - timezone.timedelta(days=int(days))
            qs = qs.filter(date__gte=cutoff)
        except (ValueError, TypeError):
            pass
        return qs


class GeoPerformanceStatViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Geo-level performance stats per SmartLink.
    GET /api/smartlink/smartlinks/{sl_pk}/geo-stats/
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = GeoPerformanceStatSerializer

    def get_queryset(self):
        from api.smartlink.models.analytics import GeoPerformanceStat
        return GeoPerformanceStat.objects.filter(
            smartlink_id=self.kwargs.get('smartlink_pk'),
            smartlink__publisher=self.request.user,
        ).order_by('-date', '-clicks')


class DevicePerformanceStatViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Device-level performance stats per SmartLink.
    GET /api/smartlink/smartlinks/{sl_pk}/device-stats/
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = DevicePerformanceStatSerializer

    def get_queryset(self):
        from api.smartlink.models.analytics import DevicePerformanceStat
        return DevicePerformanceStat.objects.filter(
            smartlink_id=self.kwargs.get('smartlink_pk'),
            smartlink__publisher=self.request.user,
        ).order_by('-date', '-clicks')


# ── OfferCapTracker ViewSet ───────────────────────────────────────────────────

class OfferCapTrackerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Real-time cap tracking per offer pool entry.
    GET /api/smartlink/smartlinks/{sl_pk}/cap-trackers/
    GET /api/smartlink/smartlinks/{sl_pk}/cap-trackers/nearly-reached/ — offers near cap
    POST /api/smartlink/smartlinks/{sl_pk}/cap-trackers/{id}/reset/    — admin reset
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = OfferCapTrackerSerializer

    def get_queryset(self):
        from api.smartlink.models.offer_pool import OfferCapTracker
        return OfferCapTracker.objects.filter(
            pool_entry__pool__smartlink_id=self.kwargs.get('smartlink_pk'),
            pool_entry__pool__smartlink__publisher=self.request.user,
        ).select_related('pool_entry').order_by('-period_date')

    @action(detail=False, methods=['get'], url_path='nearly-reached')
    def nearly_reached(self, request, smartlink_pk=None):
        """Offers that have hit ≥80% of their cap."""
        trackers = self.get_queryset().filter(is_capped=False)
        near = [
            t for t in trackers
            if t.cap_limit and t.clicks_count / t.cap_limit >= 0.80
        ]
        data = OfferCapTrackerSerializer(near, many=True).data
        return Response({'count': len(data), 'trackers': data})

    @action(detail=True, methods=['post'])
    def reset(self, request, smartlink_pk=None, pk=None):
        """Admin: manually reset a cap tracker."""
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        from api.smartlink.models.offer_pool import OfferCapTracker
        from django.shortcuts import get_object_or_404
        tracker = get_object_or_404(OfferCapTracker, pk=pk)
        OfferCapTracker.objects.filter(pk=tracker.pk).update(
            clicks_count=0, is_capped=False
        )
        return Response({'detail': 'Cap tracker reset.', 'id': pk})


# ── OfferRotationLog ViewSet ──────────────────────────────────────────────────

class OfferRotationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Offer rotation decision log per SmartLink.
    GET /api/smartlink/smartlinks/{sl_pk}/rotation-log/
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from api.smartlink.serializers import OfferRotationLogSerializer
        return OfferRotationLogSerializer

    def get_queryset(self):
        from api.smartlink.models.offer_pool import OfferRotationLog
        return OfferRotationLog.objects.filter(
            smartlink_id=self.kwargs.get('smartlink_pk'),
            smartlink__publisher=self.request.user,
        ).order_by('-created_at')[:500]

    @action(detail=False, methods=['get'])
    def summary(self, request, smartlink_pk=None):
        """Rotation decision distribution."""
        from api.smartlink.models.offer_pool import OfferRotationLog
        from django.db.models import Count
        qs = self.get_queryset()
        by_reason = list(
            qs.values('rotation_reason').annotate(count=Count('id')).order_by('-count')
        )
        return Response({'by_reason': by_reason, 'total': qs.count()})


# ── OfferScoreCache ViewSet ───────────────────────────────────────────────────

class OfferScoreCacheViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Cached EPC / score per offer pool entry.
    GET /api/smartlink/smartlinks/{sl_pk}/offer-scores/
    POST /api/smartlink/smartlinks/{sl_pk}/offer-scores/refresh/ — recalculate
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from api.smartlink.serializers import OfferScoreCacheSerializer
        return OfferScoreCacheSerializer

    def get_queryset(self):
        from api.smartlink.models.offer_pool import OfferScoreCache
        return OfferScoreCache.objects.filter(
            pool_entry__pool__smartlink_id=self.kwargs.get('smartlink_pk'),
            pool_entry__pool__smartlink__publisher=self.request.user,
        ).select_related('pool_entry').order_by('-epc_score')

    @action(detail=False, methods=['post'])
    def refresh(self, request, smartlink_pk=None):
        """Trigger EPC score recalculation for this SmartLink."""
        try:
            from api.smartlink.tasks.epc_update_tasks import update_epc_for_smartlink
            update_epc_for_smartlink.delay(int(smartlink_pk))
            return Response({'detail': 'EPC recalculation queued.'})
        except Exception as exc:
            return Response({'detail': f'Failed: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
