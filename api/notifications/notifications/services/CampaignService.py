# earning_backend/api/notifications/services/CampaignService.py
"""
CampaignService — orchestrates notification campaign lifecycle.

Responsibilities:
  - Create / update / delete campaigns
  - Start, pause, resume, cancel campaigns
  - Process campaign sends in batches (delegates to NotificationService)
  - Integrate with FatigueService and OptOutService before each send
  - Track progress and update CampaignResult
  - Support A/B test campaigns via ABTestService
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class CampaignService:
    """
    High-level campaign management service.
    Works with both the legacy NotificationCampaign model (models.py) and
    the new split NotificationCampaign model (models/campaign.py).
    """

    DEFAULT_BATCH_SIZE = 100

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_campaign(
        self,
        name: str,
        template_id: int,
        segment_conditions: Dict,
        send_at=None,
        context: Optional[Dict] = None,
        created_by=None,
        **kwargs,
    ) -> Dict:
        """
        Create a new campaign.

        Args:
            name:                 Campaign display name.
            template_id:          NotificationTemplate PK.
            segment_conditions:   Dict of conditions passed to SegmentService.
            send_at:              Datetime to start sending (None = immediate).
            context:              Template context variables.
            created_by:           User who created the campaign.
            **kwargs:             Additional model fields.

        Returns:
            Dict with: success, campaign_id, error.
        """
        try:
            from notifications.models.campaign import NotificationCampaign, CampaignSegment
            from notifications.models import NotificationTemplate

            template = NotificationTemplate.objects.get(pk=template_id)

            with transaction.atomic():
                # Build segment
                segment = CampaignSegment.objects.create(
                    name=f'{name} — segment',
                    segment_type=segment_conditions.get('type', 'all'),
                    conditions=segment_conditions,
                    created_by=created_by,
                )

                campaign = NotificationCampaign.objects.create(
                    name=name,
                    template=template,
                    segment=segment,
                    send_at=send_at,
                    context=context or {},
                    status='draft' if not send_at else 'scheduled',
                    created_by=created_by,
                    **{k: v for k, v in kwargs.items() if k in (
                        'description',
                    )},
                )

            logger.info(f'CampaignService: created campaign #{campaign.pk} "{name}"')
            return {
                'success': True,
                'campaign_id': campaign.pk,
                'segment_id': segment.pk,
                'error': '',
            }

        except Exception as exc:
            logger.error(f'CampaignService.create_campaign failed: {exc}')
            return {'success': False, 'campaign_id': None, 'error': str(exc)}

    def get_campaign(self, campaign_id: int) -> Optional[object]:
        """Return the campaign instance or None."""
        try:
            from notifications.models.campaign import NotificationCampaign
            return NotificationCampaign.objects.get(pk=campaign_id)
        except Exception:
            return None

    def update_campaign(self, campaign_id: int, updates: Dict) -> Dict:
        """Update campaign fields (only allowed on draft campaigns)."""
        try:
            from notifications.models.campaign import NotificationCampaign

            campaign = NotificationCampaign.objects.get(pk=campaign_id)
            if campaign.status not in ('draft', 'scheduled'):
                return {
                    'success': False,
                    'error': f'Cannot update campaign in status: {campaign.status}',
                }

            allowed_fields = {'name', 'description', 'send_at', 'context'}
            for field, value in updates.items():
                if field in allowed_fields:
                    setattr(campaign, field, value)
            campaign.save()

            return {'success': True, 'campaign_id': campaign_id, 'error': ''}

        except Exception as exc:
            logger.error(f'CampaignService.update_campaign #{campaign_id}: {exc}')
            return {'success': False, 'campaign_id': campaign_id, 'error': str(exc)}

    def delete_campaign(self, campaign_id: int) -> Dict:
        """Delete a campaign (only allowed on draft/cancelled campaigns)."""
        try:
            from notifications.models.campaign import NotificationCampaign
            campaign = NotificationCampaign.objects.get(pk=campaign_id)
            if campaign.status not in ('draft', 'cancelled'):
                return {
                    'success': False,
                    'error': f'Cannot delete campaign in status: {campaign.status}',
                }
            campaign.delete()
            return {'success': True, 'campaign_id': campaign_id, 'error': ''}
        except Exception as exc:
            return {'success': False, 'campaign_id': campaign_id, 'error': str(exc)}

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def start_campaign(self, campaign_id: int) -> Dict:
        """Start a campaign (triggers the send process)."""
        try:
            from notifications.models.campaign import NotificationCampaign
            from notifications.services.SegmentService import segment_service

            campaign = NotificationCampaign.objects.get(pk=campaign_id)
            if not campaign.can_start():
                return {
                    'success': False,
                    'error': f'Cannot start campaign in status: {campaign.status}',
                }

            # Evaluate segment to get total_users count
            if campaign.segment:
                user_ids = segment_service.evaluate_segment(campaign.segment)
                campaign.total_users = len(user_ids)

            campaign.start()
            logger.info(f'CampaignService: started campaign #{campaign_id}')

            return {
                'success': True,
                'campaign_id': campaign_id,
                'total_users': campaign.total_users,
                'error': '',
            }

        except Exception as exc:
            logger.error(f'CampaignService.start_campaign #{campaign_id}: {exc}')
            return {'success': False, 'campaign_id': campaign_id, 'error': str(exc)}

    def pause_campaign(self, campaign_id: int) -> Dict:
        """Pause a running campaign."""
        try:
            from notifications.models.campaign import NotificationCampaign
            campaign = NotificationCampaign.objects.get(pk=campaign_id)
            success = campaign.pause()
            return {
                'success': success,
                'campaign_id': campaign_id,
                'error': '' if success else f'Cannot pause campaign in status: {campaign.status}',
            }
        except Exception as exc:
            return {'success': False, 'campaign_id': campaign_id, 'error': str(exc)}

    def cancel_campaign(self, campaign_id: int) -> Dict:
        """Cancel a campaign."""
        try:
            from notifications.models.campaign import NotificationCampaign
            campaign = NotificationCampaign.objects.get(pk=campaign_id)
            success = campaign.cancel()
            return {
                'success': success,
                'campaign_id': campaign_id,
                'error': '' if success else 'Campaign already completed or cancelled',
            }
        except Exception as exc:
            return {'success': False, 'campaign_id': campaign_id, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Processing (batch send)
    # ------------------------------------------------------------------

    def process_campaign(
        self,
        campaign_id: int,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> Dict:
        """
        Process a running campaign: build the segment, send notifications in
        batches, and update progress counters.

        Called by campaign_tasks.py (Celery task).

        Returns:
            Dict with: success, campaign_id, total_sent, total_failed,
            campaign_status, error.
        """
        try:
            from notifications.models.campaign import NotificationCampaign
            from notifications.services.SegmentService import segment_service
            from notifications.services.FatigueService import fatigue_service
            from notifications.services.OptOutService import opt_out_service
            from notifications.services import notification_service

            campaign = NotificationCampaign.objects.get(pk=campaign_id)

            if campaign.status != 'running':
                return {
                    'success': False,
                    'campaign_id': campaign_id,
                    'error': f'Campaign is not running (status: {campaign.status})',
                }

            if not campaign.template:
                return {
                    'success': False,
                    'campaign_id': campaign_id,
                    'error': 'Campaign has no template assigned',
                }

            # Get target user IDs from segment
            user_ids = []
            if campaign.segment:
                user_ids = segment_service.evaluate_segment(campaign.segment)
            
            if not user_ids:
                campaign.complete()
                return {
                    'success': True,
                    'campaign_id': campaign_id,
                    'total_sent': 0,
                    'total_failed': 0,
                    'campaign_status': campaign.status,
                    'error': '',
                }

            # Apply opt-out filter (channel from template or 'in_app')
            channel = getattr(campaign.template, 'channel', 'in_app') or 'in_app'
            user_ids = opt_out_service.filter_opted_out_users(user_ids, channel)

            # Apply fatigue filter (use 'medium' priority by default)
            priority = getattr(campaign.template, 'priority', 'medium') or 'medium'
            user_ids = fatigue_service.filter_fatigued_users(user_ids, priority)

            # Smart Send Time: if campaign has no fixed send_at, use intelligent timing
            use_smart_timing = (
                not campaign.send_at and
                channel in ('push', 'email', 'in_app') and
                len(user_ids) <= 10000  # Only for manageable batches
            )
            if use_smart_timing:
                try:
                    from notifications.services.SmartSendTimeService import smart_send_time_service
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    sample_users = User.objects.filter(pk__in=user_ids[:100])
                    # Group users by optimal hour for staggered sends
                    from collections import defaultdict
                    hour_groups = defaultdict(list)
                    for u in sample_users:
                        hour = smart_send_time_service.get_optimal_hour(u)
                        hour_groups[hour].append(u.pk)
                    logger.info(
                        f'CampaignService: SmartSendTime grouped {len(user_ids)} users '
                        f'across {len(hour_groups)} time slots'
                    )
                except Exception as exc:
                    logger.debug(f'SmartSendTime skipped: {exc}')

            # Get User objects in batches
            from django.contrib.auth import get_user_model
            User = get_user_model()

            total_sent = 0
            total_failed = 0

            for i in range(0, len(user_ids), batch_size):
                batch_ids = user_ids[i: i + batch_size]
                batch_users = list(User.objects.filter(pk__in=batch_ids))

                for user in batch_users:
                    try:
                        notification = notification_service.create_from_template(
                            template_name=campaign.template.name,
                            user=user,
                            context=campaign.context or {},
                            campaign_id=str(campaign_id),
                        )
                        if notification:
                            sent = notification_service.send_notification(notification)
                            if sent:
                                total_sent += 1
                                fatigue_service.record_send(user, priority=priority)
                                campaign.increment_sent(save=False)
                            else:
                                total_failed += 1
                                campaign.increment_failed(save=False)
                        else:
                            total_failed += 1
                            campaign.increment_failed(save=False)
                    except Exception as exc:
                        logger.warning(
                            f'CampaignService.process_campaign: user {user.pk} — {exc}'
                        )
                        total_failed += 1
                        campaign.increment_failed(save=False)

                # Persist batch progress
                campaign.save(update_fields=['sent_count', 'failed_count', 'updated_at'])

                # Re-check campaign status (may have been paused/cancelled externally)
                campaign.refresh_from_db(fields=['status'])
                if campaign.status != 'running':
                    logger.info(
                        f'CampaignService: campaign #{campaign_id} status changed to '
                        f'{campaign.status} — stopping processing.'
                    )
                    break

            # Mark complete if we've processed all users
            if campaign.status == 'running':
                campaign.complete()

            return {
                'success': True,
                'campaign_id': campaign_id,
                'total_sent': total_sent,
                'total_failed': total_failed,
                'campaign_status': campaign.status,
                'error': '',
            }

        except Exception as exc:
            logger.error(f'CampaignService.process_campaign #{campaign_id}: {exc}')
            try:
                from notifications.models.campaign import NotificationCampaign
                NotificationCampaign.objects.filter(pk=campaign_id).update(
                    status='failed', updated_at=timezone.now()
                )
            except Exception:
                pass
            return {
                'success': False,
                'campaign_id': campaign_id,
                'total_sent': 0,
                'total_failed': 0,
                'campaign_status': 'failed',
                'error': str(exc),
            }

    # ------------------------------------------------------------------
    # Stats / reporting
    # ------------------------------------------------------------------

    def get_campaign_stats(self, campaign_id: int) -> Dict:
        """Return a stats dict for a campaign."""
        try:
            from notifications.models.campaign import NotificationCampaign, CampaignResult

            campaign = NotificationCampaign.objects.get(pk=campaign_id)
            result = CampaignResult.objects.filter(campaign=campaign).first()

            stats = {
                'campaign_id': campaign_id,
                'name': campaign.name,
                'status': campaign.status,
                'total_users': campaign.total_users,
                'sent_count': campaign.sent_count,
                'failed_count': campaign.failed_count,
                'progress_pct': campaign.progress_pct,
                'started_at': campaign.started_at.isoformat() if campaign.started_at else None,
                'completed_at': campaign.completed_at.isoformat() if campaign.completed_at else None,
            }

            if result:
                stats['results'] = result.to_dict()

            return stats

        except Exception as exc:
            return {'campaign_id': campaign_id, 'error': str(exc)}

    def list_campaigns(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict:
        """List campaigns with optional status filter."""
        try:
            from notifications.models.campaign import NotificationCampaign

            qs = NotificationCampaign.objects.all().order_by('-created_at')
            if status:
                qs = qs.filter(status=status)

            total = qs.count()
            campaigns = qs[offset: offset + limit]

            return {
                'success': True,
                'total': total,
                'campaigns': [
                    {
                        'id': c.pk,
                        'name': c.name,
                        'status': c.status,
                        'sent_count': c.sent_count,
                        'total_users': c.total_users,
                        'send_at': c.send_at.isoformat() if c.send_at else None,
                        'created_at': c.created_at.isoformat(),
                    }
                    for c in campaigns
                ],
                'error': '',
            }
        except Exception as exc:
            return {'success': False, 'total': 0, 'campaigns': [], 'error': str(exc)}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
campaign_service = CampaignService()
