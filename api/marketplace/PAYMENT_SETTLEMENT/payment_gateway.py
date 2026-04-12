"""payment_gateway.py — Gateway abstraction"""
from abc import ABC, abstractmethod


class BaseGateway(ABC):
    name: str = ""

    @abstractmethod
    def initiate(self, amount: float, phone: str, order_id: str) -> dict:
        pass

    @abstractmethod
    def verify(self, transaction_id: str) -> bool:
        pass


class BkashGateway(BaseGateway):
    name = "bkash"

    def initiate(self, amount, phone, order_id):
        # TODO: integrate bKash payment API
        return {"status": "pending", "gateway": "bkash", "amount": amount}

    def verify(self, transaction_id):
        # TODO: verify via bKash API
        return False


class NagadGateway(BaseGateway):
    name = "nagad"

    def initiate(self, amount, phone, order_id):
        return {"status": "pending", "gateway": "nagad", "amount": amount}

    def verify(self, transaction_id):
        return False


def get_gateway(method: str) -> BaseGateway:
    gateways = {"bkash": BkashGateway, "nagad": NagadGateway}
    cls = gateways.get(method)
    if not cls:
        raise ValueError(f"Unsupported gateway: {method}")
    return cls()
