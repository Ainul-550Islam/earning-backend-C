"""
SmartLink Impression Tracking Service
Records pre-click impressions, deduplicates by IP+SmartLink per 24h,
and provides aggregation for analytics.
"""
import logging
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q, Count, Sum
from api.smartlink.models.impression import ImpressionLog

logger = logging.getLogger('smartlink.impressions')


class ImpressionTrackingService:
    """
    Record and analyse SmartLink ad impressions.

    Fired by the 1×1 tracking pixel endpoint (/pixel/fire/?sl=<slug>&offer=<id>)
    before the user clicks. Enables:
      - Impression-to-click ratio (VTR)
      - View-through attribution within a 24h window
      - CPM campaign billing verification
    """

    DEDUP_WINDOW_HOURS = 24

    # ── Recording ──────────────────────────────────────────────────────────────

    def record(self, smartlink, context: dict, offer_id: int = None) -> 'ImpressionLog | None':
        """
        Record a single impression. Returns the created ImpressionLog or None if
        the impression is a bot (bots are still counted in a separate flag).

        Args:
            smartlink: SmartLink model instance
            context: dict with ip, user_agent, country, device_type, etc.
            offer_id: optional — which offer this impression is for
        """
        from api.smartlink.models.impression import ImpressionLog

        ip          = context.get('ip', '')
        country     = context.get('country', '')
        device_type = context.get('device_type', '')
        os_type     = context.get('os', '')
        browser     = context.get('browser', '')
        referrer    = context.get('referrer', '')[:1000]
        sub1        = context.get('sub1', '')[:255]
        sub2        = context.get('sub2', '')[:255]
        is_bot      = context.get('_is_bot', False)
        is_unique   = self._is_unique(smartlink.pk, ip)

        try:
            log = ImpressionLog.objects.create(
                smartlink=smartlink,
                offer_id=offer_id,
                ip=ip,
                country=country,
                device_type=device_type,
                os_type=os_type,
                browser=browser,
                referrer=referrer,
                sub1=sub1,
                sub2=sub2,
                is_unique=is_unique,
                is_bot=is_bot,
            )

            # Mark this IP as seen (for dedup) if it's the first impression
            if is_unique and not is_bot:
                self._mark_seen(smartlink.pk, ip)

            # Increment SmartLink impression counter atomically
            self._increment_counter(smartlink)

            logger.debug(
                f"Impression recorded: [{smartlink.slug}] "
                f"ip={ip[:15]} country={country} unique={is_unique}"
            )
            return log

        except Exception as e:
            logger.error(f"ImpressionLog create failed: {e}", exc_info=True)
            return None

    # ── Deduplication ──────────────────────────────────────────────────────────

    def _is_unique(self, smartlink_id: int, ip: str) -> bool:
        """Return True if this IP has NOT had an impression in the last 24 hours."""
        if not ip:
            return False
        cache_key = self._dedup_key(smartlink_id, ip)
        return cache.get(cache_key) is None

    def _mark_seen(self, smartlink_id: int, ip: str):
        """Mark this IP as seen for dedup window."""
        cache_key = self._dedup_key(smartlink_id, ip)
        cache.set(cache_key, 1, self.DEDUP_WINDOW_HOURS * 3600)

    def _dedup_key(self, smartlink_id: int, ip: str) -> str:
        import hashlib
        h = hashlib.md5(ip.encode()).hexdigest()
        return f"imp_dedup:{smartlink_id}:{h}"

    # ── Counter ────────────────────────────────────────────────────────────────

    def _increment_counter(self, smartlink):
        """Increment SmartLink total_impressions via Redis + async DB write."""
        cache_key = f"imp_count:{smartlink.pk}"
        try:
            cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, 3700)

    # ── Analytics ─────────────────────────────────────────────────────────────

    def get_summary(self, smartlink, days: int = 30) -> dict:
        """
        Return impression summary for a SmartLink over the past N days.
        Includes total, unique, bot count, and CTR vs click data.
        """
        from api.smartlink.models.impression import ImpressionLog
        from api.smartlink.models import Click
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days)
        qs = ImpressionLog.objects.filter(
            smartlink=smartlink,
            created_at__gte=cutoff,
            is_bot=False,
        )
        total_impressions  = qs.count()
        unique_impressions = qs.filter(is_unique=True).count()

        total_clicks = Click.objects.filter(
            smartlink=smartlink,
            created_at__gte=cutoff,
            is_bot=False,
            is_fraud=False,
        ).count()

        ctr = round(
            (total_clicks / total_impressions * 100) if total_impressions > 0 else 0, 2
        )

        return {
            'period_days':        days,
            'total_impressions':  total_impressions,
            'unique_impressions': unique_impressions,
            'total_clicks':       total_clicks,
            'ctr_percent':        ctr,
            'duplicate_rate':     round(
                ((total_impressions - unique_impressions) / total_impressions * 100)
                if total_impressions > 0 else 0, 2
            ),
        }

    def get_by_country(self, smartlink, days: int = 30) -> list:
        """Top countries by impression count."""
        from api.smartlink.models.impression import ImpressionLog
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return list(
            ImpressionLog.objects.filter(
                smartlink=smartlink,
                created_at__gte=cutoff,
                is_bot=False,
            )
            .values('country')
            .annotate(
                total=Count('id'),
                unique=Count('id', filter=Q(is_unique=True)),
            )
            .order_by('-total')[:20]
        )

    def get_by_device(self, smartlink, days: int = 30) -> list:
        """Impression breakdown by device type."""
        from api.smartlink.models.impression import ImpressionLog
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return list(
            ImpressionLog.objects.filter(
                smartlink=smartlink,
                created_at__gte=cutoff,
                is_bot=False,
            )
            .values('device_type')
            .annotate(total=Count('id'), unique=Count('id', filter=Q(is_unique=True)))
            .order_by('-total')
        )

    def check_view_through_attribution(self, click) -> bool:
        """
        View-through attribution check.
        Returns True if there was an impression for the same SmartLink + IP
        within the last 24h before this click — meaning the user viewed the
        ad before clicking (VTA). Stored on click for reporting.
        """
        from api.smartlink.models.impression import ImpressionLog
        cutoff = timezone.now() - timezone.timedelta(hours=24)
        return ImpressionLog.objects.filter(
            smartlink_id=click.smartlink_id,
            ip=click.ip,
            created_at__gte=cutoff,
            is_bot=False,
        ).exists()
