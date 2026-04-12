"""
postback_handlers/event_handler.py
────────────────────────────────────
Handles custom conversion events (goal tracking).
Networks like Everflow, Impact, HasOffers support multiple goals per offer.
e.g. Goal 1 = App Install (small reward), Goal 2 = First Purchase (large reward).
"""
from __future__ import annotations
import logging
from decimal import Decimal
from .base_handler import BasePostbackHandler, PostbackContext
from ..network_adapters.adapters import get_adapter

logger = logging.getLogger(__name__)


class EventHandler(BasePostbackHandler):
    """
    Handles multi-goal / event-based postbacks.
    Each goal_id maps to different reward rules.
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
        """Override reward based on goal_id if present."""
        if not ctx.goal_id:
            return
        # Look up goal-specific reward rule
        goal_key = f"goal_{ctx.goal_id}"
        reward = ctx.network.reward_rules.get(goal_key) or {}
        if reward:
            ctx.payout = Decimal(str(reward.get("usd", ctx.payout)))
            logger.debug(
                "EventHandler: goal=%s reward override → %s USD",
                ctx.goal_id, ctx.payout,
            )
