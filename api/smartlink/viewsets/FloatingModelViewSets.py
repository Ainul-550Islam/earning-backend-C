"""
SmartLink — Floating Model ViewSets
=====================================
Previously these 9 models existed in the DB (serializers written) but had
NO viewset and NO URL registration — completely inaccessible from the API.

Now wired:
  • SmartLinkRotation   → GET/PATCH  /api/smartlink/smartlinks/{sl_pk}/rotation/
  • SmartLinkFallback   → CRUD       /api/smartlink/smartlinks/{sl_pk}/fallback/
  • SmartLinkVersion    → CRUD       /api/smartlink/smartlinks/{sl_pk}/versions/
  • ClickSession        → READ-only  /api/smartlink/smartlinks/{sl_pk}/sessions/
  • ClickMetadata       → READ-only  /api/smartlink/smartlinks/{sl_pk}/clicks/{click_pk}/metadata/
  • BotClick            → READ-only  /api/smartlink/smartlinks/{sl_pk}/bot-clicks/
  • PublisherAllowList  → CRUD       /api/smartlink/publisher/allow-list/
  • PublisherBlockList  → CRUD       /api/smartlink/publisher/block-list/
  • RedirectChain       → READ-only  /api/smartlink/smartlinks/{sl_pk}/redirect-chains/
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.shortcuts import get_object_or_404

from api.smartlink.permissions import IsPublisher, IsOwnerOrAdmin

logger = logging.getLogger('smartlink.viewsets.floating')


# ─────────────────────────────────────────────────────────────────────────────
# 1. SmartLinkRotation — per-SmartLink rotation config (OneToOne)
# ─────────────────────────────────────────────────────────────────────────────

class SmartLinkRotationViewSet(viewsets.GenericViewSet):
    """
    GET/PATCH /api/smartlink/smartlinks/{smartlink_pk}/rotation/

    Retrieve or update the rotation configuration for a SmartLink.
    SmartLinkRotation is OneToOne with SmartLink — only retrieve & update.
    If no rotation config exists yet, GET auto-creates a default one.

    Fields:
      method                        — weighted | round_robin | epc_optimized | ml
      auto_optimize_epc             — bool: shift weight toward higher-EPC offers
      optimization_interval_minutes — how often EPC optimizer runs (default 30)
      epc_min_clicks                — minimum clicks before optimizer kicks in
      last_optimized_at             — readonly timestamp
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_serializer_class(self):
        from api.smartlink.serializers.MissingSerializers import SmartLinkRotationSerializer
        return SmartLinkRotationSerializer

    def _get_rotation(self, smartlink_pk, user):
        from api.smartlink.models import SmartLink
        from api.smartlink.models.smartlink import SmartLinkRotation
        from api.smartlink.choices import RotationMethod

        sl = get_object_or_404(
            SmartLink, pk=smartlink_pk,
            publisher=user if not user.is_staff else SmartLink.objects.filter(
                pk=smartlink_pk).values_list('publisher', flat=True).first(),
        )
        if not user.is_staff:
            sl = get_object_or_404(SmartLink, pk=smartlink_pk, publisher=user)

        rotation, _ = SmartLinkRotation.objects.get_or_create(
            smartlink=sl,
            defaults={'method': RotationMethod.WEIGHTED},
        )
        return rotation

    def retrieve(self, request, smartlink_pk=None, pk=None):
        """GET /smartlinks/{sl_pk}/rotation/ — retrieve rotation config."""
        rotation = self._get_rotation(smartlink_pk, request.user)
        serializer = self._get_serializer_class()(rotation)
        return Response(serializer.data)

    def partial_update(self, request, smartlink_pk=None, pk=None):
        """PATCH /smartlinks/{sl_pk}/rotation/ — update rotation config."""
        rotation = self._get_rotation(smartlink_pk, request.user)
        serializer = self._get_serializer_class()(
            rotation, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(
            f"SmartLink rotation updated: sl#{smartlink_pk} "
            f"method={request.data.get('method', '?')} "
            f"user={request.user.pk}"
        )
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# 2. SmartLinkFallback — fallback URL when no offer matches (OneToOne)
# ─────────────────────────────────────────────────────────────────────────────

class SmartLinkFallbackViewSet(viewsets.GenericViewSet):
    """
    CRUD /api/smartlink/smartlinks/{smartlink_pk}/fallback/

    Manage the fallback URL for a SmartLink.
    Called by RedirectService when no offer survives targeting rules.

    Fields:
      url       — destination when all offers are capped/targeting failed
      reason    — admin note explaining the fallback
      is_active — toggle fallback on/off (when off, 404 is returned)
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_serializer_class(self):
        from api.smartlink.serializers.MissingSerializers import SmartLinkFallbackSerializer
        return SmartLinkFallbackSerializer

    def _get_smartlink(self, smartlink_pk, user):
        from api.smartlink.models import SmartLink
        if user.is_staff:
            return get_object_or_404(SmartLink, pk=smartlink_pk)
        return get_object_or_404(SmartLink, pk=smartlink_pk, publisher=user)

    def retrieve(self, request, smartlink_pk=None, pk=None):
        """GET /smartlinks/{sl_pk}/fallback/ — get current fallback config."""
        from api.smartlink.models.smartlink import SmartLinkFallback
        sl = self._get_smartlink(smartlink_pk, request.user)
        try:
            fallback = sl.fallback
        except SmartLinkFallback.DoesNotExist:
            return Response(
                {'detail': 'No fallback configured for this SmartLink.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(self._get_serializer_class()(fallback).data)

    def create(self, request, smartlink_pk=None):
        """POST /smartlinks/{sl_pk}/fallback/ — set fallback URL."""
        from api.smartlink.models.smartlink import SmartLinkFallback
        sl = self._get_smartlink(smartlink_pk, request.user)
        existing = SmartLinkFallback.objects.filter(smartlink=sl).first()
        if existing:
            return Response(
                {'detail': 'Fallback already exists. Use PATCH to update.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self._get_serializer_class()(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(smartlink=sl)
        logger.info(f"Fallback created: sl#{sl.pk} url={request.data.get('url','?')}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, smartlink_pk=None, pk=None):
        """PATCH /smartlinks/{sl_pk}/fallback/ — update fallback."""
        from api.smartlink.models.smartlink import SmartLinkFallback
        sl = self._get_smartlink(smartlink_pk, request.user)
        fallback = get_object_or_404(SmartLinkFallback, smartlink=sl)
        serializer = self._get_serializer_class()(
            fallback, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def destroy(self, request, smartlink_pk=None, pk=None):
        """DELETE /smartlinks/{sl_pk}/fallback/ — remove fallback."""
        from api.smartlink.models.smartlink import SmartLinkFallback
        sl = self._get_smartlink(smartlink_pk, request.user)
        fallback = get_object_or_404(SmartLinkFallback, smartlink=sl)
        fallback.delete()
        logger.info(f"Fallback deleted: sl#{sl.pk} user={request.user.pk}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='toggle')
    def toggle(self, request, smartlink_pk=None):
        """POST /smartlinks/{sl_pk}/fallback/toggle/ — flip is_active."""
        from api.smartlink.models.smartlink import SmartLinkFallback
        sl = self._get_smartlink(smartlink_pk, request.user)
        fallback = get_object_or_404(SmartLinkFallback, smartlink=sl)
        fallback.is_active = not fallback.is_active
        fallback.save(update_fields=['is_active', 'updated_at'])
        return Response({'is_active': fallback.is_active})


# ─────────────────────────────────────────────────────────────────────────────
# 3. SmartLinkVersion — A/B test variants (multi-row per SmartLink)
# ─────────────────────────────────────────────────────────────────────────────

class SmartLinkVersionViewSet(viewsets.ModelViewSet):
    """
    CRUD /api/smartlink/smartlinks/{smartlink_pk}/versions/

    Manage A/B test traffic-split versions for a SmartLink.
    Each version gets a slice of traffic (traffic_split % sum ≤ 100).

    Fields:
      name          — variant name (e.g. "Control", "Variant B")
      description   — optional notes
      traffic_split — % of traffic routed to this variant (0–100)
      is_control    — flag the baseline control variant
      is_active     — exclude from rotation without deleting
      is_winner     — admin marks winning variant after significance test
      clicks / conversions / revenue — read-only aggregate stats
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_serializer_class(self):
        from api.smartlink.serializers.MissingSerializers import SmartLinkVersionSerializer
        return SmartLinkVersionSerializer

    def get_queryset(self):
        from api.smartlink.models.smartlink import SmartLinkVersion
        sl_pk = self.kwargs.get('smartlink_pk')
        if self.request.user.is_staff:
            return SmartLinkVersion.objects.filter(smartlink_id=sl_pk)
        return SmartLinkVersion.objects.filter(
            smartlink_id=sl_pk,
            smartlink__publisher=self.request.user,
        )

    def perform_create(self, serializer):
        sl_pk = self.kwargs.get('smartlink_pk')
        from api.smartlink.models import SmartLink
        if self.request.user.is_staff:
            sl = get_object_or_404(SmartLink, pk=sl_pk)
        else:
            sl = get_object_or_404(SmartLink, pk=sl_pk, publisher=self.request.user)
        serializer.save(smartlink=sl)

    @action(detail=True, methods=['post'], url_path='mark-winner')
    def mark_winner(self, request, smartlink_pk=None, pk=None):
        """POST /versions/{id}/mark-winner/ — mark this version as winner."""
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only admin can mark a winner.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        version = self.get_object()
        from api.smartlink.models.smartlink import SmartLinkVersion
        # Clear all other winners in this SmartLink
        SmartLinkVersion.objects.filter(
            smartlink=version.smartlink,
        ).update(is_winner=False)
        version.is_winner = True
        version.save(update_fields=['is_winner', 'updated_at'])
        logger.info(
            f"SmartLink version winner set: sl#{version.smartlink_id} "
            f"version#{version.pk} name={version.name}"
        )
        return Response({'is_winner': True, 'version_id': version.pk})

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request, smartlink_pk=None):
        """GET /versions/summary/ — traffic split totals and performance."""
        from django.db.models import Sum
        qs = self.get_queryset()
        total_split = qs.aggregate(total=Sum('traffic_split'))['total'] or 0
        versions = self.get_serializer_class()(qs, many=True).data
        return Response({
            'total_traffic_split': total_split,
            'remaining_unallocated': max(0, 100 - total_split),
            'versions': versions,
        })


# ─────────────────────────────────────────────────────────────────────────────
# 4. ClickSession — read-only session browser view
# ─────────────────────────────────────────────────────────────────────────────

class ClickSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    READ-ONLY /api/smartlink/smartlinks/{smartlink_pk}/sessions/

    View click sessions for a SmartLink.
    Sessions group multiple clicks from the same user/device.
    Useful for understanding user journeys and cross-session attribution.

    Filters:
      ?country=US   — filter by country code
      ?device_type= — mobile|desktop|tablet
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_serializer_class(self):
        from api.smartlink.serializers.ClickSessionSerializer import ClickSessionSerializer
        return ClickSessionSerializer

    def get_queryset(self):
        from api.smartlink.models import ClickSession
        sl_pk   = self.kwargs.get('smartlink_pk')
        country = self.request.query_params.get('country')
        device  = self.request.query_params.get('device_type')

        qs = ClickSession.objects.filter(smartlink_id=sl_pk)
        if not self.request.user.is_staff:
            qs = qs.filter(smartlink__publisher=self.request.user)
        if country:
            qs = qs.filter(country=country.upper())
        if device:
            qs = qs.filter(device_type=device)
        return qs.order_by('-last_seen')

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request, smartlink_pk=None):
        """GET /sessions/summary/ — aggregated session stats."""
        from django.db.models import Sum, Avg
        qs = self.get_queryset()
        agg = qs.aggregate(
            total_sessions=Sum('click_count'),
            avg_clicks_per_session=Avg('click_count'),
        )
        return Response({
            'total_sessions': qs.count(),
            'total_clicks_in_sessions': agg['total_sessions'] or 0,
            'avg_clicks_per_session': round(agg['avg_clicks_per_session'] or 0, 2),
            'countries': list(
                qs.values_list('country', flat=True).distinct().order_by('country')
            ),
        })


# ─────────────────────────────────────────────────────────────────────────────
# 5. ClickMetadata — sub-ID params per click (read-only)
# ─────────────────────────────────────────────────────────────────────────────

class ClickMetadataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    READ-ONLY /api/smartlink/smartlinks/{smartlink_pk}/clicks/{click_pk}/metadata/

    Retrieve sub-ID tracking parameters (sub1–sub5) and custom params
    attached to a specific click. Useful for tracing publisher sub-IDs
    and debugging postback attribution issues.

    Returns:
      sub1, sub2, sub3, sub4, sub5, custom_params,
      referrer, landing_page_url, offer_url_final
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_serializer_class(self):
        from api.smartlink.serializers.ClickMetadataSerializer import ClickMetadataSerializer
        return ClickMetadataSerializer

    def get_queryset(self):
        from api.smartlink.models import ClickMetadata
        sl_pk    = self.kwargs.get('smartlink_pk')
        click_pk = self.kwargs.get('click_pk')
        qs = ClickMetadata.objects.filter(
            click__smartlink_id=sl_pk,
        )
        if click_pk:
            qs = qs.filter(click_id=click_pk)
        if not self.request.user.is_staff:
            qs = qs.filter(click__smartlink__publisher=self.request.user)
        return qs.select_related('click')


# ─────────────────────────────────────────────────────────────────────────────
# 6. BotClick — read-only bot/crawler detection log
# ─────────────────────────────────────────────────────────────────────────────

class BotClickViewSet(viewsets.ReadOnlyModelViewSet):
    """
    READ-ONLY /api/smartlink/smartlinks/{smartlink_pk}/bot-clicks/

    View detected bot/crawler clicks for a SmartLink.
    These are clicks that were blocked by BotDetectionService and
    stored separately from real Click records.

    Useful for:
      - Auditing traffic quality
      - Identifying scrapers and crawlers
      - Disputing fraud accusations

    Filters:
      ?bot_type=Googlebot   — filter by bot type label
      ?detection_method=ua_pattern
      ?country=US
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_serializer_class(self):
        from api.smartlink.serializers.BotClickSerializer import BotClickSerializer
        return BotClickSerializer

    def get_queryset(self):
        from api.smartlink.models import BotClick
        sl_pk  = self.kwargs.get('smartlink_pk')
        qs     = BotClick.objects.filter(smartlink_id=sl_pk)
        if not self.request.user.is_staff:
            qs = qs.filter(smartlink__publisher=self.request.user)

        bot_type = self.request.query_params.get('bot_type')
        method   = self.request.query_params.get('detection_method')
        country  = self.request.query_params.get('country')
        if bot_type:
            qs = qs.filter(bot_type=bot_type)
        if method:
            qs = qs.filter(detection_method=method)
        if country:
            qs = qs.filter(country=country.upper())
        return qs.order_by('-created_at')

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request, smartlink_pk=None):
        """GET /bot-clicks/summary/ — aggregated bot traffic breakdown."""
        from django.db.models import Count
        qs = self.get_queryset()
        by_type = list(
            qs.values('bot_type', 'detection_method')
              .annotate(count=Count('id'))
              .order_by('-count')[:20]
        )
        by_country = list(
            qs.values('country').annotate(count=Count('id')).order_by('-count')[:20]
        )
        return Response({
            'total_bot_clicks': qs.count(),
            'by_bot_type': by_type,
            'by_country': by_country,
        })


# ─────────────────────────────────────────────────────────────────────────────
# 7. PublisherAllowList — admin-controlled offer category access per publisher
# ─────────────────────────────────────────────────────────────────────────────

class PublisherAllowListViewSet(viewsets.ModelViewSet):
    """
    CRUD /api/smartlink/publisher/allow-list/

    Admin-controlled whitelist of offer categories/advertisers a publisher
    can access. Publishers see their own allow-list (read-only).
    Admins can grant access.

    Used by SmartRouterService.route() to filter offers by publisher access level.

    Fields:
      category    — offer vertical (e.g. "finance", "gaming", "health")
      advertiser  — optional: specific advertiser FK (null = all in category)
      is_active   — toggle without deleting
      granted_by  — readonly: admin who granted access
      notes       — internal notes
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from api.smartlink.serializers.PublisherAllowListSerializer import PublisherAllowListSerializer
        return PublisherAllowListSerializer

    def get_queryset(self):
        from api.smartlink.models.publisher import PublisherAllowList
        if self.request.user.is_staff:
            publisher_id = self.request.query_params.get('publisher_id')
            qs = PublisherAllowList.objects.all()
            if publisher_id:
                qs = qs.filter(publisher_id=publisher_id)
            return qs.select_related('publisher', 'granted_by').order_by('-id')
        # Publishers see their own allow-list only (read-only)
        return PublisherAllowList.objects.filter(
            publisher=self.request.user, is_active=True,
        ).order_by('-id')

    def create(self, request, *args, **kwargs):
        """Admin-only: grant a publisher access to a category."""
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only admin can grant allow-list entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(granted_by=self.request.user)

    def update(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only admin can modify allow-list entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only admin can delete allow-list entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='toggle',
            permission_classes=[IsAuthenticated, IsAdminUser])
    def toggle(self, request, pk=None):
        """POST /allow-list/{id}/toggle/ — admin-only toggle is_active."""
        entry = self.get_object()
        entry.is_active = not entry.is_active
        entry.save(update_fields=['is_active'])
        logger.info(
            f"AllowList entry toggled: publisher#{entry.publisher_id} "
            f"category={entry.category} active={entry.is_active} "
            f"by admin={request.user.pk}"
        )
        return Response({'is_active': entry.is_active})


# ─────────────────────────────────────────────────────────────────────────────
# 8. PublisherBlockList — admin-controlled advertiser/category blocks
# ─────────────────────────────────────────────────────────────────────────────

class PublisherBlockListViewSet(viewsets.ModelViewSet):
    """
    CRUD /api/smartlink/publisher/block-list/

    Admin-controlled blocklist of advertisers/categories for a publisher.
    Prevents specific advertiser offers from appearing in the publisher's SmartLinks.

    Used by SmartRouterService to exclude blocked offers from rotation.

    Fields:
      advertiser  — blocked advertiser FK (null = entire category blocked)
      category    — blocked category slug
      reason      — admin note
      is_active   — soft toggle
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from api.smartlink.serializers.PublisherBlockListSerializer import PublisherBlockListSerializer
        return PublisherBlockListSerializer

    def get_queryset(self):
        from api.smartlink.models.publisher import PublisherBlockList
        if self.request.user.is_staff:
            publisher_id = self.request.query_params.get('publisher_id')
            qs = PublisherBlockList.objects.all()
            if publisher_id:
                qs = qs.filter(publisher_id=publisher_id)
            return qs.order_by('-id')
        return PublisherBlockList.objects.filter(
            publisher=self.request.user,
        ).order_by('-id')

    def create(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only admin can create block-list entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(blocked_by=self.request.user)

    def update(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only admin can update block-list entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only admin can delete block-list entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='toggle',
            permission_classes=[IsAuthenticated, IsAdminUser])
    def toggle(self, request, pk=None):
        """POST /block-list/{id}/toggle/ — admin-only toggle is_active."""
        entry = self.get_object()
        entry.is_active = not entry.is_active
        entry.save(update_fields=['is_active'])
        return Response({'is_active': entry.is_active})


# ─────────────────────────────────────────────────────────────────────────────
# 9. RedirectChain — multi-hop redirect path recorder (read-only)
# ─────────────────────────────────────────────────────────────────────────────

class RedirectChainViewSet(viewsets.ReadOnlyModelViewSet):
    """
    READ-ONLY /api/smartlink/smartlinks/{smartlink_pk}/redirect-chains/

    View the full multi-hop redirect path recorded for each click.
    The chain records every step: SmartLink → PreLander → LandingPage → Offer.

    Useful for:
      - Debugging redirect loops
      - Auditing pre-lander pass-through rates
      - Proving correct offer delivery to advertisers

    Fields:
      click_id    — the originating click
      chain       — list of hops [{step, type, url, ts}]
      hop_count   — total number of redirects
      created_at  — when the chain was recorded

    Filters:
      ?click_id=<pk>  — get chain for a specific click
      ?min_hops=3     — filter by minimum hop count (detect loops)
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_serializer_class(self):
        from api.smartlink.serializers.RedirectChainSerializer import RedirectChainSerializer
        return RedirectChainSerializer

    def get_queryset(self):
        from api.smartlink.models.redirect import RedirectChain
        sl_pk    = self.kwargs.get('smartlink_pk')
        click_id = self.request.query_params.get('click_id')
        min_hops = self.request.query_params.get('min_hops')

        qs = RedirectChain.objects.filter(smartlink_id=sl_pk)
        if not self.request.user.is_staff:
            qs = qs.filter(smartlink__publisher=self.request.user)
        if click_id:
            qs = qs.filter(click_id=click_id)
        if min_hops:
            try:
                qs = qs.filter(hop_count__gte=int(min_hops))
            except (ValueError, TypeError):
                pass
        return qs.select_related('click').order_by('-id')

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request, smartlink_pk=None):
        """GET /redirect-chains/summary/ — hop count distribution."""
        from django.db.models import Count, Avg, Max
        qs  = self.get_queryset()
        agg = qs.aggregate(
            total=Count('id'),
            avg_hops=Avg('hop_count'),
            max_hops=Max('hop_count'),
        )
        dist = list(
            qs.values('hop_count')
              .annotate(count=Count('id'))
              .order_by('hop_count')
        )
        return Response({
            'total_chains':   agg['total'] or 0,
            'avg_hop_count':  round(agg['avg_hops'] or 0, 2),
            'max_hop_count':  agg['max_hops'] or 0,
            'hop_distribution': dist,
        })
