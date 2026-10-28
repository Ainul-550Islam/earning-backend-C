"""viewsets/DisputeEscalationViewSet.py"""
import logging
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.apps import apps

logger = logging.getLogger(__name__)


class DisputeEscalationViewSet(viewsets.ModelViewSet):
    """CRUD + escalation actions for DisputeEscalation records."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['escalated_reason', 'review_notes']
    ordering_fields    = ['escalated_at', 'escalation_level']
    ordering           = ['-escalated_at']

    def get_queryset(self):
        DisputeEscalation = apps.get_model('tasks', 'DisputeEscalation')
        return DisputeEscalation.objects.select_related('dispute', 'reviewed_by').all()

    def get_serializer_class(self):
        from api.tasks.serializers import DisputeEscalationSerializer
        return DisputeEscalationSerializer

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request, pk=None):
        """Mark escalation as resolved with a resolution action."""
        obj = self.get_object()
        action_code = request.data.get('resolution_action', 'no_action')
        obj.resolution_action = action_code
        obj.reviewed_by       = request.user
        obj.review_notes      = request.data.get('notes', '')
        obj.save(update_fields=['resolution_action', 'reviewed_by', 'review_notes'])
        return Response({'status': 'resolved', 'resolution_action': action_code})
