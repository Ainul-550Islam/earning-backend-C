# api/admin_panel/serializers/AdminProfileSerializer.py
"""AdminProfile serializer — extended admin user profile."""
from rest_framework import serializers
from django.conf import settings
from ..models.core import AdminProfile


class AdminProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    is_superadmin = serializers.BooleanField(read_only=True)
    can_manage_settings = serializers.BooleanField(read_only=True)
    can_manage_users = serializers.BooleanField(read_only=True)
    can_view_reports = serializers.BooleanField(read_only=True)
    can_approve_payments = serializers.BooleanField(read_only=True)

    class Meta:
        model = AdminProfile
        fields = [
            'id', 'user', 'username', 'email', 'full_name', 'display_name',
            'role', 'avatar', 'phone', 'bio', 'department',
            'timezone', 'theme', 'language',
            'receive_digest', 'receive_alerts', 'two_factor_enabled',
            'last_seen', 'created_at', 'updated_at',
            'is_superadmin', 'can_manage_settings', 'can_manage_users',
            'can_view_reports', 'can_approve_payments',
        ]
        read_only_fields = [
            'id', 'user', 'username', 'email', 'last_seen', 'created_at', 'updated_at',
            'is_superadmin', 'can_manage_settings', 'can_manage_users',
            'can_view_reports', 'can_approve_payments',
        ]

    def get_full_name(self, obj) -> str:
        return obj.user.get_full_name()

    def get_display_name(self, obj) -> str:
        return obj.get_display_name()

    def validate_avatar(self, value):
        if value:
            max_size = 2 * 1024 * 1024  # 2MB
            if value.size > max_size:
                raise serializers.ValidationError('Avatar must be less than 2MB.')
        return value


class AdminProfileUpdateSerializer(serializers.ModelSerializer):
    """Restricted update serializer — cannot change role via this."""
    class Meta:
        model = AdminProfile
        fields = [
            'avatar', 'phone', 'bio', 'department',
            'timezone', 'theme', 'language',
            'receive_digest', 'receive_alerts',
        ]