# api/payment_gateways/integrations_adapters/PostbackAdapter.py
# Bridge between payment_gateways tracking and api.postback_engine

import logging

logger = logging.getLogger(__name__)


class PostbackAdapter:
    """
    Bridges payment_gateways PostbackEngine with your existing api.postback_engine.
    
    Your api.postback_engine likely handles:
        - Incoming advertiser postbacks
        - Outgoing publisher postbacks
        - Postback logs

    We delegate to it instead of duplicating.
    """

    def process_incoming(self, params: dict, raw_url: str, ip: str) -> dict:
        """Process incoming advertiser postback via your postback_engine."""
        try:
            from api.postback_engine.services import PostbackService
            return PostbackService().process(params, raw_url, ip)
        except ImportError:
            # Use payment_gateways built-in
            from api.payment_gateways.tracking.PostbackEngine import PostbackEngine
            return PostbackEngine().process(params, raw_url, ip)

    def fire_publisher_postback(self, conversion) -> dict:
        """Fire outgoing postback to publisher via your postback_engine."""
        try:
            from api.postback_engine.services import OutgoingPostbackService
            return OutgoingPostbackService().fire(conversion)
        except ImportError:
            from api.payment_gateways.tracking.PostbackFirer import PostbackFirer
            return PostbackFirer().fire(conversion)
