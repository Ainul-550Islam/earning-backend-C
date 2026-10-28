# engagement/serializers/referral_serializer.py
from rest_framework import serializers
from ..models.referral import Referral, ReferralProgram


class ReferralProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ReferralProgram
        fields = [
            "id", "name", "referrer_reward", "referee_reward",
            "referrer_xp", "referee_xp", "max_referrals",
            "is_active", "starts_at", "ends_at",
        ]


class ReferralSerializer(serializers.ModelSerializer):
    referrer_username = serializers.CharField(source="referrer.username", read_only=True)
    referee_username  = serializers.CharField(source="referee.username",  read_only=True)

    class Meta:
        model  = Referral
        fields = [
            "id", "referrer_username", "referee_username",
            "code", "status", "rewarded_at", "created_at",
        ]
        read_only_fields = fields
