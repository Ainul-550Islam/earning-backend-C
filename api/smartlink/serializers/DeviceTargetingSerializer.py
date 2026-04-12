from rest_framework import serializers
from ..models import DeviceTargeting


class DeviceTargetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceTargeting
        fields = ['id', 'mode', 'device_types', 'updated_at']
        read_only_fields = ['id', 'updated_at']
