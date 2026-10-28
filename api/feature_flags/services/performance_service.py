"""
NEW FILE — Performance impact analysis service.

Implements Missing Component #10 (Performance Metrics & Optimization):
previously there was no way to tell whether a flag's rollout percentage
actually matched its observed enable rate, or to get a simple
optimization signal for a flag.
"""
from typing import Dict, Any

from django.db.models import Sum

from ..models.feature_flag import FeatureFlag
from ..models.flag_analytics import FlagAnalytics


class PerformanceService:
    """Lightweight analysis of how a flag's configuration tracks its
    observed evaluation data."""

    def get_flag_impact(self, flag_id: int) -> Dict[str, Any]:
        """Summarize a flag's observed evaluation volume and enable rate."""
        flag = FeatureFlag.objects.get(id=flag_id)
        analytics = FlagAnalytics.objects.filter(flag=flag)

        total_evaluations = analytics.aggregate(total=Sum('evaluation_count'))['total'] or 0
        total_enabled = analytics.aggregate(total=Sum('enabled_count'))['total'] or 0

        enable_rate = round((total_enabled / total_evaluations * 100) if total_evaluations else 0, 2)

        return {
            'flag_name': flag.name,
            'total_evaluations': total_evaluations,
            'total_enabled': total_enabled,
            'observed_enable_rate': enable_rate,
            'configured_rollout_percentage': flag.rollout_percentage,
            'optimization_score': self.calculate_optimization_score(flag, enable_rate),
        }

    def calculate_optimization_score(self, flag: FeatureFlag, observed_enable_rate: float = None) -> float:
        """
        A 0-100 score where 100 means the observed enable rate exactly
        matches the configured rollout percentage (i.e. the flag is
        behaving as configured), and lower scores indicate drift that may
        be worth investigating (e.g. targeting rules overriding the
        percentage rollout more than expected).
        """
        if flag.rollout_percentage == 100:
            return 100.0

        if observed_enable_rate is None:
            analytics = FlagAnalytics.objects.filter(flag=flag)
            total_evaluations = analytics.aggregate(total=Sum('evaluation_count'))['total'] or 0
            total_enabled = analytics.aggregate(total=Sum('enabled_count'))['total'] or 0
            observed_enable_rate = (total_enabled / total_evaluations * 100) if total_evaluations else 0

        drift = abs(observed_enable_rate - flag.rollout_percentage)
        return round(max(0.0, 100.0 - drift), 2)
