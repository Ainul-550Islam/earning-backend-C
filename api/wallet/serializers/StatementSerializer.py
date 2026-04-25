# api/wallet/serializers/StatementSerializer.py
from rest_framework import serializers

class AccountStatementSerializer(serializers.ModelSerializer):
    net_change = serializers.SerializerMethodField()
    class Meta:
        from ..models.statement import AccountStatement
        model  = AccountStatement
        fields = ["id","period","period_start","period_end","status","opening_balance",
                  "closing_balance","total_credits","total_debits","total_fees","txn_count",
                  "pdf_file","csv_file","generated_at","net_change"]
        read_only_fields = fields

    def get_net_change(self, obj):
        return float(obj.closing_balance - obj.opening_balance)
