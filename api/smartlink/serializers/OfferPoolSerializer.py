from rest_framework import serializers
from ..models import OfferPool, OfferPoolEntry


class OfferPoolEntryInlineSerializer(serializers.ModelSerializer):
    offer_name = serializers.CharField(source='offer.name', read_only=True)

    class Meta:
        model = OfferPoolEntry
        fields = ['id', 'offer', 'offer_name', 'weight', 'priority',
                  'cap_per_day', 'cap_per_month', 'is_active', 'epc_override']


class OfferPoolSerializer(serializers.ModelSerializer):
    entries = OfferPoolEntryInlineSerializer(many=True, read_only=True)
    active_count = serializers.SerializerMethodField()

    class Meta:
        model = OfferPool
        fields = ['id', 'name', 'is_active', 'min_epc_threshold',
                  'active_count', 'entries', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_active_count(self, obj):
        return obj.entries.filter(is_active=True).count()
