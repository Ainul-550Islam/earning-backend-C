# api/admin_panel/serializers/SystemConfigSerializer.py
"""SystemConfig serializer."""
from rest_framework import serializers
from ..models.config import SystemConfig, APIRateConfig, EmailTemplate


class SystemConfigSerializer(serializers.ModelSerializer):
    typed_value = serializers.SerializerMethodField()
    updated_by_username = serializers.CharField(source='updated_by.username', read_only=True, default='')
    group_display = serializers.CharField(source='get_group_display', read_only=True)
    value_type_display = serializers.CharField(source='get_value_type_display', read_only=True)

    class Meta:
        model = SystemConfig
        fields = [
            'id', 'key', 'value', 'typed_value', 'value_type', 'value_type_display',
            'group', 'group_display', 'label', 'description',
            'is_public', 'is_encrypted', 'is_readonly',
            'validation_regex', 'updated_by', 'updated_by_username',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'updated_by', 'created_at', 'updated_at', 'typed_value']

    def get_typed_value(self, obj):
        if obj.is_encrypted:
            return '***'
        return obj.get_typed_value()

    def validate_key(self, value):
        import re
        if not re.match(r'^[a-z][a-z0-9_]*$', value):
            raise serializers.ValidationError(
                'Key must be lowercase, start with a letter, and contain only letters, digits, underscores.'
            )
        return value

    def validate(self, data):
        is_readonly = data.get('is_readonly', getattr(self.instance, 'is_readonly', False))
        if self.instance and self.instance.is_readonly and self.context['request'].method in ['PUT', 'PATCH']:
            raise serializers.ValidationError('This config key is read-only and cannot be modified.')
        return data


class APIRateConfigSerializer(serializers.ModelSerializer):
    rate_per_minute = serializers.FloatField(read_only=True)

    class Meta:
        model = APIRateConfig
        fields = [
            'id', 'endpoint_pattern', 'method', 'limit',
            'window_seconds', 'rate_per_minute',
            'is_active', 'applies_to_admins', 'description',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'rate_per_minute', 'created_at', 'updated_at']


class EmailTemplateSerializer(serializers.ModelSerializer):
    updated_by_username = serializers.CharField(source='updated_by.username', read_only=True, default='')

    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'key', 'name', 'subject', 'body_html', 'body_text',
            'variables', 'is_active', 'from_name', 'from_email', 'reply_to',
            'updated_by', 'updated_by_username', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'updated_by', 'created_at', 'updated_at']

    def validate_key(self, value):
        import re
        if not re.match(r'^[a-z][a-z0-9_]*$', value):
            raise serializers.ValidationError('Template key must be snake_case.')
        return value