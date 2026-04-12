# api/promotions/data_science/cohort_analysis.py
cohort_analysis.py
# Cohort Analysis — Retention Tracking
# =============================================================================

import logging
from dataclasses import dataclass
from datetime import date, timedelta

logger = logging.getLogger('data_science.cohort')


@dataclass
class CohortRow:
    cohort_month:    str       # '2024-01'
    cohort_size:     int
    retention:       dict      # {month_0: 100%, month_1: 60%, ...}


@dataclass
class CohortReport:
    cohorts:         list[CohortRow]
    avg_retention:   dict       # average across all cohorts
    best_cohort:     str
    worst_cohort:    str


class CohortAnalyzer:
    """
    Monthly cohort analysis — কোন মাসের user গুলো কতদিন active থাকে।
    Retention curve visualize করতে সাহায্য করে।
    """

    def analyze(self, months_back: int = 12) -> CohortReport:
        """Cohort analysis চালায়।"""
        from django.contrib.auth import get_user_model
        from api.promotions.models import TaskSubmission
        from django.db.models import Min, Count

        User = get_user_model()
        today = date.today()

        # প্রতি cohort month এর user গুলো
        cohort_rows = []
        for m in range(months_back, 0, -1):
            cohort_start = (today.replace(day=1) - timedelta(days=m*30)).replace(day=1)
            cohort_end   = (cohort_start + timedelta(days=32)).replace(day=1)

            cohort_users = list(
                User.objects.filter(
                    date_joined__gte=cohort_start,
                    date_joined__lt=cohort_end,
                ).values_list('id', flat=True)
            )

            if not cohort_users:
                continue

            cohort_size  = len(cohort_users)
            retention    = {}

            for period in range(min(m, 6)):  # সর্বোচ্চ ৬ মাস retention
                period_start = cohort_start + timedelta(days=period * 30)
                period_end   = period_start + timedelta(days=30)

                active_users = TaskSubmission.objects.filter(
                    worker_id__in=cohort_users,
                    submitted_at__date__gte=period_start,
                    submitted_at__date__lt=period_end,
                ).values('worker_id').distinct().count()

                retention[f'month_{period}'] = round(active_users / cohort_size * 100, 1)

            cohort_rows.append(CohortRow(
                cohort_month = cohort_start.strftime('%Y-%m'),
                cohort_size  = cohort_size,
                retention    = retention,
            ))

        if not cohort_rows:
            return CohortReport([], {}, '', '')

        # Average retention
        all_periods = set()
        for row in cohort_rows:
            all_periods.update(row.retention.keys())

        avg_retention = {}
        for period in sorted(all_periods):
            values = [row.retention[period] for row in cohort_rows if period in row.retention]
            avg_retention[period] = round(sum(values) / len(values), 1) if values else 0.0

        # Best and worst cohort (by month_1 retention)
        with_m1 = [r for r in cohort_rows if 'month_1' in r.retention]
        if with_m1:
            best   = max(with_m1, key=lambda r: r.retention.get('month_1', 0)).cohort_month
            worst  = min(with_m1, key=lambda r: r.retention.get('month_1', 0)).cohort_month
        else:
            best = worst = ''

        return CohortReport(
            cohorts=cohort_rows, avg_retention=avg_retention,
            best_cohort=best, worst_cohort=worst,
        )
