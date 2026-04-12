"""
Device Push Helpers — FCM, APNs, WebPush, Expo implementations.
Configure credentials in Django settings:
  FCM_SERVER_KEY        → Firebase Cloud Messaging
  APNS_CERT_FILE        → Path to .p8 key file
  APNS_KEY_ID           → APNs key ID
  APNS_TEAM_ID          → Apple team ID
  APNS_BUNDLE_ID        → App bundle ID
  VAPID_PRIVATE_KEY     → WebPush VAPID private key
  VAPID_PUBLIC_KEY      → WebPush VAPID public key
  VAPID_CLAIM_EMAIL     → Contact email for VAPID
"""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


def send_fcm(*, token: str, title: str, body: str, data: dict, priority: str = "normal") -> bool:
    """Send push via Firebase Cloud Messaging."""
    from django.conf import settings
    fcm_key = getattr(settings, "FCM_SERVER_KEY", None)
    if not fcm_key:
        logger.debug("send_fcm: FCM_SERVER_KEY not configured.")
        return False
    try:
        import requests
        payload = {
            "to": token,
            "notification": {"title": title, "body": body, "sound": "default"},
            "data": data,
            "priority": priority,
            "android": {"priority": "HIGH" if priority == "high" else "NORMAL"},
        }
        resp = requests.post(
            "https://fcm.googleapis.com/fcm/send",
            json=payload,
            headers={"Authorization": f"key={fcm_key}", "Content-Type": "application/json"},
            timeout=5,
        )
        result = resp.json()
        if result.get("failure", 0) > 0:
            logger.warning("send_fcm: token=%s failed: %s", token[:20], result.get("results"))
            return False
        return True
    except Exception as exc:
        logger.error("send_fcm: exception for token=%s: %s", token[:20], exc)
        return False


def send_apns(*, token: str, title: str, body: str, data: dict, push_type: str = "alert") -> bool:
    """Send push via Apple Push Notification Service (HTTP/2 API)."""
    from django.conf import settings
    key_file = getattr(settings, "APNS_CERT_FILE", None)
    key_id = getattr(settings, "APNS_KEY_ID", None)
    team_id = getattr(settings, "APNS_TEAM_ID", None)
    bundle_id = getattr(settings, "APNS_BUNDLE_ID", None)

    if not all([key_file, key_id, team_id, bundle_id]):
        logger.debug("send_apns: APNs not fully configured.")
        return False

    try:
        import jwt as _jwt
        import time
        import requests

        with open(key_file, "r") as f:
            private_key = f.read()

        apns_token = _jwt.encode(
            {"iss": team_id, "iat": int(time.time())},
            private_key,
            algorithm="ES256",
            headers={"alg": "ES256", "kid": key_id},
        )

        headers = {
            "authorization": f"bearer {apns_token}",
            "apns-push-type": push_type,
            "apns-topic": bundle_id,
            "content-type": "application/json",
        }

        payload_dict = {
            "aps": {
                "alert": {"title": title, "body": body},
                "sound": "default",
                "badge": 1,
            },
            **data,
        }

        import json
        resp = requests.post(
            f"https://api.push.apple.com/3/device/{token}",
            headers=headers,
            data=json.dumps(payload_dict),
            timeout=5,
        )
        return resp.status_code == 200
    except Exception as exc:
        logger.error("send_apns: exception for token=%s: %s", token[:20], exc)
        return False


def send_webpush(*, subscription_info: str, title: str, body: str, data: dict) -> bool:
    """Send Web Push Notification via VAPID."""
    from django.conf import settings
    import json

    private_key = getattr(settings, "VAPID_PRIVATE_KEY", None)
    public_key = getattr(settings, "VAPID_PUBLIC_KEY", None)
    claim_email = getattr(settings, "VAPID_CLAIM_EMAIL", None)

    if not all([private_key, public_key, claim_email]):
        logger.debug("send_webpush: VAPID keys not configured.")
        return False

    try:
        from pywebpush import webpush, WebPushException
        subscription = json.loads(subscription_info)
        webpush(
            subscription_info=subscription,
            data=json.dumps({"title": title, "body": body, "data": data}),
            vapid_private_key=private_key,
            vapid_claims={"sub": f"mailto:{claim_email}"},
        )
        return True
    except Exception as exc:
        logger.error("send_webpush: failed: %s", exc)
        return False


def send_expo_push(*, token: str, title: str, body: str, data: dict) -> bool:
    """Send Expo Push Notification (for React Native apps)."""
    try:
        import requests
        payload = {
            "to": token,
            "title": title,
            "body": body,
            "data": data,
            "sound": "default",
            "priority": "high",
        }
        resp = requests.post(
            "https://exp.host/--/api/v2/push/send",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        result = resp.json()
        status = result.get("data", {}).get("status", "")
        if status == "error":
            logger.warning("send_expo_push: token=%s error=%s", token[:20], result.get("data", {}).get("message"))
            return False
        return True
    except Exception as exc:
        logger.error("send_expo_push: exception: %s", exc)
        return False
