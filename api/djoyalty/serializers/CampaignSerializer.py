# api/djoyalty/serializers/CampaignSerializer.py
from rest_framework import serializers
from ..models.campaigns import LoyaltyCampaign, CampaignParticipant

class LoyaltyCampaignSerializer(serializers.ModelSerializer):
    participant_count = serializers.SerializerMethodField()
    class Meta:
        model = LoyaltyCampaign
        fields = ['id', 'name', 'description', 'campaign_type', 'status', 'multiplier', 'bonus_points', 'min_spend', 'max_participants', 'applicable_tiers', 'start_date', 'end_date', 'participant_count', 'created_at']
    def get_participant_count(self, obj): return obj.participants.count()
