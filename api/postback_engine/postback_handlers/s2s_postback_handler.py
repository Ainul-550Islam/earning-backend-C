"""
postback_handlers/s2s_postback_handler.py
──────────────────────────────────────────
Server-to-Server (S2S) postback handler.
Handles direct network-to-server postbacks where no browser redirect is involved.
Used by: Impact, Everflow, HasOffers, CAKE and any direct advertiser S2S setup.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from .base_handler import BasePostbackHandler, PostbackContext
from ..network_adapters.adapters import get_adapter

logger = logging.getLogger(__name__)


class S2SPostbackHandler(BasePostbackHandler):
    """
    Handles S2S (server-to-server) postbacks from affiliate/CPA networks.
    These arrive as HTTP GET/POST requests from the network's server directly.

    Key differences from browser-based:
     - No cookie tracking → rely entirely on click_id / transaction_id
     - HMAC signature is mandatory
     - IP must match network's server IP range
    """

    def __init__(self, network_key: str):
        self._network_key = network_key
        self._adapter = get_adapter(network_key)

    @property
    def network_key(self) -> str:
        return self._network_key

    def get_adapter(self):
        return self._adapter

    def pre_validate_hook(self, ctx: PostbackContext) -> None:
        """S2S: enforce that click_id or transaction_id is present."""
        if not ctx.click_id and not ctx.transaction_id:
            from ..exceptions import MissingRequiredFieldsException
            raise MissingRequiredFieldsException(
                "S2S postback requires click_id or transaction_id.",
                missing_fields=["click_id", "transaction_id"],
            )

    def post_reward_hook(self, ctx: PostbackContext) -> None:
        """After S2S reward: fire outbound confirmation postback to network if configured."""
        if not ctx.network or not ctx.conversion:
            return
        try:
            adapter = self.get_adapter()
            postback_url = adapter.build_outbound_postback_url(
                ctx.network,
                context={
                    "click_id":       ctx.click_id,
                    "lead_id":        ctx.lead_id,
                    "offer_id":       ctx.offer_id,
                    "transaction_id": ctx.transaction_id,
                    "payout":         str(ctx.payout),
                    "status":         "approved",
                    "user_id":        str(ctx.user.id) if ctx.user else "",
                },
            )
            if postback_url:
                import requests
                requests.get(postback_url, timeout=5)
                logger.info("S2S outbound confirmation sent: %s", postback_url[:80])
        except Exception as exc:
            logger.warning("S2S outbound confirmation failed (non-fatal): %s", exc)
