"""
Flag Analytics serializer for Feature Flags & A/B Testing.
"""
from rest_framework import serializers

from ..models.flag_analytics import FlagAnalytics
from .base_serializer import BaseSerializer


class FlagAnalyticsSerializer(BaseSerializer):
    """
    Serializer for FlagAnalytics model.
    """
    
    flag_name = serializers.CharField(source='flag.name', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    enable_rate = serializers.SerializerMethodField()
    conversion_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = FlagAnalytics
        fields = [
            'id', 'flag', 'flag_name', 'variant', 'variant_name',
            'date', 'hour', 'evaluation_count', 'enabled_count',
            'disabled_count', 'unique_users', 'conversion_count',
            'metrics', 'environment', 'enable_rate', 'conversion_rate',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_enable_rate(self, obj) -> float:
        """Get enable rate."""
        return obj.get_enable_rate()
    
    def get_conversion_rate(self, obj) -> float:
        """Get conversion rate."""
        return obj.get_conversion_rate()


class FlagAnalyticsListSerializer(BaseSerializer):
    """
    List serializer for FlagAnalytics model.
    """
    
    flag_name = serializers.CharField(source='flag.name', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    
    class Meta:
        model = FlagAnalytics
        fields = [
            'id', 'flag', 'flag_name', 'variant', 'variant_name',
            'date', 'hour', 'evaluation_count', 'enabled_count',
            'unique_users', 'environment', 'created_at'
        ]
        read_only_fields = ['created_at']
