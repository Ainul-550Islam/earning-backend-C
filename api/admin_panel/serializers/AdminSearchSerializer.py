# api/admin_panel/serializers/AdminSearchSerializer.py
"""AdminSearch serializer."""
from rest_framework import serializers
from ..models.activity import AdminSearch


class AdminSearchSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True, default='')

    class Meta:
        model = AdminSearch
        fields = [
            'id', 'query', 'model', 'result_count',
            'user', 'user_username', 'ip', 'created_at',
        ]
        read_only_fields = '__all__'


class GlobalSearchRequestSerializer(serializers.Serializer):
    """Validates global search request parameters."""
    q = serializers.CharField(min_length=2, max_length=200)
    model = serializers.CharField(required=False, default='', allow_blank=True)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=20)