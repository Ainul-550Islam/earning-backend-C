"""
SHIPPING_LOGISTICS/courier_integration.py — Unified Courier API Integration Hub
"""
import logging
from api.marketplace.INTEGRATIONS.shipping_carrier_integration import get_courier, CourierBase

logger = logging.getLogger(__name__)


class CourierHub:
    """Factory + unified interface for all courier integrations."""

    _instances: dict = {}

    @classmethod
    def get(cls, carrier_code: str) -> CourierBase:
        if carrier_code not in cls._instances:
            from django.conf import settings
            credentials = getattr(settings, "COURIER_CREDENTIALS", {}).get(carrier_code, {})
            cls._instances[carrier_code] = get_courier(carrier_code, credentials)
        return cls._instances[carrier_code]

    @classmethod
    def create_shipment(cls, carrier_code: str, order) -> dict:
        from api.marketplace.SHIPPING_LOGISTICS.shipping_label import generate_label_data
        courier = cls.get(carrier_code)
        label   = generate_label_data(order, carrier_code)
        return courier.create_order({
            "invoice":           label["barcode"],
            "recipient_name":    label["to_name"],
            "recipient_phone":   label["to_phone"],
            "recipient_address": label["to_address"],
            "cod_amount":        label["cod_amount"],
            "note":              f"Order #{order.order_number}",
            "weight":            label["weight_grams"] / 1000,
        })

    @classmethod
    def track(cls, carrier_code: str, tracking_no: str) -> dict:
        try:
            return cls.get(carrier_code).get_tracking(tracking_no)
        except Exception as e:
            logger.error("[CourierHub] Track error %s/%s: %s", carrier_code, tracking_no, e)
            return {"status": "error", "message": str(e)}

    @classmethod
    def cancel(cls, carrier_code: str, consignment_id: str) -> dict:
        try:
            return cls.get(carrier_code).cancel_order(consignment_id)
        except Exception as e:
            logger.error("[CourierHub] Cancel error %s/%s: %s", carrier_code, consignment_id, e)
            return {"success": False, "error": str(e)}
