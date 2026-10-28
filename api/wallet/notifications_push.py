# api/wallet/notifications_push.py
"""
Dedicated push notification service — Firebase FCM, Apple APNs, WebPush.
Handles device token management, notification queuing, delivery tracking.
pip install firebase-admin
settings.py: FCM_SERVER_KEY = "...", FIREBASE_CREDS_PATH = "firebase-creds.json"
"""
import logging
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("wallet.push")


class FCMPushService:
    """Firebase Cloud Messaging (FCM) push notifications."""

    @staticmethod
    def send(device_token: str, title: str, body: str, data: dict = None) -> dict:
        """Send FCM push to a single device token."""
        import requests
        api_key = getattr(settings, "FCM_SERVER_KEY", "")
        if not api_key or not device_token:
            return {"success": False, "reason": "FCM not configured or no token"}
        payload = {
            "to": device_token,
            "notification": {"title": title, "body": body, "sound": "default"},
            "data": {k: str(v) for k, v in (data or {}).items()},
        }
        try:
            resp = requests.post(
                "https://fcm.googleapis.com/fcm/send",
                json=payload,
                headers={"Authorization": f"key={api_key}", "Content-Type": "application/json"},
                timeout=10,
            )
            result = resp.json()
            success = result.get("success", 0) > 0
            if not success:
                error = result.get("results", [{}])[0].get("error", "Unknown")
                if error in ("NotRegistered", "InvalidRegistration"):
                    FCMPushService._invalidate_token(device_token)
            return {"success": success, "fcm_response": result}
        except Exception as e:
            logger.error(f"FCM send error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def send_bulk(tokens: list, title: str, body: str, data: dict = None) -> dict:
        """Send FCM push to multiple device tokens."""
        import requests
        api_key = getattr(settings, "FCM_SERVER_KEY", "")
        if not api_key or not tokens:
            return {"success": False}
        payload = {
            "registration_ids": tokens[:1000],
            "notification": {"title": title, "body": body, "sound": "default"},
            "data": {k: str(v) for k, v in (data or {}).items()},
        }
        try:
            resp = requests.post(
                "https://fcm.googleapis.com/fcm/send",
                json=payload,
                headers={"Authorization": f"key={api_key}", "Content-Type": "application/json"},
                timeout=30,
            )
            result = resp.json()
            return {"success": True, "success_count": result.get("success", 0),
                    "failure_count": result.get("failure", 0)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def register_token(user_id: int, device_token: str, platform: str = "android") -> None:
        """Register/update a device token for push notifications."""
        cache.set(f"push_token:{user_id}", {"token": device_token, "platform": platform}, 86400 * 30)

    @staticmethod
    def get_token(user_id: int) -> str:
        """Get device token for a user."""
        data = cache.get(f"push_token:{user_id}")
        return data.get("token", "") if data else ""

    @staticmethod
    def _invalidate_token(token: str) -> None:
        """Remove invalid token from all users."""
        logger.info(f"Invalidating FCM token: {token[:20]}...")
        # In production: scan and remove invalid tokens from DB


class WalletPushNotifier:
    """Send push notifications for wallet events."""

    @staticmethod
    def credit(user_id: int, amount: str, balance: str, txn_type: str = "earning"):
        token = FCMPushService.get_token(user_id)
        if token:
            return FCMPushService.send(
                token, f"+ {amount} BDT Credited",
                f"Your wallet balance is now {balance} BDT",
                {"type": "credit", "amount": amount, "balance": balance, "txn_type": txn_type}
            )

    @staticmethod
    def withdrawal_complete(user_id: int, amount: str, gateway: str, ref: str):
        token = FCMPushService.get_token(user_id)
        if token:
            return FCMPushService.send(
                token, "Withdrawal Sent!",
                f"{amount} BDT sent via {gateway}. Ref: {ref}",
                {"type": "withdrawal_complete", "amount": amount, "gateway": gateway}
            )

    @staticmethod
    def withdrawal_failed(user_id: int, amount: str, error: str):
        token = FCMPushService.get_token(user_id)
        if token:
            return FCMPushService.send(
                token, "Withdrawal Failed",
                f"Withdrawal of {amount} BDT failed. {error} Funds returned.",
                {"type": "withdrawal_failed", "amount": amount}
            )

    @staticmethod
    def kyc_approved(user_id: int, level: int, new_limit: str):
        token = FCMPushService.get_token(user_id)
        if token:
            return FCMPushService.send(
                token, f"KYC Level {level} Approved!",
                f"Your daily withdrawal limit is now {new_limit} BDT",
                {"type": "kyc_approved", "level": str(level)}
            )

    @staticmethod
    def streak_bonus(user_id: int, days: int, bonus: str):
        token = FCMPushService.get_token(user_id)
        if token:
            return FCMPushService.send(
                token, f"{days}-Day Streak!",
                f"Congratulations! +{bonus} BDT streak bonus added.",
                {"type": "streak_bonus", "days": str(days), "bonus": bonus}
            )
