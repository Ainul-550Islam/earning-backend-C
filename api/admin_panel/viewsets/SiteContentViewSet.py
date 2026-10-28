# api/admin_panel/viewsets/SiteContentViewSet.py
"""
SiteContentViewSet — migrated from views.py.
All original logic preserved + pagination + filters added.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.core.cache import cache
from django.db.models import Q

from ..models.core import SiteContent
from ..permissions import SystemAccessPermission
from ..pagination import AdminPagination
from ..filters import SiteContentFilter


class SiteContentViewSet(viewsets.ModelViewSet):
    """ViewSet for SiteContent — migrated from views.py (all logic kept)."""
    queryset = SiteContent.objects.all().order_by('order', 'title')
    permission_classes = [SystemAccessPermission]
    lookup_field = 'identifier'
    pagination_class = AdminPagination
    filterset_class = SiteContentFilter

    def get_serializer_class(self):
        from ..serializers.SiteContentSerializer import SiteContentSerializer
        return SiteContentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by content type
        content_type = self.request.query_params.get('content_type')
        if content_type:
            queryset = queryset.filter(content_type=content_type)

        # Filter by language
        language = self.request.query_params.get('language', 'en')
        queryset = queryset.filter(language=language)

        # Filter active only for public endpoints
        if self.action in ['get_content', 'list_public']:
            queryset = queryset.filter(is_active=True)

        return queryset

    @action(detail=True, methods=['post'])
    def toggle(self, request, identifier=None):
        """Toggle is_active on a site content."""
        obj = self.get_object()
        obj.is_active = not obj.is_active
        obj.save(update_fields=['is_active'])
        # Clear cache
        cache.delete(f'admin_panel:site_content:{obj.identifier}')
        return Response({'success': True, 'is_active': obj.is_active})

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Bulk update ordering: body = { items: [{id, order}] }."""
        from django.db import transaction
        items = request.data.get('items', [])
        with transaction.atomic():
            for item in items:
                SiteContent.objects.filter(pk=item['id']).update(order=item['order'])
        cache.delete('admin_panel:site_contents_all')
        return Response({'success': True, 'updated': len(items)})

    @action(detail=False, methods=['get'])
    def get_content(self, request, identifier=None):
        """Get content by identifier (public — cached)."""
        identifier = identifier or request.query_params.get('identifier')
        language = request.query_params.get('language', 'en')

        cache_key = f'site_content_{identifier}_{language}'
        cached_content = cache.get(cache_key)

        if cached_content is None:
            try:
                content = SiteContent.objects.get(
                    identifier=identifier,
                    language=language,
                    is_active=True
                )
                serializer = self.get_serializer(content)
                cached_content = serializer.data
                cache.set(cache_key, cached_content, timeout=300)
            except SiteContent.DoesNotExist:
                return Response({'error': 'Content not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(cached_content)

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get content by type (public)."""
        content_type = request.query_params.get('type')
        language = request.query_params.get('language', 'en')

        if not content_type:
            return Response(
                {'error': 'Content type parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        contents = SiteContent.objects.filter(
            content_type=content_type,
            language=language,
            is_active=True
        ).order_by('order')

        serializer = self.get_serializer(contents, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def list_public(self, request):
        """List only active content for public consumers."""
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)