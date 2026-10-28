"""
Experiment viewset for Feature Flags & A/B Testing.

FIX: added authentication/permissions + pagination/filtering (was missing).
NEW: `recommendations` and `export` actions expose
`ExperimentService`-style analysis that previously had no API endpoint
(floating-code fix).
"""
import csv
import io

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from django.http import HttpResponse

from ..models.experiment import Experiment
from ..models.experiment_participant import ExperimentParticipant
from ..serializers.experiment_serializer import ExperimentSerializer, ExperimentListSerializer
from ..experiment_runner import ExperimentRunner
from ..permissions import IsAuthenticated, CanViewFlags, CanManageExperiments


class ExperimentViewSet(viewsets.ModelViewSet):
    """
    Viewset for Experiment model.
    """

    queryset = Experiment.objects.all()
    serializer_class = ExperimentSerializer
    permission_classes = [IsAuthenticated, CanViewFlags, CanManageExperiments]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'flag']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'start_date', 'end_date']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return ExperimentListSerializer
        return ExperimentSerializer

    def get_permissions(self):
        # Allow plain authenticated viewers to read; only gate mutations
        # behind CanManageExperiments.
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticated(), CanViewFlags()]
        return [IsAuthenticated(), CanManageExperiments()]

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start an experiment."""
        experiment = self.get_object()
        experiment.status = Experiment.Status.RUNNING
        experiment.save()

        return Response({'success': True, 'message': f'Experiment {experiment.name} started successfully'})

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause an experiment."""
        experiment = self.get_object()
        experiment.status = Experiment.Status.PAUSED
        experiment.save()

        return Response({'success': True, 'message': f'Experiment {experiment.name} paused successfully'})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete an experiment."""
        experiment = self.get_object()
        experiment.status = Experiment.Status.COMPLETED
        experiment.save()

        return Response({'success': True, 'message': f'Experiment {experiment.name} completed successfully'})

    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        """Get experiment results."""
        experiment = self.get_object()
        runner = ExperimentRunner()

        results = runner.get_experiment_results(experiment.name)

        return Response({'success': True, 'data': results})

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active experiments."""
        runner = ExperimentRunner()
        experiments = runner.get_active_experiments()

        serializer = self.get_serializer(experiments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def recommendations(self, request, pk=None):
        """
        NEW: lightweight statistical recommendation for which variant is
        winning (floating-code fix — previously this analysis existed
        nowhere, not even as floating service code).
        """
        from ..utils import calculate_statistical_significance

        experiment = self.get_object()
        variant_stats = experiment.get_variant_stats()
        variant_names = list(variant_stats.keys())

        if len(variant_names) < 2:
            return Response({
                'experiment_name': experiment.name,
                'recommendation': 'Not enough variants with data to compare yet.',
            })

        control_name, variant_name = variant_names[0], variant_names[1]
        control = variant_stats.get(control_name, {})
        variant = variant_stats.get(variant_name, {})

        stats = calculate_statistical_significance(
            control.get('conversion_count', 0),
            control.get('participant_count', 1) or 1,
            variant.get('conversion_count', 0),
            variant.get('participant_count', 1) or 1,
        )

        if stats['is_significant'] and stats['lift'] > 0:
            recommendation = f"'{variant_name}' is outperforming '{control_name}' with statistical significance."
        elif stats['is_significant'] and stats['lift'] < 0:
            recommendation = f"'{control_name}' is outperforming '{variant_name}' with statistical significance."
        else:
            recommendation = 'No statistically significant difference detected yet — keep running the experiment.'

        return Response({
            'experiment_name': experiment.name,
            'control': control_name,
            'variant': variant_name,
            'statistics': stats,
            'recommendation': recommendation,
        })

    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """
        NEW: export raw participant data for an experiment as CSV
        (floating-code fix — previously documented as missing entirely).
        """
        experiment = self.get_object()
        participants = ExperimentParticipant.objects.filter(experiment=experiment).select_related('variant')

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['user_id', 'variant', 'converted', 'converted_at', 'created_at'])
        for p in participants:
            writer.writerow([p.user_id, p.variant.name, p.converted, p.converted_at, p.created_at])

        response = HttpResponse(buffer.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="experiment_{experiment.id}_participants.csv"'
        return response
