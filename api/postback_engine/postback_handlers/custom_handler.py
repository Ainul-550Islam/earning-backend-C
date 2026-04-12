"""
postback_handlers/custom_handler.py
─────────────────────────────────────
Fully configurable custom postback handler.
Used when a network doesn't fit any standard pattern.
All behaviour is configured via AdNetworkConfig metadata at runtime.

Example metadata config:
    {
        "custom_handler": {
            "require_click_id": true,
            "skip_signature": false,
            "reward_multiplier": 1.5,
            "max_daily_conversions_per_user": 3,
            "allowed_offer_ids": ["offer_001", "offer_002"],
            "custom_rejection_message": "Sorry, offer not available in your region"
        }
    }
"""
from __future__ import annotations
import logging
from decimal import Decimal
from .base_handler import BasePostbackHandler, PostbackContext
from ..network_adapters.adapters import get_adapter

logger = logging.getLogger(__name__)


class CustomHandler(BasePostbackHandler):
    """
    Runtime-configurable postback handler.
    Reads its behaviour from AdNetworkConfig.metadata['custom_handler'].
    """

    def __init__(self, network_key: str):
        self._network_key = network_key
        self._adapter = get_adapter(network_key)

    @property
    def network_key(self) -> str:
        return self._network_key

    def get_adapter(self):
        return self._adapter

    def _get_custom_config(self, ctx: PostbackContext) -> dict:
        """Read custom handler config from network metadata."""
        metadata = getattr(ctx.network, "metadata", {}) or {}
        return metadata.get("custom_handler", {})

    def pre_validate_hook(self, ctx: PostbackContext) -> None:
        cfg = self._get_custom_config(ctx)

        # Require click_id if configured
        if cfg.get("require_click_id") and not ctx.click_id:
            from ..exceptions import MissingRequiredFieldsException
            raise MissingRequiredFieldsException(
                "Custom handler requires click_id.",
                missing_fields=["click_id"],
            )

        # Check allowed offer IDs
        allowed_offers = cfg.get("allowed_offer_ids", [])
        if allowed_offers and ctx.offer_id and ctx.offer_id not in allowed_offers:
            from ..exceptions import OfferInactiveException
            raise OfferInactiveException(
                f"Offer '{ctx.offer_id}' not in allowed list for {ctx.network_key}."
            )

        # Apply reward multiplier
        multiplier = cfg.get("reward_multiplier", 1.0)
        if multiplier != 1.0:
            ctx.payout = ctx.payout * Decimal(str(multiplier))

        # Check max daily conversions per user
        max_daily = cfg.get("max_daily_conversions_per_user", 0)
        if max_daily > 0 and ctx.user:
            from datetime import timedelta
            from django.utils import timezone
            from ..models import Conversion
            from ..enums import ConversionStatus
            today_count = Conversion.objects.filter(
                user=ctx.user,
                converted_at__date=timezone.now().date(),
                status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
            ).count()
            if today_count >= max_daily:
                from ..exceptions import OfferInactiveException
                raise OfferInactiveException(
                    f"User reached daily conversion limit ({max_daily})."
                )

    def on_rejection_hook(self, ctx: PostbackContext) -> None:
        cfg = self._get_custom_config(ctx)
        custom_msg = cfg.get("custom_rejection_message", "")
        if custom_msg:
            ctx.rejection_detail = custom_msg

    def post_reward_hook(self, ctx: PostbackContext) -> None:
        cfg = self._get_custom_config(ctx)
        # Custom post-reward webhook if configured
        webhook_url = cfg.get("post_reward_webhook_url", "")
        if webhook_url and ctx.conversion:
            try:
                from ..webhook_manager.webhook_delivery import webhook_delivery
                webhook_delivery.deliver(webhook_url, {
                    "event": "custom.conversion",
                    "conversion_id": str(ctx.conversion.id),
                    "network": ctx.network_key,
                    "offer_id": ctx.offer_id,
                    "payout_usd": float(ctx.payout),
                    "user_id": str(ctx.user.id) if ctx.user else "",
                })
            except Exception as exc:
                logger.warning("CustomHandler post_reward_webhook failed: %s", exc)
