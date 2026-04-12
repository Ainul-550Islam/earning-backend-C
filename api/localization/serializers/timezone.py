# serializers/timezone.py
from rest_framework import serializers

class TimezoneSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.core import Timezone
        model = Timezone
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class TimezoneMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.core import Timezone
        model = Timezone
        fields = ['name', 'code', 'offset']
