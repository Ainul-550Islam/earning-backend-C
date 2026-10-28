"""
Utility functions for Real-time Dashboard Backend.

Pure functions only — no Django imports, no ORM, no side effects.
Every function here is importable from anywhere without circular imports.

WIRED (v1.2.0):
  - aggregate_metrics()          → RealTimeMetricViewSet.aggregate() action
  - validate_widget_configuration() → WidgetConfigurationSerializer.validate_value()
  - sanitize_dashboard_name()   → UserDashboardSerializer.validate_name()
  - format_metric_value()        → RealTimeMetricSerializer (method field)
  - calculate_metric_delta()     → RealTimeMetricSerializer (method field)
  - calculate_metric_percentage()→ RealTimeMetricSerializer (method field)
  - check_metric_thresholds()    → RealTimeMetricSerializer + RealTimeMetricService
"""
import re
from typing import Dict, Any, List, Optional


# ── Metric display ─────────────────────────────────────────────────────────────

def format_metric_value(value: float, unit: str = '') -> str:
    """
    Format a metric value with its unit for display.

    Examples:
        format_metric_value(87.3, '%')   → '87.3 %'
        format_metric_value(1024, 'MB')  → '1024 MB'
        format_metric_value(42.0, '')    → '42.0'
    """
    if unit:
        return f"{value} {unit}"
    return str(value)


def calculate_metric_delta(current: float, previous: Optional[float]) -> float:
    """
    Absolute change from previous value.

    Returns 0.0 when previous is None (first reading — no history yet).
    """
    if previous is None:
        return 0.0
    return current - previous


def calculate_metric_percentage(current: float, previous: Optional[float]) -> float:
    """
    Percentage change from previous value.

    Returns 0.0 when previous is None or 0 (division guard).
    Formula: ((current - previous) / |previous|) × 100
    """
    if previous is None or previous == 0:
        return 0.0
    return ((current - previous) / abs(previous)) * 100


def check_metric_thresholds(
    value: float,
    warning: Optional[float] = None,
    critical: Optional[float] = None,
) -> str:
    """
    Evaluate a metric value against warning and critical thresholds.

    Priority: critical > warning > normal.
    Thresholds are inclusive (≥).

    Returns:
        'critical' if value ≥ critical_threshold
        'warning'  if value ≥ warning_threshold
        'normal'   otherwise
    """
    if critical is not None and value >= critical:
        return 'critical'
    if warning is not None and value >= warning:
        return 'warning'
    return 'normal'


# ── Metric aggregation ────────────────────────────────────────────────────────

def aggregate_metrics(metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate a list of metric value dicts into summary statistics.

    WIRED (v1.2.0): called from RealTimeMetricViewSet.aggregate() action.
    Previously defined here but never connected to any endpoint or caller.

    Each dict in metrics must have a numeric 'value' key.

    Args:
        metrics: List of dicts, each containing at least {'value': float}.
                 May also contain 'id', 'name', 'unit', 'metric_type'.

    Returns:
        Empty dict if metrics is empty.
        Otherwise:
            {
                'count': 3,
                'sum': 240.0,
                'avg': 80.0,
                'min': 10.0,
                'max': 200.0,
            }

    DRY NOTE: key names are 'sum' and 'avg' (not 'total'/'average') to
    match the RealTimeMetricViewSet.aggregate() response schema and
    common statistical convention (SQL AVG/SUM, pandas .agg()).
    """
    if not metrics:
        return {}

    values = [float(m['value']) for m in metrics]
    total = sum(values)

    return {
        'count': len(values),
        'sum': total,
        'avg': total / len(values),
        'min': min(values),
        'max': max(values),
    }


# ── Configuration validation ───────────────────────────────────────────────────

def validate_widget_configuration(configuration: Any) -> bool:
    """
    Validate a widget configuration dict.

    WIRED (v1.2.0): called from WidgetConfigurationSerializer.validate_value().
    Previously defined here but never called — any chart config was accepted
    even when required keys were missing.

    Rules:
      - Must be a dict (not list, string, int, etc.)
      - If configuration['type'] == 'chart', must contain 'data' and 'chartType'

    Returns:
        True  — configuration is valid (or has no type-specific requirements)
        False — configuration fails a type-specific rule

    Raises:
        Nothing. The serializer wraps this in a ValidationError.

    v1.5.0: parameter was typed `Dict[str, Any]`, which told mypy the
    isinstance() check below could never be False — flagged as an
    unreachable statement. The check is genuinely live at runtime: this
    is a general-purpose utility whose one current caller happens to
    pre-check with `isinstance(value, dict)`, but the function itself
    must not assume every caller will — the JSONField it validates can
    hold any JSON value (list, string, int, None). Typed as Any so the
    isinstance check reflects the function's real contract instead of
    fighting the type checker to keep genuinely defensive code.
    """
    if not isinstance(configuration, dict):
        return False

    widget_type = configuration.get('type')
    if widget_type == 'chart':
        required_fields = ['data', 'chartType']
        return all(field in configuration for field in required_fields)

    return True


# ── Name sanitisation ─────────────────────────────────────────────────────────

def sanitize_dashboard_name(name: str) -> str:
    """
    Sanitise a dashboard name for safe storage and display.

    WIRED (v1.2.0): called from UserDashboardSerializer.validate_name().
    Previously defined here but never called — any string including SQL
    injection attempts or control characters was accepted.

    Operations (in order):
      1. Strip leading/trailing whitespace.
      2. Remove characters that are not alphanumeric, space, hyphen, or underscore.
      3. Collapse multiple consecutive spaces to a single space.
      4. Strip again in case removal left leading/trailing spaces.

    Returns an empty string if the name contains only invalid characters;
    the serializer raises ValidationError in that case.
    """
    name = name.strip()
    name = re.sub(r'[^\w\s\-]', '', name)   # keep word chars, spaces, hyphens
    name = re.sub(r'\s+', ' ', name)          # collapse whitespace runs
    return name.strip()
