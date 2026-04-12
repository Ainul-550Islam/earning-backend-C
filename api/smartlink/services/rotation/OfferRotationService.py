import random
import logging
from ...models import OfferPoolEntry, OfferRotationLog
from ...choices import RotationMethod
from ...constants import ROTATION_MAX_RETRIES
from .CapTrackerService import CapTrackerService
from .EPCOptimizer import EPCOptimizer

logger = logging.getLogger('smartlink.rotation')


class OfferRotationService:
    """
    Select an offer from the pool using the configured rotation method.
    Supports: weighted random, round-robin, EPC-optimized, priority-based.
    """

    def __init__(self):
        self.cap_tracker = CapTrackerService()
        self.epc_optimizer = EPCOptimizer()

    def select(self, smartlink, eligible_entries: list, request_context: dict):
        """
        Select a single OfferPoolEntry from the eligible list.

        Args:
            smartlink: SmartLink instance
            eligible_entries: list of OfferPoolEntry objects
            request_context: dict with country, device_type, etc.

        Returns:
            OfferPoolEntry or None if no valid offer found
        """
        if not eligible_entries:
            return None

        # Filter out capped entries
        available = self._filter_capped(eligible_entries, request_context)
        if not available:
            logger.debug(f"[{smartlink.slug}] All offers capped, returning None")
            return None

        # Get rotation method
        method = getattr(smartlink, 'rotation_method', RotationMethod.WEIGHTED)
        try:
            rotation_config = smartlink.rotation_config
            if rotation_config.auto_optimize_epc:
                method = RotationMethod.EPC_OPTIMIZED
        except Exception:
            pass

        # Select based on method
        selected = None
        reason = 'weighted_random'

        if method == RotationMethod.EPC_OPTIMIZED:
            selected = self.epc_optimizer.select(
                entries=available,
                country=request_context.get('country', ''),
                device_type=request_context.get('device_type', ''),
            )
            reason = 'epc_optimized'
            if selected is None:
                # Fallback to weighted if EPC data insufficient
                selected = self._weighted_random(available)
                reason = 'weighted_random'

        elif method == RotationMethod.PRIORITY:
            selected = self._priority_select(available)
            reason = 'priority'

        elif method == RotationMethod.ROUND_ROBIN:
            selected = self._round_robin(smartlink, available)
            reason = 'round_robin'

        else:
            # Default: weighted random
            selected = self._weighted_random(available)
            reason = 'weighted_random'

        if selected:
            self._log_rotation(smartlink, selected, reason, request_context)
            self.cap_tracker.increment(selected, request_context)

        return selected

    def _weighted_random(self, entries: list):
        """
        Weighted random selection.
        Offers with higher weights get proportionally more traffic.
        """
        if not entries:
            return None

        weights = [e.weight for e in entries]
        total = sum(weights)
        if total == 0:
            return random.choice(entries)

        rand = random.uniform(0, total)
        cumulative = 0
        for entry, weight in zip(entries, weights):
            cumulative += weight
            if rand <= cumulative:
                return entry

        return entries[-1]

    def _priority_select(self, entries: list):
        """Return the highest-priority active offer."""
        if not entries:
            return None
        sorted_entries = sorted(entries, key=lambda e: e.priority, reverse=True)
        return sorted_entries[0]

    def _round_robin(self, smartlink, entries: list):
        """
        Round-robin selection using Redis to track last-used index.
        Ensures offers are served evenly in sequence.
        """
        from django.core.cache import cache
        cache_key = f"sl_rr:{smartlink.pk}"
        last_index = cache.get(cache_key, -1)
        next_index = (last_index + 1) % len(entries)
        cache.set(cache_key, next_index, 3600)
        return entries[next_index]

    def _filter_capped(self, entries: list, context: dict) -> list:
        """
        Remove entries that have reached their daily/monthly cap.
        Uses Redis cap tracker for fast check.
        """
        available = []
        for entry in entries:
            if not self.cap_tracker.is_capped(entry):
                available.append(entry)
            else:
                logger.debug(f"Offer#{entry.offer_id} is capped, skipping")
        return available

    def _log_rotation(self, smartlink, entry: OfferPoolEntry, reason: str, context: dict):
        """Async log which offer was selected and why."""
        try:
            OfferRotationLog.objects.create(
                smartlink=smartlink,
                offer=entry.offer,
                selected_reason=reason,
                offer_weight=entry.weight,
                offer_epc=entry.epc_override,
                country=context.get('country', ''),
                device_type=context.get('device_type', ''),
            )
        except Exception as e:
            logger.warning(f"Failed to log rotation: {e}")
