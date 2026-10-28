# publisher_tools/ad_placements/__init__.py
# ============================================================
# Exports ad placement logic.
# Used by: services.py (AdUnitService), views.py (AdPlacementViewSet)
#
# Usage:
#   from .ad_placements import get_active_placements_for_site
#   from .ad_placements import get_effective_floor_price
#   from .ad_placements import analyze_all_placements
# ============================================================

# ── Placement manager (core) ──────────────────────────────────────────────────
from .placement_manager import (
    get_active_placements_for_site,
    get_active_placements_for_app,
    get_placement_config,
)

# ── Floor price ───────────────────────────────────────────────────────────────
from .placement_floor_price import (
    get_effective_floor_price,
    suggest_floor_price,
)

# ── Position scoring ──────────────────────────────────────────────────────────
from .placement_position import (
    get_position_score,
    get_viewability_benchmark,
    rank_positions_by_performance,
)

# ── Size recommendations ──────────────────────────────────────────────────────
from .placement_size import (
    get_recommended_sizes_for_position,
    get_size_ecpm_multiplier,
    parse_size_string,
)

# ── Optimizer ─────────────────────────────────────────────────────────────────
from .placement_optimizer import (
    analyze_all_placements,
)

# ── Waterfall ─────────────────────────────────────────────────────────────────
from .placement_waterfall import (
    get_placement_waterfall,
)

# ── Reporting ─────────────────────────────────────────────────────────────────
from .placement_reporting import (
    generate_placement_report,
    get_placement_efficiency_score,
)

__all__ = [
    # Manager
    'get_active_placements_for_site', 'get_active_placements_for_app', 'get_placement_config',
    # Floor price
    'get_effective_floor_price', 'suggest_floor_price',
    # Position
    'get_position_score', 'get_viewability_benchmark', 'rank_positions_by_performance',
    # Size
    'get_recommended_sizes_for_position', 'get_size_ecpm_multiplier', 'parse_size_string',
    # Optimizer
    'analyze_all_placements',
    # Waterfall
    'get_placement_waterfall',
    # Reporting
    'generate_placement_report', 'get_placement_efficiency_score',
]
