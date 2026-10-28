# api/admin_panel/serializers/AdminActivitySerializer.py
"""AdminActivity serializer."""
from rest_framework import serializers
from ..models.activity import AdminActivity, AdminNote, AdminBookmark, AdminSearch


class AdminActivitySerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True, default='')
    actor_email = serializers.CharField(source='actor.email', read_only=True, default='')
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = AdminActivity
        fields = [
            'id', 'actor', 'actor_username', 'actor_email',
            'action', 'model_name', 'object_id', 'object_repr',
            'changes', 'ip', 'user_agent', 'path', 'method',
            'response_code', 'status', 'status_display',
            'extra', 'created_at',
        ]
        read_only_fields = '__all__'

    def get_status_display(self, obj) -> str:
        icons = {'success': '✅', 'failed': '❌', 'partial': '⚠️'}
        return f"{icons.get(obj.status, '')} {obj.status}"


class AdminNoteSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = AdminNote
        fields = [
            'id', 'content_type', 'object_id', 'note',
            'created_by', 'created_by_username',
            'is_pinned', 'is_private', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class AdminBookmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminBookmark
        fields = [
            'id', 'user', 'url', 'title', 'icon', 'description',
            'sort_order', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class AdminSearchSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True, default='')

    class Meta:
        model = AdminSearch
        fields = [
            'id', 'query', 'model', 'result_count',
            'user', 'user_username', 'ip', 'created_at',
        ]
        read_only_fields = '__all__'