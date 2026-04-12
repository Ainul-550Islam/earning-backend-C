from rest_framework import serializers
from ..models import SmartLink


class PublisherAPISerializer(serializers.ModelSerializer):
    """Lightweight serializer for publisher-facing external API."""
    url = serializers.SerializerMethodField()

    class Meta:
        model = SmartLink
        fields = [
            'id', 'slug', 'name', 'type', 'url',
            'is_active', 'total_clicks', 'total_conversions',
            'total_revenue', 'created_at',
        ]
        read_only_fields = fields

    def get_url(self, obj):
        return obj.full_url
