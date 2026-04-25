# earning_backend/api/notifications/services/OptOutService.py
"""
OptOutService — manages user channel opt-outs (unsubscribes).

Responsibilities:
  - Record user opt-out events in OptOutTracking
  - Check if a user is opted out before sending
  - Re-subscribe users to a channel
  - Bulk opt-out / re-subscribe (admin)
  - Export opt-out status for compliance
"""

import logging
from typing import Dict, List, Optional

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class OptOutService:
    """
    Manages notification opt-outs (unsubscribes) for all channels.
    """

    VALID_CHANNELS = ('in_app', 'push', 'email', 'sms', 'telegram', 'whatsapp', 'browser', 'all')

    # ------------------------------------------------------------------
    # Check
    # ------------------------------------------------------------------

    def is_opted_out(self, user, channel: str) -> bool:
        """
        Return True if the user is currently opted out of the given channel.

        Passing channel='all' checks if they are opted out of everything.
        """
        from api.notifications.models.analytics import OptOutTracking

        if channel == 'all':
            return OptOutTracking.objects.filter(user=user, is_active=True).exists()

        return OptOutTracking.is_opted_out(user, channel)

    def can_receive(self, user, channel: str) -> bool:
        """Inverse of is_opted_out — True means the user CAN receive on this channel."""
        return not self.is_opted_out(user, channel)

    def get_opted_out_channels(self, user) -> List[str]:
        """Return a list of channel strings the user is currently opted out of."""
        from api.notifications.models.analytics import OptOutTracking
        return list(
            OptOutTracking.objects.filter(user=user, is_active=True)
            .values_list('channel', flat=True)
        )

    # ------------------------------------------------------------------
    # Opt-out
    # ------------------------------------------------------------------

    def opt_out(
        self,
        user,
        channel: str,
        reason: str = 'user_request',
        notes: str = '',
        triggered_by=None,
        actioned_by=None,
    ) -> Dict:
        """
        Opt a user out of a specific channel.

        If channel='all', creates opt-out records for every channel.

        Returns:
            Dict with: success (bool), user_id, channel, opted_out_at, error.
        """
        if channel not in self.VALID_CHANNELS:
            return {
                'success': False,
                'user_id': user.pk,
                'channel': channel,
                'opted_out_at': None,
                'error': f'Invalid channel: {channel}. Must be one of {self.VALID_CHANNELS}',
            }

        try:
            from api.notifications.models.analytics import OptOutTracking

            if channel == 'all':
                channels_to_opt_out = [c for c in self.VALID_CHANNELS if c != 'all']
                for ch in channels_to_opt_out:
                    OptOutTracking.opt_out(
                        user=user,
                        channel=ch,
                        reason=reason,
                        notes=notes,
                        triggered_by=triggered_by,
                        actioned_by=actioned_by,
                    )
                opted_out_at = timezone.now()
            else:
                record = OptOutTracking.opt_out(
                    user=user,
                    channel=channel,
                    reason=reason,
                    notes=notes,
                    triggered_by=triggered_by,
                    actioned_by=actioned_by,
                )
                opted_out_at = record.opted_out_at

            logger.info(f'OptOutService: user {user.pk} opted out of {channel}')

            return {
                'success': True,
                'user_id': user.pk,
                'channel': channel,
                'opted_out_at': opted_out_at.isoformat() if opted_out_at else None,
                'error': '',
            }

        except Exception as exc:
            logger.error(f'OptOutService.opt_out failed for user {user.pk}: {exc}')
            return {
                'success': False,
                'user_id': user.pk,
                'channel': channel,
                'opted_out_at': None,
                'error': str(exc),
            }

    def opt_out_from_notification(self, user, notification, channel: str = 'all') -> Dict:
        """
        Opt out triggered by a specific notification (e.g. unsubscribe link click).
        Records the triggering notification for audit.
        """
        return self.opt_out(
            user=user,
            channel=channel,
            reason='user_request',
            notes=f'Unsubscribed from notification #{notification.id}',
            triggered_by=notification,
            actioned_by=user,
        )

    # ------------------------------------------------------------------
    # Re-subscribe
    # ------------------------------------------------------------------

    def resubscribe(self, user, channel: str, actioned_by=None) -> Dict:
        """
        Re-subscribe a user to a channel.

        Returns:
            Dict with: success, user_id, channel, opted_in_at, error.
        """
        if channel not in self.VALID_CHANNELS:
            return {
                'success': False,
                'user_id': user.pk,
                'channel': channel,
                'opted_in_at': None,
                'error': f'Invalid channel: {channel}',
            }

        try:
            from api.notifications.models.analytics import OptOutTracking

            if channel == 'all':
                channels = [c for c in self.VALID_CHANNELS if c != 'all']
                OptOutTracking.objects.filter(
                    user=user, is_active=True
                ).update(
                    is_active=False,
                    opted_in_at=timezone.now(),
                    updated_at=timezone.now(),
                )
                opted_in_at = timezone.now()
            else:
                qs = OptOutTracking.objects.filter(user=user, channel=channel, is_active=True)
                opted_in_at = timezone.now()
                qs.update(is_active=False, opted_in_at=opted_in_at, updated_at=opted_in_at)

            logger.info(f'OptOutService: user {user.pk} resubscribed to {channel}')

            return {
                'success': True,
                'user_id': user.pk,
                'channel': channel,
                'opted_in_at': opted_in_at.isoformat(),
                'error': '',
            }

        except Exception as exc:
            logger.error(f'OptOutService.resubscribe failed for user {user.pk}: {exc}')
            return {
                'success': False,
                'user_id': user.pk,
                'channel': channel,
                'opted_in_at': None,
                'error': str(exc),
            }

    # ------------------------------------------------------------------
    # Bulk operations (admin / task use)
    # ------------------------------------------------------------------

    def bulk_opt_out(
        self,
        user_ids: List[int],
        channel: str,
        reason: str = 'admin_action',
        actioned_by=None,
    ) -> Dict:
        """
        Opt out multiple users from a channel in bulk.
        Returns: Dict with success, opted_out_count, errors.
        """
        from django.contrib.auth import get_user_model
        from api.notifications.models.analytics import OptOutTracking

        User = get_user_model()
        opted_out = 0
        errors = 0

        if channel not in self.VALID_CHANNELS:
            return {'success': False, 'opted_out_count': 0, 'errors': 1,
                    'error': f'Invalid channel: {channel}'}

        channels = [c for c in self.VALID_CHANNELS if c != 'all'] if channel == 'all' else [channel]

        with transaction.atomic():
            for user_id in user_ids:
                try:
                    user = User.objects.get(pk=user_id)
                    for ch in channels:
                        OptOutTracking.opt_out(
                            user=user, channel=ch,
                            reason=reason,
                            actioned_by=actioned_by,
                        )
                    opted_out += 1
                except Exception as exc:
                    logger.warning(f'OptOutService.bulk_opt_out user {user_id}: {exc}')
                    errors += 1

        return {'success': True, 'opted_out_count': opted_out, 'errors': errors, 'error': ''}

    def bulk_resubscribe(self, user_ids: List[int], channel: str) -> Dict:
        """Re-subscribe multiple users to a channel."""
        from api.notifications.models.analytics import OptOutTracking

        channels = [c for c in self.VALID_CHANNELS if c != 'all'] if channel == 'all' else [channel]

        try:
            updated = OptOutTracking.objects.filter(
                user_id__in=user_ids,
                channel__in=channels,
                is_active=True,
            ).update(
                is_active=False,
                opted_in_at=timezone.now(),
                updated_at=timezone.now(),
            )
            return {'success': True, 'resubscribed_count': updated, 'error': ''}
        except Exception as exc:
            logger.error(f'OptOutService.bulk_resubscribe failed: {exc}')
            return {'success': False, 'resubscribed_count': 0, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Filtering helpers (used by SegmentService / dispatch pipeline)
    # ------------------------------------------------------------------

    def filter_opted_out_users(
        self, user_ids: List[int], channel: str
    ) -> List[int]:
        """
        Return only user IDs that are NOT opted out of the given channel.
        """
        from api.notifications.models.analytics import OptOutTracking

        if channel == 'all':
            # Exclude users who have opted out of ANY channel
            opted_out_ids = set(
                OptOutTracking.objects.filter(is_active=True)
                .values_list('user_id', flat=True)
            )
        else:
            opted_out_ids = set(
                OptOutTracking.objects.filter(
                    user_id__in=user_ids,
                    channel=channel,
                    is_active=True,
                ).values_list('user_id', flat=True)
            )

        return [uid for uid in user_ids if uid not in opted_out_ids]

    # ------------------------------------------------------------------
    # Export / reporting
    # ------------------------------------------------------------------

    def get_opt_out_stats(self) -> Dict:
        """Return aggregate opt-out counts per channel."""
        from api.notifications.models.analytics import OptOutTracking
        from django.db.models import Count

        stats = (
            OptOutTracking.objects.filter(is_active=True)
            .values('channel')
            .annotate(count=Count('id'))
            .order_by('channel')
        )
        return {row['channel']: row['count'] for row in stats}

    def export_user_opt_outs(self, user) -> Dict:
        """Return a full opt-out export dict for a user (GDPR-style)."""
        from api.notifications.models.analytics import OptOutTracking

        records = OptOutTracking.objects.filter(user=user).order_by('channel', '-opted_out_at')
        return {
            'user_id': user.pk,
            'opt_outs': [
                {
                    'channel': r.channel,
                    'is_active': r.is_active,
                    'reason': r.reason,
                    'notes': r.notes,
                    'opted_out_at': r.opted_out_at.isoformat() if r.opted_out_at else None,
                    'opted_in_at': r.opted_in_at.isoformat() if r.opted_in_at else None,
                }
                for r in records
            ],
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
opt_out_service = OptOutService()
