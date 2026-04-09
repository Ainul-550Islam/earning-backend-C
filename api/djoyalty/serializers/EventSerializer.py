# api/djoyalty/serializers/EventSerializer.py
from rest_framework import serializers
from ..models.core import Event

class EventSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    is_anonymous = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = ['id', 'timestamp', 'customer', 'customer_name', 'is_anonymous', 'action', 'description', 'metadata']
        read_only_fields = ['timestamp']

    def get_customer_name(self, obj):
        return str(obj.customer) if obj.customer else 'Anonymous'

    def get_is_anonymous(self, obj):
        return obj.customer is None

    def validate_action(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Action cannot be empty.')
        return value.strip()
