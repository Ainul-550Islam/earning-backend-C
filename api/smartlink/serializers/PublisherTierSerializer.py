from rest_framework import serializers
from api.smartlink.models.extensions.smartlink_schedule import PublisherTier


class PublisherTierSerializer(serializers.ModelSerializer):
    """
    Serializer for PublisherTier records.
    Shows a publisher's quality tier, tier benefits, and quality metrics.
    """
    publisher_username = serializers.CharField(source='publisher.username', read_only=True)
    tier_display = serializers.CharField(source='get_tier_display', read_only=True)
    tier_emoji = serializers.CharField(read_only=True)
    next_evaluation_in_hours = serializers.SerializerMethodField()

    class Meta:
        model = PublisherTier
        fields = [
            'id',
            'publisher',
            'publisher_username',
            'tier',
            'tier_display',
            'tier_emoji',
            'max_smartlinks',
            'max_custom_domains',
            'api_rate_limit',
            'can_use_ml_rotation',
            'can_use_ab_testing',
            'can_use_pre_landers',
            'payout_bonus_percent',
            'last_quality_score',
            'last_evaluated_at',
            'next_evaluation_at',
            'next_evaluation_in_hours',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'publisher',
            'publisher_username',
            'tier_display',
            'tier_emoji',
            'max_smartlinks',
            'max_custom_domains',
            'api_rate_limit',
            'can_use_ml_rotation',
            'can_use_ab_testing',
            'can_use_pre_landers',
            'payout_bonus_percent',
            'last_quality_score',
            'last_evaluated_at',
            'next_evaluation_at',
            'next_evaluation_in_hours',
            'created_at',
            'updated_at',
        ]

    def get_next_evaluation_in_hours(self, obj):
        """Hours until the next scheduled tier evaluation."""
        from django.utils import timezone
        if obj.next_evaluation_at is None:
            return None
        now = timezone.now()
        if obj.next_evaluation_at <= now:
            return 0
        delta = obj.next_evaluation_at - now
        return round(delta.total_seconds() / 3600, 1)


class PublisherTierSummarySerializer(serializers.ModelSerializer):
    """
    Lightweight read serializer for embedding tier info in publisher profile.
    """
    tier_display = serializers.CharField(source='get_tier_display', read_only=True)
    tier_emoji = serializers.CharField(read_only=True)

    class Meta:
        model = PublisherTier
        fields = [
            'tier',
            'tier_display',
            'tier_emoji',
            'payout_bonus_percent',
            'can_use_ml_rotation',
            'can_use_ab_testing',
            'can_use_pre_landers',
            'last_quality_score',
        ]
        read_only_fields = fields


class ManualTierOverrideSerializer(serializers.Serializer):
    """
    Admin-only serializer for manually overriding a publisher's tier.
    Used when a publisher disputes an automated evaluation result.
    """
    TIER_CHOICES = [
        ('gold', 'Gold'),
        ('silver', 'Silver'),
        ('bronze', 'Bronze'),
        ('standard', 'Standard'),
        ('under_review', 'Under Review'),
    ]
    tier = serializers.ChoiceField(choices=TIER_CHOICES)
    reason = serializers.CharField(
        max_length=500,
        help_text='Internal reason for the manual override.',
    )


class TierEvaluationResultSerializer(serializers.Serializer):
    """Result returned by the evaluate-tier action."""
    publisher_id = serializers.IntegerField()
    tier = serializers.CharField()
    quality_rate = serializers.FloatField()
    unique_rate = serializers.FloatField()
    fraud_rate = serializers.FloatField()
    total_clicks = serializers.IntegerField()
    benefits = serializers.DictField()
