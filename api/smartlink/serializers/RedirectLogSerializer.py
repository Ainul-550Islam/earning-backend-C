from rest_framework import serializers
from ..models import RedirectLog


class RedirectLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = RedirectLog
        fields = [
            'id', 'smartlink', 'offer', 'ip', 'country', 'device_type',
            'redirect_type', 'destination_url', 'status_code',
            'response_time_ms', 'was_cached', 'was_fallback', 'created_at',
        ]
        read_only_fields = fields
