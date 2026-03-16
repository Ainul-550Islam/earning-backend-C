"""
Rocket (DBBL) Payment Processor.

Implements Dutch-Bangla Bank's Rocket mobile banking API for B2C disbursements.
Config keys: api_key, merchant_number, pin, base_url
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Any

from ..choices import PaymentGateway
from ..constants import GATEWAY_TIMEOUT_SECONDS, ROCKET_PHONE_REGEX
from ..exceptions import GatewayError, GatewayTimeoutError, GatewayAuthError
from ..utils.payment_gateway import BasePaymentProcessor, PayoutResult

logger = logging.getLogger(__name__)

_REQUIRED_CONFIG = ("api_key", "merchant_number", "base_url")


class RocketProcessor(BasePaymentProcessor):
    """
    Rocket (DBBL) B2C disbursement processor.
    """

    gateway = PaymentGateway.ROCKET

    def _validate_config(self) -> None:
        self._require_config(*_REQUIRED_CONFIG)

    def validate_account(self, account_number: str) -> bool:
        if not account_number or not isinstance(account_number, str):
            return False
        cleaned = account_number.strip().replace(" ", "").replace("-", "")
        return bool(re.match(ROCKET_PHONE_REGEX, cleaned))

    def send_payout(
        self,
        *,
        account_number: str,
        amount: Decimal,
        reference: str,
        **kwargs: Any,
    ) -> PayoutResult:
        """
        Initiate a Rocket B2C payment.
        """
        if not self.validate_account(account_number):
            raise GatewayError(
                f"RocketProcessor: invalid account number '{account_number}'."
            )
        if not isinstance(amount, Decimal) or amount <= Decimal("0"):
            raise GatewayError(
                f"RocketProcessor: amount must be a positive Decimal, got {amount!r}."
            )
        if not reference or not isinstance(reference, str):
            raise GatewayError("RocketProcessor: reference must be a non-empty string.")

        logger.info(
            "RocketProcessor.send_payout: account=%s amount=%s ref=%s",
            account_number, amount, reference,
        )

        try:
            response = self._post_payment(
                account_number=account_number.strip(),
                amount=amount,
                reference=reference,
            )
        except GatewayTimeoutError:
            raise
        except GatewayAuthError:
            raise
        except GatewayError:
            raise
        except Exception as exc:
            raise GatewayError(f"RocketProcessor.send_payout: unexpected: {exc}") from exc

        success = response.get("status_code") == "000" or response.get("ResponseCode") == "000"
        gateway_reference = (
            response.get("transaction_id")
            or response.get("TransactionID")
            or ""
        )

        if success:
            if not gateway_reference:
                logger.warning(
                    "RocketProcessor.send_payout: success with empty gateway_reference ref=%s",
                    reference,
                )
                gateway_reference = f"ROCKET-{reference[:20]}"
            logger.info(
                "RocketProcessor.send_payout: SUCCESS txnId=%s ref=%s",
                gateway_reference, reference,
            )
            return PayoutResult(
                success=True,
                gateway_reference=gateway_reference,
                raw_response=response,
            )

        error_code = response.get("status_code") or response.get("ResponseCode") or "UNKNOWN"
        error_message = (
            response.get("message")
            or response.get("ResponseMessage")
            or "Unknown Rocket error."
        )
        logger.warning(
            "RocketProcessor.send_payout: FAILED code=%s msg=%s ref=%s",
            error_code, error_message, reference,
        )
        return PayoutResult(
            success=False,
            error_code=error_code,
            error_message=error_message,
            raw_response=response,
        )

    def verify_transaction(self, gateway_reference: str) -> PayoutResult:
        if not gateway_reference or not isinstance(gateway_reference, str):
            raise GatewayError("gateway_reference must be a non-empty string.")
        try:
            import requests
            url = f"{self.config['base_url']}/transaction/verify"
            headers = {
                "Authorization": f"Bearer {self.config['api_key']}",
                "Content-Type": "application/json",
            }
            resp = requests.post(
                url,
                json={"transaction_id": gateway_reference},
                headers=headers,
                timeout=GATEWAY_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
            success = data.get("status_code") == "000"
            if success:
                return PayoutResult(
                    success=True, gateway_reference=gateway_reference, raw_response=data
                )
            return PayoutResult(
                success=False,
                error_code=data.get("status_code", "UNKNOWN"),
                error_message=data.get("message", ""),
                raw_response=data,
            )
        except requests.exceptions.Timeout as exc:
            raise GatewayTimeoutError(f"RocketProcessor.verify_transaction: timeout: {exc}") from exc
        except Exception as exc:
            raise GatewayError(f"RocketProcessor.verify_transaction: error: {exc}") from exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _post_payment(
        self, *, account_number: str, amount: Decimal, reference: str
    ) -> dict:
        try:
            import requests
            url = f"{self.config['base_url']}/api/v1/sendmoney"
            headers = {
                "Authorization": f"Bearer {self.config['api_key']}",
                "Content-Type": "application/json",
            }
            payload = {
                "sender": self.config["merchant_number"],
                "receiver": account_number,
                "amount": str(amount),
                "currency": "BDT",
                "reference": reference,
                "remark": f"Payout {reference}",
            }
            resp = requests.post(
                url, json=payload, headers=headers,
                timeout=GATEWAY_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout as exc:
            raise GatewayTimeoutError(f"RocketProcessor._post_payment: timeout: {exc}") from exc
        except Exception as exc:
            raise GatewayError(f"RocketProcessor._post_payment: error: {exc}") from exc
