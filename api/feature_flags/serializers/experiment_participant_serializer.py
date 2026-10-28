"""
Experiment Participant serializer for Feature Flags & A/B Testing.
"""
from rest_framework import serializers

from ..models.experiment_participant import ExperimentParticipant
from .base_serializer import BaseSerializer


class ExperimentParticipantSerializer(BaseSerializer):
    """
    Serializer for ExperimentParticipant model.
    """
    
    experiment_name = serializers.CharField(source='experiment.name', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    
    class Meta:
        model = ExperimentParticipant
        fields = [
            'id', 'experiment', 'experiment_name', 'variant', 'variant_name',
            'user_id', 'session_id', 'converted', 'converted_at',
            'context', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ExperimentParticipantListSerializer(BaseSerializer):
    """
    List serializer for ExperimentParticipant model.
    """
    
    experiment_name = serializers.CharField(source='experiment.name', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    
    class Meta:
        model = ExperimentParticipant
        fields = [
            'id', 'experiment', 'experiment_name', 'variant', 'variant_name',
            'user_id', 'converted', 'converted_at', 'created_at'
        ]
        read_only_fields = ['created_at']
