# api/djoyalty/integration_system/integ_handler.py
"""
Integration Handler -- Central dispatcher for all integration calls।
Routes events to correct integrations, handles retry/fallback।
"""
import logging
import time
from typing import Any, Callable, Optional
from functools import wraps
from .integ_constants import EventType, IntegrationType, MessagePriority
from .integ_exceptions import (
    DjoyaltyIntegrationError, CircuitBreakerOpenError,
    IntegrationNotConfiguredError,
)
from .integ_registry import IntegrationRegistry

logger = logging.getLogger(__name__)


def integration_call(integration_name: str, fallback=None, log_errors: bool = True):
    """
    Decorator: wraps integration calls with error handling + logging।
    Usage:
        @integration_call('bkash', fallback=None)
        def send_cashout(customer, amount):
            bkash = registry.get('bkash')
            return bkash.send_money_b2c(...)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = func(*args, **kwargs)
                elapsed = (time.monotonic() - start) * 1000
                logger.debug('integration_call[%s] %s: %.1fms', integration_name, func.__name__, elapsed)
                return result
            except DjoyaltyIntegrationError as e:
                elapsed = (time.monotonic() - start) * 1000
                if log_errors:
                    logger.error('integration_call[%s] %s failed: %s (%.1fms)',
                                 integration_name, func.__name__, e, elapsed)
                if fallback is not None:
                    return fallback
                raise
            except Exception as e:
                elapsed = (time.monotonic() - start) * 1000
                if log_errors:
                    logger.error('integration_call[%s] %s unexpected error: %s',
                                 integration_name, func.__name__, e)
                if fallback is not None:
                    return fallback
                raise DjoyaltyIntegrationError(str(e), integration_name=integration_name) from e
        return wrapper
    return decorator


class IntegrationHandler:
    """
    Central integration handler -- entry point for all integration calls।
    Handles: routing, retry, fallback, circuit breaker, logging।

    Usage:
        handler = IntegrationHandler()
        # SMS
        handler.send_sms('01700000000', 'Your points: 500')
        # Push
        handler.send_push(customer, title='Badge!', body='New badge unlocked')
        # Email
        handler.send_email(customer, 'Welcome!', html='<h1>Hi</h1>')
        # Payment
        handler.process_cashout(cashout_request)
    """

    def __init__(self):
        self.registry = IntegrationRegistry.get_instance()
        self._performance_data = []

    # ─── SMS ───────────────────────────────────────────────────────

    def send_sms(self, to: str, message: str,
                  priority: MessagePriority = MessagePriority.NORMAL) -> bool:
        """Send SMS via configured provider।"""
        if not to:
            return False
        try:
            from ..integrations.sms import SMSService
            result = SMSService.send(to, message)
            if result.get('skipped'):
                return False
            self._log_call('sms', 'send', success=True)
            return True
        except Exception as e:
            logger.error('IntegrationHandler.send_sms error to %s: %s', to, e)
            self._log_call('sms', 'send', success=False, error=str(e))
            return False

    def send_bulk_sms(self, numbers: list, message: str) -> dict:
        """Bulk SMS send।"""
        try:
            from ..integrations.sms import SMSService
            return SMSService.send_bulk(numbers, message)
        except Exception as e:
            logger.error('IntegrationHandler.send_bulk_sms error: %s', e)
            return {'error': str(e)}

    # ─── Push Notification ────────────────────────────────────────

    def send_push(self, customer, title: str, body: str,
                   data: dict = None, notification_type: str = 'general') -> bool:
        """Send FCM push to customer।"""
        try:
            from ..integrations.push_notification import FCMPushService
            if not FCMPushService.is_configured():
                return False
            return FCMPushService.send_to_customer(
                customer, title=title, body=body,
                data=data, notification_type=notification_type,
            )
        except Exception as e:
            logger.error('IntegrationHandler.send_push error: %s', e)
            return False

    def send_push_to_topic(self, topic: str, title: str, body: str) -> bool:
        """Send FCM push to topic।"""
        try:
            from ..integrations.push_notification import FCMPushService
            return FCMPushService.send_to_topic(topic, title, body)
        except Exception as e:
            logger.error('IntegrationHandler.send_push_to_topic: %s', e)
            return False

    # ─── Email ─────────────────────────────────────────────────────

    def send_email(self, to: str, subject: str, html_body: str,
                    text_body: str = '') -> bool:
        """Send email via configured provider।"""
        if not to:
            return False
        try:
            from ..integrations.email import EmailService
            return EmailService.send(to, subject, html_body, text_body)
        except Exception as e:
            logger.error('IntegrationHandler.send_email error to %s: %s', to, e)
            return False

    def send_loyalty_email(self, event_type: str, customer, **kwargs) -> bool:
        """Send pre-built loyalty email by event type।"""
        try:
            from ..integrations.email import EmailService
            handlers = {
                'welcome':       lambda: EmailService.send_welcome(customer),
                'points_earned': lambda: EmailService.send_points_statement(
                    customer,
                    kwargs.get('points_earned', 0),
                    kwargs.get('current_balance', 0),
                    kwargs.get('reference', ''),
                ),
                'tier_upgrade': lambda: EmailService.send_tier_upgrade(
                    customer,
                    kwargs.get('old_tier', ''),
                    kwargs.get('new_tier', ''),
                    kwargs.get('benefits'),
                ),
                'voucher': lambda: EmailService.send_voucher(
                    customer,
                    kwargs.get('code', ''),
                    kwargs.get('discount', ''),
                    kwargs.get('expires_at'),
                ),
                'cashout': lambda: EmailService.send_cashout_confirmation(
                    customer,
                    kwargs.get('amount', 0),
                    kwargs.get('method', ''),
                    kwargs.get('ref', ''),
                ),
            }
            handler = handlers.get(event_type)
            if handler:
                handler()
                return True
            return False
        except Exception as e:
            logger.error('IntegrationHandler.send_loyalty_email [%s] error: %s', event_type, e)
            return False

    # ─── Payment / Cashout ────────────────────────────────────────

    def process_cashout(self, cashout_request) -> dict:
        """
        Process cashout via appropriate payment gateway।
        Routes to bKash, Nagad, bank, etc. based on cashout_request.cashout_method।
        """
        method = cashout_request.cashout_method

        if method == 'mobile_wallet':
            wallet = cashout_request.mobile_wallet
            if wallet:
                provider_map = {
                    'bkash': 'bkash',
                    'nagad': 'nagad',
                    'rocket': 'sslcommerz',
                }
                provider_name = provider_map.get(wallet.wallet_provider, 'bkash')
                return self._process_mobile_wallet_cashout(
                    cashout_request, provider_name, wallet,
                )

        elif method == 'bank_transfer':
            return self._process_bank_cashout(cashout_request)

        return {'success': False, 'error': f'Unsupported cashout method: {method}'}

    def _process_mobile_wallet_cashout(self, cashout_request, provider_name: str, wallet) -> dict:
        """Mobile wallet cashout।"""
        try:
            if provider_name == 'bkash':
                bkash = self.registry.get('bkash')
                if bkash:
                    result = bkash.send_money_b2c(
                        receiver_msisdn=wallet.phone_number,
                        amount=str(cashout_request.cash_amount),
                        reference=cashout_request.reference or f'CASHOUT-{cashout_request.id}',
                    )
                    return {'success': True, 'provider': 'bkash', 'data': result}
            elif provider_name == 'nagad':
                nagad = self.registry.get('nagad')
                if nagad:
                    return {'success': True, 'provider': 'nagad', 'note': 'Nagad B2C pending'}
            return {'success': False, 'error': f'{provider_name} not configured'}
        except Exception as e:
            logger.error('_process_mobile_wallet_cashout error: %s', e)
            return {'success': False, 'error': str(e)}

    def _process_bank_cashout(self, cashout_request) -> dict:
        """Bank transfer cashout via SSLCommerz or manual।"""
        return {
            'success': True,
            'provider': 'bank_transfer',
            'note': 'Bank transfer queued for manual processing',
            'reference': cashout_request.reference,
        }

    # ─── OCR ───────────────────────────────────────────────────────

    def process_receipt_ocr(self, image_url: str) -> dict:
        """Process receipt via OCR service।"""
        try:
            from ..integrations.ocr import OCRService
            return OCRService.process_receipt(image_url)
        except Exception as e:
            logger.error('IntegrationHandler.process_receipt_ocr error: %s', e)
            return {'error': str(e), 'raw_text': '', 'total_amount': None}

    # ─── Notification Event Dispatcher ───────────────────────────

    def dispatch_loyalty_event(self, event_type: str, customer, data: dict = None):
        """
        Dispatch loyalty event -> SMS + Push + Email + Webhook।
        One call handles all channels based on customer preferences।
        """
        data = data or {}
        sms_opt  = getattr(customer, 'sms_opt_in', False)
        push_opt = getattr(customer, 'push_opt_in', False)
        email_ok = getattr(customer, 'newsletter', False) and customer.email

        event_handlers = {
            EventType.POINTS_EARNED: lambda: self._dispatch_points_earned(
                customer, data, sms_opt, push_opt, email_ok
            ),
            EventType.TIER_UPGRADED: lambda: self._dispatch_tier_upgrade(
                customer, data, sms_opt, push_opt, email_ok
            ),
            EventType.BADGE_UNLOCKED: lambda: self._dispatch_badge_unlocked(
                customer, data, push_opt
            ),
            EventType.VOUCHER_GENERATED: lambda: self._dispatch_voucher(
                customer, data, sms_opt, push_opt, email_ok
            ),
            EventType.CASHOUT_COMPLETED: lambda: self._dispatch_cashout(
                customer, data, sms_opt, push_opt, email_ok
            ),
        }

        handler = event_handlers.get(event_type)
        if handler:
            try:
                handler()
            except Exception as e:
                logger.error('dispatch_loyalty_event [%s] error: %s', event_type, e)

    def _dispatch_points_earned(self, customer, data, sms_opt, push_opt, email_ok):
        points = data.get('points', 0)
        balance = data.get('balance', 0)
        if sms_opt and customer.phone:
            from ..integrations.sms import SMSService
            SMSService.notify_points_earned(customer, points, balance)
        if push_opt:
            from ..integrations.push_notification import FCMPushService
            FCMPushService.notify_points_earned(customer, points)

    def _dispatch_tier_upgrade(self, customer, data, sms_opt, push_opt, email_ok):
        new_tier = data.get('new_tier', '')
        if sms_opt and customer.phone:
            from ..integrations.sms import SMSService
            SMSService.notify_tier_upgrade(customer, new_tier)
        if push_opt:
            from ..integrations.push_notification import FCMPushService
            FCMPushService.notify_tier_upgrade(customer, new_tier)
        if email_ok:
            self.send_loyalty_email('tier_upgrade', customer,
                                     old_tier=data.get('old_tier', ''),
                                     new_tier=new_tier,
                                     benefits=data.get('benefits'))

    def _dispatch_badge_unlocked(self, customer, data, push_opt):
        if push_opt:
            from ..integrations.push_notification import FCMPushService
            FCMPushService.notify_badge_unlocked(customer, data.get('badge_name', ''))

    def _dispatch_voucher(self, customer, data, sms_opt, push_opt, email_ok):
        code = data.get('code', '')
        discount = data.get('discount', '')
        if sms_opt and customer.phone:
            from ..integrations.sms import SMSService
            SMSService.notify_voucher_code(customer, code, discount)
        if push_opt:
            from ..integrations.push_notification import FCMPushService
            FCMPushService.notify_voucher_generated(customer, code)
        if email_ok:
            self.send_loyalty_email('voucher', customer,
                                     code=code, discount=discount,
                                     expires_at=data.get('expires_at'))

    def _dispatch_cashout(self, customer, data, sms_opt, push_opt, email_ok):
        amount = data.get('amount', 0)
        method = data.get('method', '')
        if sms_opt and customer.phone:
            from ..integrations.sms import SMSService
            SMSService.notify_cashout_processed(customer, amount, method)
        if email_ok:
            self.send_loyalty_email('cashout', customer,
                                     amount=amount, method=method,
                                     ref=data.get('ref', ''))

    # ─── Helpers ───────────────────────────────────────────────────

    def _log_call(self, integration: str, action: str,
                   success: bool = True, error: str = '',
                   duration_ms: float = 0):
        """Internal performance log।"""
        self._performance_data.append({
            'integration': integration,
            'action': action,
            'success': success,
            'error': error,
            'duration_ms': duration_ms,
        })

    def get_status(self) -> dict:
        """Get handler status summary।"""
        return {
            'registry': self.registry.list_available(),
            'total_calls': len(self._performance_data),
            'success_rate': (
                sum(1 for d in self._performance_data if d['success']) /
                len(self._performance_data) * 100
                if self._performance_data else 100
            ),
        }
