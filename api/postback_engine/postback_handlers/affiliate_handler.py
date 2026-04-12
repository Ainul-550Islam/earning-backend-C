"""
postback_handlers/affiliate_handler.py
────────────────────────────────────────
Handles postbacks from affiliate networks (Impact, CJ, ShareASale, Rakuten).
Affiliate networks typically have multi-step approval: pending → approved → paid.
"""
from __future__ import annotations
import logging
from .base_handler import BasePostbackHandler, PostbackContext
from ..network_adapters.adapters import get_adapter

logger = logging.getLogger(__name__)


class AffiliateHandler(BasePostbackHandler):
    """
    Handles affiliate network postbacks where conversions may be initially
    PENDING and require advertiser approval before payout.
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
        """
        For affiliate networks, check the normalised status.
        If status is 'pending', create the conversion in PENDING state
        rather than immediately crediting the wallet.
        """
        if ctx.status_normalised == "pending":
            logger.info(
                "AffiliateHandler: pending conversion — will hold wallet credit. "
                "network=%s lead=%s", ctx.network_key, ctx.lead_id
            )
            ctx.metadata = ctx.metadata or {}
            ctx.metadata["hold_wallet_credit"] = True

        elif ctx.status_normalised == "rejected":
            # Network is reporting a reversal/chargeback
            logger.info(
                "AffiliateHandler: rejection/chargeback postback. "
                "network=%s lead=%s", ctx.network_key, ctx.lead_id
            )

    def _dispatch_reward(self, ctx: PostbackContext) -> None:
        """Override: skip wallet credit for pending conversions."""
        if ctx.metadata and ctx.metadata.get("hold_wallet_credit"):
            logger.info(
                "AffiliateHandler: holding wallet credit for pending "
                "conversion=%s", ctx.conversion.id if ctx.conversion else "?"
            )
            return
        super()._dispatch_reward(ctx)
