from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from ..models import SmartLink
from ..serializers.AdminSerializer import AdminSmartLinkSerializer
from ..services.core.SmartLinkCacheService import SmartLinkCacheService
from ..filters import SmartLinkFilter
from ..pagination import StandardResultsPagination


class AdminSmartLinkViewSet(viewsets.ModelViewSet):
    """
    Admin-only SmartLink management.
    Full access to all publishers' SmartLinks.
    """
    serializer_class = AdminSmartLinkSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SmartLinkFilter
    search_fields = ['slug', 'name', 'publisher__username', 'publisher__email']
    ordering_fields = ['created_at', 'total_clicks', 'total_revenue', 'publisher__username']
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return SmartLink.objects.all().select_related(
            'publisher', 'group'
        ).prefetch_related('tags').order_by('-created_at')

    @action(detail=False, methods=['post'], url_path='warmup-cache')
    def warmup_cache(self, request):
        """POST /admin/smartlinks/warmup-cache/ — pre-warm Redis cache."""
        svc = SmartLinkCacheService()
        count = svc.warmup_all_active()
        return Response({'cached': count})

    @action(detail=True, methods=['post'], url_path='invalidate-cache')
    def invalidate_cache(self, request, pk=None):
        """Invalidate Redis cache for a specific SmartLink."""
        sl = self.get_object()
        svc = SmartLinkCacheService()
        svc.invalidate_smartlink(sl.slug)
        return Response({'status': 'cache_invalidated', 'slug': sl.slug})

    @action(detail=False, methods=['get'], url_path='health-check')
    def health_check(self, request):
        """GET all SmartLinks with 0 active offers in their pool."""
        from ..models import OfferPool
        broken = SmartLink.objects.filter(
            is_active=True, is_archived=False
        ).exclude(
            offer_pool__entries__is_active=True
        ).values('id', 'slug', 'publisher__username')
        return Response({'broken_count': len(list(broken)), 'broken': list(broken)})

    @action(detail=False, methods=['get'], url_path='platform-stats')
    def platform_stats(self, request):
        """GET platform-wide statistics."""
        from django.db.models import Sum, Count, Q
        stats = SmartLink.objects.aggregate(
            total_smartlinks=Count('id'),
            active_smartlinks=Count('id', filter=Q(is_active=True)),
            total_clicks=Sum('total_clicks'),
            total_conversions=Sum('total_conversions'),
            total_revenue=Sum('total_revenue'),
        )
        return Response(stats)
