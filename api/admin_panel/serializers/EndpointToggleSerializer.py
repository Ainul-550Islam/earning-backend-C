# api/admin_panel/serializers/EndpointToggleSerializer.py
"""EndpointToggle serializer."""
from rest_framework import serializers
from ..endpoint_toggle import EndpointToggle


class EndpointToggleSerializer(serializers.ModelSerializer):
    status_label = serializers.SerializerMethodField()

    class Meta:
        model = EndpointToggle
        fields = [
            'id', 'path', 'method', 'group', 'label',
            'is_enabled', 'disabled_message', 'updated_at', 'status_label',
        ]
        read_only_fields = ['id', 'updated_at']

    def get_status_label(self, obj) -> str:
        return '✅ Enabled' if obj.is_enabled else '❌ Disabled'