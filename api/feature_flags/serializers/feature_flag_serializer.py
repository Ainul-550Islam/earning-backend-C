"""
Feature Flag serializer for Feature Flags & A/B Testing.
"""
from rest_framework import serializers

from ..models.feature_flag import FeatureFlag
from ..utils.validators import FlagValidator
from .base_serializer import BaseSerializer


class FeatureFlagSerializer(BaseSerializer):
    """
    Serializer for FeatureFlag model.

    FIX: added real field validation (name format, rollout range,
    duplicate name-per-environment) — previously NONE of the serializers
    validated anything beyond Django's default field-type checks, so a
    flag with rollout_percentage=150 or a name containing spaces could be
    created via the API.
    """

    class Meta:
        model = FeatureFlag
        fields = [
            'id', 'name', 'description', 'flag_type', 'status',
            'default_value', 'rollout_percentage', 'targeting_rules',
            'metadata', 'tags', 'owner', 'team', 'environment',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_name(self, value):
        if not FlagValidator.validate_name(value):
            raise serializers.ValidationError(
                'Flag name must be 1-255 characters and contain only '
                'letters, numbers, hyphens, underscores, or colons.'
            )
        return value

    def validate_rollout_percentage(self, value):
        if not FlagValidator.validate_rollout_percentage(value):
            raise serializers.ValidationError('Rollout percentage must be an integer between 0 and 100.')
        return value

    def validate(self, data):
        name = data.get('name', getattr(self.instance, 'name', None))
        environment = data.get('environment', getattr(self.instance, 'environment', 'production'))

        queryset = FeatureFlag.objects.filter(name=name, environment=environment)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError({
                'name': f"A flag named '{name}' already exists in the '{environment}' environment."
            })

        return data


class FeatureFlagListSerializer(BaseSerializer):
    """
    List serializer for FeatureFlag model.
    """

    class Meta:
        model = FeatureFlag
        fields = [
            'id', 'name', 'description', 'flag_type', 'status',
            'rollout_percentage', 'environment', 'created_at'
        ]
        read_only_fields = ['created_at']
