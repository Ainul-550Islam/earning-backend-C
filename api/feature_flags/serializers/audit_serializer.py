"""
NEW FILE — Serializer for the AuditLog model.
"""
from rest_framework import serializers

from ..models.audit import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for AuditLog. Entirely read-only by design."""

    user_display = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_display', 'flag', 'flag_name_snapshot',
            'action', 'old_values', 'new_values', 'timestamp', 'ip_address',
        ]
        read_only_fields = fields

    def get_user_display(self, obj) -> str | None:
        return getattr(obj.user, 'username', None) if obj.user else None
