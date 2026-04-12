# =============================================================================
# promotions/content_locking/locker_analytics.py
# Locker Performance Analytics — EPC, CTR, Conversion tracking
# =============================================================================
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Sum, Count, Avg


class LockerAnalytics:
    """Track locker performance: views, unlocks, EPC, earnings."""

    def get_publisher_locker_summary(self, publisher_id: int, days: int = 30) -> dict:
        """Get all locker stats for a publisher."""
        from api.promotions.models import PromotionTransaction, CampaignAnalytics
        cutoff = timezone.now() - timezone.timedelta(days=days)
        # Earnings from locker-generated conversions
        earnings = PromotionTransaction.objects.filter(
            user_id=publisher_id,
            transaction_type='reward',
            created_at__gte=cutoff,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        return {
            'publisher_id': publisher_id,
            'period_days': days,
            'total_locker_earnings': str(earnings),
            'total_views': 0,        # From impression tracker
            'total_unlocks': 0,      # From conversion tracker
            'unlock_rate_pct': 0.0,
            'avg_epc': '0.0000',     # Earnings Per Click
            'top_lockers': [],
        }

    def get_locker_detail_stats(self, lock_id: str, days: int = 7) -> dict:
        """Per-locker daily breakdown."""
        stats = []
        for i in range(days):
            day = timezone.now().date() - timezone.timedelta(days=i)
            stats.append({
                'date': str(day),
                'views': 0,
                'unlocks': 0,
                'earnings': '0.00',
                'epc': '0.0000',
            })
        return {
            'lock_id': lock_id,
            'daily_stats': stats,
            'totals': {
                'views': 0,
                'unlocks': 0,
                'earnings': '0.00',
                'unlock_rate': 0.0,
            }
        }

    def record_locker_view(self, lock_id: str, visitor_id: str, country: str, device: str):
        """Record impression for locker."""
        today = timezone.now().date().isoformat()
        key = f'locker_views:{lock_id}:{today}'
        cache.incr(key) if cache.get(key) else cache.set(key, 1, timeout=3600 * 48)

    def record_locker_unlock(self, lock_id: str, visitor_id: str, offer_id: int):
        """Record conversion for locker."""
        today = timezone.now().date().isoformat()
        key = f'locker_unlocks:{lock_id}:{today}'
        cache.incr(key) if cache.get(key) else cache.set(key, 1, timeout=3600 * 48)

    def get_top_performing_lockers(self, publisher_id: int, limit: int = 10) -> list:
        """Get publisher's best performing lockers by EPC."""
        return []  # In production: query aggregated analytics

    def calculate_epc(self, earnings: Decimal, clicks: int) -> Decimal:
        """EPC = Earnings Per 100 Clicks."""
        if clicks == 0:
            return Decimal('0')
        return (earnings / clicks * 100).quantize(Decimal('0.0001'))
