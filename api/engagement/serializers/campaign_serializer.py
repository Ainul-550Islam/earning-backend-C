# engagement/serializers/campaign_serializer.py
from rest_framework import serializers
from ..models.campaign import (UserSegment, Campaign, CampaignEvent,
                                FeatureFlag, ABTest, ABTestVariant, UserABAssignment)


class UserSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UserSegment
        fields = [
            "id", "name", "slug", "criteria", "description",
            "member_count", "last_synced", "is_dynamic",
        ]
        read_only_fields = ["id", "member_count", "last_synced"]


class CampaignSerializer(serializers.ModelSerializer):
    conversion_rate  = serializers.FloatField(read_only=True)
    segment_name     = serializers.SerializerMethodField()

    class Meta:
        model  = Campaign
        fields = [
            "id", "name", "slug", "campaign_type", "status",
            "segment_name", "starts_at", "ends_at", "config",
            "reach_count", "conversion_count", "conversion_rate",
        ]
        read_only_fields = ["id", "reach_count", "conversion_count", "conversion_rate"]

    def get_segment_name(self, obj):
        return obj.target_segment.name if obj.target_segment else "All Users"


class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FeatureFlag
        fields = ["id", "slug", "name", "description", "is_enabled", "rollout_pct", "config"]


class ABTestVariantSerializer(serializers.ModelSerializer):
    conversion_rate = serializers.FloatField(read_only=True)

    class Meta:
        model  = ABTestVariant
        fields = [
            "id", "slug", "name", "traffic_pct", "config",
            "participant_count", "conversion_count", "conversion_rate",
        ]
        read_only_fields = ["id", "participant_count", "conversion_count"]


class ABTestSerializer(serializers.ModelSerializer):
    variants = ABTestVariantSerializer(many=True, read_only=True)

    class Meta:
        model  = ABTest
        fields = [
            "id", "slug", "name", "description", "status",
            "starts_at", "ends_at", "winner_variant", "variants",
        ]
        read_only_fields = ["id", "winner_variant"]
