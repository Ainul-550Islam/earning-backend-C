import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from ..models import SmartLink
from ..serializers.SmartLinkSerializer import SmartLinkSerializer
from ..serializers.SmartLinkDetailSerializer import SmartLinkDetailSerializer
from ..services.core.SmartLinkService import SmartLinkService
from ..services.core.SmartLinkBuilderService import SmartLinkBuilderService
from ..services.analytics.SmartLinkAnalyticsService import SmartLinkAnalyticsService
from ..permissions import IsPublisher, IsOwnerOrAdmin
from ..filters import SmartLinkFilter
from ..pagination import StandardResultsPagination

logger = logging.getLogger('smartlink.viewset')


class SmartLinkViewSet(viewsets.ModelViewSet):
    """
    CRUD viewset for SmartLinks.
    Publishers manage their own SmartLinks.
    Admins can manage all.
    """
    serializer_class = SmartLinkSerializer
    permission_classes = [IsAuthenticated, IsPublisher]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SmartLinkFilter
    search_fields = ['slug', 'name', 'description']
    ordering_fields = ['created_at', 'total_clicks', 'total_revenue', 'name']
    ordering = ['-created_at']
    pagination_class = StandardResultsPagination

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.smartlink_service = SmartLinkService()
        self.builder_service = SmartLinkBuilderService()
        self.analytics_service = SmartLinkAnalyticsService()

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return SmartLink.objects.all().select_related(
                'publisher', 'group'
            ).prefetch_related('tags')
        return SmartLink.objects.filter(
            publisher=user, is_archived=False
        ).select_related('group').prefetch_related('tags')

    def get_serializer_class(self):
        if self.action in ('retrieve', 'create', 'update', 'partial_update'):
            return SmartLinkDetailSerializer
        return SmartLinkSerializer

    def get_object(self):
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        smartlink = self.smartlink_service.create(
            publisher=self.request.user,
            data=serializer.validated_data,
        )
        serializer.instance = smartlink

    def perform_update(self, serializer):
        self.smartlink_service.update(
            smartlink=serializer.instance,
            data=serializer.validated_data,
            publisher=self.request.user,
        )

    def perform_destroy(self, instance):
        self.smartlink_service.archive(instance)

    # ── Custom actions ─────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        """
        POST /api/smartlink/smartlinks/generate/
        Quickly generate a SmartLink with auto slug + offer pool config.
        """
        data = request.data
        smartlink = self.builder_service.build(
            publisher=request.user,
            config=data,
        )
        serializer = SmartLinkDetailSerializer(smartlink)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='duplicate')
    def duplicate(self, request, pk=None):
        """POST /api/smartlink/smartlinks/{id}/duplicate/ — clone a SmartLink."""
        original = self.get_object()
        new_sl = self.smartlink_service.duplicate(original, publisher=request.user)
        return Response(SmartLinkDetailSerializer(new_sl).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='archive')
    def archive(self, request, pk=None):
        """POST /api/smartlink/smartlinks/{id}/archive/ — soft-delete."""
        smartlink = self.get_object()
        self.smartlink_service.archive(smartlink)
        return Response({'status': 'archived'})

    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        """POST /api/smartlink/smartlinks/{id}/restore/ — restore archived."""
        smartlink = self.get_object()
        self.smartlink_service.restore(smartlink)
        return Response({'status': 'restored'})

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        """POST /api/smartlink/smartlinks/{id}/toggle-active/ — enable/disable."""
        smartlink = self.get_object()
        smartlink.is_active = not smartlink.is_active
        smartlink.save(update_fields=['is_active', 'updated_at'])
        return Response({'is_active': smartlink.is_active})

    @action(detail=True, methods=['get'], url_path='stats')
    def stats(self, request, pk=None):
        """GET /api/smartlink/smartlinks/{id}/stats/?days=30 — quick stat summary."""
        smartlink = self.get_object()
        days = int(request.query_params.get('days', 30))
        summary = self.analytics_service.get_summary(smartlink, days=days)
        return Response(summary)

    @action(detail=True, methods=['get'], url_path='check-slug')
    def check_slug(self, request, pk=None):
        """GET /api/smartlink/smartlinks/check-slug/?slug=myslug — availability check."""
        from ..services.core.SlugGeneratorService import SlugGeneratorService
        slug = request.query_params.get('slug', '')
        svc = SlugGeneratorService()
        return Response({'slug': slug, 'available': svc.is_available(slug)})
