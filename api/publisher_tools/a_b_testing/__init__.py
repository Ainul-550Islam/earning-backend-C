# publisher_tools/a_b_testing/__init__.py
# ============================================================
# Exports A/B testing logic.
# Models (ABTest, ABTestVariant) are accessed via models.py
# after migration 0007.
#
# Usage:
#   from .a_b_testing import create_floor_price_test, ABTestAnalyzer
#   from .a_b_testing import TrafficAllocator, WinnerSelector
# ============================================================

# ── Test creation helpers ─────────────────────────────────────────────────────
from .test_manager import (
    create_floor_price_test,
    create_placement_test,
)
from .test_creator import (
    create_ab_test,
    create_multivariate_test,
    validate_test_config,
)

# ── Traffic allocation ────────────────────────────────────────────────────────
from .test_allocator import (
    allocate_traffic,
    get_variant_for_request,
    record_allocation,
)

# ── Analysis ─────────────────────────────────────────────────────────────────
from .test_analyzer import (
    analyze_test_results,
    get_winning_variant,
    calculate_uplift,
)

# ── Statistical calculations ──────────────────────────────────────────────────
from .confidence_calculator import (
    calculate_confidence_level,
    calculate_minimum_sample_size,
    is_statistically_significant,
)
from .hypothesis_tester import (
    run_t_test,
    run_z_test,
    calculate_p_value,
)

# ── Winner selection ──────────────────────────────────────────────────────────
from .winner_selector import (
    select_winner,
    auto_declare_winner,
    get_winner_recommendation,
)

# ── Reporting ─────────────────────────────────────────────────────────────────
from .test_reporting import (
    generate_test_report,
    get_test_summary,
    export_test_results,
)

# ── Placement-specific ────────────────────────────────────────────────────────
from .placement_testing import (
    create_placement_ab_test,
    analyze_placement_results,
)

# ── Multivariate ─────────────────────────────────────────────────────────────
from .multivariate_testing import (
    create_multivariate_test as create_mvt,
    analyze_multivariate_results,
)

__all__ = [
    # Creation
    'create_floor_price_test', 'create_placement_test',
    'create_ab_test', 'create_multivariate_test', 'validate_test_config',
    # Allocation
    'allocate_traffic', 'get_variant_for_request', 'record_allocation',
    # Analysis
    'analyze_test_results', 'get_winning_variant', 'calculate_uplift',
    # Statistics
    'calculate_confidence_level', 'calculate_minimum_sample_size', 'is_statistically_significant',
    'run_t_test', 'run_z_test', 'calculate_p_value',
    # Winner
    'select_winner', 'auto_declare_winner', 'get_winner_recommendation',
    # Reporting
    'generate_test_report', 'get_test_summary', 'export_test_results',
    # Placement
    'create_placement_ab_test', 'analyze_placement_results',
    # MVT
    'create_mvt', 'analyze_multivariate_results',
]
