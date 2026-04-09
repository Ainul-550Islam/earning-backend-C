# api/djoyalty/serializers/ChallengeSerializer.py
from rest_framework import serializers
from ..models.engagement import Challenge, ChallengeParticipant

class ChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = ['id', 'name', 'description', 'challenge_type', 'target_value', 'points_reward', 'status', 'start_date', 'end_date', 'max_participants', 'created_at']

class ChallengeParticipantSerializer(serializers.ModelSerializer):
    challenge_name = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    progress_percent = serializers.SerializerMethodField()
    class Meta:
        model = ChallengeParticipant
        fields = ['id', 'challenge', 'challenge_name', 'customer', 'customer_name', 'progress', 'progress_percent', 'status', 'joined_at', 'completed_at', 'points_awarded']
    def get_challenge_name(self, obj): return obj.challenge.name if obj.challenge else ''
    def get_customer_name(self, obj): return str(obj.customer) if obj.customer else ''
    def get_progress_percent(self, obj):
        if obj.challenge and obj.challenge.target_value:
            return round(float(obj.progress / obj.challenge.target_value * 100), 1)
        return 0
