# api/wallet/serializers/WalletBalanceUpdateSerializer.py
import logging
from decimal import Decimal, InvalidOperation
from rest_framework import serializers

logger = logging.getLogger("wallet.serializer")


class WalletBalanceUpdateSerializer(serializers.Serializer):
    """Validate admin balance update input."""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    type   = serializers.ChoiceField(choices=["credit", "debit", "bonus", "penalty"])
    reference   = serializers.CharField(max_length=100, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)

    def validate_amount(self, value):
        try:
            amount = Decimal(str(value))
            if amount <= 0:
                raise serializers.ValidationError("Amount must be positive")
            return amount
        except (InvalidOperation, ValueError, TypeError):
            raise serializers.ValidationError("Invalid amount")
