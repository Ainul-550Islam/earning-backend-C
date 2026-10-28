# engagement/serializers/xp_serializer.py
from rest_framework import serializers
from ..models.xp import UserXP, XPTransaction


class UserXPSerializer(serializers.ModelSerializer):
    xp_for_next_level      = serializers.IntegerField(read_only=True)
    xp_progress_in_level   = serializers.IntegerField(read_only=True)
    xp_needed_for_next     = serializers.IntegerField(read_only=True)
    level_pct              = serializers.IntegerField(read_only=True)

    class Meta:
        model  = UserXP
        fields = [
            "total_xp", "level",
            "xp_for_next_level", "xp_progress_in_level",
            "xp_needed_for_next", "level_pct",
            "level_updated_at",
        ]
        read_only_fields = fields


class XPTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = XPTransaction
        fields = ["id", "source", "amount", "note", "ref_id", "created_at"]
        read_only_fields = fields
