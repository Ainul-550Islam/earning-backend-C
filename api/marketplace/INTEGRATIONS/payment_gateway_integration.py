"""
INTEGRATIONS/payment_gateway_integration.py
Unified payment gateway integration layer.
Supported: bKash, Nagad, Rocket (Bangladesh mobile banking)
"""
import logging
import requests
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class PaymentGatewayBase(ABC):
    base_url: str = ""
    name: str = ""

    @abstractmethod
    def create_payment(self, amount: float, phone: str, reference: str) -> dict:
        pass

    @abstractmethod
    def execute_payment(self, payment_id: str, token: str) -> dict:
        pass

    @abstractmethod
    def query_payment(self, payment_id: str) -> dict:
        pass

    @abstractmethod
    def refund(self, payment_id: str, amount: float) -> dict:
        pass


class BkashIntegration(PaymentGatewayBase):
    """bKash PGW v1.2 integration (sandbox/production toggle via settings)"""
    name = "bkash"

    def __init__(self, app_key: str, app_secret: str, username: str, password: str, sandbox: bool = True):
        self.app_key = app_key
        self.app_secret = app_secret
        self.username = username
        self.password = password
        self.base_url = (
            "https://tokenized.sandbox.bka.sh/v1.2.0-beta"
            if sandbox
            else "https://tokenized.pay.bka.sh/v1.2.0-beta"
        )
        self._token = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        resp = requests.post(
            f"{self.base_url}/tokenized/checkout/token/grant",
            headers={"username": self.username, "password": self.password,
                     "Content-Type": "application/json"},
            json={"app_key": self.app_key, "app_secret": self.app_secret},
            timeout=10,
        )
        self._token = resp.json().get("id_token", "")
        return self._token

    def create_payment(self, amount: float, phone: str, reference: str) -> dict:
        token = self._get_token()
        try:
            resp = requests.post(
                f"{self.base_url}/tokenized/checkout/create",
                headers={"Authorization": token, "X-APP-Key": self.app_key,
                         "Content-Type": "application/json"},
                json={
                    "mode": "0011",
                    "payerReference": phone,
                    "callbackURL": "https://yourdomain.com/api/marketplace/payment/bkash/callback/",
                    "amount": str(amount),
                    "currency": "BDT",
                    "intent": "sale",
                    "merchantInvoiceNumber": reference,
                },
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            logger.error("bKash create_payment error: %s", e)
            return {"statusCode": "9999", "statusMessage": str(e)}

    def execute_payment(self, payment_id: str, token: str) -> dict:
        try:
            resp = requests.post(
                f"{self.base_url}/tokenized/checkout/execute",
                headers={"Authorization": self._get_token(), "X-APP-Key": self.app_key,
                         "Content-Type": "application/json"},
                json={"paymentID": payment_id},
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            logger.error("bKash execute_payment error: %s", e)
            return {"statusCode": "9999"}

    def query_payment(self, payment_id: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/tokenized/checkout/payment/status",
            headers={"Authorization": self._get_token(), "X-APP-Key": self.app_key,
                     "Content-Type": "application/json"},
            json={"paymentID": payment_id},
            timeout=10,
        )
        return resp.json()

    def refund(self, payment_id: str, amount: float) -> dict:
        resp = requests.post(
            f"{self.base_url}/tokenized/checkout/payment/refund",
            headers={"Authorization": self._get_token(), "X-APP-Key": self.app_key,
                     "Content-Type": "application/json"},
            json={"paymentID": payment_id, "amount": str(amount), "currency": "BDT",
                  "reason": "Customer refund"},
            timeout=10,
        )
        return resp.json()


class NagadIntegration(PaymentGatewayBase):
    """Nagad PGW integration (stub — implement with Nagad merchant API)"""
    name = "nagad"

    def __init__(self, merchant_id: str, merchant_number: str, public_key: str,
                 private_key: str, sandbox: bool = True):
        self.merchant_id = merchant_id
        self.merchant_number = merchant_number
        self.public_key = public_key
        self.private_key = private_key
        self.base_url = (
            "https://sandbox.mynagad.com:10080/remote-payment-gateway-1.0"
            if sandbox
            else "https://api.mynagad.com/api/dfs"
        )

    def create_payment(self, amount, phone, reference) -> dict:
        # TODO: implement Nagad PGW create payment
        return {"status": "pending", "reference": reference}

    def execute_payment(self, payment_id, token) -> dict:
        return {"status": "pending"}

    def query_payment(self, payment_id) -> dict:
        return {"status": "unknown"}

    def refund(self, payment_id, amount) -> dict:
        return {"status": "pending"}


def get_payment_gateway(method: str, settings_dict: dict) -> PaymentGatewayBase:
    """Factory — returns the correct gateway instance."""
    if method == "bkash":
        return BkashIntegration(**settings_dict)
    elif method == "nagad":
        return NagadIntegration(**settings_dict)
    raise ValueError(f"Unsupported payment method: {method}")
