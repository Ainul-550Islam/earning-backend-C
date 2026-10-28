"""viewsets/RateLimitConfigViewSet.py"""
import logging
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.apps import apps

logger = logging.getLogger(__name__)


class RateLimitConfigViewSet(viewsets.ModelViewSet):
    """Manage per-type rate limit configs."""
    permission_classes = [permissions.IsAdminUser]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['limit_type', 'display_name']
    ordering_fields    = ['limit', 'window_seconds']
    ordering           = ['limit_type']

    def get_queryset(self):
        RateLimitConfig = apps.get_model('tasks', 'RateLimitConfig')
        qs = RateLimitConfig.objects.all()
        if scope := self.request.query_params.get('scope'):
            qs = qs.filter(scope=scope)
        if active_only := self.request.query_params.get('active_only'):
            qs = qs.filter(is_active=True)
        return qs

    def get_serializer_class(self):
        from api.tasks.serializers import RateLimitConfigSerializer
        return RateLimitConfigSerializer

    @action(detail=True, methods=['post'], url_path='toggle')
    def toggle_active(self, request, pk=None):
        """Enable or disable this rate limit config."""
        obj = self.get_object()
        obj.is_active = not obj.is_active
        obj.save(update_fields=['is_active'])
        return Response({'is_active': obj.is_active})

    @action(detail=False, methods=['get'], url_path='defaults')
    def defaults(self, request):
        """Return all default rate limit configs."""
        RateLimitConfig = apps.get_model('tasks', 'RateLimitConfig')
        qs = RateLimitConfig.objects.filter(is_default=True, is_active=True)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
