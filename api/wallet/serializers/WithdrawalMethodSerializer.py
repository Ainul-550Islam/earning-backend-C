# api/wallet/serializers/WithdrawalMethodSerializer.py
from rest_framework import serializers
from ..models import WithdrawalMethod


class WithdrawalMethodSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(source="get_method_type_display", read_only=True)
    masked_account = serializers.SerializerMethodField()

    class Meta:
        model  = WithdrawalMethod
        fields = [
            "id", "user", "method_type", "method_display",
            "account_number", "masked_account", "account_name",
            "is_verified", "is_default", "is_whitelisted",
            "bank_name", "branch_name", "routing_number", "swift_code",
            "card_last_four", "card_expiry",
            "crypto_network", "crypto_address",
            "verified_at",
            "created_at", "updated_at",
        ]
        read_only_fields = ["is_verified", "verified_at", "is_whitelisted", "created_at", "updated_at"]
        extra_kwargs     = {"user": {"read_only": True}}

    def get_masked_account(self, obj):
        acc = obj.account_number or ""
        return "****" + acc[-4:] if len(acc) > 4 else acc

    def validate(self, data):
        mt  = data.get("method_type", "")
        acc = data.get("account_number", "")
        if mt in ("bkash","nagad","rocket","upay") and acc and not acc.startswith("01"):
            raise serializers.ValidationError({"account_number": f"{mt} number must start with 01"})
        if mt == "bank" and not data.get("bank_name"):
            raise serializers.ValidationError({"bank_name": "Required for bank accounts"})
        if mt in ("usdt_trc20","usdt_erc20") and not data.get("crypto_address"):
            raise serializers.ValidationError({"crypto_address": "Required for crypto"})
        return data
