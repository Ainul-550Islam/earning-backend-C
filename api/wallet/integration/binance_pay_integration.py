# api/wallet/integration/binance_pay_integration.py
"""Binance Pay crypto integration."""
import hashlib, hmac, time, logging, requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger("wallet.integration.binance")

class BinancePayService:
    BASE_URL   = "https://bpay.binanceapi.com"
    API_KEY    = getattr(settings, "BINANCE_PAY_API_KEY", "")
    API_SECRET = getattr(settings, "BINANCE_PAY_SECRET_KEY", "")
    TIMEOUT    = 15

    @classmethod
    def _sign(cls, payload: str) -> tuple:
        ts    = str(int(time.time() * 1000))
        nonce = hashlib.md5(ts.encode()).hexdigest()[:32]
        body  = ts + "\n" + nonce + "\n" + payload + "\n"
        sig   = hmac.new(cls.API_SECRET.encode(), body.encode(), hashlib.sha512).hexdigest().upper()
        return ts, nonce, sig

    @classmethod
    def create_order(cls, amount_usd: float, order_id: str,
                      goods_name: str = "Wallet Withdrawal") -> dict:
        import json
        payload_dict = {
            "env": {"terminalType": "WEB"},
            "merchantTradeNo": order_id[:32],
            "orderAmount": amount_usd,
            "currency": "USDT",
            "goods": {"goodsType": "02", "goodsCategory": "Z000",
                      "referenceGoodsId": order_id, "goodsName": goods_name},
        }
        payload_str = json.dumps(payload_dict)
        ts, nonce, sig = cls._sign(payload_str)
        try:
            resp = requests.post(f"{cls.BASE_URL}/binancepay/openapi/v2/order",
                data=payload_str,
                headers={"BinancePay-Timestamp": ts, "BinancePay-Nonce": nonce,
                         "BinancePay-Certificate-SN": cls.API_KEY,
                         "BinancePay-Signature": sig, "Content-Type": "application/json"},
                timeout=cls.TIMEOUT)
            data = resp.json()
            if data.get("status") == "SUCCESS":
                return {"success": True, "order_id": data.get("data",{}).get("prepayId",""),
                        "checkout_url": data.get("data",{}).get("checkoutUrl","")}
            return {"success": False, "error": data.get("errorMessage","Unknown")}
        except Exception as e:
            logger.error(f"Binance Pay error: {e}")
            return {"success": False, "error": str(e)}
