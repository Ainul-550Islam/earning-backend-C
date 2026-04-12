from rest_framework import serializers
from ..models import ClickMetadata


class ClickMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClickMetadata
        fields = [
            'id', 'click', 'sub1', 'sub2', 'sub3', 'sub4', 'sub5',
            'custom_params', 'referrer', 'landing_page_url',
            'offer_url_final', 'created_at',
        ]
        read_only_fields = fields
