"""
postback_handlers/advertiser_handler.py
─────────────────────────────────────────
Handles direct advertiser postbacks.
Direct advertisers integrate S2S without going through a network platform.
They typically have custom integration requirements and dedicated support.
"""
from __future__ import annotations
import logging
from .base_handler import BasePostbackHandler, PostbackContext
from ..network_adapters.adapters import get_adapter

logger = logging.getLogger(__name__)


class AdvertiserHandler(BasePostbackHandler):
    """
    Handles direct advertiser server-to-server postbacks.
    Similar to S2S but with advertiser-specific validation rules.
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
        Direct advertisers must always provide a click_id
        (no click_id = no attribution = reject).
        """
        if not ctx.click_id and not ctx.lead_id:
            from ..exceptions import MissingRequiredFieldsException
            raise MissingRequiredFieldsException(
                "Direct advertiser postback requires click_id or lead_id for attribution.",
                missing_fields=["click_id"],
            )

    def post_reward_hook(self, ctx: PostbackContext) -> None:
        """Log advertiser conversion for reconciliation reporting."""
        logger.info(
            "AdvertiserHandler: conversion confirmed — "
            "advertiser=%s offer=%s user=%s payout=%s",
            ctx.network_key, ctx.offer_id,
            getattr(ctx.user, "id", None),
            ctx.payout,
        )
