# api/admin_panel/INTEGRATION_SYSTEM/integ_signals.py
"""
Integration Signals — Django signals for cross-app communication.

When ANY app does something important, it fires a signal here.
admin_panel listens to ALL signals and triggers appropriate responses.

Usage:
    # Fire a signal from any app:
    from api.admin_panel.INTEGRATION_SYSTEM.integ_signals import integration_event
    integration_event.send(
        sender='wallet',
        event_type='WALLET_CREDITED',
        payload={'user_id': 123, 'amount': 50.0},
    )

    # Connect a handler:
    from api.admin_panel.INTEGRATION_SYSTEM.integ_signals import connect_handler
    connect_handler('FRAUD_DETECTED', my_handler)
"""
import logging
from typing import Optional
from django.dispatch import Signal, receiver
from django.utils import timezone
from .integ_constants import INTEGRATION_EVENTS

logger = logging.getLogger(__name__)

# ==================== SIGNALS ====================

# Master event signal — all cross-app events
integration_event = Signal()

# Specific signals for high-frequency events
user_event = Signal()
wallet_event = Signal()
fraud_event = Signal()
offer_event = Signal()
payout_event = Signal()
kyc_event = Signal()
system_event = Signal()
ai_event = Signal()


# ==================== MASTER RECEIVER ====================

@receiver(integration_event)
def on_integration_event(sender, event_type, payload=None, **kwargs):
    """
    Master handler — receives ALL integration events from all 50 apps.
    Routes each event to the appropriate sub-handler.
    """
    payload = payload or {}
    logger.debug(f"[IntegSignal] Event: {event_type} from {sender} payload_keys={list(payload.keys())}")

    # Route by event category
    if event_type.startswith('user.'):
        _handle_user_event(event_type, payload, sender)
    elif event_type.startswith('wallet.'):
        _handle_wallet_event(event_type, payload, sender)
    elif event_type.startswith('fraud.'):
        _handle_fraud_event(event_type, payload, sender)
    elif event_type.startswith('offer.') or event_type.startswith('conversion.'):
        _handle_offer_event(event_type, payload, sender)
    elif event_type.startswith('kyc.'):
        _handle_kyc_event(event_type, payload, sender)
    elif event_type.startswith('loyalty.'):
        _handle_loyalty_event(event_type, payload, sender)
    elif event_type.startswith('system.'):
        _handle_system_event(event_type, payload, sender)
    elif event_type.startswith('ai.'):
        _handle_ai_event(event_type, payload, sender)
    elif event_type.startswith('alert.'):
        _handle_alert_event(event_type, payload, sender)

    # Always update event log
    _log_event(event_type, payload, sender)


# ==================== EVENT HANDLERS ====================

def _handle_user_event(event_type: str, payload: dict, sender: str):
    """Handle user lifecycle events."""
    user_id = payload.get('user_id')

    if event_type == INTEGRATION_EVENTS['USER_BANNED']:
        # Freeze wallet, cancel pending withdrawals
        try:
            from api.wallet.models import Wallet
            Wallet.objects.filter(user_id=user_id).update(is_locked=True)
        except Exception as e:
            logger.error(f"[IntegSignal] Wallet freeze on user ban failed: {e}")
        # Cancel pending payout items
        try:
            from api.payout_queue.models import PayoutItem
            PayoutItem.objects.filter(user_id=user_id, status='QUEUED').update(status='CANCELLED')
        except Exception as e:
            logger.error(f"[IntegSignal] Payout cancel on user ban failed: {e}")
        # Revoke KYC if applicable
        logger.info(f"[IntegSignal] User {user_id} banned — wallet frozen, payouts cancelled")

    elif event_type == INTEGRATION_EVENTS['USER_REGISTERED']:
        # Award welcome bonus if feature flag enabled
        try:
            from api.admin_panel.services.FeatureFlagService import FeatureFlagService
            if FeatureFlagService.is_enabled('welcome_bonus'):
                from api.admin_panel.services.SystemConfigService import SystemConfigService
                bonus = SystemConfigService.get('welcome_bonus_points', default=0)
                if bonus > 0:
                    from api.admin_panel.INTEGRATION_SYSTEM.integ_handler import IntegrationHandler
                    IntegrationHandler.execute(
                        app='djoyalty',
                        action='grant_points',
                        payload={'user_id': user_id, 'amount': bonus, 'reason': 'Welcome bonus'},
                    )
        except Exception as e:
            logger.debug(f"[IntegSignal] Welcome bonus failed: {e}")


def _handle_wallet_event(event_type: str, payload: dict, sender: str):
    """Handle wallet events — large withdrawals, suspicious amounts."""
    if event_type == INTEGRATION_EVENTS['WITHDRAWAL_REQUESTED']:
        amount = float(payload.get('amount', 0))
        user_id = payload.get('user_id')
        # Auto-flag large withdrawals for review
        try:
            from api.admin_panel.services.SystemConfigService import SystemConfigService
            auto_limit = float(SystemConfigService.get('withdrawal_auto_approve_limit', default=1000))
            if amount > auto_limit:
                logger.info(f"[IntegSignal] Large withdrawal {amount} by user {user_id} — flagged for review")
                # Create admin alert
                try:
                    from api.alerts.models import AlertLog
                    AlertLog.objects.create(
                        alert_type='large_withdrawal',
                        severity='high',
                        message=f'Large withdrawal ৳{amount} by user {user_id}',
                        data=payload,
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"[IntegSignal] Withdrawal auto-flag check failed: {e}")


def _handle_fraud_event(event_type: str, payload: dict, sender: str):
    """Handle fraud events — auto-ban high-risk users."""
    if event_type == INTEGRATION_EVENTS['FRAUD_DETECTED']:
        fraud_score = int(payload.get('fraud_score', 0))
        user_id = payload.get('user_id')

        if fraud_score >= 95:
            # Critical risk: auto-ban
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                User.objects.filter(pk=user_id).update(is_active=False)
                logger.warning(f"[IntegSignal] AUTO-BAN: User {user_id} fraud_score={fraud_score}")
            except Exception as e:
                logger.error(f"[IntegSignal] Auto-ban failed for user {user_id}: {e}")
        elif fraud_score >= 80:
            # High risk: freeze wallet
            try:
                from api.wallet.models import Wallet
                Wallet.objects.filter(user_id=user_id).update(is_locked=True)
                logger.warning(f"[IntegSignal] WALLET FREEZE: User {user_id} fraud_score={fraud_score}")
            except Exception as e:
                logger.error(f"[IntegSignal] Wallet freeze failed: {e}")

    elif event_type == INTEGRATION_EVENTS['MULTI_ACCOUNT_DETECTED']:
        logger.warning(f"[IntegSignal] Multi-account detected: {payload.get('user_ids')}")


def _handle_offer_event(event_type: str, payload: dict, sender: str):
    """Handle offer and conversion events."""
    if event_type == INTEGRATION_EVENTS['CONVERSION_APPROVED']:
        # Credit user wallet
        user_id = payload.get('user_id')
        amount = float(payload.get('payout', 0))
        if user_id and amount > 0:
            try:
                from api.admin_panel.INTEGRATION_SYSTEM.integ_handler import IntegrationHandler
                IntegrationHandler.execute(
                    app='wallet',
                    action='adjust_balance',
                    payload={'user_id': user_id, 'amount': amount},
                )
                # Also award loyalty points
                from api.admin_panel.services.SystemConfigService import SystemConfigService
                points_rate = float(SystemConfigService.get('task_complete_points', default=10))
                IntegrationHandler.execute(
                    app='djoyalty',
                    action='grant_points',
                    payload={'user_id': user_id, 'amount': points_rate, 'reason': 'Offer completion'},
                )
            except Exception as e:
                logger.error(f"[IntegSignal] Wallet credit on conversion failed: {e}")


def _handle_kyc_event(event_type: str, payload: dict, sender: str):
    """Handle KYC events."""
    if event_type == INTEGRATION_EVENTS['KYC_APPROVED']:
        user_id = payload.get('user_id')
        try:
            from api.users.models import UserProfile
            UserProfile.objects.filter(user_id=user_id).update(identity_verified=True)
        except Exception as e:
            logger.debug(f"[IntegSignal] KYC profile update failed: {e}")


def _handle_loyalty_event(event_type: str, payload: dict, sender: str):
    """Handle loyalty/gamification events."""
    if event_type == INTEGRATION_EVENTS['TIER_UPGRADED']:
        user_id = payload.get('user_id')
        new_tier = payload.get('tier')
        # Send notification
        try:
            from api.notifications.models import Notification
            Notification.objects.create(
                user_id=user_id,
                title=f'🎉 Tier Upgraded to {new_tier}!',
                message=f'Congratulations! You have reached {new_tier} tier. Enjoy exclusive benefits!',
                notification_type='achievement',
            )
        except Exception as e:
            logger.debug(f"[IntegSignal] Tier upgrade notification failed: {e}")


def _handle_system_event(event_type: str, payload: dict, sender: str):
    """Handle system events — config changes, maintenance, health."""
    from django.core.cache import cache
    if event_type == INTEGRATION_EVENTS['CONFIG_UPDATED']:
        # Clear config cache
        key = payload.get('config_key')
        if key:
            cache.delete(f'admin_panel:config:{key}')
        cache.delete('admin_panel:config_all')
        logger.info(f"[IntegSignal] Config cache cleared: {key}")

    elif event_type == INTEGRATION_EVENTS['MAINTENANCE_STARTED']:
        cache.set('admin_panel:maintenance_mode_active', True, 86400)
        message = payload.get('message', 'Maintenance in progress')
        cache.set('admin_panel:maintenance_message', message, 86400)
        logger.warning(f"[IntegSignal] Maintenance started: {message}")

    elif event_type == INTEGRATION_EVENTS['MAINTENANCE_ENDED']:
        cache.delete('admin_panel:maintenance_mode_active')
        cache.delete('admin_panel:maintenance_message')
        logger.info("[IntegSignal] Maintenance ended — caches cleared")

    elif event_type == INTEGRATION_EVENTS['FEATURE_FLAG_CHANGED']:
        flag_key = payload.get('flag_key')
        cache.delete(f'admin_panel:feature_flag:{flag_key}')
        cache.delete('admin_panel:feature_flags')
        logger.info(f"[IntegSignal] Feature flag cache cleared: {flag_key}")


def _handle_ai_event(event_type: str, payload: dict, sender: str):
    """Handle AI engine events."""
    if event_type == INTEGRATION_EVENTS['ANOMALY_DETECTED']:
        metric = payload.get('metric')
        severity = payload.get('severity', 'medium')
        logger.warning(f"[IntegSignal] AI Anomaly: {metric} severity={severity}")
        # Create alert
        try:
            from api.alerts.models import AlertLog
            AlertLog.objects.create(
                alert_type='ai_anomaly',
                severity=severity,
                message=f'AI detected anomaly in {metric}',
                data=payload,
            )
        except Exception:
            pass

    elif event_type == INTEGRATION_EVENTS['CHURN_RISK_HIGH']:
        user_ids = payload.get('user_ids', [])
        logger.info(f"[IntegSignal] Churn risk: {len(user_ids)} users at risk")


def _handle_alert_event(event_type: str, payload: dict, sender: str):
    """Handle alert events."""
    if event_type == INTEGRATION_EVENTS['ALERT_TRIGGERED']:
        severity = payload.get('severity', 'medium')
        if severity in ('critical', 'high'):
            # Send to all admin users
            try:
                from api.admin_panel.services.AdminNotificationService import AdminNotificationService
                AdminNotificationService.notify_critical_alert(payload)
            except Exception as e:
                logger.debug(f"[IntegSignal] Admin alert notify failed: {e}")


def _log_event(event_type: str, payload: dict, sender: str):
    """Log integration event to audit trail."""
    try:
        from django.core.cache import cache
        key = f'admin_panel:integ_events'
        events = cache.get(key) or []
        events.insert(0, {
            'event_type': event_type,
            'sender': sender,
            'timestamp': timezone.now().isoformat(),
        })
        cache.set(key, events[:500], 3600)  # keep last 500 events, 1h TTL
    except Exception:
        pass


# ==================== HELPER FUNCTIONS ====================

def fire_event(sender: str, event_type: str, payload: Optional[dict] = None):
    """
    Convenience function to fire an integration event.

    Args:
        sender:     The app firing the event (e.g. 'wallet', 'fraud_detection')
        event_type: Event constant from INTEGRATION_EVENTS (e.g. 'wallet.credited')
        payload:    Event data dict
    """
    integration_event.send(
        sender=sender,
        event_type=event_type,
        payload=payload or {},
    )


def connect_handler(event_type: str, handler_func):
    """Register a custom handler for a specific event type."""
    from django.dispatch import receiver as django_receiver

    @receiver(integration_event)
    def _wrapped(sender, event_type=None, payload=None, **kwargs):
        if event_type == event_type:
            try:
                handler_func(sender=sender, payload=payload or {})
            except Exception as e:
                logger.error(f"[IntegSignal] Custom handler error for {event_type}: {e}")