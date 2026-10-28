"""
SmartLink ImpressionViewSet
============================
API endpoints for pre-click impression tracking.

Impressions are pre-click view events fired when a tracking pixel loads
inside an ad creative. They power:
  - View-through attribution (VTA)
  - Impression-to-click ratio (CTR for affiliate marketers)
  - CPM campaign billing verification
  - Reach / unique audience reporting

Endpoints:
  Public (pixel):
    GET  /api/smartlink/pixel/fire/?sl=<slug>&offer=<id>  — fire tracking pixel (1×1 PNG)

  Publisher (authenticated):
    GET  /api/smartlink/impressions/                              — list my impressions
    GET  /api/smartlink/impressions/summary/?slug=<slug>&days=30 — aggregated summary
    GET  /api/smartlink/impressions/by-country/?slug=<slug>      — breakdown by country
    GET  /api/smartlink/impressions/by-device/?slug=<slug>       — breakdown by device

  Admin:
    GET  /api/smartlink/admin/impressions/         — all impressions (filterable)
    GET  /api/smartlink/admin/impressions/export/  — CSV export
"""
import logging
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from api.smartlink.models.impression import ImpressionLog
from api.smartlink.models import SmartLink
from api.smartlink.serializers.ImpressionLogSerializer import (
    ImpressionLogSerializer,
    ImpressionLogListSerializer,
    ImpressionSummarySerializer,
    ImpressionCreateSerializer,
)
from api.smartlink.services.analytics.ImpressionTrackingService import ImpressionTrackingService
from api.smartlink.services.targeting.GeoTargetingService import GeoTargetingService
from api.smartlink.services.targeting.DeviceTargetingService import DeviceTargetingService
from api.smartlink.utils import get_client_ip, get_user_agent, get_referrer

logger = logging.getLogger('smartlink.viewsets.impression')


class ImpressionViewSet(viewsets.ViewSet):
    """
    Impression tracking endpoints.
    Public pixel endpoint requires no auth.
    All analytical endpoints require authentication.
    """
    permission_classes = [IsAuthenticated]

    # ── Public: 1×1 tracking pixel ───────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='pixel/fire',
            permission_classes=[AllowAny])
    def fire_pixel(self, request):
        """
        GET /api/smartlink/pixel/fire/?sl=<slug>&offer=<id>

        Fires a transparent 1×1 PNG tracking pixel and records an impression.
        Designed to be embedded in ad creatives as an <img> tag:

          <img src="https://track.example.com/api/smartlink/pixel/fire/?sl=abc123"
               width="1" height="1" style="display:none" />

        Query params:
          sl     — SmartLink slug (required)
          offer  — offer ID (optional, for offer-level impression tracking)
          sub1   — publisher sub-ID 1 (optional)
          sub2   — publisher sub-ID 2 (optional)
        """
        slug     = request.GET.get('sl', '').strip()
        offer_id = request.GET.get('offer', None)
        sub1     = request.GET.get('sub1', '')[:255]
        sub2     = request.GET.get('sub2', '')[:255]

        if not slug:
            return self._pixel_response()  # Still return pixel — never break ad creatives

        try:
            smartlink = SmartLink.objects.get(slug=slug, is_active=True)
        except SmartLink.DoesNotExist:
            return self._pixel_response()  # Silent failure — ad creative must not break

        ip          = get_client_ip(request)
        user_agent  = get_user_agent(request)
        referrer    = get_referrer(request)

        # Enrich context
        try:
            geo         = GeoTargetingService().get_country_from_ip(ip)
            device_info = DeviceTargetingService().parse_user_agent(user_agent)
        except Exception:
            geo         = {}
            device_info = {}

        context = {
            'ip':          ip,
            'user_agent':  user_agent,
            'referrer':    referrer,
            'country':     geo.get('country', ''),
            'device_type': device_info.get('device_type', 'unknown'),
            'os':          device_info.get('os', 'unknown'),
            'browser':     device_info.get('browser', 'other'),
            '_is_bot':     device_info.get('is_bot', False),
            'sub1':        sub1,
            'sub2':        sub2,
        }

        try:
            offer_id_int = int(offer_id) if offer_id else None
        except (ValueError, TypeError):
            offer_id_int = None

        # Record impression (non-blocking — service handles its own exceptions)
        try:
            ImpressionTrackingService().record(
                smartlink=smartlink,
                context=context,
                offer_id=offer_id_int,
            )
        except Exception as exc:
            logger.warning(f"Impression record failed for [{slug}]: {exc}")

        return self._pixel_response()

    # ── Publisher: list my impressions ────────────────────────────────────────

    def list(self, request):
        """
        GET /api/smartlink/impressions/
        Return paginated impression logs for the authenticated publisher.

        Query params:
          slug      — filter by SmartLink slug
          days      — last N days (default 7)
          is_unique — true/false filter
          country   — 2-letter country code filter
        """
        slug      = request.query_params.get('slug', '')
        days      = int(request.query_params.get('days', 7))
        is_unique = request.query_params.get('is_unique', '')
        country   = request.query_params.get('country', '')

        cutoff = timezone.now() - timezone.timedelta(days=min(days, 90))

        # Filter to publisher's own SmartLinks
        publisher_slugs = SmartLink.objects.filter(
            publisher=request.user
        ).values_list('slug', flat=True)

        qs = ImpressionLog.objects.filter(
            smartlink__slug__in=publisher_slugs,
            created_at__gte=cutoff,
        ).select_related('smartlink').order_by('-created_at')

        if slug:
            qs = qs.filter(smartlink__slug=slug)
        if country:
            qs = qs.filter(country=country.upper())
        if is_unique.lower() == 'true':
            qs = qs.filter(is_unique=True)
        elif is_unique.lower() == 'false':
            qs = qs.filter(is_unique=False)

        # Simple pagination
        page      = max(1, int(request.query_params.get('page', 1)))
        page_size = 50
        offset    = (page - 1) * page_size
        total     = qs.count()
        items     = qs[offset: offset + page_size]

        serializer = ImpressionLogListSerializer(items, many=True)
        return Response({
            'count':    total,
            'page':     page,
            'pages':    (total + page_size - 1) // page_size,
            'results':  serializer.data,
        })

    def retrieve(self, request, pk=None):
        """
        GET /api/smartlink/impressions/{id}/
        Detail view of a single impression log.
        """
        from django.shortcuts import get_object_or_404

        if request.user.is_staff:
            obj = get_object_or_404(ImpressionLog, pk=pk)
        else:
            obj = get_object_or_404(
                ImpressionLog,
                pk=pk,
                smartlink__publisher=request.user,
            )
        return Response(ImpressionLogSerializer(obj).data)

    # ── Publisher: aggregated summary ─────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """
        GET /api/smartlink/impressions/summary/?slug=<slug>&days=30

        Aggregated impression summary for a SmartLink.
        Returns total, unique, bot counts, CTR, and view-through rate.
        """
        slug = request.query_params.get('slug', '')
        days = int(request.query_params.get('days', 30))

        if not slug:
            return Response(
                {'detail': 'slug query parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.shortcuts import get_object_or_404
        if request.user.is_staff:
            smartlink = get_object_or_404(SmartLink, slug=slug)
        else:
            smartlink = get_object_or_404(
                SmartLink, slug=slug, publisher=request.user
            )

        svc     = ImpressionTrackingService()
        summary = svc.get_summary(smartlink, days=days)

        cutoff = timezone.now() - timezone.timedelta(days=days)
        qs     = ImpressionLog.objects.filter(
            smartlink=smartlink, created_at__gte=cutoff, is_bot=False
        )
        total_impressions  = qs.count()
        unique_impressions = qs.filter(is_unique=True).count()
        bot_count          = ImpressionLog.objects.filter(
            smartlink=smartlink, created_at__gte=cutoff, is_bot=True
        ).count()

        data = {
            'smartlink_slug':      slug,
            'total_impressions':   total_impressions,
            'unique_impressions':  unique_impressions,
            'bot_impressions':     bot_count,
            'human_impressions':   total_impressions,
            'click_through_rate':  summary.get('ctr_percent', 0),
            'view_through_rate':   0.0,   # full VTA requires per-conversion join
            'top_countries':       svc.get_by_country(smartlink, days=days),
            'top_device_types':    svc.get_by_device(smartlink, days=days),
            'period_from':         cutoff.date(),
            'period_to':           timezone.now().date(),
        }
        return Response(data)

    # ── Publisher: country breakdown ─────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='by-country')
    def by_country(self, request):
        """
        GET /api/smartlink/impressions/by-country/?slug=<slug>&days=30
        Impression breakdown by country for a SmartLink.
        """
        slug = request.query_params.get('slug', '')
        days = int(request.query_params.get('days', 30))

        if not slug:
            return Response({'detail': 'slug required.'}, status=400)

        from django.shortcuts import get_object_or_404
        if request.user.is_staff:
            smartlink = get_object_or_404(SmartLink, slug=slug)
        else:
            smartlink = get_object_or_404(SmartLink, slug=slug, publisher=request.user)

        data = ImpressionTrackingService().get_by_country(smartlink, days=days)
        return Response({'slug': slug, 'days': days, 'by_country': data})

    # ── Publisher: device breakdown ───────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='by-device')
    def by_device(self, request):
        """
        GET /api/smartlink/impressions/by-device/?slug=<slug>&days=30
        Impression breakdown by device type.
        """
        slug = request.query_params.get('slug', '')
        days = int(request.query_params.get('days', 30))

        if not slug:
            return Response({'detail': 'slug required.'}, status=400)

        from django.shortcuts import get_object_or_404
        if request.user.is_staff:
            smartlink = get_object_or_404(SmartLink, slug=slug)
        else:
            smartlink = get_object_or_404(SmartLink, slug=slug, publisher=request.user)

        data = ImpressionTrackingService().get_by_device(smartlink, days=days)
        return Response({'slug': slug, 'days': days, 'by_device': data})

    # ── Admin: all impressions ────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='admin/all',
            permission_classes=[IsAuthenticated])
    def admin_list(self, request):
        """
        GET /api/smartlink/impressions/admin/all/
        Admin only: paginated list of all impression logs.
        Filterable by slug, country, days, is_unique, is_bot.
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        slug      = request.query_params.get('slug', '')
        days      = int(request.query_params.get('days', 7))
        is_unique = request.query_params.get('is_unique', '')
        is_bot    = request.query_params.get('is_bot', '')
        country   = request.query_params.get('country', '')

        cutoff = timezone.now() - timezone.timedelta(days=min(days, 90))
        qs = ImpressionLog.objects.filter(
            created_at__gte=cutoff
        ).select_related('smartlink').order_by('-created_at')

        if slug:
            qs = qs.filter(smartlink__slug=slug)
        if country:
            qs = qs.filter(country=country.upper())
        if is_unique.lower() == 'true':
            qs = qs.filter(is_unique=True)
        elif is_unique.lower() == 'false':
            qs = qs.filter(is_unique=False)
        if is_bot.lower() == 'true':
            qs = qs.filter(is_bot=True)
        elif is_bot.lower() == 'false':
            qs = qs.filter(is_bot=False)

        page      = max(1, int(request.query_params.get('page', 1)))
        page_size = 100
        offset    = (page - 1) * page_size
        total     = qs.count()
        items     = qs[offset: offset + page_size]

        serializer = ImpressionLogListSerializer(items, many=True)
        return Response({
            'count':   total,
            'page':    page,
            'pages':   (total + page_size - 1) // page_size,
            'results': serializer.data,
        })

    # ── 1×1 transparent PNG ───────────────────────────────────────────────────

    @staticmethod
    def _pixel_response() -> HttpResponse:
        """
        Return a 1×1 transparent PNG.
        This is the actual tracking pixel image returned to the browser.
        Cache-Control: no-store prevents the browser from caching it,
        ensuring every page load fires a real impression.
        """
        # Minimal valid 1×1 transparent PNG (35 bytes)
        PNG_1x1 = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
            b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
            b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        response = HttpResponse(PNG_1x1, content_type='image/png')
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        response['Pragma']        = 'no-cache'
        response['Expires']       = '0'
        return response
