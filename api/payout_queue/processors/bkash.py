"""
payout_queue/processors/bkash.py  ← DRY v7 (built on v2)

DRY CHANGE v7:

  ① _app_headers(token) helper added  (replaces 2 duplicate dicts)

     Before:  _execute_payment() and _query_payment() each built an identical
              3-key authenticated header dict inline:
                  headers = {
                      "Content-Type": "application/json",
                      "Authorization": token,
                      "X-APP-Key": self.config["app_key"],
                  }
              If bKash adds a new required header (e.g. X-Request-ID), it must
              be added in two places.

     After:   Both methods call `headers = self._app_headers(token)` — one
              definition, two call sites.

     NOTE:    _get_grant_token() uses a different header structure
              (username + password instead of Authorization + X-APP-Key) so
              it is intentionally NOT included in _app_headers().

v2 change preserved: validate_account() uses self._normalise_account().
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Any, Optional

from ..choices import PaymentGateway
from ..constants import GATEWAY_TIMEOUT_SECONDS, BKASH_PHONE_REGEX
from ..exceptions import GatewayError, GatewayTimeoutError, GatewayAuthError
from ..utils.payment_gateway import BasePaymentProcessor, PayoutResult
import requests
from requests.exceptions import Timeout as RequestsTimeout

logger = logging.getLogger(__name__)

_REQUIRED_CONFIG = ("app_key", "app_secret", "username", "password", "base_url")

class BkashProcessor(BasePaymentProcessor):
    """
    bKash B2C disbursement processor.

    All HTTP calls are wrapped in try/except. On timeout, GatewayTimeoutError
    is raised. On auth failure, GatewayAuthError is raised. All other errors
    raise GatewayError.
    """

    gateway = PaymentGateway.BKASH

    def _validate_config(self) -> None:
        self._require_config(*_REQUIRED_CONFIG)

    # ------------------------------------------------------------------
    # DRY v7: shared authenticated header helper
    # ------------------------------------------------------------------

    def _app_headers(self, token: str) -> dict:
        """
        DRY v7: Returns the authenticated JSON headers for bKash API calls.

        Before:  _execute_payment() and _query_payment() each built this
                 identical 3-key dict inline.  Any new required header
                 (e.g. X-Request-ID, X-Idempotency-Key) would need two edits.
        After:   Both methods call self._app_headers(token).

        NOTE: _get_grant_token() uses a different structure (username/password
        credentials instead of Bearer token + app key) — intentionally excluded.
        """
        return {
            "Content-Type":  "application/json",
            "Authorization": token,
            "X-APP-Key":     self.config["app_key"],
        }

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def validate_account(self, account_number: str) -> bool:
        """
        Validate a bKash wallet number (Bangladesh mobile: 01XXXXXXXXX).

        FIX v2: uses self._normalise_account() from BasePaymentProcessor.
        """
        cleaned = self._normalise_account(account_number)
        if not cleaned:
            return False
        return bool(re.match(BKASH_PHONE_REGEX, cleaned))

    def send_payout(
        self,
        *,
        account_number: str,
        amount: Decimal,
        reference: str,
        **kwargs: Any,
    ) -> PayoutResult:
        """
        Initiate a bKash B2C disbursement.

        Steps:
        1. Obtain grant token.
        2. POST /tokenized/checkout/disbursement.

        Returns:
            PayoutResult

        Raises:
            GatewayTimeoutError: On network timeout.
            GatewayAuthError:    On token failure.
            GatewayError:        On API error.
        """
        if not self.validate_account(account_number):
            raise GatewayError(
                f"BkashProcessor: invalid account number '{account_number}'."
            )
        if not isinstance(amount, Decimal) or amount <= Decimal("0"):
            raise GatewayError(
                f"BkashProcessor: amount must be a positive Decimal, got {amount!r}."
            )
        if not reference or not isinstance(reference, str):
            raise GatewayError("BkashProcessor: reference must be a non-empty string.")

        logger.info(
            "BkashProcessor.send_payout: account=%s amount=%s ref=%s",
            account_number, amount, reference,
        )

        try:
            token    = self._get_grant_token()
            response = self._execute_payment(
                token=token,
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
                f"BkashProcessor.send_payout: unexpected error: {exc}"
            ) from exc

        success           = response.get("statusCode") == "0000"
        gateway_reference = response.get("trxID", "")

        if success:
            logger.info(
                "BkashProcessor.send_payout: SUCCESS trxID=%s ref=%s",
                gateway_reference, reference,
            )
            return PayoutResult(
                success=True,
                gateway_reference=gateway_reference,
                raw_response=response,
            )
        else:
            error_code    = response.get("statusCode", "UNKNOWN")
            error_message = response.get("statusMessage", "Unknown bKash error.")
            logger.warning(
                "BkashProcessor.send_payout: FAILED code=%s msg=%s ref=%s",
                error_code, error_message, reference,
            )
            return PayoutResult(
                success=False,
                error_code=error_code,
                error_message=error_message,
                raw_response=response,
            )

    def verify_transaction(self, gateway_reference: str) -> PayoutResult:
        """Verify a bKash transaction by trxID."""
        if not gateway_reference or not isinstance(gateway_reference, str):
            raise GatewayError("gateway_reference must be a non-empty string.")

        logger.debug(
            "BkashProcessor.verify_transaction: trxID=%s", gateway_reference
        )

        try:
            token    = self._get_grant_token()
            response = self._query_payment(token=token, trx_id=gateway_reference)
        except Exception as exc:
            raise GatewayError(
                f"BkashProcessor.verify_transaction: error: {exc}"
            ) from exc

        success = response.get("transactionStatus") == "Completed"
        if success:
            return PayoutResult(
                success=True,
                gateway_reference=gateway_reference,
                raw_response=response,
            )
        return PayoutResult(
            success=False,
            error_code=response.get("statusCode", "UNKNOWN"),
            error_message=response.get("statusMessage", ""),
            raw_response=response,
        )

    # ------------------------------------------------------------------
    # Private HTTP helpers
    # ------------------------------------------------------------------

    def _get_grant_token(self) -> str:
        """
        Obtain a bKash grant token.

        Uses credential-based headers (username + password) — intentionally
        different from _app_headers() which uses token + app_key.
        """
        try:
            url     = f"{self.config['base_url']}/tokenized/checkout/token/grant"
            headers = {
                "Content-Type": "application/json",
                "username":     self.config["username"],
                "password":     self.config["password"],
            }
            payload = {
                "app_key":    self.config["app_key"],
                "app_secret": self.config["app_secret"],
            }
            resp = requests.post(
                url, json=payload, headers=headers,
                timeout=GATEWAY_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data  = resp.json()
            token = data.get("id_token") or data.get("access_token")
            if not token:
                raise GatewayAuthError(
                    f"BkashProcessor._get_grant_token: no token in response: {data}"
                )
            return token
        except GatewayAuthError:
            raise
        except RequestsTimeout as exc:
            raise GatewayTimeoutError(
                f"BkashProcessor._get_grant_token: timeout: {exc}"
            ) from exc
        except Exception as exc:
            raise GatewayAuthError(
                f"BkashProcessor._get_grant_token: error: {exc}"
            ) from exc

    def _execute_payment(
        self,
        *,
        token: str,
        account_number: str,
        amount: Decimal,
        reference: str,
    ) -> dict:
        """POST to bKash disburse endpoint and return raw JSON."""
        try:
            url     = f"{self.config['base_url']}/tokenized/checkout/disbursement"
            # DRY v7: _app_headers() replaces the inline dict that was also in _query_payment.
            headers = self._app_headers(token)
            payload = {
                "amount":                str(amount),
                "currency":              "BDT",
                "intent":                "disbursement",
                "merchantInvoiceNumber": reference,
                "b2cPaymentInfo": [
                    {
                        "mobile": account_number,
                        "amount": str(amount),
                    }
                ],
            }
            resp = requests.post(
                url, json=payload, headers=headers,
                timeout=GATEWAY_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp.json()
        except RequestsTimeout as exc:
            raise GatewayTimeoutError(
                f"BkashProcessor._execute_payment: timeout: {exc}"
            ) from exc
        except Exception as exc:
            raise GatewayError(
                f"BkashProcessor._execute_payment: error: {exc}"
            ) from exc

    def _query_payment(self, *, token: str, trx_id: str) -> dict:
        """Query bKash transaction status."""
        try:
            url     = f"{self.config['base_url']}/tokenized/checkout/transaction/status"
            # DRY v7: _app_headers() replaces the inline dict that was also in _execute_payment.
            headers = self._app_headers(token)
            resp    = requests.post(
                url, json={"trxID": trx_id}, headers=headers,
                timeout=GATEWAY_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp.json()
        except RequestsTimeout as exc:
            raise GatewayTimeoutError(
                f"BkashProcessor._query_payment: timeout: {exc}"
            ) from exc
        except Exception as exc:
            raise GatewayError(
                f"BkashProcessor._query_payment: error: {exc}"
            ) from exc
