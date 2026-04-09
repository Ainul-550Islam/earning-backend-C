# api/djoyalty/events/event_handlers.py
import logging
from .event_registry import EventRegistry
from .event_types import TIER_CHANGED, BADGE_UNLOCKED, STREAK_MILESTONE

logger = logging.getLogger(__name__)

def handle_tier_changed(event):
    logger.info('Tier changed for %s: %s', event.customer, event.data)

def handle_badge_unlocked(event):
    logger.info('Badge unlocked for %s: %s', event.customer, event.data)

def handle_streak_milestone(event):
    logger.info('Streak milestone for %s: %s days', event.customer, event.data.get('milestone_days'))

def register_default_handlers():
    EventRegistry.register(TIER_CHANGED, handle_tier_changed)
    EventRegistry.register(BADGE_UNLOCKED, handle_badge_unlocked)
    EventRegistry.register(STREAK_MILESTONE, handle_streak_milestone)
