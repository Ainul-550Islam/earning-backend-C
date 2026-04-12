"""
postback_handlers/pixel_handler.py
────────────────────────────────────
Handles tracking pixel fires (impression tracking).
When an ad is rendered, a 1x1 pixel is loaded → records an Impression.
Also handles JavaScript pixel callbacks with richer data.
"""
from __future__ import annotations
import logging
from django.http import HttpResponse
from ..models import Impression, AdNetworkConfig
from ..enums import ImpressionStatus

logger = logging.getLogger(__name__)

# 1×1 transparent GIF bytes
PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
    b"!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01"
    b"\x00\x00\x02\x02D\x01\x00;"
)


class PixelHandler:
    """
    Handles impression pixel fires.
    Called by views when a 1x1 pixel request arrives.
    """

    def handle(
        self,
        network_key: str,
        offer_id: str,
        ip_address: str,
        user_agent: str,
        placement: str = "",
        user=None,
        country: str = "",
    ) -> HttpResponse:
        """
        Record an impression and return the 1×1 pixel.
        Non-blocking: impression is created, then pixel is returned immediately.
        """
        try:
            network = AdNetworkConfig.objects.get_by_key(network_key)
            if network:
                Impression.objects.create(
                    tenant=network.tenant,
                    network=network,
                    user=user,
                    offer_id=offer_id,
                    placement=placement,
                    ip_address=ip_address or None,
                    user_agent=user_agent,
                    country=country,
                    status=ImpressionStatus.RENDERED,
                )
        except Exception as exc:
            logger.debug("PixelHandler: impression creation failed (non-fatal): %s", exc)

        return HttpResponse(PIXEL_GIF, content_type="image/gif", status=200)

    def handle_viewable(
        self,
        network_key: str,
        offer_id: str,
        view_time_seconds: int,
        ip_address: str,
        user=None,
    ) -> dict:
        """
        Mark a previously recorded impression as viewable.
        Called by JavaScript when user has viewed the ad for the required time.
        Returns JSON response for JS callback.
        """
        try:
            Impression.objects.filter(
                network__network_key=network_key,
                offer_id=offer_id,
                ip_address=ip_address or None,
                is_viewable=False,
            ).order_by("-impressed_at").first()

            # Update to viewable
            updated = Impression.objects.filter(
                network__network_key=network_key,
                offer_id=offer_id,
                is_viewable=False,
            ).update(
                is_viewable=True,
                view_time_seconds=view_time_seconds,
                status=ImpressionStatus.VIEWABLE,
            )
            return {"status": "ok", "updated": updated}
        except Exception as exc:
            logger.warning("PixelHandler.handle_viewable failed: %s", exc)
            return {"status": "ok"}

    def get_impression_stats(self, network_key: str, days: int = 7) -> dict:
        """Return impression stats for a network."""
        from datetime import timedelta
        from django.utils import timezone
        from django.db.models import Count
        cutoff = timezone.now() - timedelta(days=days)
        qs = Impression.objects.filter(
            network__network_key=network_key,
            impressed_at__gte=cutoff,
        )
        total = qs.count()
        viewable = qs.filter(is_viewable=True).count()
        return {
            "total_impressions": total,
            "viewable_impressions": viewable,
            "viewability_rate_pct": round((viewable / total * 100) if total > 0 else 0, 2),
            "period_days": days,
        }


# Module-level singleton
pixel_handler = PixelHandler()
