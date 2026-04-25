# api/payment_gateways/offers/ConversionCapEngine.py
# Conversion cap enforcement — prevents over-delivery to advertisers

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class ConversionCapEngine:
    """
    Enforces daily, monthly, and total conversion caps on offers.

    CPAlead uses caps to:
        1. Protect advertiser budget from overspending
        2. Fair distribution across publishers
        3. Auto-pause offers when cap is hit
        4. Alert advertiser when approaching cap

    Cap types:
        - daily_cap:    Max conversions per day
        - monthly_cap:  Max conversions per month
        - total_cap:    Max total conversions (ever)
        - daily_budget: Max spend per day in USD
        - total_budget: Max total spend in USD

    When cap is hit:
        - Offer status → 'paused' (auto)
        - Publisher gets 'cap_reached' response
        - Advertiser gets email alert
        - SmartLink auto-routes to next offer
    """

    CACHE_TTL = 300  # 5 minutes

    def check_caps(self, offer, publisher_id: int = None) -> dict:
        """
        Check if an offer has available capacity.

        Returns:
            dict: {
                'can_convert': bool,
                'reason':      str (if blocked),
                'daily_remaining':   int | None,
                'monthly_remaining': int | None,
                'total_remaining':   int | None,
            }
        """
        # Cache key per offer (not per publisher — caps are global)
        cache_key = f'cap_check:{offer.id}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        result = self._check_all_caps(offer)
        cache.set(cache_key, result, self.CACHE_TTL)
        return result

    def record_conversion(self, offer):
        """
        Record a conversion and check if caps are now hit.
        Call this after every approved conversion.
        """
        # Clear cap cache so next request gets fresh count
        cache.delete(f'cap_check:{offer.id}')

        # Check if any cap is now exactly hit → pause offer
        self._auto_pause_if_capped(offer)

    def get_cap_status(self, offer) -> dict:
        """
        Get detailed cap utilization for admin/advertiser dashboard.
        """
        from api.payment_gateways.tracking.models import Conversion
        from django.db.models import Sum, Count

        today  = timezone.now().date()
        month  = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        base_qs = Conversion.objects.filter(offer=offer, status='approved')

        daily   = base_qs.filter(created_at__date=today)
        monthly = base_qs.filter(created_at__gte=month)
        total   = base_qs

        daily_count   = daily.count()
        monthly_count = monthly.count()
        total_count   = total.count()

        daily_spend   = float(daily.aggregate(s=Sum('cost'))['s'] or 0)
        total_spend   = float(total.aggregate(s=Sum('cost'))['s'] or 0)

        return {
            'daily_conversions':    daily_count,
            'daily_cap':            offer.daily_cap,
            'daily_remaining':      (offer.daily_cap - daily_count) if offer.daily_cap else None,
            'daily_pct_used':       round(daily_count / offer.daily_cap * 100, 1) if offer.daily_cap else None,

            'monthly_conversions':  monthly_count,
            'monthly_cap':          offer.monthly_cap,
            'monthly_remaining':    (offer.monthly_cap - monthly_count) if offer.monthly_cap else None,

            'total_conversions':    total_count,
            'total_cap':            offer.total_cap,
            'total_remaining':      (offer.total_cap - total_count) if offer.total_cap else None,

            'daily_spend':          daily_spend,
            'daily_budget':         float(offer.daily_budget) if offer.daily_budget else None,
            'total_spend':          total_spend,
            'total_budget':         float(offer.total_budget) if offer.total_budget else None,

            'is_capped':            not self.check_caps(offer)['can_convert'],
            'cap_reset_in':         self._time_until_daily_reset(),
        }

    def reset_daily_caps(self):
        """
        Called at midnight to reset daily cap counts.
        Scheduled via Celery Beat.
        """
        from api.payment_gateways.offers.models import Offer
        # Re-activate paused offers that were only paused due to daily cap
        paused = Offer.objects.filter(
            status='paused',
            daily_cap__isnull=False,
        )
        reactivated = 0
        for offer in paused:
            # If total/monthly cap is OK, reactivate
            result = self._check_all_caps(offer, ignore_daily=True)
            if result['can_convert']:
                offer.status = 'active'
                offer.save(update_fields=['status'])
                cache.delete(f'cap_check:{offer.id}')
                reactivated += 1

        logger.info(f'Daily cap reset: {reactivated} offers reactivated')
        return reactivated

    def _check_all_caps(self, offer, ignore_daily: bool = False) -> dict:
        """Internal: check all caps against current counts."""
        from api.payment_gateways.tracking.models import Conversion
        from django.db.models import Sum, Count

        today  = timezone.now().date()
        month  = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        base   = Conversion.objects.filter(offer=offer, status='approved')

        # ── Daily cap ──────────────────────────────────────────────────────────
        if offer.daily_cap and not ignore_daily:
            daily_count = base.filter(created_at__date=today).count()
            if daily_count >= offer.daily_cap:
                return {
                    'can_convert':       False,
                    'reason':            f'Daily cap reached ({offer.daily_cap})',
                    'daily_remaining':   0,
                    'monthly_remaining': None,
                    'total_remaining':   None,
                }

        # ── Monthly cap ────────────────────────────────────────────────────────
        if offer.monthly_cap:
            monthly_count = base.filter(created_at__gte=month).count()
            if monthly_count >= offer.monthly_cap:
                return {
                    'can_convert':       False,
                    'reason':            f'Monthly cap reached ({offer.monthly_cap})',
                    'daily_remaining':   None,
                    'monthly_remaining': 0,
                    'total_remaining':   None,
                }

        # ── Total cap ──────────────────────────────────────────────────────────
        if offer.total_cap:
            total_count = base.count()
            if total_count >= offer.total_cap:
                return {
                    'can_convert':       False,
                    'reason':            f'Total cap reached ({offer.total_cap})',
                    'daily_remaining':   None,
                    'monthly_remaining': None,
                    'total_remaining':   0,
                }

        # ── Daily budget ───────────────────────────────────────────────────────
        if offer.daily_budget:
            daily_spend = base.filter(
                created_at__date=today
            ).aggregate(s=Sum('cost'))['s'] or Decimal('0')
            if daily_spend >= offer.daily_budget:
                return {
                    'can_convert':   False,
                    'reason':        f'Daily budget exhausted (${offer.daily_budget})',
                    'daily_remaining':0,
                    'monthly_remaining': None,
                    'total_remaining':   None,
                }

        # ── Total budget ───────────────────────────────────────────────────────
        if offer.total_budget:
            total_spend = base.aggregate(s=Sum('cost'))['s'] or Decimal('0')
            if total_spend >= offer.total_budget:
                return {
                    'can_convert':       False,
                    'reason':            f'Total budget exhausted (${offer.total_budget})',
                    'daily_remaining':   None,
                    'monthly_remaining': None,
                    'total_remaining':   0,
                }

        # ── All caps OK ────────────────────────────────────────────────────────
        daily_count = base.filter(created_at__date=today).count() if offer.daily_cap else 0
        return {
            'can_convert':       True,
            'reason':            '',
            'daily_remaining':   (offer.daily_cap - daily_count) if offer.daily_cap else None,
            'monthly_remaining': None,
            'total_remaining':   None,
        }

    def _auto_pause_if_capped(self, offer):
        """Automatically pause an offer if any hard cap is reached."""
        result = self._check_all_caps(offer)
        if not result['can_convert'] and offer.status == 'active':
            from api.payment_gateways.offers.models import Offer
            Offer.objects.filter(id=offer.id).update(status='paused')
            logger.info(f'Offer {offer.id} auto-paused: {result["reason"]}')
            # TODO: Send email to advertiser

    def _time_until_daily_reset(self) -> str:
        """How long until midnight (daily cap reset)."""
        now       = timezone.now()
        midnight  = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        delta     = midnight - now
        hours     = int(delta.seconds / 3600)
        minutes   = int((delta.seconds % 3600) / 60)
        return f'{hours}h {minutes}m'
