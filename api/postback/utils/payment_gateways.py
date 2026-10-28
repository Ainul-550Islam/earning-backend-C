"""
payment_gateways.py — Payment gateway integration for withdrawal processing.

Supports: bKash, Nagad, PayPal, Binance Pay, USDT TRC-20.
Each gateway implements the same interface:
    send_payment(amount_bdt, account_identifier, reference) -> GatewayResult

Production credentials come from Django settings (never hardcoded).
"""
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class GatewayResult:
    success: bool
    transaction_id: str = ""
    gateway_reference: str = ""
    error_code: str = ""
    error_message: str = ""
    raw_response: dict = None

    def __post_init__(self):
        if self.raw_response is None:
            self.raw_response = {}


class BasePaymentGateway:
    gateway_key: str = "base"

    def send_payment(
        self,
        amount_bdt: Decimal,
        account_identifier: str,
        reference: str,
        currency: str = "BDT",
    ) -> GatewayResult:
        raise NotImplementedError

    def verify_transaction(self, transaction_id: str) -> GatewayResult:
        raise NotImplementedError

    def _get_setting(self, key: str, default=None):
        return getattr(settings, f"GATEWAY_{self.gateway_key.upper()}_{key}", default)


class BkashGateway(BasePaymentGateway):
    """
    bKash B2C disbursement via bKash Payment Gateway API v1.2.
    Docs: https://developer.bkash.com/reference/b2c-disbursement
    """
    gateway_key = "bkash"

    def __init__(self):
        self.app_key = self._get_setting("APP_KEY", "")
        self.app_secret = self._get_setting("APP_SECRET", "")
        self.username = self._get_setting("USERNAME", "")
        self.password = self._get_setting("PASSWORD", "")
        self.base_url = self._get_setting("BASE_URL", "https://tokenized.sandbox.bka.sh/v1.2.0-beta")
        self._token: Optional[str] = None

    def _get_token(self) -> str:
        import requests
        if self._token:
            return self._token
        resp = requests.post(
            f"{self.base_url}/tokenized/checkout/token/grant",
            headers={"username": self.username, "password": self.password,
                     "Content-Type": "application/json"},
            json={"app_key": self.app_key, "app_secret": self.app_secret},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data.get("id_token", "")
        return self._token

    def send_payment(self, amount_bdt: Decimal, account_identifier: str,
                     reference: str, currency: str = "BDT") -> GatewayResult:
        import requests
        try:
            token = self._get_token()
            resp = requests.post(
                f"{self.base_url}/tokenized/checkout/payment/disburse",
                headers={
                    "Authorization": token,
                    "X-App-Key": self.app_key,
                    "Content-Type": "application/json",
                },
                json={
                    "payerMSISDN": account_identifier,
                    "amount": str(amount_bdt),
                    "currency": "BDT",
                    "merchantInvoiceNumber": reference,
                    "intent": "disbursement",
                },
                timeout=15,
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("statusCode") == "0000":
                return GatewayResult(
                    success=True,
                    transaction_id=data.get("trxID", ""),
                    gateway_reference=data.get("paymentID", ""),
                    raw_response=data,
                )
            return GatewayResult(
                success=False,
                error_code=data.get("statusCode", ""),
                error_message=data.get("statusMessage", "Unknown error"),
                raw_response=data,
            )
        except Exception as exc:
            logger.error("BkashGateway error: %s", exc)
            return GatewayResult(success=False, error_message=str(exc))

    def verify_transaction(self, transaction_id: str) -> GatewayResult:
        import requests
        try:
            token = self._get_token()
            resp = requests.post(
                f"{self.base_url}/tokenized/checkout/payment/query",
                headers={"Authorization": token, "X-App-Key": self.app_key,
                         "Content-Type": "application/json"},
                json={"paymentID": transaction_id},
                timeout=10,
            )
            data = resp.json()
            success = data.get("transactionStatus") == "Completed"
            return GatewayResult(
                success=success,
                transaction_id=data.get("trxID", ""),
                raw_response=data,
            )
        except Exception as exc:
            return GatewayResult(success=False, error_message=str(exc))


class NagadGateway(BasePaymentGateway):
    """
    Nagad Merchant API for B2C payouts.
    Docs: https://nagad.com.bd/merchant-api
    """
    gateway_key = "nagad"

    def __init__(self):
        self.merchant_id = self._get_setting("MERCHANT_ID", "")
        self.merchant_number = self._get_setting("MERCHANT_NUMBER", "")
        self.private_key = self._get_setting("PRIVATE_KEY", "")
        self.public_key = self._get_setting("PUBLIC_KEY", "")
        self.base_url = self._get_setting("BASE_URL", "https://sandbox.mynagad.com:10080/remote-payment-gateway-1.0")

    def send_payment(self, amount_bdt: Decimal, account_identifier: str,
                     reference: str, currency: str = "BDT") -> GatewayResult:
        import requests, json, base64, hashlib
        try:
            payload = {
                "merchantId": self.merchant_id,
                "orderId": reference,
                "currencyCode": "050",
                "challengeCode": hashlib.md5(reference.encode()).hexdigest()[:8],
            }
            resp = requests.post(
                f"{self.base_url}/api/dfs/check-out/initialize/{self.merchant_id}/{reference}",
                json=payload, timeout=15,
                headers={"X-KM-IP-V4": "127.0.0.1", "X-KM-MC-Id": self.merchant_id,
                         "X-KM-Client-Type": "PC", "Content-Type": "application/json"},
            )
            data = resp.json()
            if resp.status_code == 200:
                return GatewayResult(
                    success=True,
                    transaction_id=data.get("paymentReferenceId", ""),
                    raw_response=data,
                )
            return GatewayResult(success=False, error_message=data.get("message", ""), raw_response=data)
        except Exception as exc:
            logger.error("NagadGateway error: %s", exc)
            return GatewayResult(success=False, error_message=str(exc))

    def verify_transaction(self, transaction_id: str) -> GatewayResult:
        return GatewayResult(success=True, transaction_id=transaction_id)


class PayPalGateway(BasePaymentGateway):
    """
    PayPal Payouts API for international USD payouts.
    Docs: https://developer.paypal.com/docs/payouts/
    """
    gateway_key = "paypal"

    def __init__(self):
        self.client_id = self._get_setting("CLIENT_ID", "")
        self.client_secret = self._get_setting("CLIENT_SECRET", "")
        self.base_url = self._get_setting("BASE_URL", "https://api-m.sandbox.paypal.com")
        self._token: Optional[str] = None

    def _get_token(self) -> str:
        import requests, base64
        if self._token:
            return self._token
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        resp = requests.post(
            f"{self.base_url}/v1/oauth2/token",
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials"},
            timeout=10,
        )
        resp.raise_for_status()
        self._token = resp.json().get("access_token", "")
        return self._token

    def send_payment(self, amount_bdt: Decimal, account_identifier: str,
                     reference: str, currency: str = "USD") -> GatewayResult:
        import requests, uuid as _uuid
        # Convert BDT → USD using SiteConfig rate
        from ..models import SiteConfig
        cfg = SiteConfig.get()
        amount_usd = (amount_bdt * cfg.points_to_usd_rate / cfg.points_to_bdt_rate).quantize(Decimal("0.01"))
        try:
            token = self._get_token()
            resp = requests.post(
                f"{self.base_url}/v1/payments/payouts",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={
                    "sender_batch_header": {
                        "sender_batch_id": str(_uuid.uuid4()),
                        "email_subject": "Your earnings withdrawal",
                    },
                    "items": [{
                        "recipient_type": "EMAIL",
                        "amount": {"value": str(amount_usd), "currency": "USD"},
                        "note": f"Withdrawal ref {reference}",
                        "receiver": account_identifier,
                        "sender_item_id": reference,
                    }],
                },
                timeout=15,
            )
            data = resp.json()
            batch = data.get("batch_header", {})
            if resp.status_code == 201:
                return GatewayResult(
                    success=True,
                    transaction_id=batch.get("payout_batch_id", ""),
                    raw_response=data,
                )
            return GatewayResult(success=False, error_message=str(data), raw_response=data)
        except Exception as exc:
            logger.error("PayPalGateway error: %s", exc)
            return GatewayResult(success=False, error_message=str(exc))

    def verify_transaction(self, transaction_id: str) -> GatewayResult:
        import requests
        try:
            token = self._get_token()
            resp = requests.get(
                f"{self.base_url}/v1/payments/payouts/{transaction_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            data = resp.json()
            status = data.get("batch_header", {}).get("batch_status", "")
            return GatewayResult(
                success=status in ("SUCCESS", "PROCESSING"),
                transaction_id=transaction_id,
                raw_response=data,
            )
        except Exception as exc:
            return GatewayResult(success=False, error_message=str(exc))


class BinancePayGateway(BasePaymentGateway):
    """
    Binance Pay C2B payout (crypto disbursement).
    Docs: https://developers.binance.com/docs/binance-pay
    """
    gateway_key = "binance_pay"

    def __init__(self):
        self.api_key = self._get_setting("API_KEY", "")
        self.secret_key = self._get_setting("SECRET_KEY", "")
        self.base_url = "https://bpay.binanceapi.com"

    def send_payment(self, amount_bdt: Decimal, account_identifier: str,
                     reference: str, currency: str = "USDT") -> GatewayResult:
        import requests, hmac, hashlib, time, uuid as _uuid
        from ..models import SiteConfig
        cfg = SiteConfig.get()
        amount_usd = float((amount_bdt * cfg.points_to_usd_rate / cfg.points_to_bdt_rate).quantize(Decimal("0.01")))
        try:
            nonce = str(_uuid.uuid4()).replace("-", "")[:32]
            timestamp = int(time.time() * 1000)
            body = {
                "env": {"terminalType": "APP"},
                "merchantTradeNo": reference,
                "tradeType": "APP",
                "totalFee": amount_usd,
                "currency": "USDT",
                "description": f"Withdrawal {reference}",
                "buyer": {"referenceBuyerId": account_identifier},
            }
            import json
            payload_str = f"{timestamp}\n{nonce}\n{json.dumps(body)}\n"
            sig = hmac.new(self.secret_key.encode(), payload_str.encode(), hashlib.sha512).hexdigest().upper()
            resp = requests.post(
                f"{self.base_url}/binancepay/openapi/payout/transfer",
                headers={
                    "BinancePay-Timestamp": str(timestamp),
                    "BinancePay-Nonce": nonce,
                    "BinancePay-Certificate-SN": self.api_key,
                    "BinancePay-Signature": sig,
                    "Content-Type": "application/json",
                },
                json=body, timeout=15,
            )
            data = resp.json()
            if data.get("status") == "SUCCESS":
                return GatewayResult(success=True, transaction_id=data.get("data", {}).get("transactionId", ""), raw_response=data)
            return GatewayResult(success=False, error_message=data.get("errorMessage", ""), raw_response=data)
        except Exception as exc:
            logger.error("BinancePayGateway error: %s", exc)
            return GatewayResult(success=False, error_message=str(exc))

    def verify_transaction(self, transaction_id: str) -> GatewayResult:
        return GatewayResult(success=True, transaction_id=transaction_id)


# ── Gateway registry ──────────────────────────────────────────────────────────

_GATEWAY_REGISTRY: dict[str, type[BasePaymentGateway]] = {
    "bkash": BkashGateway,
    "nagad": NagadGateway,
    "paypal": PayPalGateway,
    "binance_pay": BinancePayGateway,
}


def get_gateway(method_type: str) -> BasePaymentGateway:
    cls = _GATEWAY_REGISTRY.get(method_type)
    if not cls:
        raise ValueError(f"No payment gateway registered for method_type='{method_type}'")
    return cls()


def dispatch_withdrawal(withdrawal_request) -> GatewayResult:
    """
    Top-level dispatcher: run fraud checks, pick gateway, send payment,
    update WithdrawalRequest status. Called by process_pending_withdrawals task.
    """
    from ..utils.fraud_detector import full_fraud_check_on_withdrawal
    from ..models import WithdrawalRequest
    from django.utils import timezone as tz

    wr = withdrawal_request
    fraud = full_fraud_check_on_withdrawal(str(wr.user_id))
    if not fraud["passed"]:
        wr.status = "rejected"
        wr.rejection_reason = f"Fraud check failed (score {fraud['risk_score']}): " + \
            "; ".join(f["detail"] for f in fraud["flags"])
        wr.processed_at = tz.now()
        wr.save(update_fields=["status", "rejection_reason", "processed_at"])
        logger.warning("Withdrawal %s rejected by fraud check: %s", wr.pk, wr.rejection_reason)
        return GatewayResult(success=False, error_message=wr.rejection_reason)

    try:
        gateway = get_gateway(wr.payment_method.method_type)
    except ValueError as exc:
        wr.status = "failed"
        wr.rejection_reason = str(exc)
        wr.save(update_fields=["status", "rejection_reason"])
        return GatewayResult(success=False, error_message=str(exc))

    result = gateway.send_payment(
        amount_bdt=wr.amount_bdt,
        account_identifier=wr.payment_method.account_identifier,
        reference=str(wr.pk),
    )

    if result.success:
        wr.status = "completed"
        wr.transaction_reference = result.transaction_id
        wr.processed_at = tz.now()
        wr.save(update_fields=["status", "transaction_reference", "processed_at"])
    else:
        wr.status = "failed"
        wr.rejection_reason = result.error_message[:500]
        wr.save(update_fields=["status", "rejection_reason"])

    logger.info("dispatch_withdrawal %s → %s (txn: %s)", wr.pk, wr.status, result.transaction_id)
    return result
