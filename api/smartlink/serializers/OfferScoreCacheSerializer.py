from rest_framework import serializers
from api.smartlink.models.offer_pool import OfferScoreCache


class OfferScoreCacheSerializer(serializers.ModelSerializer):
    """
    Serializer for OfferScoreCache records.
    Exposes cached EPC/CR scores per offer+geo+device.
    Read-only — populated and refreshed automatically by Celery tasks.
    """
    offer_name = serializers.SerializerMethodField()
    calculated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = OfferScoreCache
        fields = [
            'id',
            'offer',
            'offer_name',
            'country',
            'device_type',
            'epc',
            'conversion_rate',
            'total_clicks',
            'total_conversions',
            'score',
            'calculated_at',
        ]
        read_only_fields = fields

    def get_offer_name(self, obj):
        if obj.offer is not None:
            return getattr(obj.offer, 'name', str(obj.offer_id))
        return None


class OfferScoreRankSerializer(serializers.Serializer):
    """
    Ranked offer score list for a given country+device combo.
    Used by the EPC optimizer to pick the best offer during routing.
    """
    rank = serializers.IntegerField(help_text='1-based rank by composite score.')
    offer_id = serializers.IntegerField()
    offer_name = serializers.CharField(allow_null=True)
    country = serializers.CharField(max_length=2)
    device_type = serializers.CharField()
    epc = serializers.DecimalField(max_digits=8, decimal_places=4)
    conversion_rate = serializers.DecimalField(max_digits=6, decimal_places=4)
    score = serializers.FloatField()
    total_clicks = serializers.IntegerField()
    calculated_at = serializers.DateTimeField()
