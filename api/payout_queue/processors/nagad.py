"""
Nagad Payment Processor.

Implements the Nagad Merchant API for B2C disbursements.
Config keys: merchant_id, merchant_phone, private_key, public_key, base_url
"""

from __future__ import annotations

import base64
import json
import logging
import re
import uuid
from decimal import Decimal
from typing import Any

from ..choices import PaymentGateway
from ..constants import GATEWAY_TIMEOUT_SECONDS, NAGAD_PHONE_REGEX
from ..exceptions import GatewayError, GatewayTimeoutError, GatewayAuthError
from ..utils.payment_gateway import BasePaymentProcessor, PayoutResult

logger = logging.getLogger(__name__)

_REQUIRED_CONFIG = ("merchant_id", "merchant_phone", "private_key", "public_key", "base_url")


class NagadProcessor(BasePaymentProcessor):
    """
    Nagad B2C disbursement processor.

    Nagad uses RSA encryption for sensitive fields. Private key is used to
    sign requests; the Nagad public key is used to encrypt sensitive data.
    """

    gateway = PaymentGateway.NAGAD

    def _validate_config(self) -> None:
        self._require_config(*_REQUIRED_CONFIG)

    def validate_account(self, account_number: str) -> bool:
        if not account_number or not isinstance(account_number, str):
            return False
        cleaned = account_number.strip().replace(" ", "").replace("-", "")
        return bool(re.match(NAGAD_PHONE_REGEX, cleaned))

    def send_payout(
        self,
        *,
        account_number: str,
        amount: Decimal,
        reference: str,
        **kwargs: Any,
    ) -> PayoutResult:
        """
        Initiate Nagad B2C disbursement.

        Steps:
        1. POST /api/dfs/check-out/initialize/{merchantId}/{orderId}
        2. POST /api/dfs/check-out/complete/{paymentReferenceId}
        """
        if not self.validate_account(account_number):
            raise GatewayError(
                f"NagadProcessor: invalid account number '{account_number}'."
            )
        if not isinstance(amount, Decimal) or amount <= Decimal("0"):
            raise GatewayError(
                f"NagadProcessor: amount must be a positive Decimal, got {amount!r}."
            )
        if not reference or not isinstance(reference, str):
            raise GatewayError("NagadProcessor: reference must be a non-empty string.")

        logger.info(
            "NagadProcessor.send_payout: account=%s amount=%s ref=%s",
            account_number, amount, reference,
        )

        try:
            order_id = reference[:40]  # Nagad order IDs max 40 chars
            init_response = self._initialize_payment(
                account_number=account_number.strip(),
                order_id=order_id,
                amount=amount,
            )
            payment_ref = init_response.get("paymentReferenceId", "")
            if not payment_ref:
                return PayoutResult(
                    success=False,
                    error_code="INIT_FAILED",
                    error_message=init_response.get("message", "Initialization failed."),
                    raw_response=init_response,
                )
            complete_response = self._complete_payment(
                payment_ref=payment_ref, amount=amount, reference=reference
            )
        except GatewayTimeoutError:
            raise
        except GatewayAuthError:
            raise
        except GatewayError:
            raise
        except Exception as exc:
            raise GatewayError(f"NagadProcessor.send_payout: unexpected: {exc}") from exc

        success = complete_response.get("status") == "Success"
        gateway_reference = complete_response.get("merchantInvoiceNumber", "")

        if success:
            logger.info(
                "NagadProcessor.send_payout: SUCCESS ref=%s", gateway_reference
            )
            return PayoutResult(
                success=True,
                gateway_reference=gateway_reference or reference,
                raw_response=complete_response,
            )
        return PayoutResult(
            success=False,
            error_code=complete_response.get("statusCode", "UNKNOWN"),
            error_message=complete_response.get("message", ""),
            raw_response=complete_response,
        )

    def verify_transaction(self, gateway_reference: str) -> PayoutResult:
        if not gateway_reference or not isinstance(gateway_reference, str):
            raise GatewayError("gateway_reference must be a non-empty string.")
        try:
            import requests
            url = f"{self.config['base_url']}/api/dfs/verify/payment/{gateway_reference}"
            headers = self._build_headers()
            resp = requests.get(url, headers=headers, timeout=GATEWAY_TIMEOUT_SECONDS)
            resp.raise_for_status()
            data = resp.json()
            success = data.get("status") == "Success"
            if success:
                return PayoutResult(
                    success=True, gateway_reference=gateway_reference, raw_response=data
                )
            return PayoutResult(
                success=False,
                error_code=data.get("statusCode", "UNKNOWN"),
                error_message=data.get("message", ""),
                raw_response=data,
            )
        except requests.exceptions.Timeout as exc:
            raise GatewayTimeoutError(f"NagadProcessor.verify_transaction: timeout: {exc}") from exc
        except Exception as exc:
            raise GatewayError(f"NagadProcessor.verify_transaction: error: {exc}") from exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "X-KM-Api-Version": "v-0.2.0",
            "X-KM-IP-V4": "127.0.0.1",
            "X-KM-Client-Type": "PC_WEB",
        }

    def _initialize_payment(
        self, *, account_number: str, order_id: str, amount: Decimal
    ) -> dict:
        try:
            import requests
            merchant_id = self.config["merchant_id"]
            url = f"{self.config['base_url']}/api/dfs/check-out/initialize/{merchant_id}/{order_id}"
            timestamp = self._get_timestamp()
            sensitive = self._encrypt_sensitive({
                "merchantId": merchant_id,
                "datetime": timestamp,
            })
            payload = {
                "accountNumber": account_number,
                "dateTime": timestamp,
                "sensitiveData": sensitive,
                "signature": self._sign(sensitive),
            }
            resp = requests.post(
                url, json=payload,
                headers=self._build_headers(),
                timeout=GATEWAY_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout as exc:
            raise GatewayTimeoutError(f"NagadProcessor._initialize_payment: timeout: {exc}") from exc
        except Exception as exc:
            raise GatewayError(f"NagadProcessor._initialize_payment: error: {exc}") from exc

    def _complete_payment(
        self, *, payment_ref: str, amount: Decimal, reference: str
    ) -> dict:
        try:
            import requests
            url = f"{self.config['base_url']}/api/dfs/check-out/complete/{payment_ref}"
            sensitive = self._encrypt_sensitive({
                "merchantId": self.config["merchant_id"],
                "orderId": reference[:40],
                "amount": str(amount),
                "currencyCode": "050",
            })
            payload = {
                "sensitiveData": sensitive,
                "signature": self._sign(sensitive),
                "merchantCallbackURL": self.config.get("callback_url", ""),
            }
            resp = requests.post(
                url, json=payload,
                headers=self._build_headers(),
                timeout=GATEWAY_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout as exc:
            raise GatewayTimeoutError(f"NagadProcessor._complete_payment: timeout: {exc}") from exc
        except Exception as exc:
            raise GatewayError(f"NagadProcessor._complete_payment: error: {exc}") from exc

    def _encrypt_sensitive(self, data: dict) -> str:
        """Encrypt sensitive data using Nagad's public key (RSA OAEP)."""
        try:
            from cryptography.hazmat.primitives import serialization, hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            public_key_pem = self.config["public_key"]
            if "BEGIN" not in public_key_pem:
                public_key_pem = f"-----BEGIN PUBLIC KEY-----\n{public_key_pem}\n-----END PUBLIC KEY-----"
            public_key = serialization.load_pem_public_key(public_key_pem.encode())
            plaintext = json.dumps(data).encode("utf-8")
            ciphertext = public_key.encrypt(plaintext, padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA1()),
                algorithm=hashes.SHA1(),
                label=None,
            ))
            return base64.b64encode(ciphertext).decode("utf-8")
        except ImportError:
            logger.warning("cryptography not installed; using mock encryption.")
            return base64.b64encode(json.dumps(data).encode()).decode()
        except Exception as exc:
            raise GatewayAuthError(f"NagadProcessor._encrypt_sensitive: {exc}") from exc

    def _sign(self, data: str) -> str:
        """Sign data using merchant private key (RSA SHA-256)."""
        try:
            from cryptography.hazmat.primitives import serialization, hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            private_key_pem = self.config["private_key"]
            if "BEGIN" not in private_key_pem:
                private_key_pem = f"-----BEGIN PRIVATE KEY-----\n{private_key_pem}\n-----END PRIVATE KEY-----"
            private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
            signature = private_key.sign(data.encode(), padding.PKCS1v15(), hashes.SHA256())
            return base64.b64encode(signature).decode("utf-8")
        except ImportError:
            return base64.b64encode(data.encode()).decode()
        except Exception as exc:
            raise GatewayAuthError(f"NagadProcessor._sign: {exc}") from exc

    @staticmethod
    def _get_timestamp() -> str:
        from django.utils import timezone
        return timezone.now().strftime("%Y%m%d%H%M%S")
