# api/payment_gateways/integration_system/integ_adapter.py
# Unified adapter — automatically discovers and wires all external app integrations

import importlib
import logging
from decimal import Decimal
from .integ_registry import registry
from .integ_constants import IntegEvent, IntegModule, Priority

logger = logging.getLogger(__name__)


class IntegrationAdapter:
    """
    Auto-discovers your existing apps and registers their handlers.

    On startup (AppConfig.ready()), this adapter:
        1. Checks which of your apps are installed
        2. Registers the right handler for each event
        3. Falls back to payment_gateways built-ins if app unavailable

    Your existing apps are automatically detected:
        api.wallet         → handles deposit/withdrawal balance
        api.notifications  → handles deposit/withdrawal emails/SMS
        api.fraud_detection→ handles fraud check
        api.postback_engine→ handles postback firing
        api.gamification   → handles badge/achievement awards
        api.analytics      → handles event tracking
        api.referral       → handles referral commission
    """

    def setup_all(self):
        """Register all available integrations. Call from AppConfig.ready()."""
        self._setup_wallet()
        self._setup_notifications()
        self._setup_fraud()
        self._setup_postback()
        self._setup_gamification()
        self._setup_analytics()
        self._setup_referral()
        logger.info('IntegrationAdapter: all integrations registered')

    # ── Wallet integration ─────────────────────────────────────────────────────
    def _setup_wallet(self):
        from .integrations import WalletIntegration
        wi = WalletIntegration()
        registry.register(IntegEvent.DEPOSIT_COMPLETED, wi.on_deposit_completed,
                           module=IntegModule.WALLET, priority=Priority.CRITICAL)
        registry.register(IntegEvent.WITHDRAWAL_PROCESSED, wi.on_withdrawal_processed,
                           module=IntegModule.WALLET, priority=Priority.CRITICAL)
        registry.register(IntegEvent.CONVERSION_APPROVED, wi.on_conversion_approved,
                           module=IntegModule.WALLET, priority=Priority.HIGH)
        registry.register(IntegEvent.CONVERSION_REVERSED, wi.on_conversion_reversed,
                           module=IntegModule.WALLET, priority=Priority.HIGH)
        logger.debug('Wallet integration registered')

    # ── Notification integration ───────────────────────────────────────────────
    def _setup_notifications(self):
        from .integrations import NotificationIntegration
        ni = NotificationIntegration()
        registry.register(IntegEvent.DEPOSIT_COMPLETED, ni.on_deposit_completed,
                           module=IntegModule.NOTIFICATIONS, priority=Priority.NORMAL,
                           is_async=True)
        registry.register(IntegEvent.DEPOSIT_FAILED, ni.on_deposit_failed,
                           module=IntegModule.NOTIFICATIONS, priority=Priority.NORMAL,
                           is_async=True)
        registry.register(IntegEvent.WITHDRAWAL_PROCESSED, ni.on_withdrawal_processed,
                           module=IntegModule.NOTIFICATIONS, priority=Priority.NORMAL,
                           is_async=True)
        registry.register(IntegEvent.WITHDRAWAL_FAILED, ni.on_withdrawal_failed,
                           module=IntegModule.NOTIFICATIONS, priority=Priority.NORMAL,
                           is_async=True)
        registry.register(IntegEvent.FRAUD_DETECTED, ni.on_fraud_detected,
                           module=IntegModule.NOTIFICATIONS, priority=Priority.HIGH,
                           is_async=True)
        logger.debug('Notification integration registered')

    # ── Fraud integration ──────────────────────────────────────────────────────
    def _setup_fraud(self):
        from .integrations import FraudIntegration
        fi = FraudIntegration()
        registry.register(IntegEvent.FRAUD_DETECTED, fi.on_fraud_detected,
                           module=IntegModule.FRAUD_DETECTION, priority=Priority.CRITICAL)
        logger.debug('Fraud integration registered')

    # ── Postback integration ───────────────────────────────────────────────────
    def _setup_postback(self):
        from .integrations import PostbackIntegration
        pi = PostbackIntegration()
        registry.register(IntegEvent.CONVERSION_APPROVED, pi.on_conversion_approved,
                           module=IntegModule.POSTBACK_ENGINE, priority=Priority.HIGH,
                           is_async=True)
        logger.debug('Postback integration registered')

    # ── Gamification integration ───────────────────────────────────────────────
    def _setup_gamification(self):
        try:
            from .integrations import GamificationIntegration
            gi = GamificationIntegration()
            registry.register(IntegEvent.DEPOSIT_COMPLETED, gi.on_deposit_completed,
                               module=IntegModule.GAMIFICATION, priority=Priority.LOW,
                               is_async=True)
            registry.register(IntegEvent.CONVERSION_APPROVED, gi.on_conversion_approved,
                               module=IntegModule.GAMIFICATION, priority=Priority.LOW,
                               is_async=True)
            logger.debug('Gamification integration registered')
        except Exception:
            pass  # Optional module

    # ── Analytics integration ──────────────────────────────────────────────────
    def _setup_analytics(self):
        try:
            from .integrations import AnalyticsIntegration
            ai = AnalyticsIntegration()
            for event in [IntegEvent.DEPOSIT_COMPLETED, IntegEvent.WITHDRAWAL_PROCESSED,
                           IntegEvent.CONVERSION_APPROVED]:
                registry.register(event, ai.track_event,
                                   module=IntegModule.ANALYTICS, priority=Priority.ASYNC,
                                   is_async=True)
            logger.debug('Analytics integration registered')
        except Exception:
            pass

    # ── Referral integration ───────────────────────────────────────────────────
    def _setup_referral(self):
        from .integrations import ReferralIntegration
        ri = ReferralIntegration()
        registry.register(IntegEvent.DEPOSIT_COMPLETED, ri.on_deposit_completed,
                           module=IntegModule.REFERRAL, priority=Priority.NORMAL,
                           is_async=True)
        logger.debug('Referral integration registered')
