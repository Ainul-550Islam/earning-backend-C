# api/wallet/services/gateway/UsdtService.py
"""
USDT TRC-20 / ERC-20 payout via NowPayments.io API.
pip install requests
settings: NOWPAYMENTS_API_KEY, NOWPAYMENTS_IPN_URL
"""
import logging
import requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger("wallet.gateway.usdt")


class UsdtService:
    """USDT payout via NowPayments.io."""

    BASE_URL = "https://api.nowpayments.io/v1"
    API_KEY  = getattr(settings, "NOWPAYMENTS_API_KEY", "")
    IPN_URL  = getattr(settings, "NOWPAYMENTS_IPN_URL", "")
    TIMEOUT  = 15

    @classmethod
    def _headers(cls) -> dict:
        return {"x-api-key": cls.API_KEY, "Content-Type": "application/json"}

    @classmethod
    def create_payout(cls, wallet_address: str, amount_bdt: Decimal,
                      currency: str = "usdttrc20") -> dict:
        """
        Create USDT payout.
        currency: 'usdttrc20' (TRC-20) or 'usdterc20' (ERC-20)
        """
        # Get BDT→USD rate first
        rate = cls.get_exchange_rate("bdt", "usd")
        amount_usd = float(amount_bdt) * rate if rate else 0

        if amount_usd <= 0:
            return {"success": False, "error": "Could not get exchange rate"}

        payload = {
            "currency":         currency,
            "amount":           amount_usd,
            "address":          wallet_address,
            "ipn_callback_url": cls.IPN_URL,
        }
        try:
            resp = requests.post(
                f"{cls.BASE_URL}/payout",
                json=payload,
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
            )
            data = resp.json()
            if "id" in data:
                return {"success": True, "payment_id": data["id"],
                        "status": data.get("status"), "amount_usdt": data.get("amount"),
                        "amount_bdt": float(amount_bdt)}
            return {"success": False, "error": str(data), "data": data}
        except Exception as e:
            logger.error(f"USDT payout error: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def get_exchange_rate(cls, from_cur: str = "bdt", to_cur: str = "usd") -> float:
        try:
            resp = requests.get(
                f"{cls.BASE_URL}/exchange-rate/{from_cur}/{to_cur}",
                headers=cls._headers(), timeout=cls.TIMEOUT,
            )
            return float(resp.json().get("rate", 0))
        except Exception as e:
            logger.error(f"Exchange rate error: {e}"); return 0.0

    @classmethod
    def validate_address(cls, address: str, currency: str = "usdt") -> bool:
        if not address: return False
        if "trc" in currency.lower(): return address.startswith("T") and len(address) == 34
        if "erc" in currency.lower(): return address.startswith("0x") and len(address) == 42
        return len(address) > 10

    @classmethod
    def get_payout_status(cls, payment_id: str) -> dict:
        try:
            resp = requests.get(
                f"{cls.BASE_URL}/payment/{payment_id}",
                headers=cls._headers(), timeout=cls.TIMEOUT,
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
