from rest_framework import serializers
from ..models import SmartLink, SmartLinkTag


class SmartLinkTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmartLinkTag
        fields = ['id', 'name', 'color']


class SmartLinkSerializer(serializers.ModelSerializer):
    tags = SmartLinkTagSerializer(many=True, read_only=True)
    tag_names = serializers.ListField(
        child=serializers.CharField(max_length=50),
        write_only=True, required=False, default=list
    )
    publisher_username = serializers.CharField(source='publisher.username', read_only=True)
    full_url = serializers.SerializerMethodField()
    epc = serializers.SerializerMethodField()
    conversion_rate = serializers.SerializerMethodField()

    class Meta:
        model = SmartLink
        fields = [
            'id', 'uuid', 'slug', 'name', 'description', 'type',
            'redirect_type', 'rotation_method', 'is_active', 'is_archived',
            'enable_ab_test', 'enable_fraud_filter', 'enable_bot_filter',
            'enable_unique_click', 'notes', 'group',
            'total_clicks', 'total_unique_clicks', 'total_conversions', 'total_revenue',
            'epc', 'conversion_rate',
            'tags', 'tag_names', 'publisher_username', 'full_url',
            'last_click_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'uuid', 'total_clicks', 'total_unique_clicks',
            'total_conversions', 'total_revenue', 'last_click_at',
            'created_at', 'updated_at',
        ]

    def get_full_url(self, obj):
        return obj.full_url

    def get_epc(self, obj):
        if obj.total_clicks == 0:
            return 0.0
        return round(float(obj.total_revenue) / obj.total_clicks, 4)

    def get_conversion_rate(self, obj):
        if obj.total_clicks == 0:
            return 0.0
        return round(obj.total_conversions / obj.total_clicks * 100, 2)

    def validate_slug(self, value):
        from ..validators import validate_slug_format
        validate_slug_format(value)
        return value
