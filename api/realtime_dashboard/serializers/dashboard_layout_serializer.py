"""
Dashboard Layout serializer for Real-time Dashboard Backend.

WIRED (v1.3.0): DashboardLayoutSerializer previously had ZERO validation.
Any values — invalid names, negative columns, oversized rows — were
accepted silently and stored in the database, breaking every dashboard
that referenced the corrupt layout.

Added:
  - validate_name_no_special_chars on name (was floating in validators.py)
  - validate_json_metadata on metadata
  - validate_tags_list on tags
  - validate() cross-field: columns must be 1–24, rows must be 1–100
"""
from rest_framework import serializers

from ..models.dashboard_layout import DashboardLayout
from ..validators import (
    validate_json_metadata,
    validate_tags_list,
    validate_name_no_special_chars,
)
from .base_serializer import BaseSerializer

# Grid bounds — kept here (not in validators.py) because they are
# layout-domain constants, not general-purpose validators.
LAYOUT_MAX_COLUMNS = 24
LAYOUT_MAX_ROWS = 100


class DashboardLayoutSerializer(BaseSerializer):
    """Full serializer for DashboardLayout — create / retrieve / update."""

    name = serializers.CharField(
        max_length=255,
        validators=[validate_name_no_special_chars],
        help_text="Layout name. Only letters, numbers, spaces, hyphens and underscores.",
    )
    metadata = serializers.JSONField(
        default=dict,
        validators=[validate_json_metadata],
    )
    tags = serializers.JSONField(
        default=list,  # type: ignore[arg-type]  # DRF stub types default as Mapping-only; list is valid
        validators=[validate_tags_list],
    )

    class Meta:
        model = DashboardLayout
        fields = [
            'id', 'name', 'description', 'layout_type', 'columns', 'rows',
            'configuration', 'metadata', 'tags', 'created_by',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        """Cross-field: columns and rows must be within safe grid bounds."""
        columns = attrs.get('columns')
        rows = attrs.get('rows')

        if columns is not None:
            if columns < 1:
                raise serializers.ValidationError(
                    {'columns': 'columns must be at least 1.'}
                )
            if columns > LAYOUT_MAX_COLUMNS:
                raise serializers.ValidationError(
                    {'columns': f'columns must not exceed {LAYOUT_MAX_COLUMNS}.'}
                )

        if rows is not None:
            if rows < 1:
                raise serializers.ValidationError(
                    {'rows': 'rows must be at least 1.'}
                )
            if rows > LAYOUT_MAX_ROWS:
                raise serializers.ValidationError(
                    {'rows': f'rows must not exceed {LAYOUT_MAX_ROWS}.'}
                )

        return attrs


class DashboardLayoutListSerializer(BaseSerializer):
    """Compact serializer for list endpoints."""

    class Meta:
        model = DashboardLayout
        fields = ['id', 'name', 'layout_type', 'columns', 'rows', 'created_at']
        read_only_fields = ['created_at']
