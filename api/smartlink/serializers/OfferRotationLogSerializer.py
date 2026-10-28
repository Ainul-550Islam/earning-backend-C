from rest_framework import serializers
from api.smartlink.models.offer_pool import OfferRotationLog


class OfferRotationLogSerializer(serializers.ModelSerializer):
    """
    Serializer for OfferRotationLog records.
    Audit trail showing which offer was selected per redirect and why.
    Read-only — written exclusively by the OfferRotationService.
    """
    smartlink_slug = serializers.CharField(source='smartlink.slug', read_only=True)
    offer_name = serializers.SerializerMethodField()

    class Meta:
        model = OfferRotationLog
        fields = [
            'id',
            'smartlink',
            'smartlink_slug',
            'offer',
            'offer_name',
            'selected_reason',
            'offer_weight',
            'offer_epc',
            'country',
            'device_type',
            'created_at',
        ]
        read_only_fields = fields

    def get_offer_name(self, obj):
        """Return offer name string if the FK resolves, else the offer ID."""
        if obj.offer is not None:
            return getattr(obj.offer, 'name', str(obj.offer_id))
        return None


class OfferRotationLogListSerializer(serializers.ModelSerializer):
    """
    Compact serializer for rotation log lists.
    Excludes heavyweight FK fields to keep list payloads small.
    """
    smartlink_slug = serializers.CharField(source='smartlink.slug', read_only=True)

    class Meta:
        model = OfferRotationLog
        fields = [
            'id',
            'smartlink_slug',
            'offer',
            'selected_reason',
            'country',
            'device_type',
            'created_at',
        ]
        read_only_fields = fields


class OfferRotationSummarySerializer(serializers.Serializer):
    """
    Aggregated rotation distribution summary.
    Shows which offers received how much traffic and by what method.
    """
    offer_id = serializers.IntegerField(allow_null=True)
    offer_name = serializers.CharField(allow_null=True)
    total_selections = serializers.IntegerField()
    percentage = serializers.FloatField(help_text='% of total rotations going to this offer.')
    avg_epc = serializers.DecimalField(max_digits=8, decimal_places=4, allow_null=True)
    top_reason = serializers.CharField(help_text='Most common selection_reason for this offer.')
