# api/wallet/serializers/AdminWalletSerializer.py
"""
Admin-facing wallet serializer — includes all fields including sensitive ones.
Never expose to non-admin users.
"""
from rest_framework import serializers
from ..models import Wallet


class AdminWalletSerializer(serializers.ModelSerializer):
    username           = serializers.CharField(source="user.username", read_only=True)
    email              = serializers.EmailField(source="user.email", read_only=True)
    available_balance  = serializers.SerializerMethodField()
    total_balance      = serializers.SerializerMethodField()
    locked_by_name     = serializers.SerializerMethodField()
    tier               = serializers.SerializerMethodField()
    kyc_level          = serializers.SerializerMethodField()
    withdrawal_block   = serializers.SerializerMethodField()
    reconciliation_status = serializers.SerializerMethodField()

    class Meta:
        model  = Wallet
        fields = [
            "id", "user", "username", "email",
            "current_balance", "pending_balance", "frozen_balance",
            "bonus_balance", "reserved_balance",
            "available_balance", "total_balance",
            "total_earned", "total_withdrawn", "total_fees_paid",
            "total_bonuses", "total_referral_earned",
            "bonus_expires_at",
            "is_locked", "locked_reason", "locked_at", "locked_by", "locked_by_name",
            "currency", "version",
            "two_fa_enabled", "daily_limit",
            "auto_withdraw", "auto_withdraw_threshold",
            "last_activity_at",
            "tier", "kyc_level", "withdrawal_block", "reconciliation_status",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_available_balance(self, obj): return str(obj.available_balance)
    def get_total_balance(self, obj):     return str(obj.total_balance)

    def get_locked_by_name(self, obj):
        return obj.locked_by.username if obj.locked_by else ""

    def get_tier(self, obj):
        return getattr(obj.user, "tier", "FREE")

    def get_kyc_level(self, obj):
        try:
            from ..models_cpalead_extra import KYCVerification
            kyc = KYCVerification.objects.filter(user=obj.user, status="approved").order_by("-level").first()
            return kyc.level if kyc else 0
        except Exception:
            return 0

    def get_withdrawal_block(self, obj):
        from ..models import WithdrawalBlock
        block = WithdrawalBlock.objects.filter(user=obj.user, is_active=True).first()
        if block and block.is_currently_active():
            return {"reason": block.reason, "until": str(block.unblock_at) if block.unblock_at else "permanent"}
        return None

    def get_reconciliation_status(self, obj):
        from ..models import LedgerReconciliation
        last = LedgerReconciliation.objects.filter(wallet=obj).order_by("-reconciled_at").first()
        if last:
            return {"status": last.status, "discrepancy": float(last.discrepancy), "at": last.reconciled_at}
        return None
