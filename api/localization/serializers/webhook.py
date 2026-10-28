# serializers/webhook.py
from rest_framework import serializers


class WebhookRegistrationSerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()

    def get_created_by_email(self, obj):
        return getattr(obj.created_by, 'email', None) if obj.created_by else None

    def get_success_rate(self, obj):
        if not obj.total_calls:
            return None
        return round((obj.total_calls - obj.failed_calls) / obj.total_calls * 100, 1)

    class Meta:
        from ..models.settings import WebhookRegistration
        model = WebhookRegistration
        fields = [
            'id', 'created_at', 'updated_at',
            'name', 'url',
            # secret intentionally excluded — write-only on create
            'events', 'is_active',
            'retry_count', 'timeout_secs',
            'last_called', 'last_status',
            'total_calls', 'failed_calls', 'success_rate',
            'headers',
            'created_by', 'created_by_email',
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'last_called', 'last_status',
            'total_calls', 'failed_calls', 'created_by',
        ]
        extra_kwargs = {
            'secret': {'write_only': True},
        }


class WebhookDeliveryLogSerializer(serializers.ModelSerializer):
    webhook_name = serializers.CharField(source='webhook.name', read_only=True)

    class Meta:
        from ..models.settings import WebhookDeliveryLog
        model = WebhookDeliveryLog
        fields = [
            'id', 'created_at',
            'webhook', 'webhook_name',
            'event', 'payload',
            'response_status', 'response_body',
            'attempt', 'delivered',
            'error', 'duration_ms',
        ]
        read_only_fields = [
            'id', 'created_at',
            'response_status', 'response_body',
            'attempt', 'delivered', 'error', 'duration_ms',
        ]
        extra_kwargs = {'webhook': {'write_only': True}}
