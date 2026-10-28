"""
correlation_tasks — Celery tasks that correlate recent alerts, group
related alert logs into AlertCorrelation records, and maintain the
correlation cache used by the intelligence pipeline.
"""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_recent_alert_logs(window_minutes: int):
    """Return AlertLog queryset for the last `window_minutes` minutes."""
    from ..models.core import AlertLog
    cutoff = timezone.now() - timedelta(minutes=window_minutes)
    return AlertLog.objects.filter(
        triggered_at__gte=cutoff
    ).select_related('rule').order_by('triggered_at')


def _group_by_rule_type(alert_logs) -> dict:
    """
    Group alert logs by alert_type.
    Returns {alert_type: [AlertLog, ...]}
    """
    groups: dict = {}
    for log in alert_logs:
        key = log.rule.alert_type
        groups.setdefault(key, []).append(log)
    return groups


def _compute_temporal_overlap(logs_a: list, logs_b: list, window_minutes: int) -> float:
    """
    Compute what fraction of logs_a have at least one log_b within
    `window_minutes` of them.  Returns a value in [0, 1].
    """
    if not logs_a or not logs_b:
        return 0.0

    matched = 0
    window = timedelta(minutes=window_minutes)
    for a in logs_a:
        for b in logs_b:
            if abs((a.triggered_at - b.triggered_at).total_seconds()) <= window.total_seconds():
                matched += 1
                break  # only need one match per a

    return matched / len(logs_a)


def _find_correlated_pairs(groups: dict, window_minutes: int, threshold: float) -> list:
    """
    For every pair of alert types in `groups`, compute temporal overlap.
    Returns list of (type_a, type_b, overlap_score) where score >= threshold.
    """
    types = list(groups.keys())
    pairs = []
    for i in range(len(types)):
        for j in range(i + 1, len(types)):
            a, b = types[i], types[j]
            score = _compute_temporal_overlap(groups[a], groups[b], window_minutes)
            if score >= threshold:
                pairs.append((a, b, round(score, 4)))
    return pairs


def _upsert_correlation(type_a: str, type_b: str, score: float,
                        window_minutes: int, alert_logs_a: list, alert_logs_b: list):
    """
    Create or update an AlertCorrelation record for the pair (type_a, type_b).
    Also links the contributing AlertLog IDs into the correlation's related_alerts
    if the model supports it.
    """
    from ..models.core import AlertRule
    from ..models.intelligence import AlertCorrelation

    # Canonical name: alphabetical order so we don't create duplicates
    name = f"auto:{min(type_a, type_b)}↔{max(type_a, type_b)}"

    correlation, created = AlertCorrelation.objects.get_or_create(
        name=name,
        defaults={
            'description': (
                f"Auto-detected temporal correlation between "
                f"'{type_a}' and '{type_b}' alerts."
            ),
            'correlation_type': 'temporal',
            'time_window_minutes': window_minutes,
            'correlation_threshold': 0.5,
            'minimum_occurrences': 2,
        },
    )

    # Update stats
    correlation.correlation_strength = score
    correlation.status = 'confirmed' if score >= 0.7 else 'pending'
    correlation.last_analyzed = timezone.now()

    # Link primary / secondary rules
    primary_rules = AlertRule.objects.filter(alert_type=type_a, is_active=True)
    secondary_rules = AlertRule.objects.filter(alert_type=type_b, is_active=True)
    correlation.primary_rules.set(primary_rules)
    correlation.secondary_rules.set(secondary_rules)

    correlation.save(update_fields=[
        'correlation_strength', 'status', 'last_analyzed',
    ])

    action = 'created' if created else 'updated'
    logger.info(
        f"_upsert_correlation: {action} '{name}' score={score} "
        f"status={correlation.status}"
    )
    return correlation


# ---------------------------------------------------------------------------
# Main tasks
# ---------------------------------------------------------------------------

@shared_task(
    name='alerts.correlate_recent_alerts',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=280,
    time_limit=300,
)
def correlate_recent_alerts(self, window_minutes: int = 60, correlation_threshold: float = 0.5):
    """
    Analyse the last `window_minutes` of alert logs and detect temporal
    correlations between different alert types.

    Scheduled every 5 minutes via Celery Beat:
        CELERY_BEAT_SCHEDULE = {
            'correlate-recent-alerts': {
                'task': 'alerts.correlate_recent_alerts',
                'schedule': crontab(minute='*/5'),
            },
        }

    Args:
        window_minutes:        look-back window for alert logs (default 60).
        correlation_threshold: minimum overlap score to record a correlation
                               (default 0.5).

    Returns:
        dict with counts of pairs found, correlations created/updated.
    """
    try:
        recent_logs = _get_recent_alert_logs(window_minutes)
        total_logs = recent_logs.count()

        if total_logs < 2:
            logger.info(
                f"correlate_recent_alerts: only {total_logs} logs in last "
                f"{window_minutes}min — nothing to correlate"
            )
            return {'total_logs': total_logs, 'pairs_found': 0, 'correlations_upserted': 0}

        groups = _group_by_rule_type(list(recent_logs))

        if len(groups) < 2:
            logger.info(
                f"correlate_recent_alerts: only 1 alert type in window — "
                f"no pairs to evaluate"
            )
            return {'total_logs': total_logs, 'pairs_found': 0, 'correlations_upserted': 0}

        pairs = _find_correlated_pairs(groups, window_minutes, correlation_threshold)
        upserted = 0

        for type_a, type_b, score in pairs:
            try:
                _upsert_correlation(
                    type_a, type_b, score,
                    window_minutes,
                    groups[type_a],
                    groups[type_b],
                )
                upserted += 1
            except Exception as e:
                logger.error(
                    f"correlate_recent_alerts: error upserting "
                    f"({type_a}, {type_b}): {e}",
                    exc_info=True,
                )

        logger.info(
            f"correlate_recent_alerts: logs={total_logs} "
            f"pairs_found={len(pairs)} upserted={upserted}"
        )
        return {
            'total_logs': total_logs,
            'alert_types': list(groups.keys()),
            'pairs_found': len(pairs),
            'correlations_upserted': upserted,
            'pairs': [(a, b, s) for a, b, s in pairs],
        }

    except Exception as exc:
        logger.error(f"correlate_recent_alerts error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'error': 'Operation failed'}


@shared_task(
    name='alerts.reanalyze_all_correlations',
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    soft_time_limit=3500,
    time_limit=3600,
)
def reanalyze_all_correlations(self):
    """
    Re-run full statistical analysis on every AlertCorrelation record
    (both auto-detected and manually created).

    Scheduled daily via Celery Beat:
        CELERY_BEAT_SCHEDULE = {
            'reanalyze-all-correlations': {
                'task': 'alerts.reanalyze_all_correlations',
                'schedule': crontab(hour=2, minute=0),  # 02:00 daily
            },
        }

    Returns:
        dict with counts of analyzed / failed correlations.
    """
    try:
        from ..models.intelligence import AlertCorrelation

        correlations = AlertCorrelation.objects.all()
        total = correlations.count()
        analyzed = 0
        failed = 0

        for correlation in correlations:
            try:
                correlation.analyze_correlation()
                analyzed += 1
            except Exception as e:
                failed += 1
                logger.error(
                    f"reanalyze_all_correlations: error on id={correlation.id}: {e}",
                    exc_info=True,
                )

        logger.info(
            f"reanalyze_all_correlations: total={total} "
            f"analyzed={analyzed} failed={failed}"
        )
        return {'total': total, 'analyzed': analyzed, 'failed': failed}

    except Exception as exc:
        logger.error(f"reanalyze_all_correlations error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'error': 'Operation failed'}


@shared_task(
    name='alerts.expire_stale_correlations',
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def expire_stale_correlations(self, stale_days: int = 7):
    """
    Mark AlertCorrelation records as 'expired' if they have not been
    analyzed in the last `stale_days` days.

    Args:
        stale_days: correlations not analyzed within this many days are expired.

    Returns:
        Number of correlations marked expired.
    """
    try:
        from ..models.intelligence import AlertCorrelation
        cutoff = timezone.now() - timedelta(days=stale_days)
        expired = AlertCorrelation.objects.filter(
            last_analyzed__lt=cutoff,
            status__in=['confirmed', 'pending'],
        ).update(status='expired')

        logger.info(
            f"expire_stale_correlations: marked {expired} correlations as expired "
            f"(not analyzed in {stale_days} days)"
        )
        return expired

    except Exception as exc:
        logger.error(f"expire_stale_correlations error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return 0


@shared_task(
    name='alerts.update_correlation_cache',
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def update_correlation_cache(self):
    """
    Rebuild the in-memory / Redis cache of confirmed correlations so that
    the real-time alert processor can look them up without hitting the DB.

    Cache key: 'confirmed_alert_correlations'
    TTL: 10 minutes

    Returns:
        Number of confirmed correlations cached.
    """
    try:
        from django.core.cache import cache
        from ..models.intelligence import AlertCorrelation

        confirmed = list(
            AlertCorrelation.objects.filter(status='confirmed')
            .prefetch_related('primary_rules', 'secondary_rules')
            .values(
                'id', 'name', 'correlation_type', 'correlation_strength',
                'time_window_minutes', 'correlation_threshold',
            )
        )

        cache.set('confirmed_alert_correlations', confirmed, timeout=600)
        logger.info(f"update_correlation_cache: cached {len(confirmed)} confirmed correlations")
        return len(confirmed)

    except Exception as exc:
        logger.error(f"update_correlation_cache error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return 0
