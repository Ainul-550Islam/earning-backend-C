# api/wallet/services/gateway/PayoneerService.py
"""
PayoneerService — Payoneer mass payout for publishers.

CPALead uses Payoneer for international publisher payouts.
Supports: mass payment (CSV batch) and single payment API.

API: Payoneer Partner API v4
Circuit breaker protected. All math in Decimal.
"""
import logging
import uuid
from decimal import Decimal

from django.conf import settings

from ...engine.circuit_breaker import get_breaker
from ...exceptions import GatewayError, InvalidAmountError

logger = logging.getLogger("wallet.gateway.payoneer")

GW_NAME      = "payoneer"
MIN_PAYOUT   = Decimal("20.00")    # Payoneer minimum $20 USD equivalent
FEE_FLAT     = Decimal("3.00")     # $3 USD flat fee per payment


class PayoneerService:
    """Payoneer publisher payout gateway."""

    @classmethod
    def disburse(
        cls,
        receiver: str,            # Payoneer account email
        amount: Decimal,          # BDT amount
        reference: str,
        currency: str = "USD",
        description: str = "Wallet payout",
    ) -> dict:
        """
        Single Payoneer payout.

        Args:
            receiver:    Payoneer account email of recipient
            amount:      BDT amount to send
            reference:   Internal reference (withdrawal_id)
            currency:    Target currency (default USD)
            description: Payment description shown to recipient

        Returns:
            {transaction_id, status, fee, currency, sandbox}
        """
        amount = Decimal(str(amount))
        if amount <= Decimal("0"):
            raise InvalidAmountError("Payoneer payout must be positive")

        breaker = get_breaker(GW_NAME)
        breaker.assert_closed()

        try:
            result = cls._send_single(receiver, amount, reference, currency, description)
            breaker.record_success()
            return result
        except GatewayError:
            breaker.record_failure()
            raise
        except Exception as e:
            breaker.record_failure()
            raise GatewayError(f"PayoneerService failed: {e}") from e

    @classmethod
    def disburse_batch(cls, payments: list) -> dict:
        """
        Submit a batch of payments to Payoneer.

        Args:
            payments: [{"receiver": email, "amount": Decimal, "reference": str}, ...]

        Returns:
            {batch_id, submitted: int, total_amount: str, status}
        """
        if not payments:
            return {"batch_id": "", "submitted": 0, "total_amount": "0", "status": "empty"}

        breaker = get_breaker(GW_NAME)
        breaker.assert_closed()

        try:
            result = cls._send_batch(payments)
            breaker.record_success()
            return result
        except GatewayError:
            breaker.record_failure()
            raise
        except Exception as e:
            breaker.record_failure()
            raise GatewayError(f"Payoneer batch failed: {e}") from e

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate Payoneer account email format."""
        import re
        return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", email or ""))

    @staticmethod
    def _get_auth() -> tuple:
        """Return (client_id, api_key, program_id) from settings."""
        return (
            getattr(settings, "PAYONEER_CLIENT_ID", ""),
            getattr(settings, "PAYONEER_API_KEY", ""),
            getattr(settings, "PAYONEER_PROGRAM_ID", ""),
        )

    @classmethod
    def _send_single(cls, receiver, amount, reference, currency, description) -> dict:
        client_id, api_key, program_id = cls._get_auth()

        if not api_key:
            logger.warning(f"PayoneerService SANDBOX: ref={reference} amount={amount}")
            return {
                "transaction_id": f"PNR-SANDBOX-{uuid.uuid4().hex[:12].upper()}",
                "status":         "pending",
                "receiver":       receiver,
                "amount":         str(amount),
                "currency":       currency,
                "fee":            str(FEE_FLAT),
                "reference":      reference,
                "sandbox":        True,
            }

        import requests
        import base64
        auth = base64.b64encode(f"{client_id}:{api_key}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type":  "application/json",
        }
        payload = {
            "payee_id":    receiver,
            "amount":      float(amount),
            "currency":    currency,
            "description": description,
            "payment_id":  reference,
            "program_id":  program_id,
        }
        resp = requests.post(
            "https://api.payoneer.com/v4/programs/payments",
            json=payload, headers=headers, timeout=20,
        )
        if resp.status_code not in (200, 201, 202):
            raise GatewayError(f"Payoneer HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return {
            "transaction_id": data.get("payment_id", reference),
            "status":         data.get("status", "pending"),
            "receiver":       receiver,
            "amount":         str(amount),
            "currency":       currency,
            "fee":            str(FEE_FLAT),
            "reference":      reference,
        }

    @classmethod
    def _send_batch(cls, payments) -> dict:
        client_id, api_key, program_id = cls._get_auth()
        batch_id = str(uuid.uuid4().hex[:16].upper())
        total = sum(Decimal(str(p["amount"])) for p in payments)

        if not api_key:
            logger.warning(f"Payoneer SANDBOX batch: {len(payments)} payments total={total}")
            return {
                "batch_id":     batch_id,
                "submitted":    len(payments),
                "total_amount": str(total),
                "status":       "pending",
                "sandbox":      True,
            }

        import requests
        import base64
        auth = base64.b64encode(f"{client_id}:{api_key}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        items = [
            {
                "payee_id":   p["receiver"],
                "amount":     float(Decimal(str(p["amount"]))),
                "currency":   p.get("currency", "USD"),
                "payment_id": p["reference"],
                "description": p.get("description", "Wallet payout"),
            }
            for p in payments
        ]
        resp = requests.post(
            "https://api.payoneer.com/v4/programs/payments/batch",
            json={"batch_id": batch_id, "program_id": program_id, "payments": items},
            headers=headers, timeout=30,
        )
        if resp.status_code not in (200, 201, 202):
            raise GatewayError(f"Payoneer batch HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return {
            "batch_id":     data.get("batch_id", batch_id),
            "submitted":    len(payments),
            "total_amount": str(total),
            "status":       data.get("status", "pending"),
        }
