"""
payout_queue/processors/rocket.py  ← DRY v7 (built on v2)

DRY CHANGE v7:

  ① _build_headers() helper added  (replaces 2 duplicate inline dicts)

     Before:  verify_transaction() and _post_payment() each built:
                  headers = {
                      "Authorization": f"Bearer {self.config['api_key']}",
                      "Content-Type":  "application/json",
                  }
              verbatim.  nagad.py already had this pattern centralised in
              _build_headers(); rocket.py was the only gateway that didn't.

     After:   Both methods call `self._build_headers()`.
              Pattern is now consistent across nagad.py and rocket.py.

v2 change preserved: validate_account() uses self._normalise_account().
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
import requests
from requests.exceptions import Timeout as RequestsTimeout

logger = logging.getLogger(__name__)

_REQUIRED_CONFIG = ("api_key", "merchant_number", "base_url")

class RocketProcessor(BasePaymentProcessor):
    """Rocket (DBBL) B2C disbursement processor."""

    gateway = PaymentGateway.ROCKET

    def _validate_config(self) -> None:
        self._require_config(*_REQUIRED_CONFIG)

    # ------------------------------------------------------------------
    # DRY v7: shared header helper (consistent with nagad.py pattern)
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict:
        """
        DRY v7: Returns the standard JSON headers for all Rocket API calls.

        Before:  verify_transaction() and _post_payment() each had an inline:
                     {"Authorization": f"Bearer {self.config['api_key']}",
                      "Content-Type": "application/json"}
                 nagad.py already centralised this in _build_headers();
                 rocket.py was inconsistent.
        After:   Both call sites use self._build_headers().
        """
        return {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type":  "application/json",
        }

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def validate_account(self, account_number: str) -> bool:
        """
        Validate a Rocket wallet number (Bangladesh mobile: 01XXXXXXXXX).

        FIX v2: uses self._normalise_account() from BasePaymentProcessor.
        """
        cleaned = self._normalise_account(account_number)
        if not cleaned:
            return False
        return bool(re.match(ROCKET_PHONE_REGEX, cleaned))

    def send_payout(
        self,
        *,
        account_number: str,
        amount: Decimal,
        reference: str,
        **kwargs: Any,
    ) -> PayoutResult:
        """Initiate a Rocket B2C payment."""
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
                account_number=self._normalise_account(account_number),
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
            raise GatewayError(
                f"RocketProcessor.send_payout: unexpected: {exc}"
            ) from exc

        success = (
            response.get("status_code") == "000"
            or response.get("ResponseCode") == "000"
        )
        gateway_reference = (
            response.get("transaction_id")
            or response.get("TransactionID")
            or ""
        )

        if success:
            if not gateway_reference:
                logger.warning(
                    "RocketProcessor.send_payout: success with empty "
                    "gateway_reference ref=%s",
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

        error_code = (
            response.get("status_code")
            or response.get("ResponseCode")
            or "UNKNOWN"
        )
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
        """Verify a Rocket transaction by transaction_id."""
        if not gateway_reference or not isinstance(gateway_reference, str):
            raise GatewayError("gateway_reference must be a non-empty string.")
        try:
            url  = f"{self.config['base_url']}/transaction/verify"
            # DRY v7: _build_headers() replaces the inline dict
            # that was also duplicated in _post_payment().
            resp = requests.post(
                url,
                json={"transaction_id": gateway_reference},
                headers=self._build_headers(),
                timeout=GATEWAY_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data    = resp.json()
            success = data.get("status_code") == "000"
            if success:
                return PayoutResult(
                    success=True,
                    gateway_reference=gateway_reference,
                    raw_response=data,
                )
            return PayoutResult(
                success=False,
                error_code=data.get("status_code", "UNKNOWN"),
                error_message=data.get("message", ""),
                raw_response=data,
            )
        except RequestsTimeout as exc:
            raise GatewayTimeoutError(
                f"RocketProcessor.verify_transaction: timeout: {exc}"
            ) from exc
        except Exception as exc:
            raise GatewayError(
                f"RocketProcessor.verify_transaction: error: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _post_payment(
        self, *, account_number: str, amount: Decimal, reference: str
    ) -> dict:
        """POST disbursement to Rocket API and return raw JSON."""
        try:
            url     = f"{self.config['base_url']}/api/v1/sendmoney"
            payload = {
                "sender":    self.config["merchant_number"],
                "receiver":  account_number,
                "amount":    str(amount),
                "currency":  "BDT",
                "reference": reference,
                "remark":    f"Payout {reference}",
            }
            # DRY v7: _build_headers() replaces the inline dict
            # that was also duplicated in verify_transaction().
            resp = requests.post(
                url, json=payload,
                headers=self._build_headers(),
                timeout=GATEWAY_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp.json()
        except RequestsTimeout as exc:
            raise GatewayTimeoutError(
                f"RocketProcessor._post_payment: timeout: {exc}"
            ) from exc
        except Exception as exc:
            raise GatewayError(
                f"RocketProcessor._post_payment: error: {exc}"
            ) from exc
