# =============================================================================
# behavior_analytics/receivers.py
# =============================================================================
"""
Signal receivers for the behavior_analytics application.

Rules:
  - Receivers are connected in AppConfig.ready() — never at module level.
  - Every receiver is idempotent and wrapped in a broad try/except so a
    receiver failure never kills the caller.
  - Side-effects (cache invalidation, Celery tasks) are isolated and logged.
  - Receivers never import from serializers or views.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import EngagementScore, UserPath
from .signals import (
    click_batch_recorded,
    engagement_score_updated,
    engagement_tier_changed,
    path_closed,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# post_save: EngagementScore → emit engagement_score_updated signal
# ---------------------------------------------------------------------------

@receiver(post_save, sender=EngagementScore)
def on_engagement_score_saved(
    sender,
    instance: EngagementScore,
    created: bool,
    **kwargs: Any,
) -> None:
    """
    After every EngagementScore save, emit our custom signal and check
    whether the tier has changed compared to the previous persisted value.
    """
    try:
        engagement_score_updated.send(
            sender=EngagementScore,
            engagement_score=instance,
            created=created,
        )

        # Tier-change detection: compare to yesterday's (or previous) score
        if not created:
            # We rely on the fact that update_or_create stores old tier
            # in instance.__dict__ before the update (available as _old_tier
            # if set by the service layer; otherwise we skip the check).
            old_tier = getattr(instance, "_old_tier", None)
            if old_tier and old_tier != instance.tier:
                engagement_tier_changed.send(
                    sender=EngagementScore,
                    user=instance.user,
                    old_tier=old_tier,
                    new_tier=instance.tier,
                    date=instance.date,
                )
                logger.info(
                    "engagement_tier_changed user_id=%s %s → %s date=%s",
                    instance.user_id, old_tier, instance.tier, instance.date,
                )
    except Exception:
        logger.exception(
            "on_engagement_score_saved.error score_id=%s", instance.pk
        )


# ---------------------------------------------------------------------------
# path_closed → invalidate path-level caches
# ---------------------------------------------------------------------------

@receiver(path_closed)
def on_path_closed(sender, path: UserPath, previous_status: str, **kwargs: Any) -> None:
    """
    Invalidate cached path summaries after a session is closed.
    """
    try:
        from django.core.cache import cache
        from .constants import CACHE_KEY_PATH_SUMMARY

        cache_key = CACHE_KEY_PATH_SUMMARY.format(session_id=path.session_id)
        cache.delete(cache_key)
        logger.debug(
            "path_closed.cache_invalidated session_id=%s", path.session_id
        )
    except Exception:
        logger.exception("on_path_closed.error path_id=%s", path.pk)


# ---------------------------------------------------------------------------
# click_batch_recorded → optionally trigger incremental score recalculation
# ---------------------------------------------------------------------------

@receiver(click_batch_recorded)
def on_click_batch_recorded(
    sender, path: UserPath, count: int, **kwargs: Any
) -> None:
    """
    After a significant batch of clicks is recorded, schedule an
    incremental engagement score recalculation for this user.

    We throttle this to avoid spamming Celery: only trigger if count ≥ 10.
    """
    THRESHOLD = 10
    if count < THRESHOLD:
        return

    try:
        from .tasks import calculate_engagement_score
        from django.utils import timezone

        calculate_engagement_score.apply_async(
            kwargs={
                "user_id":          str(path.user_id),
                "target_date_iso":  timezone.localdate().isoformat(),
            },
            countdown=30,  # wait 30 s before calculating (batch window)
        )
        logger.debug(
            "click_batch.recalc_scheduled user_id=%s count=%d",
            path.user_id, count,
        )
    except Exception:
        logger.exception(
            "on_click_batch_recorded.error path_id=%s", path.pk
        )
