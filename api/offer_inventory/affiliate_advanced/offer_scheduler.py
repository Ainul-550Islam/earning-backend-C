# api/offer_inventory/affiliate_advanced/offer_scheduler.py
"""Offer Scheduler — Advanced offer scheduling with timezone support."""
import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class OfferSchedulerEngine:
    """Schedule offer activations, deactivations, and pauses."""

    @staticmethod
    def schedule_activation(offer_id: str, activate_at,
                              deactivate_at=None) -> list:
        """Schedule offer activation and optional deactivation."""
        from api.offer_inventory.models import OfferSchedule, Offer
        offer     = Offer.objects.get(id=offer_id)
        schedules = []

        act = OfferSchedule.objects.create(
            offer       =offer,
            action      ='activate',
            scheduled_at=activate_at,
        )
        schedules.append(act)

        if deactivate_at:
            deact = OfferSchedule.objects.create(
                offer       =offer,
                action      ='deactivate',
                scheduled_at=deactivate_at,
            )
            schedules.append(deact)

        logger.info(f'Offer scheduled: {offer_id} activate@{activate_at}')
        return schedules

    @staticmethod
    def schedule_pause(offer_id: str, pause_at, resume_at=None) -> list:
        """Schedule a temporary pause."""
        from api.offer_inventory.models import OfferSchedule, Offer
        offer     = Offer.objects.get(id=offer_id)
        schedules = []

        schedules.append(OfferSchedule.objects.create(
            offer=offer, action='pause', scheduled_at=pause_at,
        ))
        if resume_at:
            schedules.append(OfferSchedule.objects.create(
                offer=offer, action='activate', scheduled_at=resume_at,
            ))
        return schedules

    @staticmethod
    def process_due_schedules() -> dict:
        """Execute all due scheduled actions."""
        from api.offer_inventory.models import OfferSchedule, Offer

        now     = timezone.now()
        due     = OfferSchedule.objects.filter(
            scheduled_at__lte=now, is_executed=False
        ).select_related('offer')

        executed = {'activated': 0, 'deactivated': 0, 'paused': 0}
        action_status_map = {
            'activate'  : 'active',
            'deactivate': 'expired',
            'pause'     : 'paused',
        }

        for schedule in due:
            try:
                new_status = action_status_map.get(schedule.action)
                if new_status:
                    Offer.objects.filter(id=schedule.offer_id).update(status=new_status)
                    key = f'{schedule.action}d'
                    executed[key] = executed.get(key, 0) + 1

                OfferSchedule.objects.filter(id=schedule.id).update(
                    is_executed=True, executed_at=now
                )
            except Exception as e:
                logger.error(f'Schedule exec error {schedule.id}: {e}')

        total = sum(executed.values())
        if total > 0:
            logger.info(f'Offer schedules processed: {executed}')
        return executed

    @staticmethod
    def get_upcoming(hours: int = 24) -> list:
        """Get schedules due in the next N hours."""
        from api.offer_inventory.models import OfferSchedule
        until = timezone.now() + timedelta(hours=hours)
        return list(
            OfferSchedule.objects.filter(
                scheduled_at__lte=until, is_executed=False
            )
            .select_related('offer')
            .values('offer__title', 'action', 'scheduled_at')
            .order_by('scheduled_at')[:50]
        )

    @staticmethod
    def cancel(schedule_id: str) -> bool:
        """Cancel a pending schedule."""
        from api.offer_inventory.models import OfferSchedule
        updated = OfferSchedule.objects.filter(
            id=schedule_id, is_executed=False
        ).update(is_executed=True, executed_at=timezone.now())
        return updated > 0

    @staticmethod
    def get_schedule_history(offer_id: str) -> list:
        """Get all schedules for an offer."""
        from api.offer_inventory.models import OfferSchedule
        return list(
            OfferSchedule.objects.filter(offer_id=offer_id)
            .order_by('-scheduled_at')
            .values('action', 'scheduled_at', 'is_executed', 'executed_at')
            [:20]
        )
