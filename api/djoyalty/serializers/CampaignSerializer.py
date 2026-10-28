# api/djoyalty/serializers/CampaignSerializer.py
from rest_framework import serializers
from ..models.campaigns import LoyaltyCampaign, CampaignSegment, CampaignParticipant, ReferralPointsRule


class CampaignSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignSegment
        fields = ['id', 'segment_type', 'condition_value', 'is_active']
        read_only_fields = ['id']


class LoyaltyCampaignSerializer(serializers.ModelSerializer):
    segments = CampaignSegmentSerializer(many=True, read_only=True)
    participant_count = serializers.SerializerMethodField()
    is_ongoing = serializers.SerializerMethodField()

    class Meta:
        model = LoyaltyCampaign
        fields = [
            'id', 'name', 'description',
            'campaign_type', 'multiplier', 'bonus_points',
            'segment_target', 'status',
            'start_date', 'end_date',
            'max_participants', 'budget_points', 'points_issued',
            'image', 'terms', 'is_featured',
            'segments', 'participant_count', 'is_ongoing',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'points_issued', 'participant_count', 'is_ongoing', 'created_at', 'updated_at']

    def get_participant_count(self, obj) -> int:
        return obj.participants.count()

    def get_is_ongoing(self, obj) -> bool:
        from django.utils import timezone
        now = timezone.now()
        if obj.status != 'active':
            return False
        if obj.start_date and obj.start_date > now:
            return False
        if obj.end_date and obj.end_date < now:
            return False
        return True


class CampaignParticipantSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()
    campaign_name = serializers.SerializerMethodField()

    class Meta:
        model = CampaignParticipant
        fields = [
            'id', 'campaign', 'campaign_name',
            'customer', 'customer_code',
            'is_active', 'points_earned_in_campaign',
            'joined_at', 'created_at',
        ]
        read_only_fields = ['id', 'customer_code', 'campaign_name', 'created_at']

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_campaign_name(self, obj) -> str:
        return obj.campaign.name if obj.campaign else ''


class ReferralPointsRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralPointsRule
        fields = [
            'id', 'tenant', 'level',
            'points_on_signup', 'points_on_first_offer',
            'multiplier', 'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


    def validate(self, data):
        from django.utils import timezone
        start = data.get('start_date')
        end = data.get('end_date')
        if start and end and end <= start:
            from rest_framework import serializers
            raise serializers.ValidationError(
                {'end_date': 'end_date must be after start_date.'}
            )
        return data
