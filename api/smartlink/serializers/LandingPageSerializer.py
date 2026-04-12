from rest_framework import serializers
from ..models import LandingPage


class LandingPageSerializer(serializers.ModelSerializer):
    ctr = serializers.SerializerMethodField()

    class Meta:
        model = LandingPage
        fields = [
            'id', 'name', 'url', 'is_active', 'is_default',
            'traffic_split', 'views', 'clicks_through', 'ctr',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'views', 'clicks_through', 'created_at', 'updated_at']

    def get_ctr(self, obj):
        return obj.ctr
