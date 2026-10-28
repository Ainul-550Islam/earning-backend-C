from rest_framework import serializers
from api.smartlink.models.click import BotClick


class BotClickSerializer(serializers.ModelSerializer):
    """
    Serializer for BotClick records.
    Bot clicks are detected and stored separately from real clicks.
    Immutable — created by the bot detection pipeline, never edited by users.
    """
    smartlink_slug = serializers.CharField(source='smartlink.slug', read_only=True)

    class Meta:
        model = BotClick
        fields = [
            'id',
            'smartlink',
            'smartlink_slug',
            'ip',
            'user_agent',
            'bot_type',
            'detection_method',
            'country',
            'created_at',
        ]
        read_only_fields = fields


class BotClickSummarySerializer(serializers.Serializer):
    """
    Aggregated bot click summary per SmartLink.
    Used in analytics dashboards and fraud reports.
    """
    total_bot_clicks = serializers.IntegerField()
    bot_types = serializers.DictField(
        child=serializers.IntegerField(),
        help_text='Bot type label → count mapping.',
    )
    detection_methods = serializers.DictField(
        child=serializers.IntegerField(),
        help_text='Detection method → count mapping.',
    )
    top_countries = serializers.ListField(
        child=serializers.DictField(),
        help_text='Top 10 countries by bot click volume.',
    )
    period_days = serializers.IntegerField(
        help_text='Number of days this summary covers.',
    )
