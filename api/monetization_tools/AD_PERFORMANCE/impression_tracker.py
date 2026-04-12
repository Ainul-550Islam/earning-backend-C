"""AD_PERFORMANCE/impression_tracker.py — Real-time impression tracking."""
import logging
from decimal import Decimal
from django.utils import timezone
from ..models import ImpressionLog, AdUnit

logger = logging.getLogger(__name__)


class ImpressionTracker:
    """Records and validates ad impressions."""

    BOT_USER_AGENTS = [
        "googlebot", "bingbot", "slurp", "duckduckbot",
        "baidu", "yandex", "sogou", "exabot", "facebot",
    ]

    @classmethod
    def is_bot(cls, user_agent: str) -> bool:
        ua = (user_agent or "").lower()
        return any(b in ua for b in cls.BOT_USER_AGENTS)

    @classmethod
    def track(cls, ad_unit_id: int, ecpm: Decimal, revenue: Decimal,
               country: str = "", device_type: str = "", os: str = "",
               user=None, placement=None, ad_network=None,
               user_agent: str = "", ip_address: str = "",
               session_id: str = "", is_viewable: bool = True) -> ImpressionLog:
        is_bot = cls.is_bot(user_agent)
        log = ImpressionLog.objects.create(
            ad_unit_id=ad_unit_id, user=user,
            placement=placement, ad_network=ad_network,
            country=country or "", device_type=device_type or "", os=os or "",
            ecpm=ecpm, revenue=revenue,
            is_viewable=is_viewable, is_bot=is_bot,
            session_id=session_id or "", ip_address=ip_address or "127.0.0.1",
        )
        if not is_bot:
            from django.db.models import F
            AdUnit.objects.filter(pk=ad_unit_id).update(
                impressions=F("impressions") + 1,
                revenue=F("revenue") + revenue,
            )
        logger.debug("Impression: unit=%s ecpm=%s bot=%s", ad_unit_id, ecpm, is_bot)
        return log

    @classmethod
    def bulk_track(cls, records: list) -> int:
        logs   = [ImpressionLog(**r) for r in records]
        created = ImpressionLog.objects.bulk_create(logs, ignore_conflicts=True)
        return len(created)
