"""
api/tasks/tasks_cap.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CAP (Capacity/Budget) Management Celery Tasks.
Checks offer caps, campaign budgets, and resets daily counters.
"""

import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.tasks_cap.check_all_offer_caps')
def check_all_offer_caps(self) -> dict:
    """
    Check daily caps for all active offers.
    Fires CAP signals for any offers that have hit their limit.
    Runs every minute via Celery Beat.
    """
    try:
        logger.debug("🔒 Checking offer caps...")
        capped   = 0
        warnings = 0

        try:
            from ad_networks.models import SmartlinkOffer
            from api.tasks.signals_cap import fire_offer_cap

            offers = SmartlinkOffer.objects.filter(
                is_active=True
            ).exclude(daily_cap__isnull=True).values(
                'id', 'external_id', 'daily_cap', 'daily_clicks_used', 'is_active'
            )

            for offer in offers:
                daily_cap  = offer['daily_cap'] or 0
                daily_used = offer['daily_clicks_used'] or 0

                if daily_cap and daily_used >= daily_cap:
                    fire_offer_cap(offer['external_id'], 'daily')
                    SmartlinkOffer.objects.filter(pk=offer['id']).update(is_active=False)
                    capped += 1
                elif daily_cap and daily_used >= daily_cap * 0.90:
                    # 90% warning
                    cache.set(f'offer_cap_warning_{offer["external_id"]}', {
                        'pct': round(daily_used / daily_cap * 100, 1),
                        'at':  timezone.now().isoformat(),
                    }, timeout=3600)
                    warnings += 1

        except ImportError as e:
            logger.warning(f"[CAP] SmartlinkOffer not available: {e}")

        return {
            'status':   'success',
            'capped':   capped,
            'warnings': warnings,
            'timestamp': timezone.now().isoformat(),
        }
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.tasks_cap.check_campaign_budgets')
def check_campaign_budgets(self) -> dict:
    """
    Check all active campaign budgets and pause those exhausted.
    Delegates to advertiser_tasks for the actual pausing.
    """
    try:
        from api.tasks.advertiser_tasks import check_advertiser_budgets
        return check_advertiser_budgets()
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=10,
             name='tasks.tasks_cap.reset_daily_caps')
def reset_daily_caps(self) -> dict:
    """
    Reset daily click/conversion counters for all offers and campaigns.
    Runs at midnight UTC via Celery Beat.
    """
    try:
        logger.info("🔄 Resetting daily caps...")
        reset = 0

        try:
            from ad_networks.models import SmartlinkOffer
            reset = SmartlinkOffer.objects.filter(is_active=False, paused_reason='daily_cap').update(
                is_active=True,
                daily_clicks_used=0,
                paused_reason='',
            )
            reset += SmartlinkOffer.objects.filter(is_active=True).update(daily_clicks_used=0)
        except ImportError:
            pass

        try:
            from ad_networks.models import Campaign
            Campaign.objects.filter(
                status='paused', pause_reason='daily_budget_reached'
            ).update(status='active', daily_clicks=0, daily_spend=Decimal('0'))
        except ImportError:
            pass

        logger.info(f"[CAP] Daily caps reset: {reset} offers")
        return {'status': 'success', 'reset': reset, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.tasks_cap.sync_cap_counters_to_bridge')
def sync_cap_counters_to_bridge(self) -> dict:
    """Sync offer cap counters to DataBridge for fast cap checking."""
    try:
        from api.tasks.integration.data_bridge import DataBridge
        synced = 0
        try:
            from ad_networks.models import SmartlinkOffer
            for offer in SmartlinkOffer.objects.filter(
                is_active=True, daily_cap__isnull=False
            ).values('external_id', 'daily_cap', 'daily_clicks_used'):
                DataBridge.set_offer(
                    offer['external_id'], 'daily_cap', offer['daily_cap'], ttl=3600
                )
                DataBridge.set_offer(
                    offer['external_id'], 'daily_clicks_used', offer['daily_clicks_used'], ttl=300
                )
                synced += 1
        except ImportError:
            pass
        return {'status': 'success', 'synced': synced, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


__all__ = [
    'check_all_offer_caps', 'check_campaign_budgets',
    'reset_daily_caps', 'sync_cap_counters_to_bridge',
]
