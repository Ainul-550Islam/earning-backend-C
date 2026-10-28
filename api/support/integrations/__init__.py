# api/support/integrations/__init__.py  — WORLD #1 FINAL
"""
Integration System — 23 files total.

CHANNEL INTEGRATIONS (5):
    email_to_ticket, telegram_bot, whatsapp_integration,
    facebook_messenger, slack_integration

INTEGRATION SYSTEM (18 files — new):
    integ_constants    — constants, event names, thresholds
    integ_registry     — singleton adapter registry
    integ_adapter      — 8 adapters (wallet, fraud, postback, offerwall, notifications, kyc, referral, analytics)
    integ_handler      — main orchestrator (offer dispute flow, ticket events)
    integ_signals      — Django signals from other apps → support
    integ_exceptions   — custom exceptions
    event_bus          — pub/sub event system
    bridge             — data transformation layer
    data_validator     — input validation
    fallback_logic     — circuit breaker pattern
    webhooks_integration — incoming webhooks
    message_queue      — high traffic async queue
    auth_bridge        — cross-module permissions
    performance_monitor — integration call timing
    integ_audit_logs   — full audit trail
    health_check       — all integrations health status
    sync_manager       — data conflict resolver

Quick use:
    from api.support.integrations import integ_handler, event_bus, health_checker
    result = integ_handler.verify_and_process_offer_dispute(dispute, ticket)
    event_bus.publish("support.ticket.created", ticket=ticket)
    health = health_checker.get_health_summary()
"""
try:
    from .integ_handler  import integ_handler
    from .event_bus      import event_bus
    from .integ_registry import get_registry
    from .health_check   import health_checker
    from .fallback_logic import fallback_manager
    from .integ_adapter  import (
        wallet_adapter, fraud_adapter, postback_adapter,
        notifications_adapter, kyc_adapter, referral_adapter, analytics_adapter,
    )
except ImportError as e:
    import logging
    logging.getLogger(__name__).debug(f'Integration partial import: {e}')
    integ_handler = None
    event_bus     = None

__all__ = [
    'integ_handler', 'event_bus', 'get_registry',
    'health_checker', 'fallback_manager',
    'wallet_adapter', 'fraud_adapter', 'postback_adapter',
    'notifications_adapter', 'kyc_adapter', 'referral_adapter', 'analytics_adapter',
]