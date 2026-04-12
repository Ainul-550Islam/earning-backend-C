# api/offer_inventory/user_behavior_analysis/retention_engine.py
"""Retention Engine — Day-N retention analysis and cohort curves."""
import logging
from datetime import timedelta, date
from django.utils import timezone

logger = logging.getLogger(__name__)


class RetentionEngine:
    """User retention analysis."""

    @staticmethod
    def get_day_n_retention(cohort_date: date, n_days: int) -> float:
        """
        Day-N retention: % of cohort users active on day N.
        cohort_date: date users first signed up.
        """
        from django.contrib.auth import get_user_model
        from api.offer_inventory.models import Click
        User = get_user_model()

        cohort_users = list(
            User.objects.filter(
                date_joined__date=cohort_date,
            ).values_list('id', flat=True)
        )
        if not cohort_users:
            return 0.0

        target_date  = cohort_date + timedelta(days=n_days)
        returned     = (
            Click.objects.filter(
                user_id__in=cohort_users,
                created_at__date=target_date,
            ).values('user_id').distinct().count()
        )
        return round(returned / len(cohort_users) * 100, 1)

    @staticmethod
    def get_retention_curve(cohort_date: date) -> list:
        """Full D1/D3/D7/D14/D30 retention curve for a cohort."""
        return [
            {
                'day'           : d,
                'retention_pct' : RetentionEngine.get_day_n_retention(cohort_date, d),
            }
            for d in [1, 3, 7, 14, 30]
        ]

    @staticmethod
    def get_weekly_retention(weeks: int = 4) -> list:
        """Week-over-week retention rates."""
        from django.contrib.auth import get_user_model
        from api.offer_inventory.models import Click
        User  = get_user_model()
        today = timezone.now().date()
        data  = []
        for week in range(weeks):
            week_start = today - timedelta(days=(week + 1) * 7)
            week_end   = today - timedelta(days=week * 7)
            cohort     = User.objects.filter(
                date_joined__date__gte=week_start,
                date_joined__date__lt =week_end,
            ).values_list('id', flat=True)
            if not cohort:
                continue
            next_week_start = week_end
            next_week_end   = week_end + timedelta(days=7)
            returned = Click.objects.filter(
                user_id__in=cohort,
                created_at__date__gte=next_week_start,
                created_at__date__lt =next_week_end,
            ).values('user_id').distinct().count()
            data.append({
                'cohort_week'   : week_start.strftime('%Y-%m-%d'),
                'cohort_size'   : len(cohort),
                'returned_next' : returned,
                'retention_pct' : round(returned / len(cohort) * 100, 1),
            })
        return data
