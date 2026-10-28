"""
Dashboard Widget serializer for Real-time Dashboard Backend.

WIRED (v1.3.0):
  - validate_positive_integer wired to refresh_interval field.
    Previously defined in validators.py but never applied to any field.
    refresh_interval=-1 caused a nonsensical "refresh every -1 seconds"
    cycle in the Celery broadcast task. The model-level clean() caught it
    on full_clean() but the REST API path never called full_clean(), so
    invalid values entered the DB silently.

  - validate_name_no_special_chars wired to name field.
    Previously defined in validators.py but never applied to any name field.
    Widget names are reflected into WebSocket broadcast payloads and displayed
    in the admin; a name like '<script>alert(1)</script>' entered unvalidated
    and was later echoed to every dashboard subscriber.
"""
from rest_framework import serializers

from ..models.dashboard_widget import DashboardWidget
from ..validators import (
    validate_json_metadata,
    validate_tags_list,
    validate_widget_configuration,
    validate_widget_dimensions,
    validate_positive_integer,
    validate_name_no_special_chars,
)
from .base_serializer import BaseSerializer


class DashboardWidgetSerializer(BaseSerializer):
    """Full serializer for DashboardWidget — create / retrieve / update."""

    name = serializers.CharField(
        max_length=255,
        validators=[validate_name_no_special_chars],
        help_text=(
            "Widget display name. Only letters, numbers, spaces, hyphens and "
            "underscores are allowed (name is reflected into WebSocket payloads)."
        ),
    )
    refresh_interval = serializers.IntegerField(
        default=60,
        validators=[validate_positive_integer],
        help_text=(
            "How often (seconds) the widget polls for new data. "
            "Must be > 0. Typical values: 30 (near-real-time), 300 (dashboard)."
        ),
    )
    metadata = serializers.JSONField(
        default=dict,
        validators=[validate_json_metadata],
    )
    tags = serializers.JSONField(
        default=list,  # type: ignore[arg-type]  # DRF stub types default as Mapping-only; list is valid
        validators=[validate_tags_list],
    )
    configuration = serializers.JSONField(
        default=dict,
        validators=[validate_widget_configuration],
    )

    class Meta:
        model = DashboardWidget
        fields = [
            'id', 'name', 'description', 'widget_type', 'status', 'configuration',
            'data_source', 'refresh_interval', 'width', 'height', 'metadata', 'tags',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        """Cross-field: width and height must be within grid bounds (1–12 × 1–24)."""
        validate_widget_dimensions(
            attrs.get('width'),
            attrs.get('height'),
        )
        return attrs


class DashboardWidgetListSerializer(BaseSerializer):
    """Compact serializer for list endpoints."""

    class Meta:
        model = DashboardWidget
        fields = [
            'id', 'name', 'widget_type', 'status', 'refresh_interval',
            'width', 'height', 'created_at',
        ]
        read_only_fields = ['created_at']
