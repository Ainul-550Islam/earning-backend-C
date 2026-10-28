"""
services/payment_gateway.py — Pluggable payment gateway integration.

Supports: bKash, Nagad, PayPal Payouts, Binance Pay.
Each gateway implements PaymentGatewayBase.

Usage:
    from api.postback.services.payment_gateway import get_gateway
    gw = get_gateway("bkash")
    result = gw.send_payout(withdrawal)
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PayoutResult:
    success: bool
    transaction_id: str = ""
    gateway_reference: str = ""
    error_code: str = ""
    error_message: str = ""
    raw_response: dict = None

    @classmethod
    def ok(cls, txn_id: str, ref: str = "", raw: dict = None) -> "PayoutResult":
        return cls(success=True, transaction_id=txn_id, gateway_reference=ref, raw_response=raw or {})

    @classmethod
    def fail(cls, code: str, message: str, raw: dict = None) -> "PayoutResult":
        return cls(success=False, error_code=code, error_message=message, raw_response=raw or {})


class PaymentGatewayBase(ABC):
    """Abstract base for all payout gateways."""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def send_payout(self, withdrawal) -> PayoutResult:
        """
        Dispatch the actual payout for a WithdrawalRequest.
        Must be idempotent — withdrawal.pk is the idempotency key.
        """

    @abstractmethod
    def check_status(self, transaction_id: str) -> PayoutResult:
        """Query the gateway for the status of a sent payout."""

    @abstractmethod
    def get_balance(self) -> Optional[Decimal]:
        """Return the gateway wallet balance (for ops monitoring). None if unsupported."""


class BkashGateway(PaymentGatewayBase):
    """
    bKash B2C Disbursement API integration.
    Docs: https://developer.bka.sh/docs/b2c-api
    """
    BASE_URL = "https://tokenized.pay.bka.sh/v1.2.0-beta"

    def _get_token(self) -> str:
        import requests
        resp = requests.post(
            f"{self.BASE_URL}/tokenized/checkout/token/grant",
            json={
                "app_key": self.config["app_key"],
                "app_secret": self.config["app_secret"],
            },
            headers={
                "username": self.config["username"],
                "password": self.config["password"],
                "content-type": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["id_token"]

    def send_payout(self, withdrawal) -> PayoutResult:
        import requests
        try:
            token = self._get_token()
            payload = {
                "amount": str(withdrawal.amount_bdt),
                "currency": "BDT",
                "intent": "disbursement",
                "merchantInvoiceNumber": f"WD-{withdrawal.pk}",
                "receiverMSISDN": withdrawal.payment_method.account_identifier,
                "reference": f"EarnApp withdrawal {withdrawal.pk}",
            }
            resp = requests.post(
                f"{self.BASE_URL}/tokenized/checkout/create",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-APP-Key": self.config["app_key"],
                    "content-type": "application/json",
                },
                timeout=20,
            )
            data = resp.json()
            if data.get("statusCode") == "0000":
                return PayoutResult.ok(
                    txn_id=data.get("trxID", ""),
                    ref=data.get("merchantInvoiceNumber", ""),
                    raw=data,
                )
            return PayoutResult.fail(
                code=data.get("statusCode", "UNKNOWN"),
                message=data.get("statusMessage", "bKash error"),
                raw=data,
            )
        except Exception as exc:
            logger.error("bKash payout failed: %s", exc)
            return PayoutResult.fail("EXCEPTION", str(exc))

    def check_status(self, transaction_id: str) -> PayoutResult:
        import requests
        try:
            token = self._get_token()
            resp = requests.post(
                f"{self.BASE_URL}/tokenized/checkout/payment/status",
                json={"paymentID": transaction_id},
                headers={"Authorization": f"Bearer {token}", "X-APP-Key": self.config["app_key"]},
                timeout=15,
            )
            data = resp.json()
            if data.get("transactionStatus") == "Completed":
                return PayoutResult.ok(txn_id=transaction_id, raw=data)
            return PayoutResult.fail(
                code=data.get("transactionStatus", "UNKNOWN"),
                message=data.get("statusMessage", ""),
                raw=data,
            )
        except Exception as exc:
            return PayoutResult.fail("EXCEPTION", str(exc))

    def get_balance(self) -> Optional[Decimal]:
        return None  # bKash does not expose merchant balance via API


class NagadGateway(PaymentGatewayBase):
    """Nagad Merchant API (B2C disbursement)."""
    BASE_URL = "https://api.mynagad.com/api/dfs"

    def send_payout(self, withdrawal) -> PayoutResult:
        import requests, hashlib, hmac, time, base64, json
        try:
            ts = str(int(time.time() * 1000))
            merchant_id = self.config["merchant_id"]
            body = {
                "merchantId": merchant_id,
                "orderId": f"WD-{withdrawal.pk}",
                "amount": str(withdrawal.amount_bdt),
                "currencyCode": "050",
                "challenge": ts,
            }
            body_str = json.dumps(body, separators=(",", ":"))
            sig = hmac.new(
                self.config["merchant_private_key"].encode(),
                body_str.encode(),
                hashlib.sha256,
            ).hexdigest()
            resp = requests.post(
                f"{self.BASE_URL}/check-out/initialize/{merchant_id}/{f'WD-{withdrawal.pk}'}",
                json=body,
                headers={
                    "X-KM-Api-Version": "v-0.2.0",
                    "X-KM-IP-V4": "127.0.0.1",
                    "X-KM-Client-Type": "PC_WEB",
                    "Signature": sig,
                    "DateTime": ts,
                },
                timeout=20,
            )
            data = resp.json()
            if resp.status_code == 200:
                return PayoutResult.ok(txn_id=data.get("orderId", ""), raw=data)
            return PayoutResult.fail(code=str(resp.status_code), message=str(data), raw=data)
        except Exception as exc:
            logger.error("Nagad payout failed: %s", exc)
            return PayoutResult.fail("EXCEPTION", str(exc))

    def check_status(self, transaction_id: str) -> PayoutResult:
        return PayoutResult.fail("NOT_IMPLEMENTED", "Nagad status check not implemented")

    def get_balance(self) -> Optional[Decimal]:
        return None


class PayPalPayoutsGateway(PaymentGatewayBase):
    """PayPal Payouts API (international)."""
    BASE_URL = "https://api-m.paypal.com"

    def _get_access_token(self) -> str:
        import requests
        from base64 import b64encode
        creds = b64encode(
            f"{self.config['client_id']}:{self.config['client_secret']}".encode()
        ).decode()
        resp = requests.post(
            f"{self.BASE_URL}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {creds}"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def send_payout(self, withdrawal) -> PayoutResult:
        import requests, uuid as _uuid
        try:
            token = self._get_access_token()
            payload = {
                "sender_batch_header": {
                    "sender_batch_id": f"WD-{withdrawal.pk}",
                    "email_subject": "EarnApp Payout",
                },
                "items": [{
                    "recipient_type": "EMAIL",
                    "amount": {"value": str(withdrawal.amount_bdt), "currency": "USD"},
                    "note": "EarnApp earnings payout",
                    "sender_item_id": str(withdrawal.pk),
                    "receiver": withdrawal.payment_method.account_identifier,
                }],
            }
            resp = requests.post(
                f"{self.BASE_URL}/v1/payments/payouts",
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=20,
            )
            data = resp.json()
            if resp.status_code in (200, 201):
                return PayoutResult.ok(
                    txn_id=data.get("batch_header", {}).get("payout_batch_id", ""),
                    raw=data,
                )
            return PayoutResult.fail(
                code=data.get("name", "PAYPAL_ERROR"),
                message=data.get("message", ""),
                raw=data,
            )
        except Exception as exc:
            logger.error("PayPal payout failed: %s", exc)
            return PayoutResult.fail("EXCEPTION", str(exc))

    def check_status(self, transaction_id: str) -> PayoutResult:
        import requests
        try:
            token = self._get_access_token()
            resp = requests.get(
                f"{self.BASE_URL}/v1/payments/payouts/{transaction_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            data = resp.json()
            batch_status = data.get("batch_header", {}).get("batch_status", "")
            if batch_status == "SUCCESS":
                return PayoutResult.ok(txn_id=transaction_id, raw=data)
            return PayoutResult.fail(code=batch_status, message="", raw=data)
        except Exception as exc:
            return PayoutResult.fail("EXCEPTION", str(exc))

    def get_balance(self) -> Optional[Decimal]:
        return None


class ManualGateway(PaymentGatewayBase):
    """
    Manual gateway — for cash, bank transfer, or gift cards.
    Records intent; actual dispatch is handled by admin staff.
    """
    def send_payout(self, withdrawal) -> PayoutResult:
        return PayoutResult.ok(
            txn_id=f"MANUAL-{withdrawal.pk}",
            ref="Requires manual processing",
        )

    def check_status(self, transaction_id: str) -> PayoutResult:
        return PayoutResult.ok(txn_id=transaction_id)

    def get_balance(self) -> Optional[Decimal]:
        return None


# ── Gateway registry ───────────────────────────────────────────────────────────

_GATEWAY_REGISTRY = {
    "bkash": BkashGateway,
    "nagad": NagadGateway,
    "paypal": PayPalPayoutsGateway,
    "amazon_gift": ManualGateway,
    "bank_transfer": ManualGateway,
    "skrill": ManualGateway,
    "wise": ManualGateway,
    "binance_pay": ManualGateway,
    "usdt_trc20": ManualGateway,
    "bitcoin": ManualGateway,
}


def get_gateway(method_type: str) -> PaymentGatewayBase:
    """Return instantiated gateway for a PaymentMethod.method_type."""
    from django.conf import settings as djs
    gateway_configs = getattr(djs, "PAYMENT_GATEWAY_CONFIGS", {})
    config = gateway_configs.get(method_type, {})
    cls = _GATEWAY_REGISTRY.get(method_type, ManualGateway)
    return cls(config)


def dispatch_withdrawal(withdrawal) -> PayoutResult:
    """
    High-level: look up gateway from withdrawal.payment_method.method_type,
    send the payout, update withdrawal status, return result.
    """
    method_type = withdrawal.payment_method.method_type
    gw = get_gateway(method_type)
    result = gw.send_payout(withdrawal)

    from django.utils import timezone as tz
    if result.success:
        withdrawal.status = "completed"
        withdrawal.transaction_reference = result.transaction_id
        withdrawal.processed_at = tz.now()
        withdrawal.save(update_fields=["status", "transaction_reference", "processed_at"])
        logger.info("Withdrawal %s completed via %s txn=%s", withdrawal.pk, method_type, result.transaction_id)
    else:
        withdrawal.status = "failed"
        withdrawal.admin_note = f"Gateway error: [{result.error_code}] {result.error_message}"
        withdrawal.save(update_fields=["status", "admin_note"])
        logger.error("Withdrawal %s FAILED via %s: %s", withdrawal.pk, method_type, result.error_message)

    return result
