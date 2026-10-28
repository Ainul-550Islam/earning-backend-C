# publisher_tools/ad_unit_management/__init__.py
# ============================================================
# Exports ad unit management logic.
# Used by: services.py (AdUnitService), views.py (AdUnitViewSet)
#
# Usage:
#   from .ad_unit_management import get_unit_performance_report
#   from .ad_unit_management import apply_targeting_rules
#   from .ad_unit_management import get_recommendations
# ============================================================

# ── Performance ───────────────────────────────────────────────────────────────
from .ad_unit_performance import (
    get_unit_performance_report,
    get_unit_daily_trend,
    compare_unit_performance,
)

# ── Placement recommendations ─────────────────────────────────────────────────
from .ad_unit_placement import (
    get_recommendations,
    get_viewability_benchmark,
    analyze_placement_performance,
)

# ── Targeting rules ───────────────────────────────────────────────────────────
from .ad_unit_targeting import (
    apply_targeting_rules,
)

__all__ = [
    # Performance
    'get_unit_performance_report', 'get_unit_daily_trend', 'compare_unit_performance',
    # Placement
    'get_recommendations', 'get_viewability_benchmark', 'analyze_placement_performance',
    # Targeting
    'apply_targeting_rules',
]
