# api/wallet/serializers/WalletInsightSerializer.py
from rest_framework import serializers
from ..models import WalletInsight


class WalletInsightSerializer(serializers.ModelSerializer):
    wallet_user = serializers.CharField(source="wallet.user.username", read_only=True)
    net_change  = serializers.SerializerMethodField()

    class Meta:
        model  = WalletInsight
        fields = [
            "id", "wallet", "wallet_user", "date",
            "opening_balance", "closing_balance", "peak_balance",
            "total_credits", "total_credit_count",
            "total_debits", "total_debit_count",
            "txn_count", "wd_count", "earn_count", "bonus_count", "reversal_count",
            "earnings_by_source", "net_change",
            "computed_at",
        ]
        read_only_fields = fields

    def get_net_change(self, obj):
        return float(obj.closing_balance - obj.opening_balance)
