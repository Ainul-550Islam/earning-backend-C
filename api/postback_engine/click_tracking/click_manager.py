"""
click_tracking/click_manager.py – Click generation, validation & analytics.
"""
import hashlib
import logging
from typing import Optional

from django.utils import timezone

from ..constants import CLICK_EXPIRY_HOURS
from ..enums import ClickStatus, DeviceType
from ..exceptions import ClickExpiredException, ClickNotFoundException, FraudDetectedException
from ..models import ClickLog, AdNetworkConfig

logger = logging.getLogger(__name__)


class ClickManager:
    """
    Handles the full click lifecycle:
      generate → validate → fingerprint → expire → analytics
    """

    def generate(
        self,
        user,
        network: AdNetworkConfig,
        offer_id: str,
        offer_name: str = "",
        ip_address: str = "",
        user_agent: str = "",
        device_type: str = DeviceType.UNKNOWN,
        country: str = "",
        sub_id: str = "",
        referrer: str = "",
        metadata: dict = None,
    ) -> ClickLog:
        """
        Create a new ClickLog with a unique click_id.
        Async: dispatches fraud scan + geo enrichment to Celery.
        """
        from ..services import generate_click
        click_log = generate_click(
            user=user,
            network=network,
            offer_id=offer_id,
            offer_name=offer_name,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
            country=country,
            sub_id=sub_id,
            referrer=referrer,
            metadata=metadata or {},
        )

        # Async: fingerprint + fraud scan
        from ..tasks import process_click_task
        process_click_task.apply_async(
            args=[str(click_log.id)], countdown=1
        )

        return click_log

    def validate(self, click_id: str) -> ClickLog:
        """Validate a click for conversion attribution."""
        from ..services import resolve_click
        return resolve_click(click_id)

    def build_offer_url(
        self,
        base_url: str,
        click_log: ClickLog,
        extra_params: dict = None,
    ) -> str:
        """
        Replace {click_id} / {sub_id} / {user_id} macros in offer URL.
        """
        params = {
            "click_id": click_log.click_id,
            "sub_id": click_log.sub_id,
            "user_id": str(click_log.user_id) if click_log.user_id else "",
            "offer_id": click_log.offer_id,
            **(extra_params or {}),
        }
        url = base_url
        for key, value in params.items():
            url = url.replace(f"{{{key}}}", str(value))
        return url

    def get_device_fingerprint(self, ip: str, user_agent: str) -> str:
        """
        Generate a deterministic device fingerprint from IP + UA.
        In production: combine with canvas fingerprint from JS SDK.
        """
        raw = f"{ip}:{user_agent}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def expire_stale_clicks(self) -> int:
        """Expire clicks past their expiry time. Returns count expired."""
        expired = ClickLog.objects.expired().update(status=ClickStatus.EXPIRED)
        logger.info("expired %d stale clicks", expired)
        return expired

    def get_click_stats_for_offer(self, offer_id: str, days: int = 7) -> dict:
        """Return click/conversion stats for an offer."""
        from django.db.models import Count
        cutoff = timezone.now() - timezone.timedelta(days=days)
        qs = ClickLog.objects.filter(offer_id=offer_id, clicked_at__gte=cutoff)
        agg = qs.aggregate(
            total_clicks=Count("id"),
            converted=Count("id", filter={"converted": True}),
            fraud=Count("id", filter={"is_fraud": True}),
        )
        total = agg["total_clicks"] or 0
        conv = agg["converted"] or 0
        return {
            "offer_id": offer_id,
            "total_clicks": total,
            "conversions": conv,
            "fraud_clicks": agg["fraud"] or 0,
            "conversion_rate": round((conv / total * 100) if total > 0 else 0, 2),
            "period_days": days,
        }


# Module-level singleton
click_manager = ClickManager()
