from typing import Dict, List, Any, Optional, Tuple, Union
from api.cms.permissions import IsOwnerOrAdmin, IsCMSAdmin
# api/cms/viewsets/PageViewSet.py
"""
PageViewSet: Full CRUD for CMS ContentPage with publish, preview,
scheduling, versioning, bulk actions, and analytics.
Fixes and extends the existing ContentPageViewSet in views.py.
"""
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated, IsAdminUser, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils import timezone
from django.db.models import Q, F, Sum, Count
from django.core.cache import cache
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)


class PageViewSet(viewsets.ModelViewSet):
    """
    Extended CMS Page ViewSet with full workflow support.

    Endpoints:
        GET    /api/cms/pages/                         - List pages
        POST   /api/cms/pages/                         - Create page (auth)
        GET    /api/cms/pages/{slug}/                  - Page detail
        PUT    /api/cms/pages/{slug}/                  - Update page (auth)
        PATCH  /api/cms/pages/{slug}/                  - Partial update
        DELETE /api/cms/pages/{slug}/                  - Delete (admin)
        POST   /api/cms/pages/{id}/publish/            - Publish page
        POST   /api/cms/pages/{id}/unpublish/          - Revert to draft
        POST   /api/cms/pages/{id}/schedule/           - Schedule publish
        GET    /api/cms/pages/{id}/preview/            - Preview draft (auth)
        GET    /api/cms/pages/{id}/version_history/    - Version history
        POST   /api/cms/pages/{id}/create_version/     - Create new version
        POST   /api/cms/pages/bulk_publish/            - Bulk publish (admin)
        POST   /api/cms/pages/bulk_status/             - Bulk status update (admin)
        GET    /api/cms/pages/published/               - Published pages (public)
        GET    /api/cms/pages/featured/                - Featured pages (public)
        GET    /api/cms/pages/by_type/{type}/          - Pages by type (public)
        GET    /api/cms/pages/statistics/              - Page statistics (admin)
        POST   /api/cms/pages/{id}/record_share/       - Record share event
    """
    authentication_classes = [JWTAuthentication]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'subtitle', 'excerpt', 'slug']
    ordering_fields = ['published_date', 'view_count', 'created_at', 'share_count']
    ordering = ['-published_date', '-created_at']
    lookup_field = 'slug'

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'published', 'featured', 'by_type'):
            return [AllowAny()]
        if self.action in ('statistics', 'bulk_publish', 'bulk_status', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        from api.cms.models import ContentPage
        user = self.request.user
        qs = ContentPage.objects.select_related('category', 'author', 'related_offer', 'related_task')

        # Staff/admin see all; others see published + own
        if user and user.is_authenticated and user.is_staff:
            pass  # no filter
        elif user and user.is_authenticated:
            qs = qs.filter(
                Q(status='published', is_active=True) | Q(author=user)
            )
        else:
            qs = qs.filter(status='published', is_active=True, visibility='public')

        # Query param filters
        qp = self.request.query_params
        if qp.get('status') and (user and user.is_staff):
            qs = qs.filter(status=qp['status'])
        if qp.get('category'):
            qs = qs.filter(category__slug=qp['category'])
        if qp.get('page_type'):
            qs = qs.filter(page_type=qp['page_type'])
        if qp.get('language'):
            qs = qs.filter(language=qp['language'])
        if qp.get('featured') == 'true':
            qs = qs.filter(is_featured=True)

        return qs

    def get_serializer_class(self):
        from api.cms.serializers import ContentPageSerializer, ContentPageListSerializer
        if self.action == 'list':
            return ContentPageListSerializer
        return ContentPageSerializer

    def retrieve(self, request, *args, **kwargs):
        self.check_object_permissions(request, self.get_object())
        """Get page detail and increment view count."""
        instance = self.get_object()
        instance.increment_view_count()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Create a new CMS page."""
        from api.cms.services_new.PageService import PageService
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        page = PageService.create_page(
            author=request.user,
            **serializer.validated_data
        )
        if page:
            out = self.get_serializer(page)
            return Response(out.data, status=status.HTTP_201_CREATED)
        return Response({'error': 'Failed to create page'}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        """Update an existing page."""
        from api.cms.services_new.PageService import PageService
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        success = PageService.update_page(instance, dict(serializer.validated_data))
        if success:
            return Response(self.get_serializer(instance).data)
        return Response({'error': 'Update failed'}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """Soft-delete a page."""
        from api.cms.services_new.PageService import PageService
        instance = self.get_object()
        hard = request.query_params.get('hard', 'false') == 'true'
        PageService.delete_page(instance, soft=not hard)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Publishing Workflow ───────────────────────────────────────

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def publish(self, request, slug=None):
        """Publish a CMS page."""
        from api.cms.services_new.PageService import PageService
        page = self.get_object()
        publish_date = None
        if request.data.get('publish_date'):
            publish_date = parse_datetime(request.data['publish_date'])
        success = PageService.publish_page(page, publish_date=publish_date)
        if success:
            return Response({'status': 'published', 'published_date': page.published_date})
        return Response({'error': 'Publish failed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def unpublish(self, request, slug=None):
        """Revert page to draft status."""
        from api.cms.services_new.PageService import PageService
        page = self.get_object()
        if not request.user.is_staff and getattr(page, 'author', None) != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        success = PageService.unpublish_page(page)
        if success:
            return Response({'status': 'draft'})
        return Response({'error': 'Unpublish failed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def schedule(self, request, slug=None):
        """Schedule page for future publishing."""
        from api.cms.services_new.PageService import PageService
        page = self.get_object()
        scheduled_date_str = request.data.get('scheduled_date')
        if not scheduled_date_str:
            return Response({'error': 'scheduled_date required'}, status=status.HTTP_400_BAD_REQUEST)
        dt = parse_datetime(scheduled_date_str)
        if not dt:
            return Response({'error': 'Invalid date format'}, status=status.HTTP_400_BAD_REQUEST)
        success = PageService.schedule_page(page, scheduled_date=dt)
        if success:
            return Response({'status': 'scheduled', 'scheduled_date': dt})
        return Response({'error': 'Scheduling failed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def preview(self, request, slug=None):
        """Preview a page (including drafts) for author/staff."""
        from api.cms.models import ContentPage
        try:
            page = ContentPage.objects.select_related('category', 'author').get(slug=slug)
            if not request.user.is_staff and getattr(page, 'author', None) != request.user:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            from api.cms.serializers import ContentPageSerializer
            return Response({**ContentPageSerializer(page).data, 'preview_mode': True})
        except ContentPage.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    # ── Versioning ────────────────────────────────────────────────

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def version_history(self, request, slug=None):
        """Get version history of a page."""
        from api.cms.services_new.VersioningService import VersioningService
        page = self.get_object()
        history = VersioningService.get_version_history_page(page)
        return Response(history)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def create_version(self, request, slug=None):
        """Create a new draft version from current page."""
        from api.cms.services_new.VersioningService import VersioningService
        page = self.get_object()
        new_version = VersioningService.create_page_version(page)
        if new_version:
            from api.cms.serializers import ContentPageSerializer
            return Response(ContentPageSerializer(new_version).data, status=status.HTTP_201_CREATED)
        return Response({'error': 'Version creation failed'}, status=status.HTTP_400_BAD_REQUEST)

    # ── Bulk Actions ──────────────────────────────────────────────

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def bulk_publish(self, request):
        """Bulk publish pages."""
        from api.cms.models import ContentPage
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        count = ContentPage.objects.filter(id__in=ids).update(
            status='published', published_date=now
        )
        return Response({'published': count})

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def bulk_status(self, request):
        """Bulk update status for multiple pages."""
        from api.cms.models import ContentPage
        ids = request.data.get('ids', [])
        new_status = request.data.get('status', '')
        valid_statuses = ['draft', 'review', 'approved', 'published', 'archived', 'scheduled']
        if not ids or new_status not in valid_statuses:
            return Response(
                {'error': f'Valid ids and status ({", ".join(valid_statuses)}) required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        update_data = {'status': new_status}
        if new_status == 'published':
            update_data['published_date'] = timezone.now()
        count = ContentPage.objects.filter(id__in=ids).update(**update_data)
        return Response({'updated': count, 'status': new_status})

    # ── Public Listing Endpoints ──────────────────────────────────

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def published(self, request):
        """Get all published pages (public)."""
        from api.cms.models import ContentPage
        from api.cms.serializers import ContentPageListSerializer
        qs = ContentPage.objects.filter(
            status='published', is_active=True, visibility='public',
            published_date__lte=timezone.now()
        ).select_related('category', 'author').order_by('-published_date')

        lang = request.query_params.get('language')
        if lang:
            qs = qs.filter(language=lang)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ContentPageListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(ContentPageListSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def featured(self, request):
        """Get featured published pages."""
        from api.cms.models import ContentPage
        from api.cms.serializers import ContentPageListSerializer
        lang = request.query_params.get('language', 'en')
        limit = int(request.query_params.get('limit', 10))
        qs = ContentPage.objects.filter(
            is_featured=True, status='published', is_active=True,
            language=lang, published_date__lte=timezone.now()
        ).select_related('category', 'author').order_by('-published_date')[:limit]
        return Response({'results': ContentPageListSerializer(qs, many=True).data})

    @action(detail=False, methods=['get'], permission_classes=[AllowAny],
            url_path='by_type/(?P<page_type>[^/.]+)')
    def by_type(self, request, page_type=None):
        """Get pages by type (blog, news, tutorial, etc.)."""
        from api.cms.models import ContentPage
        from api.cms.serializers import ContentPageListSerializer
        lang = request.query_params.get('language', 'en')
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))
        qs = ContentPage.objects.filter(
            page_type=page_type, status='published',
            is_active=True, language=lang,
            published_date__lte=timezone.now()
        ).select_related('category', 'author').order_by('-published_date')
        total = qs.count()
        results = qs[offset:offset + limit]
        return Response({
            'count': total,
            'page_type': page_type,
            'results': ContentPageListSerializer(results, many=True).data
        })

    # ── Analytics ─────────────────────────────────────────────────

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def statistics(self, request):
        """Get overall CMS page statistics."""
        from api.cms.services_new.PageService import PageService
        return Response(PageService.get_page_statistics())

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def record_share(self, request, slug=None):
        """Record a page share event."""
        from api.cms.models import ContentPage
        from api.cms.models import ContentShare
        try:
            page = ContentPage.objects.get(slug=slug)
            platform = request.data.get('platform', 'other')
            user = request.user if request.user.is_authenticated else None
            ContentShare.objects.create(
                content=page,
                user=user,
                share_platform=platform,
                share_url=request.data.get('share_url', ''),
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            ContentPage.objects.filter(id=page.id).update(share_count=F('share_count') + 1)
            return Response({'shared': True, 'platform': platform})
        except ContentPage.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error recording share: {e}")
            return Response({'error': 'Share recording failed'}, status=status.HTTP_400_BAD_REQUEST)
