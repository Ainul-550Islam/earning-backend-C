from rest_framework import serializers
from ..models import SmartLinkDailyStat, SmartLinkStat


class SmartLinkStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmartLinkDailyStat
        fields = [
            'id', 'smartlink', 'date',
            'clicks', 'unique_clicks', 'bot_clicks', 'fraud_clicks',
            'conversions', 'revenue', 'epc', 'conversion_rate',
            'top_country', 'top_device', 'updated_at',
        ]
        read_only_fields = fields


class SmartLinkHourlyStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmartLinkStat
        fields = [
            'id', 'smartlink', 'hour', 'country', 'device_type',
            'clicks', 'unique_clicks', 'bot_clicks', 'fraud_clicks',
            'conversions', 'revenue', 'epc', 'conversion_rate', 'updated_at',
        ]
        read_only_fields = fields
