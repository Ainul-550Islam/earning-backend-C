"""
SmartLink Scheduler Service
Evaluates SmartLink schedules and auto-activates/deactivates links.
Runs every minute via Celery Beat.
"""
import logging
from django.utils import timezone

logger = logging.getLogger('smartlink.scheduler')


class SmartLinkSchedulerService:
    """Auto-manage SmartLink active state based on schedules and caps."""

    def process_all_schedules(self) -> dict:
        """
        Evaluate all enabled schedules and update SmartLink active states.
        Called every minute by Celery Beat.
        """
        from ...models.extensions.smartlink_schedule import SmartLinkSchedule
        from ...models import SmartLink

        schedules = SmartLinkSchedule.objects.filter(
            is_enabled=True
        ).select_related('smartlink')

        activated   = 0
        deactivated = 0
        skipped     = 0

        for schedule in schedules:
            sl = schedule.smartlink
            try:
                should_active = schedule.should_be_active()

                if should_active and not sl.is_active:
                    SmartLink.objects.filter(pk=sl.pk).update(
                        is_active=True,
                        updated_at=timezone.now(),
                    )
                    SmartLinkSchedule.objects.filter(pk=schedule.pk).update(
                        last_activated_at=timezone.now(),
                        activation_count=schedule.activation_count + 1,
                    )
                    activated += 1
                    logger.info(f"Auto-activated: [{sl.slug}]")

                elif not should_active and sl.is_active:
                    SmartLink.objects.filter(pk=sl.pk).update(
                        is_active=False,
                        updated_at=timezone.now(),
                    )
                    SmartLinkSchedule.objects.filter(pk=schedule.pk).update(
                        last_deactivated_at=timezone.now(),
                    )
                    # Invalidate cache
                    from ...services.core.SmartLinkCacheService import SmartLinkCacheService
                    SmartLinkCacheService().invalidate_smartlink(sl.slug)
                    deactivated += 1
                    logger.info(f"Auto-deactivated: [{sl.slug}]")

                else:
                    skipped += 1

            except Exception as e:
                logger.error(f"Schedule error for [{sl.slug}]: {e}")

        return {
            'activated':   activated,
            'deactivated': deactivated,
            'skipped':     skipped,
            'total':       schedules.count(),
        }

    def create_schedule(self, smartlink, params: dict):
        """Create or update a SmartLink schedule."""
        from ...models.extensions.smartlink_schedule import SmartLinkSchedule
        schedule, _ = SmartLinkSchedule.objects.update_or_create(
            smartlink=smartlink,
            defaults={
                'is_enabled':         params.get('is_enabled', True),
                'schedule_type':      params.get('schedule_type', 'once'),
                'activate_at':        params.get('activate_at'),
                'deactivate_at':      params.get('deactivate_at'),
                'daily_start_hour':   params.get('daily_start_hour'),
                'daily_end_hour':     params.get('daily_end_hour'),
                'max_total_clicks':   params.get('max_total_clicks'),
                'max_total_revenue':  params.get('max_total_revenue'),
            }
        )
        return schedule
