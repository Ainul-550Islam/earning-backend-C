import logging
from django.core.cache import cache
from django.utils import timezone
from ...models import OfferPoolEntry, OfferCapTracker
from ...choices import CapPeriod
from ...constants import CAP_BUFFER_PERCENT

logger = logging.getLogger('smartlink.cap_tracker')


class CapTrackerService:
    """
    Enforce daily and monthly click caps per offer per pool.
    Uses Redis for fast real-time cap checking.
    DB records are the source of truth; reset by Celery task at midnight UTC.
    """

    def is_capped(self, entry: OfferPoolEntry) -> bool:
        """
        Check if the offer entry has reached its daily cap.
        Redis-first for <1ms check.
        """
        if not entry.cap_per_day:
            return False  # No cap set

        cache_key = self._daily_cap_key(entry)
        count = cache.get(cache_key)

        if count is None:
            # Cache miss — load from DB
            count = self._load_count_from_db(entry, CapPeriod.DAILY)
            cache.set(cache_key, count, 3700)  # slightly over 1 hour

        effective_cap = self._apply_buffer(entry.cap_per_day)
        return count >= effective_cap

    def increment(self, entry: OfferPoolEntry, context: dict = None):
        """
        Increment cap counter for an offer entry.
        Updates Redis atomically; DB is updated asynchronously.
        """
        if not entry.cap_per_day and not entry.cap_per_month:
            return  # No caps, skip tracking

        if entry.cap_per_day:
            cache_key = self._daily_cap_key(entry)
            try:
                cache.incr(cache_key)
            except ValueError:
                # Key doesn't exist yet
                count = self._load_count_from_db(entry, CapPeriod.DAILY)
                cache.set(cache_key, count + 1, 3700)

        if entry.cap_per_month:
            monthly_key = self._monthly_cap_key(entry)
            try:
                cache.incr(monthly_key)
            except ValueError:
                count = self._load_count_from_db(entry, CapPeriod.MONTHLY)
                cache.set(monthly_key, count + 1, 86400 * 32)

        # Async DB update
        try:
            from ...tasks.cap_reset_tasks import update_cap_tracker_db
            update_cap_tracker_db.delay(entry.pk)
        except Exception as e:
            logger.warning(f"Failed to queue cap DB update: {e}")

    def reset_daily_caps(self):
        """
        Reset all daily cap counters. Called at midnight UTC.
        Clears Redis keys and resets DB OfferCapTracker records.
        """
        from ...models import OfferPoolEntry
        today = timezone.now().date()

        entries = OfferPoolEntry.objects.filter(
            is_active=True,
            cap_per_day__isnull=False,
        )

        reset_count = 0
        for entry in entries:
            cache.delete(self._daily_cap_key(entry))
            OfferCapTracker.objects.filter(
                pool_entry=entry,
                period=CapPeriod.DAILY,
                period_date=today,
            ).update(clicks_count=0, is_capped=False)
            reset_count += 1

        logger.info(f"Daily caps reset for {reset_count} entries.")
        return reset_count

    def get_usage(self, entry: OfferPoolEntry) -> dict:
        """Return current cap usage for an entry."""
        daily_used = 0
        monthly_used = 0

        if entry.cap_per_day:
            cache_key = self._daily_cap_key(entry)
            daily_used = cache.get(cache_key) or self._load_count_from_db(entry, CapPeriod.DAILY)

        if entry.cap_per_month:
            monthly_key = self._monthly_cap_key(entry)
            monthly_used = cache.get(monthly_key) or self._load_count_from_db(entry, CapPeriod.MONTHLY)

        return {
            'daily_used': daily_used,
            'daily_cap': entry.cap_per_day,
            'daily_remaining': max(0, (entry.cap_per_day or 0) - daily_used),
            'monthly_used': monthly_used,
            'monthly_cap': entry.cap_per_month,
            'monthly_remaining': max(0, (entry.cap_per_month or 0) - monthly_used),
            'is_daily_capped': entry.cap_per_day and daily_used >= entry.cap_per_day,
            'is_monthly_capped': entry.cap_per_month and monthly_used >= entry.cap_per_month,
        }

    # ── Private ──────────────────────────────────────────────────────

    def _daily_cap_key(self, entry: OfferPoolEntry) -> str:
        today = timezone.now().date().isoformat()
        return f"cap:daily:{entry.pk}:{today}"

    def _monthly_cap_key(self, entry: OfferPoolEntry) -> str:
        now = timezone.now()
        month = f"{now.year}-{now.month:02d}"
        return f"cap:monthly:{entry.pk}:{month}"

    def _load_count_from_db(self, entry: OfferPoolEntry, period: str) -> int:
        today = timezone.now().date()
        try:
            tracker = OfferCapTracker.objects.get(
                pool_entry=entry,
                period=period,
                period_date=today,
            )
            return tracker.clicks_count
        except OfferCapTracker.DoesNotExist:
            return 0

    def _apply_buffer(self, cap: int) -> int:
        """Apply a buffer to prevent going slightly over cap due to race conditions."""
        buffer = max(1, int(cap * CAP_BUFFER_PERCENT / 100))
        return cap - buffer
