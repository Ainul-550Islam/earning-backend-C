# api/wallet/serializers/ReportSerializer.py
from rest_framework import serializers

class DailySummarySerializer(serializers.Serializer):
    date               = serializers.CharField()
    total_wallets      = serializers.IntegerField()
    active_wallets     = serializers.IntegerField()
    locked_wallets     = serializers.IntegerField()
    total_credits      = serializers.FloatField()
    total_debits       = serializers.FloatField()
    total_txn_count    = serializers.IntegerField()
    total_earned       = serializers.FloatField()
    withdrawals_pending= serializers.IntegerField()
    withdrawal_volume  = serializers.FloatField()
    fee_income         = serializers.FloatField()
    total_liability    = serializers.FloatField()

class TopEarnerSerializer(serializers.Serializer):
    username = serializers.CharField(source="wallet__user__username")
    total    = serializers.FloatField()
    count    = serializers.IntegerField()
