# api/wallet/serializers/BulkWalletUpdateSerializer.py
import logging
from decimal import Decimal, InvalidOperation
from rest_framework import serializers

logger = logging.getLogger("wallet.serializer")


class BulkWalletUpdateSerializer(serializers.Serializer):
    """Validate bulk wallet update input (max 100 items)."""
    updates = serializers.ListField(
        child=serializers.DictField(),
        max_length=100,  # Prevent DoS
    )

    def validate_updates(self, value):
        if not value:
            raise serializers.ValidationError("Updates list cannot be empty")

        validated = []
        for idx, update in enumerate(value):
            try:
                wallet_id = update.get("wallet_id")
                amount    = update.get("amount")
                if not wallet_id or amount is None:
                    logger.warning(f"Skipping invalid update at index {idx}: {update}")
                    continue
                validated.append({
                    "wallet_id":   wallet_id,
                    "amount":      Decimal(str(amount)),
                    "type":        update.get("type", "credit"),
                    "description": update.get("description", ""),
                })
            except (ValueError, InvalidOperation, TypeError) as e:
                logger.error(f"Failed to validate update {idx}: {e}")
                continue

        if not validated:
            raise serializers.ValidationError("No valid updates found")
        return validated
