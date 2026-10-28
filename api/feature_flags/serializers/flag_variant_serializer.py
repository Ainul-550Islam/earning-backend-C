"""
Flag Variant serializer for Feature Flags & A/B Testing.
"""
from rest_framework import serializers

from ..models.flag_variant import FlagVariant
from .base_serializer import BaseSerializer


class FlagVariantSerializer(BaseSerializer):
    """
    Serializer for FlagVariant model.

    FIX: added weight range validation (0-100) and duplicate
    variant-name-per-flag validation, neither of which existed before.
    """

    flag_name = serializers.CharField(source='flag.name', read_only=True)

    class Meta:
        model = FlagVariant
        fields = [
            'id', 'flag', 'flag_name', 'name', 'description',
            'value', 'weight', 'is_control', 'is_active',
            'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_weight(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError('Weight must be between 0 and 100.')
        return value

    def validate(self, data):
        flag = data.get('flag', getattr(self.instance, 'flag', None))
        name = data.get('name', getattr(self.instance, 'name', None))

        if flag and name:
            queryset = FlagVariant.objects.filter(flag=flag, name=name)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({
                    'name': f"A variant named '{name}' already exists for this flag."
                })
        return data


class FlagVariantListSerializer(BaseSerializer):
    """
    List serializer for FlagVariant model.
    """

    flag_name = serializers.CharField(source='flag.name', read_only=True)

    class Meta:
        model = FlagVariant
        fields = [
            'id', 'flag', 'flag_name', 'name', 'weight',
            'is_control', 'is_active', 'created_at'
        ]
        read_only_fields = ['created_at']
