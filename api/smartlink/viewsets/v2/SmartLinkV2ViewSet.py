"""
SmartLink API V2 ViewSet
Enhanced API with bulk operations, advanced filtering, and new features.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from ...models import SmartLink
from ...serializers.SmartLinkDetailSerializer import SmartLinkDetailSerializer
from ...serializers.SmartLinkSerializer import SmartLinkSerializer
from ...services.core.SmartLinkService import SmartLinkService
from ...services.smartrouter.SmartRouterService import SmartRouterService
from ...services.conversion.ConversionFunnelService import ConversionFunnelService
from ...services.fingerprint.DeviceFingerprintService import DeviceFingerprintService
from ...permissions import IsPublisher
from ...filters import SmartLinkFilter
from ...pagination import StandardResultsPagination


class SmartLinkV2ViewSet(viewsets.ModelViewSet):
    """
    V2 SmartLink API with advanced features:
    - Bulk create/update/archive
    - Conversion funnel data
    - Smart Router explain
    - Device fingerprint dedup insights
    - Real-time routing decision preview
    """
    serializer_class   = SmartLinkSerializer
    permission_classes = [IsAuthenticated, IsPublisher]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class    = SmartLinkFilter
    search_fields      = ['slug', 'name', 'description']
    ordering_fields    = ['created_at', 'total_clicks', 'total_revenue', 'name']
    pagination_class   = StandardResultsPagination

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sl_service     = SmartLinkService()
        self.router_svc     = SmartRouterService()
        self.funnel_svc     = ConversionFunnelService()
        self.fingerprint_svc = DeviceFingerprintService()

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return SmartLink.objects.all().select_related('publisher', 'group')
        return SmartLink.objects.filter(
            publisher=user, is_archived=False
        ).select_related('group').prefetch_related('tags')

    def get_serializer_class(self):
        if self.action in ('retrieve', 'create', 'update', 'partial_update'):
            return SmartLinkDetailSerializer
        return SmartLinkSerializer

    # ── Bulk operations ────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """
        POST /api/v2/smartlinks/bulk-create/
        Create multiple SmartLinks in one request.
        Body: {"smartlinks": [{name, type, ...}, ...]}
        """
        items   = request.data.get('smartlinks', [])
        created = []
        errors  = []

        for i, item in enumerate(items[:50]):  # Max 50 per batch
            try:
                sl = self.sl_service.create(request.user, item)
                created.append({'index': i, 'id': sl.pk, 'slug': sl.slug})
            except Exception as e:
                errors.append({'index': i, 'error': str(e)})

        return Response({
            'created': len(created),
            'errors':  len(errors),
            'results': created,
            'error_details': errors,
        }, status=status.HTTP_207_MULTI_STATUS)

    @action(detail=False, methods=['post'], url_path='bulk-archive')
    def bulk_archive(self, request):
        """Archive multiple SmartLinks by IDs."""
        ids = request.data.get('ids', [])
        qs  = SmartLink.objects.filter(
            pk__in=ids,
            publisher=request.user,
        )
        count = qs.update(is_active=False, is_archived=True)
        return Response({'archived': count})

    @action(detail=False, methods=['post'], url_path='bulk-toggle')
    def bulk_toggle(self, request):
        """Toggle is_active for multiple SmartLinks."""
        ids      = request.data.get('ids', [])
        activate = request.data.get('activate', True)
        qs = SmartLink.objects.filter(pk__in=ids, publisher=request.user)
        count = qs.update(is_active=activate)
        return Response({'updated': count, 'is_active': activate})

    # ── Advanced analytics ─────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='funnel')
    def funnel(self, request, pk=None):
        """GET conversion funnel for a SmartLink."""
        sl   = self.get_object()
        days = int(request.query_params.get('days', 7))
        return Response(self.funnel_svc.get_funnel(sl, days=days))

    @action(detail=True, methods=['get'], url_path='geo-funnel')
    def geo_funnel(self, request, pk=None):
        """GET conversion funnel breakdown by country."""
        sl   = self.get_object()
        days = int(request.query_params.get('days', 7))
        return Response(self.funnel_svc.get_geo_funnel(sl, days=days))

    @action(detail=True, methods=['get'], url_path='time-funnel')
    def time_funnel(self, request, pk=None):
        """GET conversion rate by hour of day."""
        sl   = self.get_object()
        days = int(request.query_params.get('days', 7))
        return Response(self.funnel_svc.get_time_funnel(sl, days=days))

    @action(detail=True, methods=['get'], url_path='router-explain')
    def router_explain(self, request, pk=None):
        """
        GET /api/v2/smartlinks/{id}/router-explain/?country=BD&device=mobile
        Show why SmartRouter would choose a specific offer.
        """
        sl      = self.get_object()
        context = {
            'country':     request.query_params.get('country', 'US'),
            'device_type': request.query_params.get('device', 'mobile'),
            'os':          request.query_params.get('os', 'android'),
            'isp':         request.query_params.get('isp', ''),
            'hour':        int(request.query_params.get('hour', 12)),
        }
        explanation = self.router_svc.get_routing_explanation(sl, context)
        return Response(explanation)

    @action(detail=True, methods=['get'], url_path='cache-status')
    def cache_status(self, request, pk=None):
        """Check if SmartLink is cached in Redis."""
        from django.core.cache import cache
        sl        = self.get_object()
        is_cached = bool(cache.get(f"sl:{sl.slug}"))
        pool_key  = f"sl_pool:{sl.pk}"
        pool_cached = bool(cache.get(pool_key))
        return Response({
            'slug':          sl.slug,
            'is_cached':     is_cached,
            'pool_cached':   pool_cached,
            'cache_key':     f"sl:{sl.slug}",
        })
