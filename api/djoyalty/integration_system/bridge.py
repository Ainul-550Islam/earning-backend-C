# api/djoyalty/integration_system/bridge.py
"""
Service Bridge -- Bridges Djoyalty services ↔ external systems।
High-level API for cross-module operations।
Single entry point for all service-to-integration calls।
"""
import logging
from decimal import Decimal
from typing import Optional
from .integ_registry import IntegrationRegistry

logger = logging.getLogger(__name__)


class LoyaltyBridge:
    """
    Bridge between loyalty business logic and external integrations।

    This is the SINGLE entry point for:
    - Points earned -> notify customer (SMS + Push + Email)
    - Tier upgraded -> notify + update webhook
    - Cashout requested -> initiate payment gateway
    - Receipt scanned -> process OCR
    - Offer completed -> award points + postback confirm

    Usage:
        bridge = LoyaltyBridge()
        bridge.on_points_earned(customer, 100, 500)
        bridge.on_cashout_requested(cashout_request)
    """

    def __init__(self):
        self.registry = IntegrationRegistry.get_instance()

    # ─── Loyalty Event Bridges ────────────────────────────────────

    def on_points_earned(self, customer, points: Decimal, new_balance: Decimal,
                          source: str = 'purchase', reference: str = ''):
        """Bridge: points earned -> all integrations।"""
        from .event_bus import EventBus
        from .integ_constants import EventType
        EventBus.publish(
            EventType.POINTS_EARNED,
            customer=customer,
            data={
                'points': str(points),
                'balance': str(new_balance),
                'source': source,
                'reference': reference,
            },
        )

    def on_points_redeemed(self, customer, points: Decimal, reward_type: str = ''):
        """Bridge: points redeemed।"""
        from .event_bus import EventBus
        from .integ_constants import EventType
        EventBus.publish(
            EventType.POINTS_REDEEMED,
            customer=customer,
            data={'points': str(points), 'reward_type': reward_type},
        )

    def on_tier_changed(self, customer, old_tier: str, new_tier: str,
                         change_type: str = 'upgrade'):
        """Bridge: tier changed -> SMS + Push + Email + Webhook।"""
        from .event_bus import EventBus
        from .integ_constants import EventType
        event = EventType.TIER_UPGRADED if change_type == 'upgrade' else EventType.TIER_DOWNGRADED
        EventBus.publish(
            event,
            customer=customer,
            data={'old_tier': old_tier, 'new_tier': new_tier},
        )

    def on_badge_unlocked(self, customer, badge_name: str, badge_icon: str = '🏅'):
        """Bridge: badge unlocked -> push notification।"""
        from .event_bus import EventBus
        from .integ_constants import EventType
        EventBus.publish(
            EventType.BADGE_UNLOCKED,
            customer=customer,
            data={'badge_name': badge_name, 'badge_icon': badge_icon},
        )

    def on_voucher_issued(self, customer, code: str, discount: str, expires_at=None):
        """Bridge: voucher generated -> SMS + Email + Push।"""
        from .event_bus import EventBus
        from .integ_constants import EventType
        EventBus.publish(
            EventType.VOUCHER_GENERATED,
            customer=customer,
            data={'code': code, 'discount': discount, 'expires_at': expires_at},
        )

    def on_cashout_completed(self, customer, amount: Decimal, method: str, ref: str):
        """Bridge: cashout completed -> notify customer।"""
        from .event_bus import EventBus
        from .integ_constants import EventType
        EventBus.publish(
            EventType.CASHOUT_COMPLETED,
            customer=customer,
            data={'amount': str(amount), 'method': method, 'ref': ref},
        )

    def on_churn_alert(self, customer, risk_level: str, probability: Decimal):
        """Bridge: churn alert -> AI personalization + webhook।"""
        from .event_bus import EventBus
        from .integ_constants import EventType
        EventBus.publish(
            EventType.CHURN_ALERT,
            customer=customer,
            data={'risk_level': risk_level, 'probability': str(probability)},
        )

    # ─── Payment Bridges ──────────────────────────────────────────

    def initiate_cashout_payment(self, cashout_request) -> dict:
        """Bridge: initiate payment gateway for cashout।"""
        from .integ_handler import IntegrationHandler
        handler = IntegrationHandler()
        return handler.process_cashout(cashout_request)

    def verify_payment(self, method: str, payment_id: str) -> dict:
        """Bridge: verify payment via adapter।"""
        from .integ_adapter import AdapterFactory
        adapter = AdapterFactory.get_payment_adapter(method)
        if not adapter:
            return {'success': False, 'error': f'No adapter for {method}'}
        return adapter.verify_payment(payment_id)

    # ─── OCR Bridge ───────────────────────────────────────────────

    def process_receipt(self, image_url: str) -> dict:
        """Bridge: process receipt image via OCR।"""
        from .integ_handler import IntegrationHandler
        handler = IntegrationHandler()
        return handler.process_receipt_ocr(image_url)

    # ─── Notification Bridges ─────────────────────────────────────

    def send_expiry_warning(self, customer, points: Decimal, days: int):
        """Bridge: points expiring soon -> warn customer।"""
        try:
            if customer.sms_opt_in and customer.phone:
                from ..integrations.sms import SMSService
                SMSService.notify_points_expiring(customer, float(points), days)
            if customer.push_opt_in:
                from ..integrations.push_notification import FCMPushService
                FCMPushService.notify_points_expiring(customer, float(points), days)
        except Exception as e:
            logger.error('LoyaltyBridge.send_expiry_warning error: %s', e)

    def send_personalized_offer(self, customer, offer):
        """Bridge: AI offer -> push + email notification।"""
        try:
            if customer.push_opt_in:
                from ..integrations.push_notification import FCMPushService
                FCMPushService.notify_personalized_offer(customer, offer.title)
            from .event_bus import EventBus
            from .integ_constants import EventType
            EventBus.publish(EventType.OFFER_PERSONALIZED, customer=customer,
                             data={'offer_title': offer.title, 'offer_type': offer.offer_type})
        except Exception as e:
            logger.error('LoyaltyBridge.send_personalized_offer error: %s', e)

    # ─── Health Check Bridge ──────────────────────────────────────

    def get_all_integration_health(self) -> dict:
        """Bridge: get health of all integrations।"""
        from .health_check import HealthCheckService
        return HealthCheckService.check_all()


# ─── Module-level singleton ──────────────────────────────────────────────────
loyalty_bridge = LoyaltyBridge()
