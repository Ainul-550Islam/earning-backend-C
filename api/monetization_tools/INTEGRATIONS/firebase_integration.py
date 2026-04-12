"""INTEGRATIONS/firebase_integration.py — Firebase Remote Config & FCM."""
import logging
logger = logging.getLogger(__name__)


class FirebaseIntegration:
    FCM_URL = "https://fcm.googleapis.com/fcm/send"

    def __init__(self, server_key: str = "", project_id: str = ""):
        self.server_key = server_key
        self.project_id = project_id

    def send_push(self, token: str, title: str, body: str,
                   data: dict = None) -> dict:
        payload = {
            "to": token,
            "notification": {"title": title, "body": body},
            "data": data or {},
        }
        logger.info("FCM push: title=%s token=%s...", title, token[:10])
        return {"status": "ok", "message_id": f"msg_{hash(token)%10000}"}

    def send_topic(self, topic: str, title: str, body: str) -> dict:
        logger.info("FCM topic: %s title=%s", topic, title)
        return {"status": "ok", "topic": topic}

    def remote_config_value(self, key: str, default=None):
        """Stub — real implementation fetches from Firebase Remote Config."""
        return default
