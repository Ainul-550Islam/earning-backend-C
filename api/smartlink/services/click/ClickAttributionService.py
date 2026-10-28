import logging
from django.utils import timezone
from django.conf import settings
from django.db.models import F
from api.smartlink.models import Click, UniqueClick

logger = logging.getLogger('smartlink.attribution')


# Attribution lookback window — configurable via Django settings.
# Previously hardcoded to 24h; now reads SMARTLINK_ATTRIBUTION_WINDOW_HOURS.
# Default: 24h (standard affiliate window).
# Set to 168 for 7-day window, 720 for 30-day.
ATTRIBUTION_WINDOW_HOURS = getattr(settings, 'SMARTLINK_ATTRIBUTION_WINDOW_HOURS', 24)


class ClickAttributionService:
    """
    Attribute a conversion (postback) back to the originating click.
    Supports last-click attribution model with configurable lookback window.

    Window resolution priority (highest → lowest):
      1. Per-publisher override  — PublisherProfile.attribution_window_days
         (set via /api/smartlink/publisher/profile/my-profile/ or admin)
      2. Global Django setting   — settings.SMARTLINK_ATTRIBUTION_WINDOW_HOURS
      3. Hard default            — 24 hours

    FIX 1: Attribution window is now configurable via
            settings.SMARTLINK_ATTRIBUTION_WINDOW_HOURS (default 24h).
            Previously hardcoded to 24h in both _find_by_ip and _find_by_sub1.

    FIX 2: After successful attribution, fires the offer's postback URL
            with all {macro} tokens replaced. Previously TrackingPixelService
            was never called from attribution — offer postback URLs were never fired.

    FIX 3: Per-publisher attribution window — reads PublisherProfile.attribution_window_days
            when available, overriding the global setting.
    """

    def __init__(self, publisher=None):
        """
        Args:
            publisher: Optional Django User instance (the publisher whose click is
                       being attributed). When supplied, the per-publisher
                       PublisherProfile.attribution_window_days is checked first.
        """
        global_hours = getattr(
            settings, 'SMARTLINK_ATTRIBUTION_WINDOW_HOURS', ATTRIBUTION_WINDOW_HOURS
        )
        self.window_hours = self._resolve_window_hours(publisher, global_hours)
        self._publisher = publisher

    # ── Window resolution ──────────────────────────────────────────────────────

    @staticmethod
    def _resolve_window_hours(publisher, global_hours: int) -> int:
        """
        Return the effective attribution window in hours for this publisher.

        Resolution order:
          1. PublisherProfile.attribution_window_days  (per-publisher override)
          2. global_hours (settings.SMARTLINK_ATTRIBUTION_WINDOW_HOURS)
        """
        if publisher is None:
            return global_hours
        try:
            from api.smartlink.models.billing import PublisherProfile
            profile = PublisherProfile.objects.filter(publisher=publisher).only(
                'attribution_window_days'
            ).first()
            if profile and profile.attribution_window_days is not None:
                window_hours = profile.attribution_window_days * 24
                logger.debug(
                    f"Using per-publisher attribution window: "
                    f"{profile.attribution_window_days} days "
                    f"({window_hours}h) for publisher={publisher.pk}"
                )
                return window_hours
        except Exception as e:
            logger.warning(
                f"Could not read per-publisher attribution window "
                f"for publisher={getattr(publisher, 'pk', '?')}: {e} — "
                f"falling back to global setting ({global_hours}h)"
            )
        return global_hours

    # ── Public API ─────────────────────────────────────────────────────────────

    def attribute(self, offer_id: int, sub1: str = '', ip: str = '',
                  payout: float = 0.0, transaction_id: str = '') -> object:
        """
        Find the originating click for a conversion postback and mark it as converted.

        Attribution priority:
        1. sub1 match  (most accurate — publisher sets sub1={click_id} in SmartLink URL)
        2. IP + offer + recent click within attribution window (fallback)

        Returns the attributed Click or None.
        """
        click = None

        # Strategy 1: sub1 contains click ID
        if sub1:
            click = self._find_by_sub1(sub1, offer_id)

        # Strategy 2: IP + offer ID match (last click within attribution window)
        if not click and ip:
            click = self._find_by_ip(ip, offer_id)

        if click:
            self._mark_converted(click, payout)
            # FIX 2: Fire offer postback URL with macro replacement
            self._fire_offer_postback(
                click=click,
                offer_id=offer_id,
                payout=payout,
                transaction_id=transaction_id,
            )
            logger.info(
                f"Conversion attributed: click#{click.pk} "
                f"offer#{offer_id} payout={payout} txn={transaction_id} "
                f"window={self.window_hours}h"
            )
        else:
            logger.warning(
                f"Could not attribute conversion: "
                f"offer#{offer_id} sub1={sub1} ip={ip} window={self.window_hours}h"
            )

        return click

    # ── Private helpers ────────────────────────────────────────────────────────

    def _find_by_sub1(self, sub1_value: str, offer_id: int) -> object:
        """Find click where sub1 matches the postback sub1 value."""
        # sub1 = click ID (publisher appends ?sub1={click_id} to SmartLink URL)
        if sub1_value.isdigit():
            try:
                return Click.objects.get(
                    pk=int(sub1_value),
                    offer_id=offer_id,
                    is_converted=False,
                )
            except Click.DoesNotExist:
                pass
            except (ValueError, TypeError):
                pass

        # sub1 may contain a custom value — match via ClickMetadata
        try:
            from api.smartlink.models import ClickMetadata
            cutoff = timezone.now() - timezone.timedelta(hours=self.window_hours * 30)
            metadata = ClickMetadata.objects.select_related('click').get(
                sub1=sub1_value,
                click__offer_id=offer_id,
                click__is_converted=False,
                click__created_at__gte=cutoff,
            )
            return metadata.click
        except Exception:
            return None

    def _find_by_ip(self, ip: str, offer_id: int) -> object:
        """
        Last-click attribution by IP within the configurable attribution window.
        FIX: Was hardcoded to 24h. Now reads settings.SMARTLINK_ATTRIBUTION_WINDOW_HOURS,
             further overridden by PublisherProfile.attribution_window_days.
        """
        cutoff = timezone.now() - timezone.timedelta(hours=self.window_hours)
        return Click.objects.filter(
            ip=ip,
            offer_id=offer_id,
            is_converted=False,
            is_fraud=False,
            is_bot=False,
            created_at__gte=cutoff,
        ).order_by('-created_at').first()

    def _mark_converted(self, click: Click, payout: float):
        """Mark a click as converted and update SmartLink aggregate totals."""
        Click.objects.filter(pk=click.pk).update(
            is_converted=True,
            payout=F('payout') + payout,
        )
        from api.smartlink.models import SmartLink
        SmartLink.objects.filter(pk=click.smartlink_id).update(
            total_conversions=F('total_conversions') + 1,
            total_revenue=F('total_revenue') + payout,
        )

    def _fire_offer_postback(self, click, offer_id: int,
                             payout: float, transaction_id: str = ''):
        """
        Fire the offer's postback URL with macro replacement.
        FIX: Previously TrackingPixelService was never called from attribution,
             so offer postback URLs (containing {click_id}, {payout} etc.)
             were never triggered on conversion.
        """
        try:
            from django.apps import apps
            from django.conf import settings as dj_settings
            offer_model_label = getattr(
                dj_settings, 'SMARTLINK_OFFER_MODEL', 'offer_inventory.Offer'
            )
            OfferModel = apps.get_model(offer_model_label)
            offer = OfferModel.objects.get(pk=offer_id)
            postback_url = getattr(offer, 'postback_url', None)
            if not postback_url:
                return
            from ..redirect.TrackingPixelService import TrackingPixelService
            TrackingPixelService().fire_postback(
                offer=offer,
                click_id=click.pk,
                payout=payout,
                currency=getattr(click.smartlink, 'default_payout_model', 'USD'),
                transaction_id=transaction_id,
                status='approved',
                click=click,
            )
        except Exception as e:
            logger.warning(
                f"Offer postback fire failed for offer#{offer_id} click#{click.pk}: {e}"
            )
