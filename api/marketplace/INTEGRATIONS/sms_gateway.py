"""
INTEGRATIONS/sms_gateway.py — SMS gateway integration (Bangladesh)
Providers: SSL Wireless, Twilio, Infobip
"""
import logging
import requests

logger = logging.getLogger(__name__)


class SMSGatewayBase:
    def send(self, to: str, message: str) -> dict:
        raise NotImplementedError


class SSLWirelessSMS(SMSGatewayBase):
    """SSL Wireless (Bangladesh) SMS integration"""

    def __init__(self, api_key: str, sid: str):
        self.api_key = api_key
        self.sid = sid
        self.url = "https://sms.sslwireless.com/pushapi/dynamic/server.php"

    def send(self, to: str, message: str) -> dict:
        try:
            resp = requests.post(
                self.url,
                data={
                    "api_token": self.api_key,
                    "sid": self.sid,
                    "smsText": message,
                    "csmsId": f"MKT{to[-6:]}",
                    "mobile": to,
                },
                timeout=10,
            )
            return {"success": True, "response": resp.text}
        except Exception as e:
            logger.error("SSLWireless SMS error: %s", e)
            return {"success": False, "error": str(e)}


def send_order_confirmation_sms(phone: str, order_number: str, total: str):
    """Convenience function — send order confirmation SMS."""
    msg = f"আপনার অর্ডার #{order_number} কনফার্ম হয়েছে। মোট: {total} টাকা। ধন্যবাদ!"
    # TODO: initialise gateway from Django settings
    logger.info(f"[SMS] → {phone}: {msg}")
    return msg


def send_otp_sms(phone: str, otp: str):
    msg = f"আপনার OTP: {otp}। এটি ৫ মিনিটের মধ্যে মেয়াদ শেষ হবে।"
    logger.info(f"[OTP SMS] → {phone}: {msg}")
    return msg
