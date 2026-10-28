# api/admin_panel/serializers/BulkActionSerializer.py
"""BulkAction request/response serializers."""
from rest_framework import serializers
from ..constants import BULK_ACTION_MAX_IDS


class BulkActionSerializer(serializers.Serializer):
    """Validates a bulk action request."""
    model = serializers.CharField(max_length=100)
    action = serializers.ChoiceField(choices=[
        'approve', 'reject', 'delete', 'ban', 'unban', 'verify',
        'activate', 'deactivate', 'send_notification', 'export',
    ])
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=BULK_ACTION_MAX_IDS,
    )
    params = serializers.DictField(required=False, default=dict)

    def validate_model(self, value):
        from django.apps import apps
        parts = value.split('.')
        if len(parts) != 2:
            raise serializers.ValidationError('model must be in format "app_label.ModelName".')
        try:
            apps.get_model(parts[0], parts[1])
        except LookupError:
            raise serializers.ValidationError(f'Model "{value}" not found.')
        return value

    def validate(self, data):
        action = data.get('action')
        # delete requires superadmin — checked in view, but add note in serializer
        if action == 'delete':
            # This note is surfaced to the API consumer
            data['_requires_superadmin'] = True
        return data


class BulkActionResultSerializer(serializers.Serializer):
    """Response shape for bulk action results."""
    success = serializers.BooleanField()
    action = serializers.CharField()
    model = serializers.CharField()
    result = serializers.DictField()
    error = serializers.CharField(required=False, allow_blank=True)