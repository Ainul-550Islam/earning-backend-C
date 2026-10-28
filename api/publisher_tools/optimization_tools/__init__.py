# publisher_tools/optimization_tools/__init__.py
# ============================================================
# Exports all optimization helpers so services.py and tasks.py
# can import cleanly:
#   from .optimization_tools import optimize_floor_prices
#   from .optimization_tools import suggest_waterfall_optimization
# ============================================================
from .yield_optimizer import (
    optimize_floor_prices,
    suggest_waterfall_optimization,
    get_ad_load_optimization,
    calculate_revenue_opportunity,
)
from .geo_optimizer import (
    get_geo_optimization_recommendations,
    get_ecpm_by_country_benchmark,
)
from .frequency_capper import (
    get_recommended_frequency_cap,
    analyze_frequency_caps,
    estimate_ctr_improvement,
)
from .viewability_optimizer import (
    get_viewability_recommendations,
    calculate_viewability_lift,
)
from .latency_optimizer import (
    get_latency_recommendations,
)
# NOTE: analyze_timeout_settings, get_best_serving_windows and
# analyze_time_of_day_performance are called from
# views_optimization_extended.py but are not defined anywhere in
# this package yet. Do not re-add them here until they exist in
# latency_optimizer.py / time_optimizer.py: a missing name in this
# file breaks every import of the whole package, not just the one
# caller that needed it.

__all__ = [
    # Yield / revenue
    'optimize_floor_prices',
    'suggest_waterfall_optimization',
    'get_ad_load_optimization',
    'calculate_revenue_opportunity',
    # Geo
    'get_geo_optimization_recommendations',
    'get_ecpm_by_country_benchmark',
    # Frequency
    'get_recommended_frequency_cap',
    'analyze_frequency_caps',
    'estimate_ctr_improvement',
    # Viewability
    'get_viewability_recommendations',
    'calculate_viewability_lift',
    # Latency
    'get_latency_recommendations',
]
