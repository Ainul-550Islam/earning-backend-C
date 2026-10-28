# api/admin_panel/serializers/AdminSessionSerializer.py
"""AdminSession serializer."""
from rest_framework import serializers
from ..models.activity import AdminSession


class AdminSessionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    force_logout_by_username = serializers.CharField(
        source='force_logout_by.username', read_only=True, default=''
    )
    duration_seconds = serializers.IntegerField(read_only=True)
    duration_human = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AdminSession
        fields = [
            'id', 'user', 'username', 'email',
            'session_key', 'ip', 'user_agent', 'location',
            'started_at', 'last_seen', 'ended_at',
            'is_active', 'status', 'status_display',
            'force_logout_by', 'force_logout_by_username', 'force_logout_reason',
            'duration_seconds', 'duration_human',
        ]
        read_only_fields = '__all__'

    def get_duration_human(self, obj) -> str:
        seconds = obj.duration_seconds
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        elif seconds < 86400:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            return f"{h}h {m}m"
        else:
            d = seconds // 86400
            h = (seconds % 86400) // 3600
            return f"{d}d {h}h"