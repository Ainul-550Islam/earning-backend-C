# api/payment_gateways/registry.py
# Full service and handler registry for payment_gateways
# "Do not summarize or skip any logic. Provide the full code."

import logging
from typing import Callable, Dict, List, Any, Optional, Type
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ── Payment Gateway Service Registry ──────────────────────────────────────────
class GatewayServiceRegistry:
    """
    Central registry for all payment gateway service classes.

    Allows dynamic gateway registration — add new gateways without
    modifying PaymentFactory.

    Usage:
        registry = GatewayServiceRegistry.get_instance()
        registry.register('bkash', BkashService)
        service = registry.get('bkash')()
        result  = service.process_deposit(user, amount)
    """
    _instance: Optional['GatewayServiceRegistry'] = None
    _services: Dict[str, Type] = {}
    _metadata: Dict[str, dict] = {}

    @classmethod
    def get_instance(cls) -> 'GatewayServiceRegistry':
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._auto_register()
        return cls._instance

    def register(self, gateway_name: str, service_class: Type,
                  metadata: dict = None):
        """
        Register a gateway service class.

        Args:
            gateway_name:  Gateway identifier ('bkash', 'stripe', etc.)
            service_class: Service class with process_deposit/process_withdrawal methods
            metadata:      Optional metadata (display_name, region, currencies, etc.)
        """
        self._services[gateway_name.lower()] = service_class
        self._metadata[gateway_name.lower()]  = metadata or {
            'name':         gateway_name,
            'display_name': gateway_name.upper(),
            'region':       'BD' if gateway_name in ('bkash','nagad','sslcommerz','amarpay','upay','shurjopay') else 'GLOBAL',
        }
        logger.debug(f'Gateway registered: {gateway_name} → {service_class.__name__}')

    def get(self, gateway_name: str) -> Optional[Type]:
        """Get service class for a gateway. Returns None if not registered."""
        return self._services.get(gateway_name.lower())

    def get_instance(self, gateway_name: str):
        """Get instantiated service object for a gateway."""
        svc_class = self.get(gateway_name)
        if not svc_class:
            raise ValueError(
                f'No service registered for gateway: {gateway_name}. '
                f'Registered: {list(self._services.keys())}'
            )
        return svc_class()

    def list_gateways(self) -> List[str]:
        """List all registered gateway names."""
        return list(self._services.keys())

    def get_metadata(self, gateway_name: str) -> dict:
        """Get metadata for a gateway."""
        return self._metadata.get(gateway_name.lower(), {})

    def get_all_metadata(self) -> dict:
        """Get metadata for all registered gateways."""
        return dict(self._metadata)

    def is_registered(self, gateway_name: str) -> bool:
        """Check if a gateway is registered."""
        return gateway_name.lower() in self._services

    def unregister(self, gateway_name: str):
        """Remove a gateway from the registry."""
        self._services.pop(gateway_name.lower(), None)
        self._metadata.pop(gateway_name.lower(), None)

    def _auto_register(self):
        """Auto-register all built-in gateways on first access."""
        gateways = [
            ('bkash',      'BkashService',      {'region': 'BD',     'currency': 'BDT', 'display': 'bKash',        'color': '#E2136E'}),
            ('nagad',      'NagadService',       {'region': 'BD',     'currency': 'BDT', 'display': 'Nagad',        'color': '#F7941D'}),
            ('sslcommerz', 'SSLCommerzService',  {'region': 'BD',     'currency': 'BDT', 'display': 'SSLCommerz',   'color': '#0072BC'}),
            ('amarpay',    'AmarPayService',     {'region': 'BD',     'currency': 'BDT', 'display': 'AmarPay',      'color': '#00AEEF'}),
            ('upay',       'UpayService',        {'region': 'BD',     'currency': 'BDT', 'display': 'Upay',         'color': '#005BAA'}),
            ('shurjopay',  'ShurjoPayService',   {'region': 'BD',     'currency': 'BDT', 'display': 'ShurjoPay',    'color': '#6A0DAD'}),
            ('stripe',     'StripeService',      {'region': 'GLOBAL', 'currency': 'USD', 'display': 'Stripe',       'color': '#635BFF'}),
            ('paypal',     'PayPalService',      {'region': 'GLOBAL', 'currency': 'USD', 'display': 'PayPal',       'color': '#003087'}),
            ('payoneer',   'PayoneerService',    {'region': 'GLOBAL', 'currency': 'USD', 'display': 'Payoneer',     'color': '#FF4800'}),
            ('wire',       'WireTransferService',{'region': 'GLOBAL', 'currency': 'USD', 'display': 'Wire Transfer','color': '#2C3E50'}),
            ('ach',        'ACHService',         {'region': 'US',     'currency': 'USD', 'display': 'ACH Bank',     'color': '#0A6640'}),
            ('crypto',     'CryptoService',      {'region': 'GLOBAL', 'currency': 'USDT','display': 'Crypto',       'color': '#F7931A'}),
        ]

        for gateway_name, class_name, meta in gateways:
            try:
                module = __import__(
                    f'api.payment_gateways.services.{class_name}',
                    fromlist=[class_name]
                )
                svc_class = getattr(module, class_name)
                self.register(gateway_name, svc_class, meta)
            except (ImportError, AttributeError) as e:
                logger.debug(f'Could not auto-register {gateway_name}: {e}')


# ── Integration Handler Registry ───────────────────────────────────────────────
# Re-export from integration_system for convenience
from api.payment_gateways.integration_system.integ_registry import (
    IntegrationRegistry, registry as integration_registry
)


# ── Notification Template Registry ─────────────────────────────────────────────
class NotificationTemplateRegistry:
    """
    Registry of email/SMS notification templates for payment events.
    Allows customization of notification content per event type.
    """
    _templates: Dict[str, dict] = {}

    @classmethod
    def get_instance(cls) -> 'NotificationTemplateRegistry':
        if not hasattr(cls, '_instance_obj'):
            cls._instance_obj = cls()
            cls._instance_obj._load_defaults()
        return cls._instance_obj

    def register(self, template_name: str, subject: str, body_template: str,
                  channels: List[str] = None):
        self._templates[template_name] = {
            'subject':  subject,
            'body':     body_template,
            'channels': channels or ['email'],
        }

    def get(self, template_name: str) -> Optional[dict]:
        return self._templates.get(template_name)

    def render(self, template_name: str, context: dict) -> Optional[dict]:
        tmpl = self.get(template_name)
        if not tmpl:
            return None
        try:
            return {
                'subject':  tmpl['subject'].format(**context),
                'body':     tmpl['body'].format(**context),
                'channels': tmpl['channels'],
            }
        except KeyError as e:
            logger.warning(f'Template {template_name} missing context key: {e}')
            return None

    def _load_defaults(self):
        self.register(
            'payment_deposit_completed',
            subject='✅ Deposit Confirmed — {currency} {amount}',
            body=(
                'Hi {user_name},\n\n'
                'Your deposit of {currency} {amount} has been successfully credited to your account.\n\n'
                'Gateway: {gateway}\n'
                'Reference: {reference}\n'
                'Date: {date}\n\n'
                'Thank you for using our service!\n'
                'support@yourdomain.com'
            ),
            channels=['email', 'in_app', 'push'],
        )
        self.register(
            'payment_withdrawal_processed',
            subject='💸 Withdrawal Processed — {currency} {amount}',
            body=(
                'Hi {user_name},\n\n'
                'Your withdrawal of {currency} {amount} has been processed.\n\n'
                'Method: {method}\n'
                'Account: {account}\n'
                'Reference: {reference}\n\n'
                'Funds should arrive within 1-3 business days.\n'
            ),
            channels=['email', 'in_app'],
        )
        self.register(
            'payment_conversion_earned',
            subject='🎉 New Earning — {currency} {payout}',
            body=(
                'Congratulations!\n\n'
                'You earned {currency} {payout} from: {offer}\n'
                'Conversion ID: {conversion_id}\n\n'
                'Keep it up! Check your dashboard for more offers.\n'
            ),
            channels=['in_app', 'push'],
        )
        self.register(
            'payment_deposit_failed',
            subject='❌ Deposit Failed',
            body=(
                'Hi {user_name},\n\n'
                'Your deposit of {currency} {amount} via {gateway} could not be completed.\n\n'
                'Reason: {error}\n\n'
                'Please try again or contact support if the problem persists.\n'
            ),
            channels=['email', 'in_app'],
        )


# ── Webhook Handler Registry ────────────────────────────────────────────────────
class WebhookHandlerRegistry:
    """
    Registry of webhook handlers per gateway.
    Maps gateway name → handler function.
    """
    _handlers: Dict[str, Callable] = {}

    @classmethod
    def get_instance(cls) -> 'WebhookHandlerRegistry':
        if not hasattr(cls, '_instance_obj'):
            cls._instance_obj = cls()
        return cls._instance_obj

    def register(self, gateway: str, handler: Callable):
        """Register a webhook handler for a gateway."""
        self._handlers[gateway.lower()] = handler
        logger.debug(f'Webhook handler registered: {gateway}')

    def get(self, gateway: str) -> Optional[Callable]:
        """Get webhook handler for a gateway."""
        return self._handlers.get(gateway.lower())

    def dispatch(self, gateway: str, payload: dict, headers: dict) -> dict:
        """
        Dispatch webhook to registered handler.
        Falls back to generic handler if no specific handler registered.
        """
        handler = self.get(gateway)
        if handler:
            try:
                return handler(payload, headers)
            except Exception as e:
                logger.error(f'Webhook handler for {gateway} failed: {e}')
                return {'success': False, 'error': str(e)}

        # Generic fallback handler
        logger.warning(f'No specific webhook handler for {gateway}, using generic')
        return self._generic_handler(gateway, payload)

    def _generic_handler(self, gateway: str, payload: dict) -> dict:
        """Generic webhook handler — processes via DepositService."""
        from api.payment_gateways.services.DepositService import DepositService
        ref_id = (payload.get('reference_id') or payload.get('tran_id') or
                  payload.get('orderId') or payload.get('paymentID') or '')
        gw_ref = (payload.get('trxID') or payload.get('id') or ref_id)
        if ref_id:
            try:
                result = DepositService().verify_and_complete(ref_id, gw_ref, payload)
                return {'success': True, 'result': result}
            except Exception as e:
                return {'success': False, 'error': str(e)}
        return {'success': False, 'error': 'reference_id not found in payload'}

    def list_handlers(self) -> List[str]:
        return list(self._handlers.keys())


# ── Global registry instances ──────────────────────────────────────────────────
gateway_registry      = GatewayServiceRegistry.get_instance()
notification_registry = NotificationTemplateRegistry.get_instance()
webhook_registry      = WebhookHandlerRegistry.get_instance()
registry              = integration_registry  # Alias

__all__ = [
    'GatewayServiceRegistry', 'IntegrationRegistry',
    'NotificationTemplateRegistry', 'WebhookHandlerRegistry',
    'gateway_registry', 'notification_registry', 'webhook_registry',
    'registry', 'integration_registry',
]
