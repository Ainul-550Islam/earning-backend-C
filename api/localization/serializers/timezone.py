# serializers/timezone.py
from rest_framework import serializers

class TimezoneSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.core import Timezone
        model = Timezone
        fields = ['id', 'created_at', 'updated_at', 'name', 'code', 'offset', 'offset_seconds', 'is_dst', 'is_active']
        read_only_fields = ['id', 'created_at', 'updated_at']

class TimezoneMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.core import Timezone
        model = Timezone
        fields = ['name', 'code', 'offset']