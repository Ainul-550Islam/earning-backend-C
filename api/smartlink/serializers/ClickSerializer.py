from rest_framework import serializers
from ..models import Click, ClickMetadata


class ClickMetadataInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClickMetadata
        fields = ['sub1', 'sub2', 'sub3', 'sub4', 'sub5', 'custom_params', 'offer_url_final']


class ClickSerializer(serializers.ModelSerializer):
    metadata = ClickMetadataInlineSerializer(read_only=True)
    offer_name = serializers.CharField(source='offer.name', read_only=True)

    class Meta:
        model = Click
        fields = [
            'id', 'smartlink', 'offer', 'offer_name',
            'ip', 'country', 'region', 'city',
            'device_type', 'os', 'browser',
            'is_unique', 'is_fraud', 'is_bot', 'is_converted',
            'fraud_score', 'payout', 'referrer',
            'metadata', 'created_at',
        ]
        read_only_fields = fields
