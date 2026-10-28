# publisher_tools/publisher_management/__init__.py
# ============================================================
# Exports publisher management logic (KYC, analytics, profile).
# Used by: services.py (PublisherService), views.py (PublisherViewSet)
#
# Usage:
#   from .publisher_management import get_publisher_overview
#   from .publisher_management import get_publisher_profile_completion
#   from .publisher_management import calculate_publisher_health_score
# ============================================================

# ── Analytics ────────────────────────────────────────────────────────────────
from .publisher_analytics import (
    get_publisher_overview,
    get_revenue_breakdown,
    get_performance_metrics,
)

# ── Profile helpers ───────────────────────────────────────────────────────────
from .publisher_profile import (
    get_publisher_profile_completion,
    get_publisher_level,
    calculate_publisher_health_score,
)

__all__ = [
    # Analytics
    'get_publisher_overview',
    'get_revenue_breakdown',
    'get_performance_metrics',
    # Profile
    'get_publisher_profile_completion',
    'get_publisher_level',
    'calculate_publisher_health_score',
]
