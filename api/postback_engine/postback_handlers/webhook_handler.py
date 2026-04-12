"""
postback_handlers/webhook_handler.py
──────────────────────────────────────
Handles inbound webhook events from ad networks.
These are typically JSON POST requests (not GET query strings).
Networks: Stripe, PayPal, Facebook Conversions API, TikTok Events API.
"""
from __future__ import annotations
import json
import logging
from .base_handler import BasePostbackHandler, PostbackContext
from ..network_adapters.adapters import get_adapter

logger = logging.getLogger(__name__)


class WebhookHandler(BasePostbackHandler):
    """
    Handles JSON-body webhook postbacks.
    Extracts payload from request body (not query string).
    """

    def __init__(self, network_key: str):
        self._network_key = network_key
        self._adapter = get_adapter(network_key)

    @property
    def network_key(self) -> str:
        return self._network_key

    def get_adapter(self):
        return self._adapter

    def execute(self, raw_payload: dict, method: str, query_string: str,
                headers: dict, source_ip: str, signature: str = "",
                timestamp_str: str = "", nonce: str = "", body_bytes: bytes = b""):
        """
        Override execute to merge JSON body with query params.
        Some webhooks put data in the body, others in both body + query string.
        """
        # Parse JSON body if present
        if body_bytes:
            try:
                body_data = json.loads(body_bytes.decode("utf-8"))
                if isinstance(body_data, dict):
                    merged = {**raw_payload, **body_data}
                    return super().execute(
                        merged, method, query_string, headers,
                        source_ip, signature, timestamp_str, nonce, body_bytes,
                    )
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        return super().execute(
            raw_payload, method, query_string, headers,
            source_ip, signature, timestamp_str, nonce, body_bytes,
        )
