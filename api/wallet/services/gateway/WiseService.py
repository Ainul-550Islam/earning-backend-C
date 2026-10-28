# api/wallet/services/gateway/WiseService.py
"""
WiseService — Wise (formerly TransferWise) international payout.

Supports BDT → USD/EUR/GBP conversions and transfers to Wise accounts.
Uses Wise API v3: https://api.wise.com

Circuit breaker protected. All amounts in Decimal.
"""
import logging
import uuid
from decimal import Decimal

from django.conf import settings

from ...engine.circuit_breaker import get_breaker
from ...exceptions import GatewayError, InvalidAmountError

logger = logging.getLogger("wallet.gateway.wise")

GW_NAME = "wise"
WISE_FEE_PCT = Decimal("0.0065")   # 0.65% Wise fee
WISE_FEE_MIN = Decimal("0.50")     # USD minimum


class WiseService:
    """International payout via Wise API."""

    @classmethod
    def disburse(
        cls,
        receiver: str,          # Wise account email or profile ID
        amount: Decimal,        # BDT amount
        reference: str,
        target_currency: str = "USD",
        recipient_name: str = "",
    ) -> dict:
        """
        Send international payout via Wise.
        BDT is converted to target_currency at live rate.

        Args:
            receiver:        Wise account email or profile ID
            amount:          Source amount in BDT
            reference:       Internal reference (withdrawal_id)
            target_currency: Destination currency (USD/EUR/GBP/...)
            recipient_name:  Full name of recipient

        Returns:
            {transaction_id, exchange_rate, target_amount, fee, status}
        """
        amount = Decimal(str(amount))
        if amount <= Decimal("0"):
            raise InvalidAmountError("Wise transfer amount must be positive")

        breaker = get_breaker(GW_NAME)
        breaker.assert_closed()

        try:
            result = cls._send(
                receiver=receiver,
                amount=amount,
                reference=reference,
                target_currency=target_currency,
                recipient_name=recipient_name,
            )
            breaker.record_success()
            return result
        except GatewayError:
            breaker.record_failure()
            raise
        except Exception as e:
            breaker.record_failure()
            raise GatewayError(f"WiseService failed: {e}") from e

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate that receiver looks like a valid email for Wise."""
        import re
        return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", email or ""))

    @staticmethod
    def _send(receiver, amount, reference, target_currency, recipient_name) -> dict:
        api_key = getattr(settings, "WISE_API_KEY", "")
        profile_id = getattr(settings, "WISE_PROFILE_ID", "")

        if not api_key:
            # Sandbox mode
            logger.warning(f"WiseService SANDBOX: ref={reference} amount={amount}")
            mock_rate = Decimal("0.0091")   # ~110 BDT/USD
            target_amount = (amount * mock_rate).quantize(Decimal("0.01"))
            fee = max(amount * WISE_FEE_PCT, WISE_FEE_MIN * Decimal("110")).quantize(Decimal("0.01"))
            return {
                "transaction_id":  f"WISE-SANDBOX-{uuid.uuid4().hex[:12].upper()}",
                "exchange_rate":   str(mock_rate),
                "source_amount":   str(amount),
                "source_currency": "BDT",
                "target_amount":   str(target_amount),
                "target_currency": target_currency,
                "fee":             str(fee),
                "status":          "processing",
                "reference":       reference,
                "sandbox":         True,
            }

        import requests
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        # Step 1: Get exchange rate quote
        quote_resp = requests.post(
            "https://api.wise.com/v3/quotes",
            json={
                "sourceCurrency": "BDT",
                "targetCurrency": target_currency,
                "sourceAmount":   float(amount),
                "profile":        profile_id,
            },
            headers=headers, timeout=15,
        )
        if quote_resp.status_code != 200:
            raise GatewayError(f"Wise quote failed: {quote_resp.text[:200]}")
        quote = quote_resp.json()
        quote_id = quote["id"]

        # Step 2: Create transfer
        transfer_resp = requests.post(
            "https://api.wise.com/v1/transfers",
            json={
                "targetAccount": receiver,
                "quoteUuid":     quote_id,
                "customerTransactionId": str(uuid.uuid4()),
                "details": {"reference": reference},
            },
            headers=headers, timeout=15,
        )
        if transfer_resp.status_code not in (200, 201):
            raise GatewayError(f"Wise transfer failed: {transfer_resp.text[:200]}")
        txn = transfer_resp.json()

        return {
            "transaction_id":  str(txn.get("id")),
            "exchange_rate":   str(quote.get("rate", 0)),
            "source_amount":   str(amount),
            "source_currency": "BDT",
            "target_amount":   str(quote.get("targetAmount", 0)),
            "target_currency": target_currency,
            "fee":             str(quote.get("fee", 0)),
            "status":          txn.get("status", "processing"),
            "reference":       reference,
        }
