"""
INTEGRATIONS/shipping_carrier_integration.py
Bangladeshi courier integrations: Pathao, Steadfast, Redx, eCourier
"""
import logging
import requests

logger = logging.getLogger(__name__)


class CourierBase:
    name: str = ""
    api_url: str = ""

    def create_order(self, data: dict) -> dict:
        raise NotImplementedError

    def get_tracking(self, consignment_id: str) -> dict:
        raise NotImplementedError

    def cancel_order(self, consignment_id: str) -> dict:
        raise NotImplementedError


class SteadfastCourier(CourierBase):
    """Steadfast Courier API integration"""
    name = "steadfast"
    api_url = "https://portal.steadfast.com.bd/api/v1"

    def __init__(self, api_key: str, secret_key: str):
        self.headers = {
            "Api-Key": api_key,
            "Secret-Key": secret_key,
            "Content-Type": "application/json",
        }

    def create_order(self, data: dict) -> dict:
        """
        data keys: invoice, recipient_name, recipient_phone,
                   recipient_address, cod_amount, note
        """
        try:
            resp = requests.post(
                f"{self.api_url}/create_order",
                headers=self.headers,
                json=data,
                timeout=15,
            )
            return resp.json()
        except Exception as e:
            logger.error("Steadfast create_order error: %s", e)
            return {"status": 0, "error": str(e)}

    def get_tracking(self, consignment_id: str) -> dict:
        try:
            resp = requests.get(
                f"{self.api_url}/status_by_cid/{consignment_id}",
                headers=self.headers,
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def cancel_order(self, consignment_id: str) -> dict:
        return {"message": "Contact Steadfast support to cancel."}


class PathaoIntegration(CourierBase):
    """Pathao Courier API stub"""
    name = "pathao"

    def create_order(self, data):
        # TODO: Implement Pathao courier API
        return {"consignment_id": None, "status": "stub"}

    def get_tracking(self, consignment_id):
        return {"status": "unknown"}

    def cancel_order(self, consignment_id):
        return {"status": "stub"}


def get_courier(name: str, credentials: dict) -> CourierBase:
    couriers = {
        "steadfast": SteadfastCourier,
        "pathao": PathaoIntegration,
    }
    cls = couriers.get(name)
    if not cls:
        raise ValueError(f"Unknown courier: {name}")
    return cls(**credentials)
