# api/rate_limit/signals_cap.py
"""Capacity/limit change signals for rate_limit module."""
import logging
from django.dispatch import Signal

logger = logging.getLogger(__name__)

# Signals fired when rate limit capacity changes
rate_limit_config_changed = Signal()
rate_limit_capacity_updated = Signal()
user_limit_upgraded = Signal()
user_limit_downgraded = Signal()
ip_block_capacity_reached = Signal()
rate_limit_exceeded = Signal()
abuse_detected = Signal()
ip_blocked = Signal()
ip_block_triggered = Signal()
rate_limit_warning = Signal()
rate_limit_cleared = Signal()
user_blocked = Signal()
user_unblocked = Signal()
config_created = Signal()
config_updated = Signal()
config_deleted = Signal()


def send_config_changed(config, changed_by=None):
    """Send config changed signal."""
    rate_limit_config_changed.send(
        sender=config.__class__,
        config=config,
        changed_by=changed_by,
    )


def send_capacity_updated(config, old_limit, new_limit):
    """Send capacity updated signal."""
    rate_limit_capacity_updated.send(
        sender=config.__class__,
        config=config,
        old_limit=old_limit,
        new_limit=new_limit,
    )


__all__ = [
    'rate_limit_config_changed',
    'rate_limit_capacity_updated',
    'user_limit_upgraded',
    'user_limit_downgraded',
    'ip_block_capacity_reached',
        'rate_limit_exceeded',
    'abuse_detected',
    'ip_blocked',
    'ip_block_triggered',
    'rate_limit_warning',
    'rate_limit_cleared',
    'user_blocked',
    'user_unblocked',
    'config_created',
    'config_updated',
    'config_deleted',
    'send_config_changed',
    'send_capacity_updated',
]
