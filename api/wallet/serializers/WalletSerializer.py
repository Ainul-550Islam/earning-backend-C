# api/wallet/serializers/WalletSerializer.py
from decimal import Decimal
from rest_framework import serializers
from django.utils import timezone
from ..models import Wallet


class WalletSerializer(serializers.ModelSerializer):
    user_id          = serializers.IntegerField(source="user.id", read_only=True)
    username         = serializers.CharField(source="user.username", read_only=True)
    email            = serializers.EmailField(source="user.email", read_only=True)
    available_balance = serializers.SerializerMethodField()
    total_balance    = serializers.SerializerMethodField()
    is_bonus_active  = serializers.BooleanField(read_only=True)
    tier             = serializers.SerializerMethodField()
    publisher_level  = serializers.SerializerMethodField()
    points           = serializers.SerializerMethodField()

    class Meta:
        model  = Wallet
        fields = [
            "id", "user_id", "username", "email",
            "current_balance", "pending_balance", "frozen_balance",
            "bonus_balance", "reserved_balance",
            "available_balance", "total_balance",
            "total_earned", "total_withdrawn", "total_fees_paid",
            "total_bonuses", "total_referral_earned",
            "bonus_expires_at", "is_bonus_active",
            "is_locked", "locked_reason", "locked_at",
            "currency", "version",
            "two_fa_enabled", "daily_limit",
            "auto_withdraw", "auto_withdraw_threshold",
            "last_activity_at",
            "tier", "publisher_level", "points",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "current_balance", "pending_balance", "frozen_balance",
            "reserved_balance", "total_earned", "total_withdrawn",
            "total_fees_paid", "version", "is_locked",
            "created_at", "updated_at",
        ]

    def get_available_balance(self, obj):
        return str(obj.available_balance)

    def get_total_balance(self, obj):
        return str(obj.total_balance)

    def get_tier(self, obj):
        return getattr(obj.user, "tier", "FREE")

    def get_publisher_level(self, obj):
        try:
            from ..models_cpalead_extra import PublisherLevel
            pl = PublisherLevel.objects.get(wallet=obj)
            return {"level": pl.level, "payout_freq": pl.payout_freq}
        except Exception:
            return {"level": 1, "payout_freq": "net30"}

    def get_points(self, obj):
        try:
            from ..models_cpalead_extra import PointsLedger
            pl = PointsLedger.objects.get(wallet=obj)
            return {"total": pl.total_points, "tier": pl.current_tier}
        except Exception:
            return {"total": 0, "tier": ""}
