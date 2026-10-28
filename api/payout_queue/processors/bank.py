"""
payout_queue/processors/bank.py  ← FIXED v2

CHANGE v2: validate_account() uses self._normalise_account() from
BasePaymentProcessor. BankProcessor uses a numeric-only regex (different from
mobile regex), so the guard refactor still applies but the regex is local.
All send_payout / _call_bank_api logic unchanged.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Any

from ..choices import PaymentGateway
from ..exceptions import GatewayError, GatewayTimeoutError
from ..utils.payment_gateway import BasePaymentProcessor, PayoutResult

logger = logging.getLogger(__name__)

_REQUIRED_CONFIG = ("api_key", "base_url")

# Bangladesh bank account: typically 10–20 digit numeric string
_BANK_ACCOUNT_REGEX = re.compile(r"^\d{10,20}$")

class BankProcessor(BasePaymentProcessor):
    """
    Generic bank transfer processor (BEFTN / RTGS).

    Required config keys: api_key, base_url
    Optional:            timeout (int, seconds)

    In production this calls your bank's core-banking or BEFTN API.
    The implementation here is a skeleton — replace _call_bank_api
    with the real HTTP call for your bank partner.
    """

    gateway = PaymentGateway.BANK

    def _validate_config(self) -> None:
        self._require_config(*_REQUIRED_CONFIG)

    def validate_account(self, account_number: str) -> bool:
        """
        Validate a bank account number (10–20 digit numeric).

        FIX v2: uses self._normalise_account() from BasePaymentProcessor.
        BankProcessor strips spaces and hyphens (common in IBAN-style formatting)
        before applying the numeric regex.
        """
        cleaned = self._normalise_account(account_number)
        if not cleaned:
            return False
        return bool(_BANK_ACCOUNT_REGEX.match(cleaned))

    def send_payout(
        self,
        *,
        account_number: str,
        amount: Decimal,
        reference: str,
        **kwargs: Any,
    ) -> PayoutResult:
        """
        Initiate a bank transfer.

        Args:
            account_number: Destination bank account number.
            amount:         Net transfer amount (Decimal, BDT).
            reference:      Unique idempotency key.

        Returns:
            PayoutResult

        Raises:
            GatewayError:        On API error / invalid input.
            GatewayTimeoutError: On network timeout.
        """
        if not self.validate_account(account_number):
            raise GatewayError(
                f"BankProcessor: invalid account number '{account_number}'."
            )
        if amount <= Decimal("0"):
            raise GatewayError(
                f"BankProcessor: amount must be positive, got {amount}."
            )

        try:
            raw = self._call_bank_api(
                self._normalise_account(account_number), amount, reference
            )
        except TimeoutError as exc:
            raise GatewayTimeoutError(
                f"BankProcessor: request timed out: {exc}"
            ) from exc
        except Exception as exc:
            raise GatewayError(f"BankProcessor: unexpected error: {exc}") from exc

        if raw.get("status") == "SUCCESS":
            return PayoutResult(
                success=True,
                gateway_reference=str(raw["transaction_id"]),
                raw_response=raw,
            )
        return PayoutResult(
            success=False,
            error_code=str(raw.get("error_code", "BANK_ERROR")),
            error_message=str(raw.get("error_message", "Bank transfer failed.")),
            raw_response=raw,
        )

    def verify_transaction(self, gateway_reference: str) -> PayoutResult:
        """Verify a previously initiated bank transfer."""
        if not gateway_reference:
            raise GatewayError("gateway_reference must not be empty.")

        # Bank (BEFTN/RTGS) does not provide real-time transaction status APIs.
        # Verification must be done out-of-band (bank statement reconciliation).
        # This method returns a pending result rather than raising, allowing
        # callers to distinguish "not supported" from a real gateway error.
        #
        # To implement: call your bank partner's reconciliation API or
        # query their BEFTN status endpoint when available.
        return PayoutResult(
            success=False,
            error_code="VERIFICATION_NOT_SUPPORTED",
            error_message=(
                f"Bank (BEFTN/RTGS) does not support real-time transaction "
                f"verification. Reference {gateway_reference!r} must be "
                f"reconciled via bank statement."
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_bank_api(
        self, account_number: str, amount: Decimal, reference: str
    ) -> dict:
        """
        Placeholder for the real bank HTTP call.
        Replace with your bank partner's SDK or REST call.
        """
        import requests
        from ..constants import GATEWAY_TIMEOUT_SECONDS

        api_key  = self.config["api_key"]
        base_url = self.config["base_url"].rstrip("/")
        timeout  = self.config.get("timeout", GATEWAY_TIMEOUT_SECONDS)

        response = requests.post(
            f"{base_url}/transfer",
            json={
                "account_number": account_number,
                "amount":         str(amount),
                "reference":      reference,
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
