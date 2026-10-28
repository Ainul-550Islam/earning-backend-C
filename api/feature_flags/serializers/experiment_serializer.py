"""
Experiment serializer for Feature Flags & A/B Testing.
"""
from rest_framework import serializers

from ..models.experiment import Experiment
from .base_serializer import BaseSerializer


class ExperimentSerializer(BaseSerializer):
    """
    Serializer for Experiment model.

    FIX: added start/end date ordering validation and sample-size
    positivity check — previously an experiment could be created with
    end_date before start_date or a negative min_sample_size.
    """

    flag_name = serializers.CharField(source='flag.name', read_only=True)
    participant_count = serializers.SerializerMethodField()

    class Meta:
        model = Experiment
        fields = [
            'id', 'name', 'description', 'flag', 'flag_name', 'status',
            'start_date', 'end_date', 'target_audience', 'success_metrics',
            'min_sample_size', 'significance_threshold', 'metadata',
            'owner', 'team', 'participant_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_participant_count(self, obj) -> int:
        """Get participant count."""
        return obj.get_participant_count()

    def validate_min_sample_size(self, value):
        if value <= 0:
            raise serializers.ValidationError('Minimum sample size must be a positive integer.')
        return value

    def validate(self, data):
        start_date = data.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = data.get('end_date', getattr(self.instance, 'end_date', None))

        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError({'end_date': 'End date must be after start date.'})

        return data


class ExperimentListSerializer(BaseSerializer):
    """
    List serializer for Experiment model.
    """

    flag_name = serializers.CharField(source='flag.name', read_only=True)

    class Meta:
        model = Experiment
        fields = [
            'id', 'name', 'description', 'flag', 'flag_name', 'status',
            'start_date', 'end_date', 'owner', 'created_at'
        ]
        read_only_fields = ['created_at']
