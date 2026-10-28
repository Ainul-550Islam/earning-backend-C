# api/djoyalty/cohort_analysis.py
"""
Djoyalty Cohort Analysis -- Track loyalty cohort retention over time।
Month-by-month retention of customers who joined in the same period।
Industry standard for measuring loyalty program effectiveness।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
import calendar

logger = logging.getLogger(__name__)


class LoyaltyCohortAnalyzer:
    """
    Cohort retention analysis for loyalty program।

    A cohort = all customers who joined in month X।
    We then track: what % of them were still active in month X+1, X+2 etc।

    Usage:
        analyzer = LoyaltyCohortAnalyzer(tenant=my_tenant)
        cohorts = analyzer.get_cohort_table(months=6)
        # Returns: {
        #   '2025-01': {'size': 120, 'month_1': '80%', 'month_2': '65%', ...},
        #   '2025-02': {'size': 145, 'month_1': '82%', ...},
        # }
    """

    def __init__(self, tenant=None):
        self.tenant = tenant

    def _get_cohort_customers(self, year: int, month: int):
        """Get all customers who joined in a specific month."""
        from .models.core import Customer
        import django.utils.timezone as tz

        start = tz.datetime(year, month, 1, tzinfo=tz.utc)
        end_day = calendar.monthrange(year, month)[1]
        end = tz.datetime(year, month, end_day, 23, 59, 59, tzinfo=tz.utc)

        qs = Customer.objects.filter(
            created_at__range=(start, end),
            is_active=True,
        )
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)
        return qs

    def _get_active_in_month(self, customer_ids, year: int, month: int) -> int:
        """Count how many customers made a transaction in a specific month."""
        from .models.core import Txn
        import django.utils.timezone as tz

        start = tz.datetime(year, month, 1, tzinfo=tz.utc)
        end_day = calendar.monthrange(year, month)[1]
        end = tz.datetime(year, month, end_day, 23, 59, 59, tzinfo=tz.utc)

        return Txn.objects.filter(
            customer_id__in=customer_ids,
            created_at__range=(start, end),
        ).values('customer_id').distinct().count()

    def get_cohort_retention(self, cohort_year: int, cohort_month: int,
                              follow_months: int = 6) -> dict:
        """Get retention data for a single cohort."""
        cohort_customers = self._get_cohort_customers(cohort_year, cohort_month)
        customer_ids = list(cohort_customers.values_list('id', flat=True))
        cohort_size = len(customer_ids)

        if cohort_size == 0:
            return {
                'cohort': f'{cohort_year}-{cohort_month:02d}',
                'size': 0,
                'retention': {},
            }

        retention = {}
        for i in range(1, follow_months + 1):
            # Calculate target month
            target_month = cohort_month + i
            target_year = cohort_year + (target_month - 1) // 12
            target_month = ((target_month - 1) % 12) + 1

            # Don't analyze future months
            now = timezone.now()
            if target_year > now.year or (target_year == now.year and target_month > now.month):
                break

            active_count = self._get_active_in_month(customer_ids, target_year, target_month)
            rate = active_count / cohort_size * 100
            retention[f'month_{i}'] = {
                'active': active_count,
                'rate': f'{rate:.1f}%',
                'rate_float': round(rate, 1),
            }

        return {
            'cohort': f'{cohort_year}-{cohort_month:02d}',
            'size': cohort_size,
            'retention': retention,
        }

    def get_cohort_table(self, months: int = 6) -> list:
        """
        Get retention table for last N cohorts।
        Returns list of cohort dicts sorted by cohort date।
        """
        now = timezone.now()
        results = []

        for i in range(months):
            # Go back i months from now
            target = now - timedelta(days=30 * i)
            year = target.year
            month = target.month

            cohort = self.get_cohort_retention(
                cohort_year=year,
                cohort_month=month,
                follow_months=min(6, months - i),
            )
            if cohort['size'] > 0:
                results.append(cohort)

        return sorted(results, key=lambda x: x['cohort'])

    def get_avg_retention_rate(self, month_offset: int = 1) -> str:
        """Get average month-N retention rate across all cohorts."""
        cohorts = self.get_cohort_table(months=6)
        rates = []
        for cohort in cohorts:
            month_key = f'month_{month_offset}'
            if month_key in cohort.get('retention', {}):
                rates.append(cohort['retention'][month_key]['rate_float'])

        if not rates:
            return 'N/A'
        avg = sum(rates) / len(rates)
        return f'{avg:.1f}%'

    def get_summary(self) -> dict:
        """Get cohort analysis summary."""
        cohorts = self.get_cohort_table(months=6)
        return {
            'cohorts_analyzed': len(cohorts),
            'avg_month_1_retention': self.get_avg_retention_rate(1),
            'avg_month_3_retention': self.get_avg_retention_rate(3),
            'avg_month_6_retention': self.get_avg_retention_rate(6),
            'cohort_data': cohorts,
            'industry_benchmarks': {
                'month_1': '60-70% is good',
                'month_3': '40-50% is good',
                'month_6': '25-35% is good',
            },
            'generated_at': timezone.now().isoformat(),
        }
