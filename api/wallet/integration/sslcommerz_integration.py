# api/wallet/integration/sslcommerz_integration.py
"""SSLCommerz payment gateway integration."""
import logging, requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger("wallet.integration.sslcommerz")

class SSLCommerzService:
    BASE_URL    = getattr(settings, "SSLCOMMERZ_BASE_URL", "https://sandbox.sslcommerz.com")
    STORE_ID    = getattr(settings, "SSLCOMMERZ_STORE_ID", "")
    STORE_PASSWD= getattr(settings, "SSLCOMMERZ_STORE_PASSWD", "")
    TIMEOUT     = 30

    @classmethod
    def initiate_payment(cls, order_id: str, amount: Decimal, user_email: str,
                          user_phone: str, success_url: str, fail_url: str,
                          cancel_url: str, ipn_url: str) -> dict:
        payload = {
            "store_id": cls.STORE_ID, "store_passwd": cls.STORE_PASSWD,
            "total_amount": str(amount), "currency": "BDT",
            "tran_id": order_id, "success_url": success_url,
            "fail_url": fail_url, "cancel_url": cancel_url,
            "ipn_url": ipn_url, "cus_name": user_email.split("@")[0],
            "cus_email": user_email, "cus_phone": user_phone,
            "cus_add1": "Bangladesh", "cus_city": "Dhaka",
            "cus_country": "Bangladesh", "shipping_method": "NO",
            "product_name": "Wallet Top-up", "product_category": "Digital",
            "product_profile": "non-physical-goods",
        }
        try:
            resp = requests.post(f"{cls.BASE_URL}/gwprocess/v4/api.php", data=payload, timeout=cls.TIMEOUT)
            data = resp.json()
            if data.get("status") == "SUCCESS":
                return {"success": True, "redirect_url": data["GatewayPageURL"], "session_key": data.get("sessionkey")}
            return {"success": False, "error": data.get("failedreason", "Unknown")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def validate_ipn(cls, val_id: str) -> dict:
        try:
            resp = requests.get(f"{cls.BASE_URL}/validator/api/validationserverAPI.php",
                params={"val_id": val_id, "store_id": cls.STORE_ID, "store_passwd": cls.STORE_PASSWD,
                        "format": "json"}, timeout=cls.TIMEOUT)
            data = resp.json()
            return {"valid": data.get("status") == "VALID", "amount": data.get("amount", 0), "data": data}
        except Exception as e:
            return {"valid": False, "error": str(e)}
