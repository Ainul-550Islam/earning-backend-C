"""
conversion_tracking/conversion_validator.py
─────────────────────────────────────────────
Validates a conversion before it is created.
Checks: payout cap, offer active, user eligibility, conversion window, geo restrictions.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from django.utils import timezone
from ..constants import MAX_PAYOUT_USD_PER_CONVERSION, MAX_CONVERSIONS_PER_OFFER_USER
from ..exceptions import (
    OfferInactiveException,
    PayoutLimitExceededException,
    ConversionWindowExpiredException,
    UserResolutionException,
)
from ..models import AdNetworkConfig, ClickLog

logger = logging.getLogger(__name__)


class ConversionValidator:

    def validate_all(
        self,
        network: AdNetworkConfig,
        payout: Decimal,
        user,
        offer_id: str,
        click_log: ClickLog = None,
        country: str = "",
    ) -> None:
        """Run all validation gates. Raises on first failure."""
        self.validate_payout_cap(payout)
        self.validate_offer_active(network, offer_id, country)
        self.validate_user_conversion_cap(network, user, offer_id)
        if click_log:
            self.validate_conversion_window(click_log, network)

    def validate_payout_cap(self, payout: Decimal) -> None:
        if payout > MAX_PAYOUT_USD_PER_CONVERSION:
            raise PayoutLimitExceededException(
                f"Payout {payout} exceeds system cap {MAX_PAYOUT_USD_PER_CONVERSION}.",
                payout=payout, limit=MAX_PAYOUT_USD_PER_CONVERSION,
            )

    def validate_offer_active(self, network: AdNetworkConfig, offer_id: str, country: str = "") -> None:
        try:
            offer_cfg = network.offer_postbacks.get(offer_id=offer_id, is_active=True)
            # Geo restriction
            if country and offer_cfg.blocked_countries and country.upper() in [c.upper() for c in offer_cfg.blocked_countries]:
                raise OfferInactiveException(f"Offer {offer_id} blocked in country {country}.")
            if country and offer_cfg.allowed_countries and country.upper() not in [c.upper() for c in offer_cfg.allowed_countries]:
                raise OfferInactiveException(f"Offer {offer_id} not allowed in country {country}.")
        except network.offer_postbacks.model.DoesNotExist:
            pass   # No per-offer config → use network defaults

    def validate_user_conversion_cap(self, network: AdNetworkConfig, user, offer_id: str) -> None:
        """Check per-user conversion cap for an offer."""
        try:
            offer_cfg = network.offer_postbacks.get(offer_id=offer_id, is_active=True)
            max_conv = offer_cfg.max_conversions_per_user
            if max_conv == 0:
                return
            from ..models import Conversion
            from ..enums import ConversionStatus
            count = Conversion.objects.filter(
                user=user, offer_id=offer_id,
                status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
            ).count()
            if count >= max_conv:
                raise OfferInactiveException(
                    f"User reached max {max_conv} conversion(s) for offer {offer_id}."
                )
        except network.offer_postbacks.model.DoesNotExist:
            pass

    def validate_conversion_window(self, click_log: ClickLog, network: AdNetworkConfig) -> None:
        window_hours = network.conversion_window_hours
        if window_hours == 0:
            return
        cutoff = timezone.now() - timezone.timedelta(hours=window_hours)
        if click_log.clicked_at < cutoff:
            raise ConversionWindowExpiredException(
                f"Click {click_log.click_id} is {window_hours}h window expired."
            )


# Module-level singleton
conversion_validator = ConversionValidator()
