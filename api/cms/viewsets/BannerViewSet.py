from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/viewsets/BannerViewSet.py
"""
BannerViewSet: Full banner management with CPAlead earning integration.
Covers: CRUD, impression/click tracking, reward awarding, analytics,
targeting, A/B testing support, and bulk operations.
"""
import logging
from datetime import timedelta
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils import timezone
from django.db.models import Q, F, Sum, Count, Avg
from django.core.cache import cache

logger = logging.getLogger(__name__)


class BannerViewSet(viewsets.ModelViewSet):
    """
    Full-featured Banner ViewSet with CPAlead earning system integration.

    Endpoints:
        GET    /api/cms/banners/                          - List banners (admin)
        POST   /api/cms/banners/                          - Create banner (admin)
        GET    /api/cms/banners/{id}/                     - Banner detail
        PUT    /api/cms/banners/{id}/                     - Update banner (admin)
        DELETE /api/cms/banners/{id}/                     - Delete banner (admin)
        GET    /api/cms/banners/active/                   - Get active banners (public)
        POST   /api/cms/banners/{id}/record_impression/   - Record impression
        POST   /api/cms/banners/{id}/record_click/        - Record click + reward
        GET    /api/cms/banners/{id}/statistics/          - Banner statistics (admin)
        GET    /api/cms/banners/analytics/                - All banners analytics (admin)
        GET    /api/cms/banners/statistics/               - Summary stats (admin)
        POST   /api/cms/banners/bulk_activate/            - Bulk activate (admin)
        POST   /api/cms/banners/bulk_deactivate/          - Bulk deactivate (admin)
        POST   /api/cms/banners/deactivate_expired/       - Deactivate expired (admin)
        POST   /api/cms/banners/from_template/            - Create from template (admin)
    """
    authentication_classes = [JWTAuthentication]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'title', 'description']
    ordering_fields = ['priority', 'impression_count', 'click_count', 'created_at']
    ordering = ['-priority', '-created_at']

    def get_permissions(self):
        if self.action in ('active', 'record_impression', 'record_click'):
            return [AllowAny()]
        if self.action in ('list', 'retrieve', 'statistics', 'analytics'):
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        from api.cms.models import Banner
        qs = Banner.objects.select_related('internal_page', 'offer', 'task')
        user = self.request.user

        if not (user and user.is_authenticated and user.is_staff):
            qs = qs.filter(is_active=True)

        # Filter params
        qp = self.request.query_params
        if qp.get('banner_type'):
            qs = qs.filter(banner_type=qp['banner_type'])
        if qp.get('position'):
            qs = qs.filter(position=qp['position'])
        if qp.get('device'):
            qs = qs.filter(target_device__in=[qp['device'], 'all'])
        if qp.get('is_active'):
            qs = qs.filter(is_active=qp['is_active'].lower() == 'true')

        return qs.order_by('-priority', '-created_at')

    def get_serializer_class(self):
        from api.cms.serializers import BannerSerializer
        return BannerSerializer

    def create(self, request, *args, **kwargs):
        """Create a new banner."""
        from api.cms.models import Banner
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        banner = serializer.save()
        logger.info(f"Banner created: {banner.id} by user {request.user.id}")
        return Response(self.get_serializer(banner).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """Update a banner and invalidate cache."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        banner = serializer.save()
        cache.delete(f'banner_active_{banner.id}')
        return Response(self.get_serializer(banner).data)

    def destroy(self, request, *args, **kwargs):
        """Deactivate or delete a banner."""
        instance = self.get_object()
        hard = request.query_params.get('hard', 'false') == 'true'
        if hard:
            instance.delete()
        else:
            instance.is_active = False
            instance.save(update_fields=['is_active'])
        cache.delete(f'banner_active_{instance.id}')
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Public Banner Display ─────────────────────────────────────

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def active(self, request):
        """
        Get active banners for display — public endpoint.
        Supports device, position targeting.
        CPAlead pattern: returns banners with reward_amount for click/view rewards.
        """
        from api.cms.services.BannerService import BannerService
        from api.cms.serializers import BannerSerializer

        device = request.query_params.get('device', 'all')
        position = request.query_params.get('position', None)
        limit = int(request.query_params.get('limit', 10))
        user = request.user if request.user.is_authenticated else None

        banners = BannerService.get_active_banners(
            user=user,
            device=device,
            position=position,
            limit=limit,
        )

        # Add reward eligibility flag for CPAlead-style earning
        data = []
        for banner in banners:
            banner_data = BannerSerializer(banner).data
            banner_data['reward_eligible'] = (
                banner.reward_amount > 0 and
                user is not None
            )
            data.append(banner_data)

        return Response({'results': data, 'count': len(data)})

    # ── Impression & Click Tracking (CPAlead pattern) ─────────────

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def record_impression(self, request, pk=None):
        """
        Record a banner impression.
        CPAlead pattern: tracked for view-based rewards.
        """
        from api.cms.services.BannerService import BannerService
        banner = self.get_object()
        user = request.user if request.user.is_authenticated else None
        success = BannerService.record_impression(
            banner=banner,
            user=user,
            request=request,
            impression_type=request.data.get('impression_type', 'view'),
        )
        return Response({'recorded': success, 'banner_id': banner.id})

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def record_click(self, request, pk=None):
        """
        Record a banner click and optionally award CPAlead-style reward.
        Returns redirect_url + reward_awarded flag.
        """
        from api.cms.services.BannerService import BannerService
        banner = self.get_object()
        user = request.user if request.user.is_authenticated else None
        result = BannerService.record_click(
            banner=banner,
            user=user,
            request=request,
            click_type=request.data.get('click_type', 'user'),
        )
        return Response(result)

    # ── Statistics & Analytics ────────────────────────────────────

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def statistics(self, request, pk=None):
        """Get detailed statistics for a specific banner."""
        from api.cms.services.BannerService import BannerService
        from django.utils.dateparse import parse_datetime
        banner = self.get_object()
        start_date = None
        end_date = None
        if request.query_params.get('start_date'):
            start_date = parse_datetime(request.query_params['start_date'])
        if request.query_params.get('end_date'):
            end_date = parse_datetime(request.query_params['end_date'])
        stats = BannerService.get_banner_statistics(banner, start_date=start_date, end_date=end_date)
        return Response(stats)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def analytics(self, request):
        """Get analytics for all banners."""
        from api.cms.services.BannerService import BannerService
        from django.utils.dateparse import parse_datetime
        start_date = None
        end_date = None
        if request.query_params.get('start_date'):
            start_date = parse_datetime(request.query_params['start_date'])
        if request.query_params.get('end_date'):
            end_date = parse_datetime(request.query_params['end_date'])
        banner_type = request.query_params.get('banner_type')
        position = request.query_params.get('position')
        data = BannerService.get_analytics(
            start_date=start_date, end_date=end_date,
            banner_type=banner_type, position=position
        )
        return Response(data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def overall_stats(self, request):
        """Get overall banner system statistics."""
        from api.cms.services.BannerService import BannerService
        return Response(BannerService.get_statistics())

    # ── Bulk Operations ───────────────────────────────────────────

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def bulk_activate(self, request):
        """Bulk activate banners."""
        from api.cms.models import Banner
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
        count = Banner.objects.filter(id__in=ids).update(is_active=True)
        # Clear caches
        for bid in ids:
            cache.delete(f'banner_active_{bid}')
        return Response({'activated': count})

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def bulk_deactivate(self, request):
        """Bulk deactivate banners."""
        from api.cms.models import Banner
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
        count = Banner.objects.filter(id__in=ids).update(is_active=False)
        for bid in ids:
            cache.delete(f'banner_active_{bid}')
        return Response({'deactivated': count})

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def deactivate_expired(self, request):
        """Deactivate all expired banners."""
        from api.cms.services.BannerService import BannerService
        deactivated, total = BannerService.deactivate_expired_banners()
        return Response({'deactivated': deactivated, 'total_expired': total})

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def from_template(self, request):
        """Create a banner from a preset template."""
        from api.cms.services.BannerService import BannerService
        template_name = request.data.get('template')
        data = request.data.get('data', {})
        if not template_name:
            return Response({'error': 'template name required'}, status=status.HTTP_400_BAD_REQUEST)
        banner = BannerService.create_banner_from_template(
            template_name=template_name,
            data=data,
            user=request.user
        )
        if banner:
            return Response(self.get_serializer(banner).data, status=status.HTTP_201_CREATED)
        return Response({'error': 'Template creation failed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def generate_report(self, request):
        """Generate a detailed banner performance report."""
        from api.cms.services.BannerService import BannerService
        from django.utils.dateparse import parse_datetime
        banner_ids = request.data.get('banner_ids')
        start_date = None
        end_date = None
        if request.data.get('start_date'):
            start_date = parse_datetime(request.data['start_date'])
        if request.data.get('end_date'):
            end_date = parse_datetime(request.data['end_date'])
        report_type = request.data.get('report_type', 'performance')
        report = BannerService.generate_banner_report(
            banner_ids=banner_ids,
            start_date=start_date,
            end_date=end_date,
            report_type=report_type
        )
        return Response(report)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def cleanup_logs(self, request):
        """Clean up old banner impression/click logs."""
        from api.cms.services.BannerService import BannerService
        days = int(request.data.get('days', 90))
        imp_deleted, click_deleted = BannerService.cleanup_old_logs(days=days)
        return Response({
            'impressions_deleted': imp_deleted,
            'clicks_deleted': click_deleted,
            'days': days
        })
