"""
Widget Configuration serializer for Real-time Dashboard Backend.

WIRED (v1.2.0): utils.validate_widget_configuration() was defined but
NEVER called from anywhere. The obvious single place to enforce it is
validate_value() in this serializer — every WidgetConfiguration write
goes through here.

Validation logic (from utils.validate_widget_configuration):
  - configuration must be a dict (not a list, string, etc.)
  - if configuration['type'] == 'chart', requires 'data' and 'chartType' keys

Previously, a client could POST {"type": "chart"} without data or
chartType and the record would be created silently. This serializer now
returns a 400 with a descriptive error in that case.
"""
from rest_framework import serializers

from ..models.widget_configuration import WidgetConfiguration
from ..utils import validate_widget_configuration
from .base_serializer import BaseSerializer


class WidgetConfigurationSerializer(BaseSerializer):
    """Full serializer for WidgetConfiguration — create / retrieve / update."""

    widget_name = serializers.CharField(source='widget.name', read_only=True)

    class Meta:
        model = WidgetConfiguration
        fields = [
            'id', 'widget', 'widget_name', 'config_type', 'key', 'value',
            'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_value(self, value):
        """
        WIRED (v1.2.0): run the floating utils.validate_widget_configuration()
        check on the configuration value before saving.

        WidgetConfiguration.value is a JSONField that stores the configuration
        dict for this configuration entry (e.g. chart type settings, threshold
        bounds, colour schemes). validate_widget_configuration() enforces that
        chart-type configurations have the required 'data' and 'chartType' keys.

        Returns the value unchanged if valid; raises ValidationError otherwise.
        """
        if isinstance(value, dict) and not validate_widget_configuration(value):
            raise serializers.ValidationError(
                "Invalid configuration: chart-type configurations must include "
                "'data' and 'chartType' keys."
            )
        return value


class WidgetConfigurationListSerializer(BaseSerializer):
    """Compact serializer for list endpoints."""

    widget_name = serializers.CharField(source='widget.name', read_only=True)

    class Meta:
        model = WidgetConfiguration
        fields = ['id', 'widget', 'widget_name', 'config_type', 'key', 'created_at']
        read_only_fields = ['created_at']
