"""
Backup Module Push Notifications
Sends real-time push notifications for backup events via FCM, APNs, or WebSocket.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Notification Payload
# ---------------------------------------------------------------------------

@dataclass
class PushNotificationPayload:
    title: str
    body: str
    data: Dict[str, Any] = field(default_factory=dict)
    icon: Optional[str] = None
    badge: Optional[int] = None
    sound: str = "default"
    priority: str = "high"   # high | normal

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "body": self.body,
            "data": self.data,
            "icon": self.icon,
            "badge": self.badge,
            "sound": self.sound,
            "priority": self.priority,
        }


# ---------------------------------------------------------------------------
# Abstract Backend
# ---------------------------------------------------------------------------

class PushBackend(ABC):
    """Contract for push notification backends"""

    @abstractmethod
    def send(self, device_token: str, payload: PushNotificationPayload) -> bool:
        raise NotImplementedError

    @abstractmethod
    def send_bulk(self, device_tokens: List[str],
                  payload: PushNotificationPayload) -> Dict[str, bool]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# FCM Backend (Firebase Cloud Messaging)
# ---------------------------------------------------------------------------

class FCMPushBackend(PushBackend):
    """Firebase Cloud Messaging push notification backend"""

    FCM_URL = "https://fcm.googleapis.com/fcm/send"

    def __init__(self, server_key: Optional[str] = None):
        self.server_key = server_key or getattr(settings, "FCM_SERVER_KEY", "")
        if not self.server_key:
            logger.warning("FCM_SERVER_KEY not configured — push notifications disabled.")

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"key={self.server_key}",
            "Content-Type": "application/json",
        }

    def send(self, device_token: str, payload: PushNotificationPayload) -> bool:
        body = {
            "to": device_token,
            "notification": {
                "title": payload.title,
                "body": payload.body,
                "sound": payload.sound,
            },
            "data": payload.data,
            "priority": payload.priority,
        }
        try:
            resp = requests.post(
                self.FCM_URL,
                json=body,
                headers=self._build_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            result = resp.json()
            success = result.get("success", 0) > 0
            if not success:
                logger.warning("FCM delivery failed for token %s: %s", device_token[:10], result)
            return success
        except requests.RequestException as exc:
            logger.error("FCM send error: %s", exc)
            return False

    def send_bulk(self, device_tokens: List[str],
                  payload: PushNotificationPayload) -> Dict[str, bool]:
        if not device_tokens:
            return {}
        body = {
            "registration_ids": device_tokens,
            "notification": {
                "title": payload.title,
                "body": payload.body,
                "sound": payload.sound,
            },
            "data": payload.data,
            "priority": payload.priority,
        }
        try:
            resp = requests.post(
                self.FCM_URL,
                json=body,
                headers=self._build_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            result = resp.json()
            results_list = result.get("results", [])
            return {
                token: ("error" not in r)
                for token, r in zip(device_tokens, results_list)
            }
        except requests.RequestException as exc:
            logger.error("FCM bulk send error: %s", exc)
            return {token: False for token in device_tokens}


# ---------------------------------------------------------------------------
# WebSocket Push Backend (via Django Channels)
# ---------------------------------------------------------------------------

class ChannelsPushBackend(PushBackend):
    """Sends push notifications via Django Channels layer"""

    def __init__(self, channel_layer=None):
        self._channel_layer = channel_layer

    def _get_layer(self):
        if self._channel_layer:
            return self._channel_layer
        from channels.layers import get_channel_layer
        return get_channel_layer()

    def send(self, device_token: str, payload: PushNotificationPayload) -> bool:
        """device_token here is the channel group name"""
        import asyncio
        layer = self._get_layer()
        if layer is None:
            logger.warning("No channel layer configured.")
            return False
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                layer.group_send(
                    device_token,
                    {"type": "push.notification", "payload": payload.to_dict()},
                )
            )
            loop.close()
            return True
        except Exception as exc:
            logger.error("Channels push error: %s", exc)
            return False

    def send_bulk(self, device_tokens: List[str],
                  payload: PushNotificationPayload) -> Dict[str, bool]:
        return {token: self.send(token, payload) for token in device_tokens}


# ---------------------------------------------------------------------------
# High-level Backup Push Notification Service
# ---------------------------------------------------------------------------

class BackupPushNotificationService:
    """
    High-level service for sending backup-specific push notifications.
    Wraps a push backend and provides convenience methods for each event.
    """

    def __init__(self, backend: Optional[PushBackend] = None):
        self.backend = backend or FCMPushBackend()

    # --- Convenience factory payloads ---

    def _backup_completed_payload(self, backup_name: str, size_human: str) -> PushNotificationPayload:
        return PushNotificationPayload(
            title="✅ Backup Completed",
            body=f"{backup_name} ({size_human}) backed up successfully.",
            data={"event": "backup_completed", "backup_name": backup_name},
        )

    def _backup_failed_payload(self, backup_name: str, error: str) -> PushNotificationPayload:
        return PushNotificationPayload(
            title="❌ Backup Failed",
            body=f"{backup_name} failed: {error[:100]}",
            data={"event": "backup_failed", "backup_name": backup_name, "error": error},
            priority="high",
        )

    def _restore_completed_payload(self, backup_name: str) -> PushNotificationPayload:
        return PushNotificationPayload(
            title="🔄 Restore Completed",
            body=f"Restore from {backup_name} completed successfully.",
            data={"event": "restore_completed", "backup_name": backup_name},
        )

    def _storage_warning_payload(self, usage_pct: float) -> PushNotificationPayload:
        return PushNotificationPayload(
            title="⚠️ Storage Warning",
            body=f"Backup storage is {usage_pct:.0f}% full.",
            data={"event": "storage_warning", "usage_pct": usage_pct},
            priority="high",
        )

    # --- Public dispatch methods ---

    def notify_backup_completed(self, tokens: List[str], backup_name: str,
                                 size_human: str = "unknown size") -> Dict[str, bool]:
        payload = self._backup_completed_payload(backup_name, size_human)
        return self.backend.send_bulk(tokens, payload)

    def notify_backup_failed(self, tokens: List[str], backup_name: str,
                              error: str) -> Dict[str, bool]:
        payload = self._backup_failed_payload(backup_name, error)
        return self.backend.send_bulk(tokens, payload)

    def notify_restore_completed(self, tokens: List[str],
                                  backup_name: str) -> Dict[str, bool]:
        payload = self._restore_completed_payload(backup_name)
        return self.backend.send_bulk(tokens, payload)

    def notify_storage_warning(self, tokens: List[str],
                                usage_pct: float) -> Dict[str, bool]:
        payload = self._storage_warning_payload(usage_pct)
        return self.backend.send_bulk(tokens, payload)

    def notify_single(self, token: str, title: str, body: str,
                      data: Optional[Dict] = None) -> bool:
        payload = PushNotificationPayload(title=title, body=body, data=data or {})
        return self.backend.send(token, payload)
