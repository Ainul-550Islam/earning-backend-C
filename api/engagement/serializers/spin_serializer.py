# engagement/serializers/spin_serializer.py
from rest_framework import serializers
from ..models.spinwheel import SpinWheel
from ..constants import SPIN_MAX_PER_DAY


class SpinWheelSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model  = SpinWheel
        fields = [
            "id", "user", "username", "coins_won", "xp_earned",
            "spun_at", "outcome_idx", "is_boosted",
        ]
        read_only_fields = ["id", "spun_at"]


class SpinStatsSerializer(serializers.Serializer):
    total_spins_today     = serializers.IntegerField()
    total_coins_won_today = serializers.FloatField()
    total_spins_ever      = serializers.IntegerField()
    total_coins_won_ever  = serializers.FloatField()
    my_spins_today        = serializers.IntegerField()
    my_spins_remaining    = serializers.IntegerField()
    my_total_coins_won    = serializers.FloatField()
    max_spins_per_day     = serializers.IntegerField(default=SPIN_MAX_PER_DAY)
