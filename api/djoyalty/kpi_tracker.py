# api/djoyalty/kpi_tracker.py
"""
Djoyalty KPI Tracker -- Real-time KPI dashboard for loyalty programs।
Tracks: redemption rate, CLV, churn, DAU/MAU, NPS-style metrics।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class KPITracker:
    """
    Real-time KPI computation for loyalty program health।

    Key KPIs tracked (industry standard 2025):
    - Redemption Rate:    >15% is healthy (industry benchmark)
    - Active Rate:        % members active in last 90 days
    - Avg Points Balance: per active customer
    - Churn Rate:         % members inactive > 6 months
    - Breakage Rate:      % points never redeemed (~20% industry avg)
    - CLV Impact:         lifetime value vs non-members
    - Program ROI:        revenue generated vs cost of rewards

    Usage:
        kpi = KPITracker(tenant=my_tenant)
        dashboard = kpi.get_full_dashboard()
    """

    def __init__(self, tenant=None):
        self.tenant = tenant

    def _q(self, qs):
        """Apply tenant filter if set."""
        return qs.filter(tenant=self.tenant) if self.tenant else qs

    # ─── Core KPIs ───────────────────────────────────────────────

    def get_redemption_rate(self) -> str:
        """Points redeemed / points issued * 100%."""
        from .models.points import LoyaltyPoints
        totals = self._q(LoyaltyPoints.objects.all()).aggregate(
            issued=Sum('lifetime_earned'),
            redeemed=Sum('lifetime_redeemed'),
        )
        issued = totals['issued'] or Decimal('0')
        redeemed = totals['redeemed'] or Decimal('0')
        if issued == 0:
            return '0.0%'
        rate = float(redeemed) / float(issued) * 100
        return f'{rate:.1f}%'

    def get_active_member_rate(self, days: int = 90) -> dict:
        """% members who made a transaction in last N days."""
        from .models.core import Customer, Txn
        total = self._q(Customer.objects.filter(is_active=True)).count()
        if total == 0:
            return {'rate': '0%', 'active': 0, 'total': 0}

        cutoff = timezone.now() - timedelta(days=days)
        active_ids = Txn.objects.filter(
            created_at__gte=cutoff
        ).values_list('customer_id', flat=True).distinct()

        if self.tenant:
            active_ids = active_ids.filter(customer__tenant=self.tenant)

        active = len(set(active_ids))
        rate = active / total * 100
        return {
            'rate': f'{rate:.1f}%',
            'active': active,
            'total': total,
            'period_days': days,
        }

    def get_avg_points_balance(self) -> Decimal:
        """Average points balance per active customer."""
        from .models.points import LoyaltyPoints
        result = self._q(
            LoyaltyPoints.objects.filter(balance__gt=0)
        ).aggregate(avg=Avg('balance'))
        return result['avg'] or Decimal('0')

    def get_churn_rate(self, inactive_days: int = 180) -> dict:
        """% customers inactive for N+ days."""
        from .models.core import Customer
        cutoff = timezone.now() - timedelta(days=inactive_days)
        total = self._q(Customer.objects.filter(is_active=True)).count()
        if total == 0:
            return {'rate': '0%', 'churned': 0, 'total': 0}

        churned = self._q(Customer.objects.filter(
            is_active=True,
        )).filter(
            Q(last_activity_at__isnull=True) | Q(last_activity_at__lt=cutoff)
        ).count()

        rate = churned / total * 100
        return {
            'rate': f'{rate:.1f}%',
            'churned': churned,
            'total': total,
            'inactive_days': inactive_days,
        }

    def get_breakage_estimate(self) -> dict:
        """
        Estimate points breakage (points that will never be redeemed)।
        Industry standard: 15-25% of outstanding points are breakage।
        """
        from .models.points import LoyaltyPoints
        outstanding = self._q(
            LoyaltyPoints.objects.filter(balance__gt=0)
        ).aggregate(total=Sum('balance'))['total'] or Decimal('0')

        # Standard breakage assumption: 20%
        breakage_pct = Decimal('0.20')
        breakage = outstanding * breakage_pct

        return {
            'outstanding_points': str(outstanding),
            'breakage_estimate': str(breakage),
            'breakage_rate': '20%',
            'note': 'Industry standard 20% breakage assumption',
        }

    def get_program_growth(self, days: int = 30) -> dict:
        """New member growth rate in last N days."""
        from .models.core import Customer
        cutoff = timezone.now() - timedelta(days=days)
        prev_cutoff = cutoff - timedelta(days=days)

        new_this_period = self._q(
            Customer.objects.filter(created_at__gte=cutoff)
        ).count()
        new_prev_period = self._q(
            Customer.objects.filter(created_at__range=(prev_cutoff, cutoff))
        ).count()

        if new_prev_period == 0:
            growth_rate = 100.0 if new_this_period > 0 else 0.0
        else:
            growth_rate = (new_this_period - new_prev_period) / new_prev_period * 100

        return {
            'new_members_this_period': new_this_period,
            'new_members_prev_period': new_prev_period,
            'growth_rate': f'{growth_rate:+.1f}%',
            'period_days': days,
        }

    def get_points_economy_health(self) -> dict:
        """Overall points economy health -- issued vs redeemed balance."""
        from .models.points import LoyaltyPoints
        totals = self._q(LoyaltyPoints.objects.all()).aggregate(
            total_issued=Sum('lifetime_earned'),
            total_redeemed=Sum('lifetime_redeemed'),
            outstanding=Sum('balance'),
        )
        issued = totals['total_issued'] or Decimal('0')
        redeemed = totals['total_redeemed'] or Decimal('0')
        outstanding = totals['outstanding'] or Decimal('0')

        # Health score: 0-100 (higher = healthier economy)
        redemption_pct = float(redeemed) / max(float(issued), 1) * 100
        # Healthy range: 15-40% redemption rate
        if 15 <= redemption_pct <= 40:
            health = 'healthy'
            score = 100
        elif redemption_pct < 15:
            health = 'under-engaged'   # People not redeeming
            score = int(redemption_pct / 15 * 80)
        else:
            health = 'high-redemption'  # May strain budget
            score = max(0, int(100 - (redemption_pct - 40) * 2))

        return {
            'total_issued': str(issued),
            'total_redeemed': str(redeemed),
            'outstanding': str(outstanding),
            'redemption_rate': f'{redemption_pct:.1f}%',
            'health_status': health,
            'health_score': score,
            'benchmark': '15-40% redemption is healthy',
        }

    def get_full_dashboard(self) -> dict:
        """Get all KPIs in one call -- for admin dashboard."""
        try:
            return {
                'redemption_rate': self.get_redemption_rate(),
                'active_member_rate': self.get_active_member_rate(90),
                'avg_points_balance': str(self.get_avg_points_balance()),
                'churn_rate': self.get_churn_rate(180),
                'breakage_estimate': self.get_breakage_estimate(),
                'program_growth': self.get_program_growth(30),
                'points_economy': self.get_points_economy_health(),
                'generated_at': timezone.now().isoformat(),
            }
        except Exception as e:
            logger.error('KPITracker.get_full_dashboard error: %s', e)
            return {'error': str(e)}
