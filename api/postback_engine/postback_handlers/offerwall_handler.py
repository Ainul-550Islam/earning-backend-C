"""
postback_handlers/offerwall_handler.py
────────────────────────────────────────
Offerwall-specific postback handler.
Handles: CPALead, AdGate, OfferToro, Adscend, Revenue Wall, AdGem, Tapjoy, etc.

Offerwall networks have unique characteristics:
  - Virtual currency rewards (points, coins, gems) not USD
  - user_id is often the game player ID embedded as a macro
  - Offer completion = user finishes a survey/game/install
  - Some networks don't send HMAC (IP-only authentication)
"""
from __future__ import annotations
import logging
from decimal import Decimal
from .base_handler import BasePostbackHandler, PostbackContext
from ..network_adapters.adapters import get_adapter

logger = logging.getLogger(__name__)


class OfferwallHandler(BasePostbackHandler):
    """
    Handles offerwall postbacks.
    Primary reward unit = points (virtual currency), not USD.
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
        Offerwall: extract and validate virtual currency amount.
        Many offerwall networks send 'virtual_currency' or 'reward' instead of 'payout'.
        """
        # Try to get virtual currency amount from various field names
        vc = (
            ctx.normalised.get("virtual_currency")
            or ctx.normalised.get("reward")
            or ctx.normalised.get("amount")
            or ctx.normalised.get("payout")
        )
        if vc is not None:
            try:
                ctx.payout = Decimal(str(vc))
            except Exception:
                pass

        # Offerwall user_id is often a game player ID — try to normalise
        if not ctx.click_id:
            player_id = (
                ctx.normalised.get("player_id")
                or ctx.normalised.get("snuid")
                or ctx.normalised.get("user_id")
                or ctx.normalised.get("sub1")
            )
            if player_id:
                ctx.click_id = str(player_id)
                if not ctx.lead_id:
                    ctx.lead_id = ctx.click_id

    def post_reward_hook(self, ctx: PostbackContext) -> None:
        """Log offerwall reward for analytics."""
        logger.info(
            "Offerwall reward: network=%s user=%s offer=%s points=%d",
            ctx.network_key,
            getattr(ctx.user, "id", None),
            ctx.offer_id,
            ctx.conversion.points_awarded if ctx.conversion else 0,
        )


# ── Concrete offerwall handler instances ──────────────────────────────────────

class CPALeadOfferwallHandler(OfferwallHandler):
    def __init__(self): super().__init__("cpalead")

class AdGateOfferwallHandler(OfferwallHandler):
    def __init__(self): super().__init__("adgate")

class OfferToroOfferwallHandler(OfferwallHandler):
    def __init__(self): super().__init__("offertoro")

class AdGemOfferwallHandler(OfferwallHandler):
    def __init__(self): super().__init__("adgem")

class TapjoyOfferwallHandler(OfferwallHandler):
    def __init__(self): super().__init__("tapjoy")

class RevenueWallHandler(OfferwallHandler):
    def __init__(self): super().__init__("revenuewall")
