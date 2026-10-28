"""
User Dashboard serializer for Real-time Dashboard Backend.

WIRED (v1.1.0): utils.sanitize_dashboard_name was defined in utils.py but
never called anywhere. It is now applied in validate_name() so dashboard
names are stripped, normalised, and validated consistently at the serializer
layer — before the data reaches the model's clean() method.

Sanitisation rules (from utils.sanitize_dashboard_name):
  - Strip leading/trailing whitespace
  - Collapse internal whitespace runs to a single space
  - Remove characters that are not alphanumeric, space, hyphen, or underscore
  - Require the result to be non-empty after sanitisation
"""
from rest_framework import serializers

from ..models.user_dashboard import UserDashboard
from ..utils import sanitize_dashboard_name
from ..validators import validate_json_metadata, validate_tags_list
from .base_serializer import BaseSerializer


class UserDashboardSerializer(BaseSerializer):
    """
    Full serializer for UserDashboard — used on create / retrieve / update.

    user_id is read-only: it is always set by the viewset's perform_create()
    from request.user.pk. Client-supplied values are silently ignored at both
    the serializer (read_only=True) and the viewset layer, so there is no
    single point of failure for the ownership invariant.
    """

    layout_name = serializers.CharField(source='layout.name', read_only=True)
    user_id = serializers.CharField(read_only=True)

    metadata = serializers.JSONField(
        default=dict,
        validators=[validate_json_metadata],
    )
    tags = serializers.JSONField(
        default=list,  # type: ignore[arg-type]  # DRF stub types default as Mapping-only; list is valid
        validators=[validate_tags_list],
    )

    class Meta:
        model = UserDashboard
        fields = [
            'id', 'name', 'description', 'status', 'layout', 'layout_name',
            'widgets', 'user_id', 'metadata', 'tags', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'user_id']

    def validate_name(self, value: str) -> str:
        """
        Sanitise and validate the dashboard name.

        WIRED (v1.1.0): utils.sanitize_dashboard_name was defined but never
        called. Applying it here ensures:
          - Names are stripped and normalised before storage.
          - Invalid characters (e.g. SQL injection attempts, unicode control
            chars) are removed at the boundary, not inside the model.
          - The validation error is surfaced to the API client as a 400 with
            a field-specific message, not as a cryptic DB constraint violation.
        """
        sanitised = sanitize_dashboard_name(value)
        if not sanitised:
            raise serializers.ValidationError(
                "Dashboard name contains only invalid characters. "
                "Use alphanumeric characters, spaces, hyphens, or underscores."
            )
        return sanitised


class UserDashboardListSerializer(BaseSerializer):
    """Compact serializer for list endpoints."""

    class Meta:
        model = UserDashboard
        fields = [
            'id', 'name', 'status', 'user_id', 'created_at',
        ]
        read_only_fields = ['created_at', 'user_id']
