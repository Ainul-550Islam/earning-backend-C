# publisher_tools/site_management/__init__.py
# ============================================================
# Exports site management logic.
# Used by: services.py (SiteService), views.py (SiteViewSet)
#
# Usage:
#   from .site_management import verify_ads_txt, verify_meta_tag
#   from .site_management import is_valid_domain, clean_domain
#   from .site_management import get_site_performance_summary
#   from .site_management import calculate_composite_score
# ============================================================

# ── Domain utilities ──────────────────────────────────────────────────────────
from .site_domain import (
    clean_domain,
    is_valid_domain,
    get_root_domain,
)

# ── Verification ──────────────────────────────────────────────────────────────
from .site_verification import (
    verify_ads_txt,
    verify_meta_tag,
    verify_dns_record,
)

# ── Quality score ────────────────────────────────────────────────────────────
from .site_quality_score import (
    calculate_composite_score,
)

# ── Analytics ────────────────────────────────────────────────────────────────
from .site_analytics import (
    get_site_performance_summary,
)

__all__ = [
    # Domain
    'clean_domain', 'is_valid_domain', 'get_root_domain',
    # Verification
    'verify_ads_txt', 'verify_meta_tag', 'verify_dns_record',
    # Quality
    'calculate_composite_score',
    # Analytics
    'get_site_performance_summary',
]
