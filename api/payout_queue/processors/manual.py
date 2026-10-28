"""
payout_queue/processors/manual.py  ← NEW FILE

The MANUAL gateway means a human will process the transfer offline.
The processor records the intent and always returns a synthetic success
so the batch can transition to COMPLETED.  The gateway_reference is
the internal_reference (no external transaction ID is issued).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from ..choices import PaymentGateway
from ..exceptions import GatewayError
from ..utils.payment_gateway import BasePaymentProcessor, PayoutResult

logger = logging.getLogger(__name__)

class ManualProcessor(BasePaymentProcessor):
    """
    Manual payout processor — no real API call.

    Marks every payout as SUCCESS immediately so the batch can
    complete; a human is expected to actually execute the transfers
    using the PayoutItem records in the admin.

    Config: none required (accepts empty dict).
    """

    gateway = PaymentGateway.MANUAL

    def _validate_config(self) -> None:
        pass  # No required keys for manual processing

    def validate_account(self, account_number: str) -> bool:
        """Any non-empty account number is valid for manual processing."""
        return bool(account_number and account_number.strip())

    def send_payout(
        self,
        *,
        account_number: str,
        amount: Decimal,
        reference: str,
        **kwargs: Any,
    ) -> PayoutResult:
        """
        Record a manual payout intent.  Always succeeds immediately.
        The gateway_reference is the internal reference (no external TRX ID).
        """
        if not self.validate_account(account_number):
            raise GatewayError(
                "ManualProcessor: account_number must not be empty."
            )
        if amount <= Decimal("0"):
            raise GatewayError(
                f"ManualProcessor: amount must be positive, got {amount}."
            )

        logger.info(
            "ManualProcessor: payout recorded (to be processed manually): "
            "account=%s amount=%s ref=%s",
            account_number, amount, reference,
        )
        return PayoutResult(
            success=True,
            gateway_reference=reference,  # use internal ref as the "transaction id"
            raw_response={
                "processor": "MANUAL",
                "account_number": account_number,
                "amount": str(amount),
                "reference": reference,
                "note": "Pending manual execution",
            },
        )

    def verify_transaction(self, gateway_reference: str) -> PayoutResult:
        """Manual transactions cannot be auto-verified."""
        raise GatewayError(
            "ManualProcessor: verification is not supported for manual payouts."
        )
