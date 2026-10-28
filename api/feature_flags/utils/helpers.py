"""
Utility functions for Feature Flags & A/B Testing.

This file is the original `utils.py` (now relocated into the `utils/`
package — see the package docstring in `utils/__init__.py` for why this
became a package). Functions that duplicated logic now in
`FlagValidator` / `ContextExtractor` delegate to those classes instead
(DRY fix) but keep their original names/signatures so every existing
caller (`from feature_flags.utils import get_user_hash`, etc.) keeps
working unchanged.
"""
from typing import Dict, Any, Optional
from django.utils import timezone
import hashlib
import json

from .validators import FlagValidator
from .context_extractor import ContextExtractor


def get_user_hash(user_id: str) -> int:
    """
    Get a hash value for a user ID.

    Args:
        user_id: User ID string

    Returns:
        Integer hash value (0-99)
    """
    if not user_id:
        return 0

    hash_value = hashlib.md5(str(user_id).encode()).hexdigest()
    return int(hash_value[:8], 16) % 100


def update_flag_analytics(flag, variant, user_id: str) -> None:
    """
    Update flag analytics for a user.

    Args:
        flag: Feature flag instance
        variant: Flag variant instance (optional)
        user_id: User ID
    """
    from ..models.flag_analytics import FlagAnalytics

    today = timezone.now().date()
    current_hour = timezone.now().hour

    analytics, created = FlagAnalytics.objects.get_or_create(
        flag=flag,
        variant=variant,
        date=today,
        hour=current_hour,
        environment=flag.environment,
        defaults={
            'evaluation_count': 1,
            'enabled_count': 1,
            'unique_users': 1,
        }
    )

    if not created:
        analytics.evaluation_count += 1
        analytics.enabled_count += 1
        analytics.unique_users += 1
        analytics.save()


def normalize_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize context dictionary.

    Args:
        context: Context dictionary

    Returns:
        Normalized context dictionary
    """
    if not context:
        return {}

    normalized = {}

    for key, value in context.items():
        if value is None:
            continue

        if isinstance(value, (str, int, float, bool)):
            normalized[key] = value
        elif isinstance(value, (list, dict)):
            normalized[key] = json.dumps(value)
        else:
            normalized[key] = str(value)

    return normalized


def validate_flag_name(name: str) -> bool:
    """
    Validate a flag name.

    DRY FIX: delegates to FlagValidator.validate_name() — kept as a
    thin wrapper so existing `from feature_flags.utils import
    validate_flag_name` call sites keep working.
    """
    return FlagValidator.validate_name(name)


def validate_rollout_percentage(percentage: int) -> bool:
    """
    Validate a rollout percentage.

    DRY FIX: delegates to FlagValidator.validate_rollout_percentage().
    """
    return FlagValidator.validate_rollout_percentage(percentage)


def calculate_sample_size(
    baseline_rate: float,
    mde: float,
    alpha: float = 0.05,
    power: float = 0.8
) -> int:
    """
    Calculate required sample size for A/B test.

    Args:
        baseline_rate: Baseline conversion rate (0-1)
        mde: Minimum detectable effect (0-1)
        alpha: Significance level (0-1)
        power: Statistical power (0-1)

    Returns:
        Required sample size
    """
    import math

    p1 = baseline_rate
    p2 = baseline_rate + mde

    if p2 > 1:
        p2 = 1.0

    pooled_p = (p1 + p2) / 2

    z_alpha = 1.96  # For alpha = 0.05
    z_beta = 0.84   # For power = 0.8

    numerator = (z_alpha + z_beta) ** 2 * 2 * pooled_p * (1 - pooled_p)
    denominator = (p2 - p1) ** 2

    if denominator == 0:
        return 1000

    sample_size = int(math.ceil(numerator / denominator))

    return max(sample_size, 100)


def calculate_statistical_significance(
    control_conversions: int,
    control_size: int,
    variant_conversions: int,
    variant_size: int
) -> Dict[str, Any]:
    """
    Calculate statistical significance for A/B test.

    Args:
        control_conversions: Control group conversions
        control_size: Control group size
        variant_conversions: Variant group conversions
        variant_size: Variant group size

    Returns:
        Dictionary with statistical results
    """
    import math

    control_rate = control_conversions / control_size if control_size > 0 else 0
    variant_rate = variant_conversions / variant_size if variant_size > 0 else 0

    lift = (variant_rate - control_rate) / control_rate if control_rate > 0 else 0

    p_pool = (control_conversions + variant_conversions) / (control_size + variant_size) \
        if (control_size + variant_size) > 0 else 0
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / control_size + 1 / variant_size)) \
        if control_size > 0 and variant_size > 0 else 0

    if se == 0:
        z_score = 0
    else:
        z_score = (variant_rate - control_rate) / se

    p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(z_score) / math.sqrt(2))))

    return {
        'control_rate': round(control_rate * 100, 2),
        'variant_rate': round(variant_rate * 100, 2),
        'lift': round(lift * 100, 2),
        'z_score': round(z_score, 2),
        'p_value': round(p_value, 4),
        'is_significant': p_value < 0.05
    }


def format_flag_value(value: Any, flag_type: str) -> Any:
    """
    Format a flag value based on its type.

    Args:
        value: Value to format
        flag_type: Type of flag

    Returns:
        Formatted value
    """
    if flag_type == 'boolean':
        return bool(value)
    elif flag_type == 'string':
        return str(value)
    elif flag_type == 'number':
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    elif flag_type == 'json':
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {}
        return value if isinstance(value, dict) else {}

    return value


def get_flag_context_from_request(request) -> Dict[str, Any]:
    """
    Extract flag context from a Django request.

    DRY FIX: delegates to ContextExtractor.from_request() — this used to
    be one of FOUR separate hand-rolled implementations of "pull
    user_id/email/session_id out of a request" (the others lived in
    decorators.py x3). Kept as a thin wrapper for backwards compatibility.
    """
    return ContextExtractor.from_request(request)
