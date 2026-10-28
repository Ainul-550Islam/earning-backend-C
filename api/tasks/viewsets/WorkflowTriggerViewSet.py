"""viewsets/WorkflowTriggerViewSet.py"""
import logging
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.apps import apps
from django.utils import timezone

logger = logging.getLogger(__name__)


class WorkflowTriggerViewSet(viewsets.ModelViewSet):
    """Manage triggers that fire workflows automatically."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['description', 'trigger_type']
    ordering_fields    = ['created_at', 'trigger_count']
    ordering           = ['-created_at']

    def get_queryset(self):
        WorkflowTrigger = apps.get_model('tasks', 'WorkflowTrigger')
        qs = WorkflowTrigger.objects.select_related('workflow').all()
        if workflow_id := self.request.query_params.get('workflow_id'):
            qs = qs.filter(workflow_id=workflow_id)
        if active_only := self.request.query_params.get('active_only'):
            qs = qs.filter(is_active=True)
        return qs

    def get_serializer_class(self):
        from api.tasks.serializers import WorkflowTriggerSerializer
        return WorkflowTriggerSerializer

    @action(detail=True, methods=['post'], url_path='fire')
    def fire(self, request, pk=None):
        """Manually fire a trigger (for testing)."""
        trigger = self.get_object()
        if not trigger.is_active:
            return Response({'error': 'Trigger is not active'}, status=400)
        trigger.last_triggered_at = timezone.now()
        trigger.trigger_count += 1
        trigger.save(update_fields=['last_triggered_at', 'trigger_count'])
        logger.info(f'Trigger {trigger.id} manually fired by {request.user}')
        return Response({'fired': True, 'trigger_count': trigger.trigger_count})

    @action(detail=True, methods=['post'], url_path='toggle')
    def toggle(self, request, pk=None):
        trigger = self.get_object()
        trigger.is_active = not trigger.is_active
        trigger.save(update_fields=['is_active'])
        return Response({'is_active': trigger.is_active})
