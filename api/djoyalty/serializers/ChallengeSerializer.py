# api/djoyalty/serializers/ChallengeSerializer.py
from rest_framework import serializers
from ..models.engagement import Challenge, ChallengeParticipant


class ChallengeSerializer(serializers.ModelSerializer):
    participant_count = serializers.SerializerMethodField()
    is_ongoing = serializers.SerializerMethodField()

    class Meta:
        model = Challenge
        fields = [
            'id', 'name', 'description',
            'challenge_type', 'target_action', 'target_value', 'target_count',
            'points_reward', 'bonus_points', 'badge_reward',
            'status', 'start_date', 'end_date',
            'max_participants', 'image', 'terms',
            'participant_count', 'is_ongoing',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'participant_count', 'is_ongoing', 'created_at', 'updated_at']

    def get_participant_count(self, obj) -> int:
        return obj.participants.count()

    def get_is_ongoing(self, obj) -> bool:
        from django.utils import timezone
        now = timezone.now()
        if obj.status != 'active':
            return False
        if obj.end_date and obj.end_date < now:
            return False
        return True


class ChallengeParticipantSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()
    challenge_name = serializers.SerializerMethodField()
    progress_percent = serializers.SerializerMethodField()

    class Meta:
        model = ChallengeParticipant
        fields = [
            'id', 'challenge', 'challenge_name',
            'customer', 'customer_code',
            'progress', 'status',
            'completed_at', 'reward_claimed', 'points_awarded',
            'progress_percent',
            'joined_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'customer_code', 'challenge_name',
            'status', 'completed_at', 'points_awarded',
            'progress_percent', 'created_at',
        ]

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_challenge_name(self, obj) -> str:
        return obj.challenge.name if obj.challenge else ''

    def get_progress_percent(self, obj) -> float:
        target = obj.challenge.target_value if obj.challenge else 0
        if not target or target == 0:
            return 0.0
        return round(float(min(obj.progress / target * 100, 100)), 1)
