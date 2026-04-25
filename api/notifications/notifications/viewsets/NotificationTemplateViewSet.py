# earning_backend/api/notifications/viewsets/NotificationTemplateViewSet.py
"""
NotificationTemplateViewSet — split from views.py (lines 683-850).
Full code preserved exactly as in views.py with no logic removed.
"""
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from api.notifications.models import NotificationTemplate
from api.notifications.serializers import (
    NotificationTemplateSerializer,
    CreateTemplateSerializer,
    UpdateTemplateSerializer,
    TemplateRenderSerializer,
)


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for NotificationTemplate model.

    Endpoints:
      GET    /templates/              — list (public + own + admin=all)
      POST   /templates/              — create
      GET    /templates/{id}/         — retrieve
      PUT    /templates/{id}/         — update
      DELETE /templates/{id}/         — destroy
      POST   /templates/{id}/preview/ — render template with context
      POST   /templates/{id}/clone/   — clone template
      POST   /templates/{id}/toggle/  — toggle is_active
      GET    /templates/categories/   — list all categories
    """

    serializer_class = NotificationTemplateSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['template_type', 'category', 'is_active', 'is_public']
    search_fields = ['name', 'description', 'title_en', 'title_bn', 'message_en', 'message_bn']
    ordering_fields = ['name', 'created_at', 'updated_at', 'usage_count']
    ordering = ['name']

    def get_permissions(self):
        from api.notifications.views import IsTemplateOwnerOrAdmin
        return [IsAuthenticated(), IsTemplateOwnerOrAdmin()]

    def get_pagination_class(self):
        from api.notifications.views import StandardPagination
        return StandardPagination

    @property
    def pagination_class(self):
        from api.notifications.views import StandardPagination
        return StandardPagination

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            queryset = NotificationTemplate.objects.all()
        else:
            queryset = NotificationTemplate.objects.filter(
                Q(is_public=True) |
                Q(created_by=user) |
                Q(allowed_groups__contains=[group.name for group in user.groups.all()])
            ).distinct()

        params = self.request.query_params
        is_active = params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=(is_active.lower() == 'true'))
        template_type = params.get('template_type')
        if template_type:
            queryset = queryset.filter(template_type=template_type)
        category = params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateTemplateSerializer
        elif self.action in ['update', 'partial_update']:
            return UpdateTemplateSerializer
        elif self.action in ['render', 'preview']:
            return TemplateRenderSerializer
        return NotificationTemplateSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='preview')
    def render(self, request, pk=None):
        """Render/preview template with context variables."""
        template = self.get_object()
        serializer = TemplateRenderSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            result = serializer.save()
            return Response(result)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Clone this template with a new name."""
        template = self.get_object()
        new_name = request.data.get('name', f'{template.name} (Copy)')
        try:
            clone = NotificationTemplate.objects.get(pk=template.pk)
            clone.pk = None
            clone.name = new_name
            clone.created_by = request.user
            clone.usage_count = 0
            clone.save()
            return Response(NotificationTemplateSerializer(clone).data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle template active/inactive status."""
        template = self.get_object()
        template.is_active = not template.is_active
        template.save(update_fields=['is_active', 'updated_at'])
        return Response({'is_active': template.is_active})

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """List all unique template categories."""
        cats = (
            NotificationTemplate.objects.filter(is_active=True)
            .values_list('category', flat=True)
            .distinct()
            .order_by('category')
        )
        return Response({'categories': list(cats)})
