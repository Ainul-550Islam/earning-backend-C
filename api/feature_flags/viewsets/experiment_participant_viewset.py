"""
Experiment Participant viewset for Feature Flags & A/B Testing.
"""
from django.utils import timezone  # FIX: was missing — `convert` action raised NameError on every call
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from ..models.experiment_participant import ExperimentParticipant
from ..serializers.experiment_participant_serializer import (
    ExperimentParticipantSerializer, ExperimentParticipantListSerializer
)
from ..permissions import CanViewFlags, CanEditFlags


class ExperimentParticipantViewSet(viewsets.ModelViewSet):
    """
    Viewset for ExperimentParticipant model.
    """

    queryset = ExperimentParticipant.objects.all()
    serializer_class = ExperimentParticipantSerializer
    permission_classes = [IsAuthenticated, CanViewFlags]

    # NEW: pagination/filtering (previously NONE on any viewset)
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['experiment', 'variant', 'converted']
    ordering_fields = ['created_at', 'converted_at']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return ExperimentParticipantListSerializer
        return ExperimentParticipantSerializer

    def get_permissions(self):
        if self.request.method not in ['GET', 'HEAD', 'OPTIONS']:
            return [IsAuthenticated(), CanEditFlags()]
        return [IsAuthenticated(), CanViewFlags()]

    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        """
        Mark a participant as converted.

        FIX: `timezone` is now imported at module level (see top of file) —
        previously this action raised `NameError: name 'timezone' is not
        defined` on every single invocation.
        """
        participant = self.get_object()
        participant.converted = True
        participant.converted_at = timezone.now()
        participant.save()

        return Response({
            'success': True,
            'message': f'Participant {participant.user_id} marked as converted'
        })

    @action(detail=False, methods=['get'])
    def by_experiment(self, request):
        """
        Get participants by experiment.
        """
        experiment_id = request.query_params.get('experiment_id')

        if not experiment_id:
            return Response({
                'success': False,
                'error': 'experiment_id parameter is required'
            }, status=400)

        participants = self.queryset.filter(experiment_id=experiment_id)
        page = self.paginate_queryset(participants)
        serializer = self.get_serializer(page if page is not None else participants, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def converted(self, request):
        """
        Get all converted participants.
        """
        participants = self.queryset.filter(converted=True)
        page = self.paginate_queryset(participants)
        serializer = self.get_serializer(page if page is not None else participants, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)
