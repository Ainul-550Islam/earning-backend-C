"""
adaptive_threshold_tasks — Celery tasks that recalculate adaptive threshold
baselines on an hourly schedule and record every change in ThresholdHistory.
"""
import logging
import math
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_rolling_stats(values: list) -> dict:
    """
    Compute mean, standard deviation, p50, p90, p99 for a list of floats.
    Returns zeros if the list is empty.
    """
    if not values:
        return {'mean': 0.0, 'stddev': 0.0, 'p50': 0.0, 'p90': 0.0, 'p99': 0.0, 'count': 0}

    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    stddev = math.sqrt(variance)

    sorted_vals = sorted(values)

    def percentile(p):
        idx = int(math.ceil(p / 100.0 * n)) - 1
        return sorted_vals[max(0, min(idx, n - 1))]

    return {
        'mean': round(mean, 4),
        'stddev': round(stddev, 4),
        'p50': round(percentile(50), 4),
        'p90': round(percentile(90), 4),
        'p99': round(percentile(99), 4),
        'count': n,
    }


def _get_historical_values(alert_rule, window_days: int) -> list:
    """
    Fetch trigger_value list from AlertLog for the given rule over the
    last `window_days` days.
    """
    from ..models.core import AlertLog
    cutoff = timezone.now() - timedelta(days=window_days)
    return list(
        AlertLog.objects.filter(
            rule=alert_rule,
            triggered_at__gte=cutoff,
        ).values_list('trigger_value', flat=True)
    )


def _apply_exponential_smoothing(current: float, new_value: float, alpha: float) -> float:
    """Exponential smoothing: S_t = alpha * x_t + (1 - alpha) * S_{t-1}"""
    return alpha * new_value + (1 - alpha) * current


def _record_history(adaptive_threshold, old_value: float, new_value: float,
                    change_type: str, reason: str, changed_by=None) -> None:
    """Persist a ThresholdHistory record for the change."""
    try:
        from ..models.threshold import ThresholdHistory
        if old_value == 0:
            change_pct = 0.0
        else:
            change_pct = round(((new_value - old_value) / abs(old_value)) * 100, 2)

        ThresholdHistory.objects.create(
            adaptive_threshold=adaptive_threshold,
            change_type=change_type,
            old_threshold=old_value,
            new_threshold=new_value,
            change_percentage=change_pct,
            reason=reason,
            changed_by=changed_by,
        )
    except Exception as e:
        logger.error(f"_record_history error: {e}")


# ---------------------------------------------------------------------------
# Per-threshold recalculation
# ---------------------------------------------------------------------------

def _recalculate_single(adaptive_threshold) -> dict:
    """
    Recalculate the baseline for one AdaptiveThreshold instance.

    Strategy selection:
        exponential_smoothing  — EMA of recent trigger values
        moving_average         — simple mean of window
        linear_regression      — least-squares trend extrapolation
        neural_network         — falls back to moving_average (placeholder)
        ensemble               — average of all three numeric methods

    Returns a dict with keys: old_threshold, new_threshold, method, stats
    """
    from ..models.threshold import AdaptiveThreshold

    rule = adaptive_threshold.threshold_config.alert_rule
    window_days = adaptive_threshold.adaptation_window_days
    values = _get_historical_values(rule, window_days)

    # AdaptiveThreshold has no `min_samples` column (AttributeError on every run) ->
    # fall back to the project-wide constant.
    from ..constants import THRESHOLD_MIN_SAMPLES
    min_samples = getattr(adaptive_threshold, 'min_samples', None) or THRESHOLD_MIN_SAMPLES
    if len(values) < min_samples:
        logger.info(
            f"AdaptiveThreshold id={adaptive_threshold.id}: only {len(values)} samples "
            f"(need {min_samples}), skipping"
        )
        return {}

    stats = _compute_rolling_stats(values)
    old_threshold = adaptive_threshold.current_threshold
    method = adaptive_threshold.adaptation_method

    # ---- compute new threshold per method ----
    if method == 'exponential_smoothing':
        # Use the most recent value as the new observation
        new_threshold = _apply_exponential_smoothing(
            old_threshold, values[-1], adaptive_threshold.learning_rate
        )

    elif method == 'moving_average':
        new_threshold = stats['mean']

    elif method == 'linear_regression':
        n = len(values)
        x_mean = (n - 1) / 2.0
        y_mean = stats['mean']
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0
        # Predict one step ahead
        new_threshold = y_mean + slope * (n - x_mean)

    elif method == 'neural_network':
        # Placeholder: use moving average until a real model is trained
        new_threshold = stats['mean']

    elif method == 'ensemble':
        ema = _apply_exponential_smoothing(
            old_threshold, values[-1], adaptive_threshold.learning_rate
        )
        ma = stats['mean']
        n = len(values)
        x_mean = (n - 1) / 2.0
        y_mean = stats['mean']
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0
        lr = y_mean + slope * (n - x_mean)
        new_threshold = (ema + ma + lr) / 3.0

    else:
        logger.warning(f"Unknown adaptation method '{method}', using moving_average")
        new_threshold = stats['mean']

    # ---- apply constraints ----
    new_threshold = max(adaptive_threshold.min_threshold,
                        min(adaptive_threshold.max_threshold, new_threshold))

    max_adj = adaptive_threshold.base_threshold * (adaptive_threshold.max_adjustment_percentage / 100.0)
    delta = new_threshold - adaptive_threshold.base_threshold
    if abs(delta) > max_adj:
        new_threshold = adaptive_threshold.base_threshold + (max_adj if delta > 0 else -max_adj)

    new_threshold = round(new_threshold, 4)

    # ---- persist ----
    if abs(new_threshold - old_threshold) > 1e-6:
        adaptive_threshold.current_threshold = new_threshold
        adaptive_threshold.last_adaptation = timezone.now()
        adaptive_threshold.adaptation_count += 1
        adaptive_threshold.save(update_fields=[
            'current_threshold', 'last_adaptation', 'adaptation_count'
        ])

        _record_history(
            adaptive_threshold,
            old_value=old_threshold,
            new_value=new_threshold,
            change_type='automatic',
            reason=(
                f"Hourly recalculation via {method}. "
                f"Samples={stats['count']}, mean={stats['mean']}, "
                f"stddev={stats['stddev']}, p90={stats['p90']}"
            ),
        )

        logger.info(
            f"AdaptiveThreshold id={adaptive_threshold.id} rule='{rule.name}': "
            f"{old_threshold} → {new_threshold} ({method})"
        )
    else:
        logger.debug(
            f"AdaptiveThreshold id={adaptive_threshold.id}: no significant change "
            f"({old_threshold} ≈ {new_threshold})"
        )

    return {
        'adaptive_threshold_id': adaptive_threshold.id,
        'rule_name': rule.name,
        'method': method,
        'old_threshold': old_threshold,
        'new_threshold': new_threshold,
        'stats': stats,
    }


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------

@shared_task(
    name='alerts.recalculate_adaptive_thresholds',
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    soft_time_limit=3500,
    time_limit=3600,
)
def recalculate_adaptive_thresholds(self):
    """
    Recalculate baselines for ALL active AdaptiveThreshold instances.

    Scheduled hourly via Celery Beat:
        CELERY_BEAT_SCHEDULE = {
            'recalculate-adaptive-thresholds': {
                'task': 'alerts.recalculate_adaptive_thresholds',
                'schedule': crontab(minute=0),  # top of every hour
            },
        }

    Returns:
        dict with counts of updated / skipped / failed thresholds.
    """
    try:
        from ..models.threshold import AdaptiveThreshold

        active_thresholds = AdaptiveThreshold.objects.filter(
            is_active=True
        ).select_related('threshold_config__alert_rule')

        total = active_thresholds.count()
        updated = 0
        skipped = 0
        failed = 0
        results = []

        for at in active_thresholds:
            try:
                result = _recalculate_single(at)
                if result:
                    updated += 1
                    results.append(result)
                else:
                    skipped += 1
            except Exception as e:
                failed += 1
                logger.error(
                    f"recalculate_adaptive_thresholds: error on id={at.id}: {e}",
                    exc_info=True,
                )

        logger.info(
            f"recalculate_adaptive_thresholds: total={total} "
            f"updated={updated} skipped={skipped} failed={failed}"
        )
        return {
            'total': total,
            'updated': updated,
            'skipped': skipped,
            'failed': failed,
            'results': results,
        }

    except Exception as exc:
        logger.error(f"recalculate_adaptive_thresholds task error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'error': 'Operation failed'}


@shared_task(
    name='alerts.recalculate_single_adaptive_threshold',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def recalculate_single_adaptive_threshold(self, adaptive_threshold_id: int):
    """
    Recalculate baseline for a single AdaptiveThreshold by ID.
    Useful for on-demand recalculation triggered by signals or admin actions.

    Args:
        adaptive_threshold_id: PK of the AdaptiveThreshold to recalculate.

    Returns:
        Result dict from _recalculate_single, or None on failure.
    """
    try:
        from ..models.threshold import AdaptiveThreshold
        at = AdaptiveThreshold.objects.select_related(
            'threshold_config__alert_rule'
        ).get(id=adaptive_threshold_id)

        result = _recalculate_single(at)
        logger.info(
            f"recalculate_single_adaptive_threshold id={adaptive_threshold_id}: {result}"
        )
        return result

    except Exception as exc:
        logger.error(
            f"recalculate_single_adaptive_threshold id={adaptive_threshold_id} error: {exc}",
            exc_info=True,
        )
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return None


@shared_task(
    name='alerts.update_threshold_profiles',
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def update_threshold_profiles(self):
    """
    Re-apply active ThresholdProfiles to their linked ThresholdConfigs.
    Runs after recalculate_adaptive_thresholds to propagate profile
    multipliers onto freshly recalculated baselines.

    Returns:
        Number of ThresholdConfig objects updated.
    """
    try:
        from ..models.threshold import ThresholdProfile, ThresholdConfig

        profiles = ThresholdProfile.objects.filter(is_active=True)
        updated = 0

        for profile in profiles:
            # Find all ThresholdConfigs whose alert_rule matches the profile's
            # alert_type_settings keys
            for alert_type_key in profile.alert_type_settings.keys():
                configs = ThresholdConfig.objects.filter(
                    alert_rule__alert_type=alert_type_key,
                    is_active=True,
                )
                for config in configs:
                    try:
                        profile.apply_to_threshold_config(config)
                        updated += 1
                    except Exception as e:
                        logger.error(
                            f"update_threshold_profiles: error applying profile "
                            f"id={profile.id} to config id={config.id}: {e}"
                        )

        logger.info(f"update_threshold_profiles: updated {updated} configs")
        return updated

    except Exception as exc:
        logger.error(f"update_threshold_profiles error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return 0


@shared_task(
    name='alerts.cleanup_old_threshold_history',
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def cleanup_old_threshold_history(self, days_to_keep: int = 90):
    """
    Delete ThresholdHistory records older than `days_to_keep` days.

    Args:
        days_to_keep: history older than this many days is deleted (default 90).

    Returns:
        Number of records deleted.
    """
    try:
        from ..models.threshold import ThresholdHistory
        cutoff = timezone.now() - timedelta(days=days_to_keep)
        deleted, _ = ThresholdHistory.objects.filter(created_at__lt=cutoff).delete()
        logger.info(f"cleanup_old_threshold_history: deleted {deleted} records older than {days_to_keep} days")
        return deleted

    except Exception as exc:
        logger.error(f"cleanup_old_threshold_history error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return 0
