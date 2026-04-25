# api/wallet/serializers/LedgerEntrySerializer.py
from rest_framework import serializers
from ..models import LedgerEntry


class LedgerEntrySerializer(serializers.ModelSerializer):
    ledger_id  = serializers.UUIDField(source="ledger.ledger_id", read_only=True)
    wallet_id  = serializers.IntegerField(source="ledger.wallet_id", read_only=True)
    is_debit   = serializers.SerializerMethodField()

    class Meta:
        model  = LedgerEntry
        fields = [
            "id", "ledger", "ledger_id", "wallet_id",
            "entry_type", "account", "amount", "balance_after",
            "ref_type", "ref_id",
            "is_debit", "created_at",
        ]
        read_only_fields = fields

    def get_is_debit(self, obj):
        return obj.entry_type == "debit"
