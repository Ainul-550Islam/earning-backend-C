"""INTEGRATIONS/segment_integration.py — Segment CDP integration."""
import logging
logger = logging.getLogger(__name__)


class SegmentIntegration:
    TRACK_URL    = "https://api.segment.io/v1/track"
    IDENTIFY_URL = "https://api.segment.io/v1/identify"

    def __init__(self, write_key: str = ""):
        self.write_key = write_key

    def track(self, user_id: str, event: str, properties: dict = None) -> dict:
        logger.info("Segment track: %s user=%s", event, user_id)
        return {"status": "ok"}

    def identify(self, user_id: str, traits: dict) -> dict:
        logger.info("Segment identify: user=%s traits=%s", user_id, list(traits.keys()))
        return {"status": "ok"}

    def page(self, user_id: str, name: str, properties: dict = None) -> dict:
        logger.info("Segment page: %s user=%s", name, user_id)
        return {"status": "ok"}
