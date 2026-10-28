# engagement/serializers/challenge_serializer.py
from rest_framework import serializers
from ..models.challenge import Challenge, ChallengeParticipant


class ChallengeSerializer(serializers.ModelSerializer):
    is_active            = serializers.BooleanField(read_only=True)
    participant_count    = serializers.SerializerMethodField()

    class Meta:
        model  = Challenge
        fields = [
            "id", "title", "description", "type", "metric", "target",
            "starts_at", "ends_at", "coin_reward", "xp_reward",
            "max_participants", "is_public", "is_active", "participant_count",
        ]

    def get_participant_count(self, obj):
        return obj.participants.count()


class ChallengeParticipantSerializer(serializers.ModelSerializer):
    username  = serializers.CharField(source="user.username", read_only=True)
    challenge = ChallengeSerializer(read_only=True)

    class Meta:
        model  = ChallengeParticipant
        fields = [
            "id", "username", "challenge", "status",
            "score", "rank", "joined_at", "completed_at", "reward_distributed",
        ]
        read_only_fields = ["id", "joined_at", "rank"]
