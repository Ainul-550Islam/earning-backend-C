# api/djoyalty/serializers/EventSerializer.py
from rest_framework import serializers
from ..models.core import Event


class EventSerializer(serializers.ModelSerializer):
    is_anonymous = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id', 'customer', 'customer_name', 'is_anonymous',
            'action', 'description', 'event_category',
            'metadata', 'source', 'timestamp', 'created_at',
        ]
        read_only_fields = ['id', 'is_anonymous', 'customer_name', 'created_at']

    def get_is_anonymous(self, obj) -> bool:
        return obj.is_anonymous

    def get_customer_name(self, obj) -> str:
        if obj.customer:
            return obj.customer.full_name
        return 'Anonymous'

    def validate_action(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Action cannot be empty.')
        return value.strip()
