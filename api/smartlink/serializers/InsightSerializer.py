from rest_framework import serializers


class InsightSerializer(serializers.Serializer):
    """Generic serializer for computed insight payloads (read-only)."""
    smartlink_id = serializers.IntegerField(read_only=True)
    period_days = serializers.IntegerField(read_only=True)
    clicks = serializers.IntegerField(read_only=True)
    unique_clicks = serializers.IntegerField(read_only=True)
    conversions = serializers.IntegerField(read_only=True)
    revenue = serializers.DecimalField(max_digits=12, decimal_places=4, read_only=True)
    epc = serializers.FloatField(read_only=True)
    conversion_rate = serializers.FloatField(read_only=True)
    quality_rate = serializers.FloatField(read_only=True)
    bot_clicks = serializers.IntegerField(read_only=True)
    fraud_clicks = serializers.IntegerField(read_only=True)
