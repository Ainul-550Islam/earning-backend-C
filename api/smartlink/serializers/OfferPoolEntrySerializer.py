from rest_framework import serializers
from ..models import OfferPoolEntry


class OfferPoolEntrySerializer(serializers.ModelSerializer):
    offer_name = serializers.CharField(source='offer.name', read_only=True)
    cap_usage = serializers.SerializerMethodField()

    class Meta:
        model = OfferPoolEntry
        fields = [
            'id', 'offer', 'offer_name', 'weight', 'priority',
            'cap_per_day', 'cap_per_month', 'is_active',
            'epc_override', 'cap_usage', 'added_at', 'updated_at',
        ]
        read_only_fields = ['id', 'added_at', 'updated_at']

    def get_cap_usage(self, obj):
        if not obj.cap_per_day:
            return None
        from ..services.rotation.CapTrackerService import CapTrackerService
        return CapTrackerService().get_usage(obj)

    def validate_weight(self, value):
        if not (1 <= value <= 1000):
            raise serializers.ValidationError('Weight must be between 1 and 1000.')
        return value
