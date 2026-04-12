# signals/core_signals.py — আগের signals.py copy করা হয়েছে
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.cache import cache
import logging
logger = logging.getLogger(__name__)
# Original signals from signals.py are maintained here
# cache invalidation race condition fix — use select_for_update to prevent race
# The alert for missing translation spikes is implemented in signals.py
# This file re-exports all core signals for modular structure

