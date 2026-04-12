"""
postback_handlers/callback_handler.py
───────────────────────────────────────
Handles async callback / notification postbacks.
These are delayed notifications (hours/days after the initial click)
for offers that require manual review (e.g. loan applications, insurance quotes).
"""
from __future__ import annotations
import logging
from .base_handler import BasePostbackHandler, PostbackContext
from ..network_adapters.adapters import get_adapter
from ..enums import ConversionStatus

logger = logging.getLogger(__name__)


class CallbackHandler(BasePostbackHandler):
    """
    Handles delayed callback postbacks where the conversion may come
    hours or days after the initial click/action.
    Extends conversion window check to be more lenient.
    """

    def __init__(self, network_key: str):
        self._network_key = network_key
        self._adapter = get_adapter(network_key)

    @property
    def network_key(self) -> str:
        return self._network_key

    def get_adapter(self):
        return self._adapter

    def _validate_business(self, ctx: PostbackContext) -> None:
        """
        For callbacks, skip strict conversion window — some offers
        have 30-90 day review periods. Only check payout cap.
        """
        from ..constants import MAX_PAYOUT_USD_PER_CONVERSION
        from ..exceptions import PayoutLimitExceededException
        if ctx.payout > MAX_PAYOUT_USD_PER_CONVERSION:
            raise PayoutLimitExceededException(
                f"Payout {ctx.payout} > cap {MAX_PAYOUT_USD_PER_CONVERSION}.",
                payout=ctx.payout, limit=MAX_PAYOUT_USD_PER_CONVERSION,
            )
        # No conversion window check for callbacks
        logger.debug("CallbackHandler: skipping conversion window for delayed callback.")

    def post_reward_hook(self, ctx: PostbackContext) -> None:
        if ctx.conversion:
            logger.info(
                "Delayed callback rewarded: network=%s offer=%s user=%s days_after_click=%s",
                ctx.network_key, ctx.offer_id, getattr(ctx.user, "id", None),
                f"{(ctx.conversion.time_to_convert_seconds or 0) / 86400:.1f}d",
            )
