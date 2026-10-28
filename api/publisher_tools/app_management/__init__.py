# publisher_tools/app_management/__init__.py
# ============================================================
# Exports app management logic.
# Used by: services.py (AppService), views.py (AppViewSet),
#          views_app_management_full.py, views_app_management.py
#
# Usage:
#   from .app_management import get_app_performance_summary
#   from .app_management import get_app_revenue_by_format
#   from .app_management import AppApprovalRecord
#   from .app_management import AppSDKConfig
#   from .app_management import AppDownloadSnapshot
#   from .app_management import AppQualityScore
# ============================================================

# ── Analytics functions ───────────────────────────────────────────────────────
from .app_analytics import (
    get_app_performance_summary,
    get_app_revenue_by_format,
    get_app_top_countries,
)

# ── Model classes ─────────────────────────────────────────────────────────────
from .app_approval      import AppApprovalRecord
from .app_sdk           import AppSDKConfig
from .app_downloads     import AppDownloadSnapshot
from .app_quality_score import AppQualityScore

__all__ = [
    # Analytics
    'get_app_performance_summary',
    'get_app_revenue_by_format',
    'get_app_top_countries',
    # Models
    'AppApprovalRecord',
    'AppSDKConfig',
    'AppDownloadSnapshot',
    'AppQualityScore',
]
