# earning_backend/api/notifications/services/FatigueService.py
"""
FatigueService — prevents notification fatigue for users.

Responsibilities:
  - Check if a user has received too many notifications today / this week
  - Increment counters after successful sends
  - Reset counters daily / weekly (called by fatigue_check_tasks)
  - Return whether a notification should be suppressed for a fatigued user
  - Allow per-user and system-level limit configuration

System default limits (override in Django settings):
    NOTIFICATION_FATIGUE_DAILY_LIMIT   = 10  (default)
    NOTIFICATION_FATIGUE_WEEKLY_LIMIT  = 50  (default)
    NOTIFICATION_FATIGUE_EXEMPT_PRIORITIES = ['critical', 'urgent']
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System defaults (can be overridden in Django settings)
# ---------------------------------------------------------------------------
DEFAULT_DAILY_LIMIT: int = getattr(settings, 'NOTIFICATION_FATIGUE_DAILY_LIMIT', 10)
DEFAULT_WEEKLY_LIMIT: int = getattr(settings, 'NOTIFICATION_FATIGUE_WEEKLY_LIMIT', 50)
EXEMPT_PRIORITIES: List[str] = getattr(
    settings,
    'NOTIFICATION_FATIGUE_EXEMPT_PRIORITIES',
    ['critical', 'urgent'],
)


class FatigueService:
    """
    Service for managing notification fatigue.

    All public methods accept a User model instance and return structured
    dicts consistent with the rest of the notification service layer.
    """

    # ------------------------------------------------------------------
    # Check / gate
    # ------------------------------------------------------------------

    def is_fatigued(self, user, priority: str = 'medium') -> bool:
        """
        Return True if the user is currently fatigued and the notification
        should be suppressed.

        Critical / urgent notifications always bypass the fatigue gate.

        Args:
            user:     Django User instance.
            priority: Notification priority string.

        Returns:
            True if the notification should be suppressed, False to allow.
        """
        # Exempt high-priority notifications
        if priority in EXEMPT_PRIORITIES:
            return False

        record = self._get_or_create(user)
        return record.is_fatigued

    def can_send(self, user, priority: str = 'medium') -> Dict:
        """
        Check whether a notification can be sent to the user without
        triggering fatigue.

        Returns:
            Dict with: allowed (bool), reason (str), sent_today (int),
            sent_this_week (int), daily_limit (int), weekly_limit (int).
        """
        if priority in EXEMPT_PRIORITIES:
            return {
                'allowed': True,
                'reason': 'exempt_priority',
                'sent_today': 0,
                'sent_this_week': 0,
                'daily_limit': DEFAULT_DAILY_LIMIT,
                'weekly_limit': DEFAULT_WEEKLY_LIMIT,
            }

        record = self._get_or_create(user)
        daily_limit = record.get_effective_daily_limit()
        weekly_limit = record.get_effective_weekly_limit()

        if record.sent_today >= daily_limit:
            return {
                'allowed': False,
                'reason': 'daily_limit_exceeded',
                'sent_today': record.sent_today,
                'sent_this_week': record.sent_this_week,
                'daily_limit': daily_limit,
                'weekly_limit': weekly_limit,
            }

        if record.sent_this_week >= weekly_limit:
            return {
                'allowed': False,
                'reason': 'weekly_limit_exceeded',
                'sent_today': record.sent_today,
                'sent_this_week': record.sent_this_week,
                'daily_limit': daily_limit,
                'weekly_limit': weekly_limit,
            }

        return {
            'allowed': True,
            'reason': 'within_limits',
            'sent_today': record.sent_today,
            'sent_this_week': record.sent_this_week,
            'daily_limit': daily_limit,
            'weekly_limit': weekly_limit,
        }

    # ------------------------------------------------------------------
    # Increment
    # ------------------------------------------------------------------

    def record_send(self, user, priority: str = 'medium') -> Dict:
        """
        Increment the user's fatigue counters after a successful send.
        Re-evaluates the fatigue flag after incrementing.

        Returns:
            Dict with: sent_today, sent_this_week, is_fatigued.
        """
        record = self._get_or_create(user)

        with transaction.atomic():
            # Re-fetch with lock to avoid race conditions
            record = (
                type(record).objects.select_for_update()
                .get(pk=record.pk)
            )
            record.increment(save=False)
            record.evaluate_fatigue(save=False)
            record.save(update_fields=[
                'sent_today', 'sent_this_week', 'sent_this_month',
                'is_fatigued', 'last_evaluated_at', 'updated_at',
            ])

        return {
            'sent_today': record.sent_today,
            'sent_this_week': record.sent_this_week,
            'is_fatigued': record.is_fatigued,
        }

    # ------------------------------------------------------------------
    # Bulk reset (called by fatigue_check_tasks)
    # ------------------------------------------------------------------

    def reset_daily_counters(self) -> Dict:
        """
        Reset daily counters for all users.
        Called by fatigue_check_tasks.py every day at midnight.

        Returns:
            Dict with: reset_count, errors.
        """
        from api.notifications.models.analytics import NotificationFatigue

        reset_count = 0
        errors = 0

        qs = NotificationFatigue.objects.all()
        for record in qs.iterator(chunk_size=500):
            try:
                record.reset_daily(save=False)
                record.evaluate_fatigue(save=False)
                record.save(update_fields=[
                    'sent_today', 'daily_reset_at',
                    'is_fatigued', 'last_evaluated_at', 'updated_at',
                ])
                reset_count += 1
            except Exception as exc:
                logger.warning(f'FatigueService.reset_daily_counters: user {record.user_id} — {exc}')
                errors += 1

        logger.info(f'FatigueService: reset daily counters for {reset_count} users ({errors} errors)')
        return {'reset_count': reset_count, 'errors': errors}

    def reset_weekly_counters(self) -> Dict:
        """
        Reset weekly counters for all users.
        Called by fatigue_check_tasks.py every Monday.

        Returns:
            Dict with: reset_count, errors.
        """
        from api.notifications.models.analytics import NotificationFatigue

        reset_count = 0
        errors = 0

        qs = NotificationFatigue.objects.all()
        for record in qs.iterator(chunk_size=500):
            try:
                record.reset_weekly(save=False)
                record.evaluate_fatigue(save=False)
                record.save(update_fields=[
                    'sent_this_week', 'weekly_reset_at',
                    'is_fatigued', 'last_evaluated_at', 'updated_at',
                ])
                reset_count += 1
            except Exception as exc:
                logger.warning(f'FatigueService.reset_weekly_counters: user {record.user_id} — {exc}')
                errors += 1

        logger.info(f'FatigueService: reset weekly counters for {reset_count} users ({errors} errors)')
        return {'reset_count': reset_count, 'errors': errors}

    def recalculate_all(self) -> Dict:
        """
        Re-evaluate the fatigue flag for all users based on current counters.
        Useful after changing system-wide limits.

        Returns:
            Dict with: evaluated_count, fatigued_count, errors.
        """
        from api.notifications.models.analytics import NotificationFatigue

        evaluated = 0
        fatigued = 0
        errors = 0

        for record in NotificationFatigue.objects.all().iterator(chunk_size=500):
            try:
                was_fatigued = record.evaluate_fatigue(save=True)
                evaluated += 1
                if was_fatigued:
                    fatigued += 1
            except Exception as exc:
                logger.warning(f'FatigueService.recalculate_all: user {record.user_id} — {exc}')
                errors += 1

        return {'evaluated_count': evaluated, 'fatigued_count': fatigued, 'errors': errors}

    # ------------------------------------------------------------------
    # Per-user limit management
    # ------------------------------------------------------------------

    def set_user_limits(self, user, daily_limit: int = 0, weekly_limit: int = 0) -> Dict:
        """
        Override daily/weekly limits for a specific user.
        Pass 0 to revert to system defaults.
        """
        record = self._get_or_create(user)
        record.daily_limit = max(0, daily_limit)
        record.weekly_limit = max(0, weekly_limit)
        record.save(update_fields=['daily_limit', 'weekly_limit', 'updated_at'])
        return {
            'user_id': user.pk,
            'daily_limit': record.daily_limit or DEFAULT_DAILY_LIMIT,
            'weekly_limit': record.weekly_limit or DEFAULT_WEEKLY_LIMIT,
        }

    def get_user_fatigue_status(self, user) -> Dict:
        """Return full fatigue status dict for a user."""
        record = self._get_or_create(user)
        return {
            'user_id': user.pk,
            'sent_today': record.sent_today,
            'sent_this_week': record.sent_this_week,
            'sent_this_month': record.sent_this_month,
            'daily_limit': record.get_effective_daily_limit(),
            'weekly_limit': record.get_effective_weekly_limit(),
            'is_fatigued': record.is_fatigued,
            'last_evaluated_at': (
                record.last_evaluated_at.isoformat() if record.last_evaluated_at else None
            ),
        }

    def clear_fatigue(self, user) -> Dict:
        """
        Manually clear the fatigue flag for a user (e.g. admin override).
        """
        record = self._get_or_create(user)
        record.is_fatigued = False
        record.last_evaluated_at = timezone.now()
        record.save(update_fields=['is_fatigued', 'last_evaluated_at', 'updated_at'])
        return {'user_id': user.pk, 'is_fatigued': False}

    # ------------------------------------------------------------------
    # Bulk fatigue query (for SegmentService)
    # ------------------------------------------------------------------

    def get_fatigued_user_ids(self) -> List[int]:
        """Return a list of user IDs currently marked as fatigued."""
        from api.notifications.models.analytics import NotificationFatigue
        return list(
            NotificationFatigue.objects.filter(is_fatigued=True).values_list('user_id', flat=True)
        )

    def filter_fatigued_users(self, user_ids: List[int], priority: str = 'medium') -> List[int]:
        """
        Given a list of user IDs, return only those NOT fatigued (safe to send to).
        Exempt priorities bypass this filter entirely.
        """
        if priority in EXEMPT_PRIORITIES:
            return user_ids

        from api.notifications.models.analytics import NotificationFatigue
        fatigued_ids = set(
            NotificationFatigue.objects.filter(
                user_id__in=user_ids, is_fatigued=True
            ).values_list('user_id', flat=True)
        )
        return [uid for uid in user_ids if uid not in fatigued_ids]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_or_create(user):
        """Get or create the NotificationFatigue record for a user."""
        from api.notifications.models.analytics import NotificationFatigue
        return NotificationFatigue.get_or_create_for_user(user)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
fatigue_service = FatigueService()
