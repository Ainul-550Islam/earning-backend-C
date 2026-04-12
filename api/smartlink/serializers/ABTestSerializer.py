from rest_framework import serializers
from ..models import SmartLinkVersion


class ABTestSerializer(serializers.ModelSerializer):
    epc = serializers.SerializerMethodField()
    conversion_rate = serializers.SerializerMethodField()

    class Meta:
        model = SmartLinkVersion
        fields = [
            'id', 'smartlink', 'name', 'description',
            'traffic_split', 'is_control', 'is_active', 'is_winner',
            'clicks', 'conversions', 'revenue',
            'epc', 'conversion_rate',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'clicks', 'conversions', 'revenue', 'is_winner', 'created_at', 'updated_at']

    def get_epc(self, obj):
        return obj.epc

    def get_conversion_rate(self, obj):
        return obj.conversion_rate

    def validate_traffic_split(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError('traffic_split must be between 0 and 100.')
        return value
