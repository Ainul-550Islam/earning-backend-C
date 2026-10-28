# engagement/serializers/anti_cheat_serializer.py
from rest_framework import serializers
from ..models.anti_cheat import AntiCheatRule, AntiCheatLog, UserRiskScore, IPReputation


class AntiCheatRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AntiCheatRule
        fields = [
            "id", "slug", "name", "rule_type", "description",
            "threshold", "window_seconds", "action", "severity", "is_active",
        ]


class AntiCheatLogSerializer(serializers.ModelSerializer):
    username     = serializers.CharField(source="user.username", read_only=True)
    rule_name    = serializers.CharField(source="rule.name",     read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = AntiCheatLog
        fields = [
            "id", "username", "rule_name", "status", "severity",
            "details", "ip_address", "device_id",
            "reviewed_by_name", "reviewed_at", "notes", "created_at",
        ]
        read_only_fields = ["id", "username", "rule_name", "created_at"]

    def get_reviewed_by_name(self, obj):
        return obj.reviewed_by.username if obj.reviewed_by else None


class UserRiskScoreSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model  = UserRiskScore
        fields = [
            "id", "username", "score", "flag_count",
            "is_suspended", "suspended_at", "suspension_reason", "last_flag_at",
        ]
        read_only_fields = fields


class IPReputationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = IPReputation
        fields = ["id", "ip_address", "reputation", "reason", "hit_count", "last_seen"]
