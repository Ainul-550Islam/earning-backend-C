"""
Dashboard Widget serializer. DRY: inherits BaseSerializer.
"""
from rest_framework import serializers

from ..models.dashboard_widget import DashboardWidget
from ..choices import WidgetTypeChoices, DataSourceChoices
from .base_serializer import BaseSerializer


class DashboardWidgetSerializer(BaseSerializer):
    class Meta:
        model  = DashboardWidget
        fields = [
            'id', 'name', 'widget_type', 'data_source',
            'query', 'config', 'position_x', 'position_y',
            'width', 'height', 'refresh_interval', 'is_active',
            'dashboard', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_widget_type(self, value):
        if value not in WidgetTypeChoices.values:
            raise serializers.ValidationError(
                f"Invalid widget_type. Must be one of: {WidgetTypeChoices.values}."
            )
        return value

    def validate_data_source(self, value):
        if value not in DataSourceChoices.values:
            raise serializers.ValidationError(
                f"Invalid data_source. Must be one of: {DataSourceChoices.values}."
            )
        return value

    def validate_width(self, value):
        if not (1 <= value <= 12):
            raise serializers.ValidationError("Width must be between 1 and 12.")
        return value

    def validate_height(self, value):
        if not (1 <= value <= 12):
            raise serializers.ValidationError("Height must be between 1 and 12.")
        return value

    def validate_refresh_interval(self, value):
        if value < 0:
            raise serializers.ValidationError("refresh_interval cannot be negative.")
        return value

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Widget name cannot be empty.")
        return value


class DashboardWidgetCreateSerializer(BaseSerializer):
    class Meta:
        model  = DashboardWidget
        fields = [
            'name', 'widget_type', 'data_source',
            'query', 'config', 'position_x', 'position_y',
            'width', 'height', 'refresh_interval', 'is_active', 'dashboard',
        ]

    def validate_width(self, value):
        if not (1 <= value <= 12):
            raise serializers.ValidationError("Width must be between 1 and 12.")
        return value

    def validate_height(self, value):
        if not (1 <= value <= 12):
            raise serializers.ValidationError("Height must be between 1 and 12.")
        return value

    def validate_refresh_interval(self, value):
        if value < 0:
            raise serializers.ValidationError("refresh_interval cannot be negative.")
        return value


class DashboardWidgetUpdateSerializer(BaseSerializer):
    """Partial update — all fields optional."""
    class Meta:
        model  = DashboardWidget
        fields = [
            'name', 'widget_type', 'data_source',
            'query', 'config', 'position_x', 'position_y',
            'width', 'height', 'refresh_interval', 'is_active', 'dashboard',
        ]
        extra_kwargs = {f: {'required': False} for f in fields}
