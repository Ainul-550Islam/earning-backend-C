# api/admin_panel/signals_cap.py
"""
Signals CAP (Cross-App Propagation) — fire signals to other apps.
admin_panel fires these; other apps listen.
Principle: admin_panel is the ONLY controller, others only listen.
"""
import logging
from django.dispatch import Signal

logger = logging.getLogger(__name__)

# ─── Admin-fired signals ─────────────────────────────────────────────────────
admin_user_banned       = Signal()   # args: user_id, reason, banned_by
admin_user_unbanned     = Signal()   # args: user_id, unbanned_by
admin_withdrawal_approved = Signal() # args: item_id, amount, gateway, user_id
admin_withdrawal_rejected = Signal() # args: item_id, reason
admin_kyc_approved      = Signal()   # args: kyc_id, user_id
admin_broadcast_sent    = Signal()   # args: broadcast_id, audience_count
admin_config_changed    = Signal()   # args: config_key, old_value, new_value
admin_flag_changed      = Signal()   # args: flag_key, is_enabled, rollout_pct
admin_maintenance_on    = Signal()   # args: message, duration_minutes
admin_maintenance_off   = Signal()   # args:
admin_fraud_blocked     = Signal()   # args: ip_address, reason
admin_offer_approved    = Signal()   # args: offer_id, approved_by
admin_offer_paused      = Signal()   # args: offer_id, reason


def fire_user_banned(user_id, reason: str, banned_by=None):
    """Fire when admin bans a user."""
    admin_user_banned.send(sender='admin_panel', user_id=user_id, reason=reason, banned_by=banned_by)
    try:
        from api.admin_panel.INTEGRATION_SYSTEM.event_bus import event_bus
        event_bus.publish('user.banned', {'user_id': user_id, 'reason': reason}, source='admin_panel')
    except Exception as e:
        logger.debug(f"[signals_cap.fire_user_banned] event_bus: {e}")


def fire_withdrawal_approved(item_id, amount: float, gateway: str, user_id):
    admin_withdrawal_approved.send(
        sender='admin_panel', item_id=item_id,
        amount=amount, gateway=gateway, user_id=user_id,
    )
    try:
        from api.admin_panel.INTEGRATION_SYSTEM.event_bus import event_bus
        event_bus.publish('wallet.withdrawal_approved',
                          {'item_id': item_id, 'amount': amount, 'gateway': gateway, 'user_id': user_id},
                          source='admin_panel')
    except Exception as e:
        logger.debug(f"[signals_cap] event_bus: {e}")


def fire_config_changed(config_key: str, old_value, new_value, updated_by=None):
    admin_config_changed.send(
        sender='admin_panel', config_key=config_key,
        old_value=old_value, new_value=new_value, updated_by=updated_by,
    )
    try:
        from api.admin_panel.INTEGRATION_SYSTEM.event_bus import event_bus
        event_bus.publish('system.config_updated',
                          {'config_key': config_key, 'old': old_value, 'new': new_value},
                          source='admin_panel')
    except Exception as e:
        logger.debug(f"[signals_cap] event_bus: {e}")


def fire_flag_changed(flag_key: str, is_enabled: bool, rollout_pct: int = 100):
    admin_flag_changed.send(sender='admin_panel', flag_key=flag_key,
                            is_enabled=is_enabled, rollout_pct=rollout_pct)
    try:
        from api.admin_panel.INTEGRATION_SYSTEM.event_bus import event_bus
        event_bus.publish('system.feature_flag_changed',
                          {'flag_key': flag_key, 'is_enabled': is_enabled, 'rollout_pct': rollout_pct},
                          source='admin_panel')
    except Exception as e:
        logger.debug(f"[signals_cap] event_bus: {e}")