# engagement/serializers/quest_serializer.py
from rest_framework import serializers
from ..models.quest import Quest, UserQuest


class QuestSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Quest
        fields = [
            "id", "slug", "title", "description", "type", "icon",
            "target", "action", "coin_reward", "xp_reward", "order",
        ]


class UserQuestSerializer(serializers.ModelSerializer):
    quest = QuestSerializer(read_only=True)
    pct   = serializers.IntegerField(read_only=True)

    class Meta:
        model  = UserQuest
        fields = [
            "id", "quest", "period_date", "status",
            "progress", "pct", "completed_at", "reward_claimed",
        ]
        read_only_fields = ["id", "period_date", "completed_at"]
