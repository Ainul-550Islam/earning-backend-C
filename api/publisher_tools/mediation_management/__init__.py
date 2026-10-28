# publisher_tools/mediation_management/__init__.py
# ============================================================
# Exports mediation management logic.
# Used by: services.py (MediationService.optimize_waterfall),
#          tasks.py (auto_optimize_waterfalls),
#          views.py (MediationGroupViewSet)
#
# Usage:
#   from .mediation_management import run_full_optimization
#   from .mediation_management import get_hybrid_ad_response
#   from .mediation_management import generate_waterfall_report
# ============================================================

# ── Core waterfall management ─────────────────────────────────────────────────
from .waterfall_manager import (
    create_default_waterfall,
    reorder_by_ecpm,
    get_waterfall_stats,
)

# ── Floor price management ────────────────────────────────────────────────────
from .floor_price_manager import (
    get_floor_price_recommendations,
    calculate_optimal_floor,
    apply_floor_price_update,
)

# ── Network priority ──────────────────────────────────────────────────────────
from .network_priority import (
    calculate_network_priority_score,
    get_optimal_priorities,
    apply_optimal_priorities,
)

# ── Bidding optimizer ─────────────────────────────────────────────────────────
from .bidding_optimizer import (
    optimize_bid_timeout,
    analyze_lost_bids,
    get_bid_density_report,
)

# ── Header bidding ────────────────────────────────────────────────────────────
from .header_bidding_manager import (
    get_bidder_configurations,
    calculate_bid_win_rate,
)

# ── Hybrid mediation ─────────────────────────────────────────────────────────
from .hybrid_mediation import (
    get_hybrid_ad_response,
)

# ── Analytics ────────────────────────────────────────────────────────────────
from .mediation_analytics import (
    get_mediation_performance,
    get_network_comparison,
    calculate_mediation_efficiency,
)

# ── Optimizer ────────────────────────────────────────────────────────────────
from .mediation_optimizer import (
    run_full_optimization,
    get_optimization_opportunities,
    schedule_auto_optimization,
)

# ── Reporting ────────────────────────────────────────────────────────────────
from .mediation_reporting import (
    generate_waterfall_report,
    generate_network_roi_report,
)

# ── Models (registered separately via migration 0008) ────────────────────────
# Do NOT import model classes here to avoid circular deps.
# Access them via: from publisher_tools.models import MediationConfig
# (after migration 0008 runs and they're moved to models.py)

__all__ = [
    # Waterfall
    'create_default_waterfall', 'reorder_by_ecpm', 'get_waterfall_stats',
    # Floor price
    'get_floor_price_recommendations', 'calculate_optimal_floor', 'apply_floor_price_update',
    # Priority
    'calculate_network_priority_score', 'get_optimal_priorities', 'apply_optimal_priorities',
    # Bidding
    'optimize_bid_timeout', 'analyze_lost_bids', 'get_bid_density_report',
    # Header bidding
    'get_bidder_configurations', 'calculate_bid_win_rate',
    # Hybrid
    'get_hybrid_ad_response',
    # Analytics
    'get_mediation_performance', 'get_network_comparison', 'calculate_mediation_efficiency',
    # Optimizer
    'run_full_optimization', 'get_optimization_opportunities', 'schedule_auto_optimization',
    # Reporting
    'generate_waterfall_report', 'generate_network_roi_report',
]
