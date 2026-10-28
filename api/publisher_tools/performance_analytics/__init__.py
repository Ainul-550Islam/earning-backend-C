# publisher_tools/performance_analytics/__init__.py
# ============================================================
# Exports all analytics functions.
# Used by: api_endpoints/analytics_api.py, api_endpoints/reporting_api.py,
#          services.py (EarningService), tasks.py (generate_daily_earning_report)
#
# Usage:
#   from .performance_analytics import get_dashboard_summary, generate_daily_report
#   from .performance_analytics import forecast_next_month, get_ecpm_trend
# ============================================================

# ── Dashboard ─────────────────────────────────────────────────────────────────
from .publisher_dashboard import (
    get_realtime_stats,
    get_dashboard_summary,
    get_performance_alerts,
)

# ── Revenue tracking ──────────────────────────────────────────────────────────
from .revenue_tracker import (
    get_revenue_by_dimension,
    get_top_performing_units,
    get_revenue_trend,
)

# ── eCPM analysis ─────────────────────────────────────────────────────────────
from .ecpm_analyzer import (
    get_ecpm_by_country,
    get_ecpm_by_format,
    get_ecpm_trend,
)

# ── CTR analysis ──────────────────────────────────────────────────────────────
from .CTR_analyzer import (
    get_ctr_by_format,
    get_ctr_trend,
    identify_ctr_anomalies,
)

# ── RPM analysis ──────────────────────────────────────────────────────────────
from .RPM_analyzer import (
    calculate_site_rpm,
    get_rpm_by_publisher,
    get_rpm_benchmarks,
)

# ── Fill rate ─────────────────────────────────────────────────────────────────
from .fill_rate_analyzer import (
    get_fill_rate_by_unit,
    get_fill_rate_by_country,
    identify_fill_rate_issues,
)

# ── Reports ───────────────────────────────────────────────────────────────────
from .daily_report import (
    generate_daily_report,
    get_daily_comparison,
)
from .weekly_report import generate_weekly_report
from .monthly_report import (
    generate_monthly_report,
    get_monthly_growth_trend,
)
from .hourly_report import (
    generate_hourly_report,
    get_best_hours,
)
from .custom_report import (
    build_custom_report,
    export_report_to_csv,
)

# ── Forecasting ───────────────────────────────────────────────────────────────
from .revenue_forecast import (
    forecast_publisher_revenue,
    forecast_next_month,
)

# ── Real-time ─────────────────────────────────────────────────────────────────
from .real_time_analytics import (
    get_live_stats,
    get_realtime_fill_rate,
    track_ad_request,
)

# ── Trackers ──────────────────────────────────────────────────────────────────
from .impression_tracker import (
    track_impression,
    get_hourly_impressions,
    get_daily_impressions,
)
from .click_tracker import (
    track_click,
    get_click_through_rate,
)

__all__ = [
    # Dashboard
    'get_realtime_stats', 'get_dashboard_summary', 'get_performance_alerts',
    # Revenue
    'get_revenue_by_dimension', 'get_top_performing_units', 'get_revenue_trend',
    # eCPM
    'get_ecpm_by_country', 'get_ecpm_by_format', 'get_ecpm_trend',
    # CTR
    'get_ctr_by_format', 'get_ctr_trend', 'identify_ctr_anomalies',
    # RPM
    'calculate_site_rpm', 'get_rpm_by_publisher', 'get_rpm_benchmarks',
    # Fill rate
    'get_fill_rate_by_unit', 'get_fill_rate_by_country', 'identify_fill_rate_issues',
    # Reports
    'generate_daily_report', 'get_daily_comparison',
    'generate_weekly_report',
    'generate_monthly_report', 'get_monthly_growth_trend',
    'generate_hourly_report', 'get_best_hours',
    'build_custom_report', 'export_report_to_csv',
    # Forecast
    'forecast_publisher_revenue', 'forecast_next_month',
    # Real-time
    'get_live_stats', 'get_realtime_fill_rate', 'track_ad_request',
    # Trackers
    'track_impression', 'get_hourly_impressions', 'get_daily_impressions',
    'track_click', 'get_click_through_rate',
]
