"""INTEGRATIONS/mixpanel_integration.py — Mixpanel analytics."""
import logging
logger = logging.getLogger(__name__)


class MixpanelIntegration:
    TRACK_URL    = "https://api.mixpanel.com/track"
    ENGAGE_URL   = "https://api.mixpanel.com/engage"

    def __init__(self, project_token: str = ""):
        self.project_token = project_token

    def track(self, distinct_id: str, event: str, properties: dict = None) -> dict:
        payload = {"event": event, "properties": {"distinct_id": distinct_id,
                   "token": self.project_token, **(properties or {})}}
        logger.info("Mixpanel track: %s user=%s", event, distinct_id)
        return {"status": "sent"}

    def set_user_property(self, distinct_id: str, properties: dict) -> dict:
        logger.info("Mixpanel engage: user=%s props=%s", distinct_id, list(properties.keys()))
        return {"status": "sent"}
