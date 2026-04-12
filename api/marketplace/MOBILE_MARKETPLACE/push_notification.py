"""
MOBILE_MARKETPLACE/push_notification.py — Push Notification Service
=====================================================================
Supports: Firebase FCM (Android/iOS), Expo Push (React Native)
"""
from __future__ import annotations
import logging
import requests
from django.db import models
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

FCM_URL = "https://fcm.googleapis.com/fcm/send"
EXPO_URL = "https://exp.host/--/api/v2/push/send"


class DeviceToken(models.Model):
    PLATFORM_CHOICES = [("android","Android"),("ios","iOS"),("web","Web"),("expo","Expo")]
    tenant    = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                   related_name="device_tokens_tenant")
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="device_tokens")
    token     = models.CharField(max_length=500, unique=True)
    platform  = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default="android")
    device_name = models.CharField(max_length=100, blank=True)
    app_version = models.CharField(max_length=20, blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    last_used   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_device_token"

    def __str__(self):
        return f"{self.user.username} | {self.platform} | {self.token[:30]}..."


class PushNotificationService:

    def __init__(self):
        self.fcm_key  = getattr(settings, "FCM_SERVER_KEY", "")
        self.expo_key = getattr(settings, "EXPO_ACCESS_TOKEN", "")

    def send_to_user(self, user, title: str, body: str, data: dict = None) -> dict:
        tokens = DeviceToken.objects.filter(user=user, is_active=True)
        results = {"sent": 0, "failed": 0}
        for token in tokens:
            ok = self._send_single(token, title, body, data or {})
            if ok:
                results["sent"] += 1
            else:
                results["failed"] += 1
        return results

    def send_bulk(self, user_ids: list, title: str, body: str, data: dict = None) -> dict:
        tokens = DeviceToken.objects.filter(user_id__in=user_ids, is_active=True)
        results = {"sent": 0, "failed": 0}
        fcm_tokens = [t.token for t in tokens if t.platform in ("android","ios","web")]
        expo_tokens = [t.token for t in tokens if t.platform == "expo"]

        if fcm_tokens:
            ok, fail = self._send_fcm_batch(fcm_tokens, title, body, data or {})
            results["sent"] += ok; results["failed"] += fail
        for token in expo_tokens:
            ok = self._send_expo(token, title, body, data or {})
            if ok: results["sent"] += 1
            else:  results["failed"] += 1
        return results

    def send_order_notification(self, user, order_number: str, status: str):
        messages = {
            "confirmed": ("Order Confirmed ✅", f"Order #{order_number} confirmed by seller."),
            "shipped":   ("Your Order is Shipped 🚚", f"Order #{order_number} is on the way!"),
            "delivered": ("Order Delivered 🎉", f"Order #{order_number} delivered. Enjoy!"),
            "cancelled": ("Order Cancelled ❌", f"Order #{order_number} has been cancelled."),
        }
        title, body = messages.get(status, ("Order Update", f"Order #{order_number}: {status}"))
        return self.send_to_user(user, title, body, {"order_number": order_number, "type": "order_update"})

    def send_promo_notification(self, user_ids: list, campaign_name: str, discount: str):
        title = f"🔥 {campaign_name}"
        body  = f"Flash deal! Get up to {discount} off. Limited time only!"
        return self.send_bulk(user_ids, title, body, {"type": "promotion", "campaign": campaign_name})

    def _send_single(self, token: DeviceToken, title: str, body: str, data: dict) -> bool:
        if token.platform == "expo":
            return self._send_expo(token.token, title, body, data)
        return self._send_fcm_single(token.token, title, body, data)

    def _send_fcm_single(self, token: str, title: str, body: str, data: dict) -> bool:
        if not self.fcm_key:
            logger.warning("[Push] FCM_SERVER_KEY not configured")
            return False
        try:
            resp = requests.post(
                FCM_URL,
                headers={"Authorization": f"key={self.fcm_key}", "Content-Type": "application/json"},
                json={"to": token, "notification": {"title": title, "body": body}, "data": data},
                timeout=10,
            )
            result = resp.json()
            if result.get("failure"):
                logger.warning("[Push] FCM failure for token %s: %s", token[:20], result)
                if result.get("results", [{}])[0].get("error") == "NotRegistered":
                    DeviceToken.objects.filter(token=token).update(is_active=False)
                return False
            return True
        except Exception as e:
            logger.error("[Push] FCM error: %s", e)
            return False

    def _send_fcm_batch(self, tokens: list, title: str, body: str, data: dict):
        if not self.fcm_key:
            return 0, len(tokens)
        try:
            resp = requests.post(
                FCM_URL,
                headers={"Authorization": f"key={self.fcm_key}", "Content-Type": "application/json"},
                json={"registration_ids": tokens, "notification": {"title": title, "body": body}, "data": data},
                timeout=15,
            )
            result = resp.json()
            return result.get("success", 0), result.get("failure", 0)
        except Exception as e:
            logger.error("[Push] FCM batch error: %s", e)
            return 0, len(tokens)

    def _send_expo(self, token: str, title: str, body: str, data: dict) -> bool:
        try:
            resp = requests.post(
                EXPO_URL,
                json={"to": token, "title": title, "body": body, "data": data, "sound": "default"},
                headers={"Authorization": f"Bearer {self.expo_key}"} if self.expo_key else {},
                timeout=10,
            )
            result = resp.json()
            status = result.get("data", {}).get("status", "")
            return status != "error"
        except Exception as e:
            logger.error("[Push] Expo error: %s", e)
            return False


def notify_user(user, title: str, body: str, data: dict = None) -> dict:
    return PushNotificationService().send_to_user(user, title, body, data)
