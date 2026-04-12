"""
conversion_tracking/conversion_manager.py – Conversion lifecycle management.
"""
import logging
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.utils import timezone

from ..models import Conversion, ClickLog, PostbackRawLog, AdNetworkConfig
from ..enums import ConversionStatus
from ..exceptions import (
    ConversionWindowExpiredException,
    DuplicateConversionException,
    OfferInactiveException,
    PayoutLimitExceededException,
)
from ..constants import MAX_PAYOUT_USD_PER_CONVERSION, CONVERSION_WINDOW_DAYS

logger = logging.getLogger(__name__)


class ConversionManager:
    """
    Manages the full lifecycle of a conversion:
      create → approve → credit → [reverse]
    """

    def validate_conversion_window(
        self, click_log: ClickLog, network: AdNetworkConfig
    ) -> bool:
        """
        Check whether the conversion happened within the allowed window.
        """
        window_hours = network.conversion_window_hours
        if window_hours == 0:
            return True  # unlimited window

        cutoff = timezone.now() - timezone.timedelta(hours=window_hours)
        if click_log.clicked_at < cutoff:
            raise ConversionWindowExpiredException(
                f"Click {click_log.click_id} is outside the {window_hours}h conversion window."
            )
        return True

    def check_offer_conversion_cap(
        self,
        user,
        offer_id: str,
        network: AdNetworkConfig,
    ) -> bool:
        """
        Check whether the user has reached the max conversions for this offer.
        """
        try:
            offer_cfg = network.offer_postbacks.get(offer_id=offer_id, is_active=True)
        except Exception:
            return True  # no per-offer config = unlimited

        max_conv = offer_cfg.max_conversions_per_user
        if max_conv == 0:
            return True  # unlimited

        count = Conversion.objects.filter(
            user=user,
            offer_id=offer_id,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        ).count()

        if count >= max_conv:
            raise OfferInactiveException(
                f"User has reached the max {max_conv} conversion(s) for offer {offer_id}."
            )
        return True

    @transaction.atomic
    def reverse_conversion(self, conversion: Conversion, reason: str = "") -> bool:
        """
        Reverse an approved/paid conversion and deduct from wallet.
        """
        if conversion.is_reversed:
            logger.warning("Conversion %s already reversed.", conversion.id)
            return False

        conversion.reverse(reason=reason)

        # Deduct from wallet
        try:
            from api.wallet.services import debit_for_reversal
            debit_for_reversal(
                user=conversion.user,
                amount=conversion.actual_payout,
                points=conversion.points_awarded,
                ref_id=str(conversion.id),
                description=f"Conversion reversal: {conversion.offer_id}",
            )
        except Exception as exc:
            logger.error(
                "Wallet debit failed during reversal of conversion=%s: %s",
                conversion.id, exc,
            )

        logger.info(
            "Conversion reversed: %s | user=%s | reason=%s",
            conversion.id, conversion.user_id, reason,
        )
        return True

    def get_conversion_stats_for_user(self, user, days: int = 30) -> dict:
        """Return conversion summary for a user in the last N days."""
        cutoff = timezone.now() - timezone.timedelta(days=days)
        qs = Conversion.objects.filter(
            user=user,
            converted_at__gte=cutoff,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        )
        from django.db.models import Sum, Count
        agg = qs.aggregate(
            total=Count("id"),
            total_payout=Sum("actual_payout"),
            total_points=Sum("points_awarded"),
        )
        return {
            "total_conversions": agg["total"] or 0,
            "total_payout_usd": float(agg["total_payout"] or 0),
            "total_points": agg["total_points"] or 0,
            "period_days": days,
        }


# Module-level singleton
conversion_manager = ConversionManager()
