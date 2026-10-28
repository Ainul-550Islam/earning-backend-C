"""
SmartLink ImpressionLog Serializer
=====================================
Serializes impression tracking records (pre-click view events).
Used by ImpressionViewSet for the impression analytics API.
"""
from rest_framework import serializers
from api.smartlink.models.impression import ImpressionLog


class ImpressionLogSerializer(serializers.ModelSerializer):
    """
    Full read-only view of an impression record.
    Exposes all fields for analytics and reporting.
    """
    smartlink_slug = serializers.SerializerMethodField()

    class Meta:
        model = ImpressionLog
        fields = [
            'id',
            'smartlink',
            'smartlink_slug',
            'offer_id',
            'ip',
            'country',
            'device_type',
            'os_type',
            'browser',
            'referrer',
            'sub1',
            'sub2',
            'is_unique',
            'is_bot',
            'created_at',
        ]
        read_only_fields = fields

    def get_smartlink_slug(self, obj):
        return obj.smartlink.slug


class ImpressionLogListSerializer(serializers.ModelSerializer):
    """
    Compact list view for impression logs (pagination-optimised).
    Excludes large fields not needed in list views.
    """
    smartlink_slug = serializers.SerializerMethodField()

    class Meta:
        model = ImpressionLog
        fields = [
            'id',
            'smartlink_slug',
            'offer_id',
            'country',
            'device_type',
            'is_unique',
            'is_bot',
            'created_at',
        ]
        read_only_fields = fields

    def get_smartlink_slug(self, obj):
        return obj.smartlink.slug


class ImpressionSummarySerializer(serializers.Serializer):
    """
    Aggregated impression summary for a SmartLink.
    Returned by the /impressions/summary/ endpoint.
    """
    smartlink_slug          = serializers.CharField()
    total_impressions       = serializers.IntegerField()
    unique_impressions      = serializers.IntegerField()
    bot_impressions         = serializers.IntegerField()
    human_impressions       = serializers.IntegerField()
    click_through_rate      = serializers.FloatField(
        help_text='Percentage of impressions that resulted in a click.'
    )
    view_through_rate       = serializers.FloatField(
        help_text='Percentage of impressions that resulted in a conversion (VTA).'
    )
    top_countries           = serializers.ListField(child=serializers.DictField())
    top_device_types        = serializers.ListField(child=serializers.DictField())
    period_from             = serializers.DateField()
    period_to               = serializers.DateField()


class ImpressionCreateSerializer(serializers.Serializer):
    """
    Input for recording an impression via the tracking pixel or API.
    Most fields are optional — collected from request context server-side.
    """
    smartlink_slug = serializers.SlugField()
    offer_id       = serializers.IntegerField(required=False, allow_null=True)
    sub1           = serializers.CharField(max_length=255, required=False, allow_blank=True)
    sub2           = serializers.CharField(max_length=255, required=False, allow_blank=True)
