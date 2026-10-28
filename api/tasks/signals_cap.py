"""
api/tasks/signals_cap.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CAP (Capacity/Budget) Management Signals.
Fires when offers, campaigns, or ad units hit their caps.
Automatically pauses, rotates, or alerts when limits are reached.
"""

import logging
from django.dispatch import Signal
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── CAP signals ────────────────────────────────────────────────────────────
offer_daily_cap_reached    = Signal()   # sender=offer_id, remaining=0
offer_total_cap_reached    = Signal()   # sender=offer_id
campaign_budget_exhausted  = Signal()   # sender=campaign_id
campaign_daily_budget_hit  = Signal()   # sender=campaign_id
ad_unit_impression_cap_hit = Signal()   # sender=ad_unit_id
publisher_cap_reached      = Signal()   # sender=publisher_id, cap_type=str


# ── Signal handlers ────────────────────────────────────────────────────────

def on_offer_daily_cap_reached(sender, offer_id=None, **kwargs):
    """Pause offer and warm cache when daily cap is hit."""
    try:
        if not offer_id:
            return
        logger.info(f"[CAP] Offer daily cap reached: {offer_id}")

        # Mark offer as capped in DataBridge
        from api.tasks.integration.data_bridge import DataBridge
        DataBridge.set_offer(offer_id, 'is_daily_capped', True, ttl=86400)

        # Pause offer via Celery task
        from celery import current_app
        current_app.send_task(
            'tasks.offer_tasks.auto_pause_low_cvr_offers',
            queue='high',
        )

        # Notify admin
        cache.set(f'offer_cap_alert_{offer_id}', {
            'type':   'daily_cap',
            'offer':  offer_id,
            'at':     timezone.now().isoformat(),
        }, timeout=3600)

    except Exception as e:
        logger.error(f"[CAP SIGNAL] on_offer_daily_cap_reached: {e}")


def on_campaign_budget_exhausted(sender, campaign_id=None, **kwargs):
    """Pause campaign and notify advertiser when budget is exhausted."""
    try:
        if not campaign_id:
            return
        logger.warning(f"[CAP] Campaign budget exhausted: {campaign_id}")

        from celery import current_app
        current_app.send_task(
            'tasks.self_serve_campaign_tasks.pause_campaign',
            kwargs={'campaign_id': campaign_id, 'reason': 'budget_exhausted'},
            queue='high',
        )
    except Exception as e:
        logger.error(f"[CAP SIGNAL] on_campaign_budget_exhausted: {e}")


def on_campaign_daily_budget_hit(sender, campaign_id=None, **kwargs):
    """Pause campaign for remainder of day when daily budget is hit."""
    try:
        if not campaign_id:
            return
        logger.info(f"[CAP] Campaign daily budget hit: {campaign_id}")
        cache.set(f'campaign_daily_paused_{campaign_id}', True, timeout=86400)
    except Exception as e:
        logger.error(f"[CAP SIGNAL] on_campaign_daily_budget_hit: {e}")


# ── Connect signals ────────────────────────────────────────────────────────

def connect_cap_signals():
    """Connect all CAP signals. Called from apps.py."""
    offer_daily_cap_reached.connect(
        on_offer_daily_cap_reached,
        dispatch_uid='cap_offer_daily'
    )
    campaign_budget_exhausted.connect(
        on_campaign_budget_exhausted,
        dispatch_uid='cap_campaign_budget'
    )
    campaign_daily_budget_hit.connect(
        on_campaign_daily_budget_hit,
        dispatch_uid='cap_campaign_daily'
    )
    logger.info("[CAP SIGNALS] All CAP signals connected")


def fire_offer_cap(offer_id: str, cap_type: str = 'daily') -> None:
    """Helper: fire an offer cap signal."""
    if cap_type == 'daily':
        offer_daily_cap_reached.send(sender=None, offer_id=offer_id)
    elif cap_type == 'total':
        offer_total_cap_reached.send(sender=None, offer_id=offer_id)


def fire_campaign_budget_signal(campaign_id: int, budget_type: str = 'total') -> None:
    """Helper: fire a campaign budget signal."""
    if budget_type == 'total':
        campaign_budget_exhausted.send(sender=None, campaign_id=campaign_id)
    elif budget_type == 'daily':
        campaign_daily_budget_hit.send(sender=None, campaign_id=campaign_id)


__all__ = [
    'offer_daily_cap_reached', 'offer_total_cap_reached',
    'campaign_budget_exhausted', 'campaign_daily_budget_hit',
    'ad_unit_impression_cap_hit', 'publisher_cap_reached',
    'connect_cap_signals', 'fire_offer_cap', 'fire_campaign_budget_signal',
]
