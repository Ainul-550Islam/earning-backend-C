# api/wallet/schemas.py
"""
OpenAPI schema customization using drf-spectacular.
Generates Swagger/OpenAPI 3.0 docs for the wallet API.

Install: pip install drf-spectacular
settings.py:
  INSTALLED_APPS += ["drf_spectacular"]
  REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"
  SPECTACULAR_SETTINGS = {
      "TITLE": "Wallet API",
      "VERSION": "2.0.0",
      "DESCRIPTION": "World-class affiliate wallet system",
  }
"""
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers


# ── Response Schemas ──────────────────────────────────────────

class SuccessResponseSchema(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    data    = serializers.DictField()
    message = serializers.CharField(required=False)


class ErrorResponseSchema(serializers.Serializer):
    success = serializers.BooleanField(default=False)
    error   = serializers.CharField()
    code    = serializers.CharField(required=False)


class WalletBalanceSchema(serializers.Serializer):
    current_balance   = serializers.DecimalField(max_digits=20, decimal_places=8)
    pending_balance   = serializers.DecimalField(max_digits=20, decimal_places=8)
    available_balance = serializers.DecimalField(max_digits=20, decimal_places=8)
    bonus_balance     = serializers.DecimalField(max_digits=20, decimal_places=8)
    frozen_balance    = serializers.DecimalField(max_digits=20, decimal_places=8)
    reserved_balance  = serializers.DecimalField(max_digits=20, decimal_places=8)
    total_earned      = serializers.DecimalField(max_digits=20, decimal_places=8)
    total_withdrawn   = serializers.DecimalField(max_digits=20, decimal_places=8)
    is_locked         = serializers.BooleanField()
    currency          = serializers.CharField()


class TransferRequestSchema(serializers.Serializer):
    recipient = serializers.CharField(help_text="Recipient username or email")
    amount    = serializers.DecimalField(max_digits=12, decimal_places=2, help_text="Amount in BDT")
    note      = serializers.CharField(required=False)


class WithdrawalRequestSchema(serializers.Serializer):
    payment_method_id = serializers.IntegerField()
    amount            = serializers.DecimalField(max_digits=12, decimal_places=2,
                                                  help_text="Amount in BDT (min 50)")
    note              = serializers.CharField(required=False)


class FeePreviewSchema(serializers.Serializer):
    amount     = serializers.FloatField()
    fee        = serializers.FloatField()
    net_amount = serializers.FloatField()
    gateway    = serializers.CharField()
    fee_type   = serializers.CharField()


# ── Schema Decorators ─────────────────────────────────────────

wallet_me_schema = extend_schema(
    summary="Get My Wallet",
    description="Get the current authenticated user's wallet with all 5 balance types.",
    responses={200: WalletBalanceSchema, 404: ErrorResponseSchema},
    tags=["Wallet"],
)

wallet_transfer_schema = extend_schema(
    summary="Transfer to User",
    description="Transfer BDT from your wallet to another user.",
    request=TransferRequestSchema,
    responses={200: SuccessResponseSchema, 400: ErrorResponseSchema},
    tags=["Wallet"],
    examples=[
        OpenApiExample("Transfer 500 BDT",
            value={"recipient": "john_doe", "amount": "500.00", "note": "Payment for service"},
            request_only=True)
    ],
)

withdrawal_create_schema = extend_schema(
    summary="Request Withdrawal",
    description="Create a new withdrawal request. Subject to daily limits and KYC requirements.",
    request=WithdrawalRequestSchema,
    responses={201: SuccessResponseSchema, 400: ErrorResponseSchema, 429: ErrorResponseSchema},
    tags=["Withdrawal"],
    parameters=[
        OpenApiParameter("Idempotency-Key", OpenApiTypes.STR, OpenApiParameter.HEADER,
                          description="Unique key to prevent duplicate requests")
    ],
)

fee_preview_schema = extend_schema(
    summary="Withdrawal Fee Preview",
    description="Get fee estimate before submitting withdrawal.",
    responses={200: FeePreviewSchema},
    tags=["Withdrawal"],
    parameters=[
        OpenApiParameter("amount", OpenApiTypes.FLOAT, OpenApiParameter.QUERY, required=True),
        OpenApiParameter("gateway", OpenApiTypes.STR, OpenApiParameter.QUERY,
                          enum=["bkash","nagad","rocket","usdt_trc20","paypal"]),
    ],
)
