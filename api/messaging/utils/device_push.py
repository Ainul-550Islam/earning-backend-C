"""
Device Push Helpers — FCM, APNs, WebPush, Expo implementations.
Configure credentials in Django settings:
  FCM_SERVICE_ACCOUNT_FILE → Path to a Firebase service-account JSON key
                              (Firebase console -> Project settings ->
                              Service accounts -> Generate new private key).
                              project_id is read from the file itself.
  APNS_CERT_FILE        → Path to .p8 key file
  APNS_KEY_ID           → APNs key ID
  APNS_TEAM_ID          → Apple team ID
  APNS_BUNDLE_ID        → App bundle ID
  VAPID_PRIVATE_KEY     → WebPush VAPID private key
  VAPID_PUBLIC_KEY      → WebPush VAPID public key
  VAPID_CLAIM_EMAIL     → Contact email for VAPID

Part 6 audit note: send_fcm() previously posted to the legacy
fcm.googleapis.com/fcm/send endpoint with a static FCM_SERVER_KEY. Google
deprecated that endpoint on 2023-06-20 and it has been rejecting all
requests since 2024-06-21, so the old implementation could never actually
deliver a push in production regardless of configuration. Rewritten below
to use the HTTP v1 API with a service-account JWT bearer token - the same
self-signed-JWT approach send_apns() already uses, so no new dependency.
If FCM_SERVER_KEY is still set in a deployment's settings it is no longer
read; add FCM_SERVICE_ACCOUNT_FILE to restore FCM push delivery.
"""
from __future__ import annotations
import logging
from typing import Any
import requests  # noqa: F401  (module-level so tests can patch it)
import jwt as _jwt  # noqa: F401  (module-level so tests can patch it)
from pywebpush import webpush, WebPushException  # noqa: F401  (module-level so tests can patch it)

logger = logging.getLogger(__name__)


def _get_fcm_access_token():
    """
    Mint a short-lived OAuth2 access token for the FCM HTTP v1 API from a
    Firebase service-account key, via the standard JWT Bearer Token flow
    (RFC 7523) - the same self-signed-JWT technique send_apns() uses, so no
    dependency beyond PyJWT + requests (both already used in this module).

    Google-issued tokens are valid for 1 hour; this caches one for 55
    minutes (Django cache) so a burst of pushes doesn't mint a fresh token
    - and make a network round trip to Google's token endpoint - per push.

    Returns (access_token, project_id); either is None if the service
    account isn't configured or minting failed.
    """
    from django.conf import settings
    from django.core.cache import cache
    import json as _json
    import time

    service_account_file = getattr(settings, "FCM_SERVICE_ACCOUNT_FILE", None)
    if not service_account_file:
        logger.debug("_get_fcm_access_token: FCM_SERVICE_ACCOUNT_FILE not configured.")
        return None, None

    cache_key = f"fcm:access_token:{service_account_file}"
    cached = cache.get(cache_key)
    if cached:
        return cached["token"], cached["project_id"]

    try:
        with open(service_account_file, "r") as f:
            account = _json.load(f)

        now = int(time.time())
        assertion = _jwt.encode(
            {
                "iss": account["client_email"],
                "scope": "https://www.googleapis.com/auth/firebase.messaging",
                "aud": "https://oauth2.googleapis.com/token",
                "iat": now,
                "exp": now + 3600,
            },
            account["private_key"],
            algorithm="RS256",
        )
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            timeout=5,
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        project_id = account.get("project_id")
        if token and project_id:
            cache.set(cache_key, {"token": token, "project_id": project_id}, 55 * 60)
        return token, project_id
    except Exception as exc:
        logger.error("_get_fcm_access_token: failed: %s", exc)
        return None, None


def send_fcm(*, token: str, title: str, body: str, data: dict, priority: str = "normal") -> bool:
    """Send push via Firebase Cloud Messaging HTTP v1 API."""
    access_token, project_id = _get_fcm_access_token()
    if not access_token or not project_id:
        return False
    try:
        payload = {
            "message": {
                "token": token,
                "notification": {"title": title, "body": body},
                "data": {str(k): str(v) for k, v in (data or {}).items()},
                "android": {"priority": "high" if priority == "high" else "normal"},
            }
        }
        resp = requests.post(
            f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning(
                "send_fcm: token=%s failed status=%s body=%s",
                token[:20], resp.status_code, resp.text[:200],
            )
            return False
        return True
    except Exception as exc:
        logger.error("send_fcm: exception for token=%s: %s", token[:20], exc)
        return False


def _get_apns_provider_token(*, key_file: str, key_id: str, team_id: str) -> str:
    """
    APNs provider (JWT) tokens are valid for up to 1 hour, and Apple's docs
    ask clients to reuse one rather than minting a fresh token per push -
    doing otherwise risks APNs throttling the connection
    (TooManyProviderTokenUpdates). Cached for 55 minutes per (team_id, key_id).
    """
    from django.core.cache import cache
    import time

    cache_key = f"apns:provider_token:{team_id}:{key_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    with open(key_file, "r") as f:
        private_key = f.read()

    token = _jwt.encode(
        {"iss": team_id, "iat": int(time.time())},
        private_key,
        algorithm="ES256",
        headers={"alg": "ES256", "kid": key_id},
    )
    cache.set(cache_key, token, 55 * 60)
    return token


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
        apns_token = _get_apns_provider_token(key_file=key_file, key_id=key_id, team_id=team_id)

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
