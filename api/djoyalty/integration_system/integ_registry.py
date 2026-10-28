# api/djoyalty/integration_system/integ_registry.py
"""
Integration Registry -- Plug & Play integration management।
Register, discover, enable/disable integrations dynamically।
Pattern: Service Locator + Registry।
"""
import logging
import threading
from typing import Any, Dict, Optional, Type
from .integ_constants import IntegrationType, IntegrationStatus
from .integ_exceptions import IntegrationNotConfiguredError, IntegrationDisabledError

logger = logging.getLogger(__name__)

_registry_lock = threading.Lock()


class IntegrationMeta:
    """Metadata for a registered integration।"""
    def __init__(self, name: str, cls: type, config: dict,
                 status: IntegrationStatus = IntegrationStatus.UNKNOWN,
                 description: str = ''):
        self.name = name
        self.cls = cls
        self.config = config
        self.status = status
        self.description = description
        self._instance: Optional[Any] = None

    def get_instance(self):
        """Get or create singleton instance।"""
        if self._instance is None:
            self._instance = self.cls()
        return self._instance

    def is_healthy(self) -> bool:
        return self.status in (IntegrationStatus.HEALTHY, IntegrationStatus.UNKNOWN)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'configured': self.cls.is_configured() if hasattr(self.cls, 'is_configured') else True,
        }


class IntegrationRegistry:
    """
    Central registry for all Djoyalty integrations।
    Singleton -- one registry for entire app।

    Usage:
        registry = IntegrationRegistry.get_instance()
        bkash = registry.get('bkash')
        bkash.create_payment(...)

        # Auto-register all configured integrations
        registry.auto_register()
    """

    _instance: Optional['IntegrationRegistry'] = None

    def __init__(self):
        self._integrations: Dict[str, IntegrationMeta] = {}

    @classmethod
    def get_instance(cls) -> 'IntegrationRegistry':
        """Get or create singleton registry।"""
        if cls._instance is None:
            with _registry_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ─── Registration ──────────────────────────────────────────────

    def register(self, name: str, cls: type, description: str = '') -> 'IntegrationRegistry':
        """Register an integration class।"""
        from django.conf import settings
        config = getattr(settings, f'DJOYALTY_{name.upper()}', {})
        meta = IntegrationMeta(
            name=name,
            cls=cls,
            config=config,
            description=description,
        )
        with _registry_lock:
            self._integrations[name] = meta
        logger.debug('IntegrationRegistry: registered %s', name)
        return self

    def unregister(self, name: str):
        """Unregister an integration।"""
        with _registry_lock:
            self._integrations.pop(name, None)

    def auto_register(self):
        """Auto-register all built-in integrations।"""
        from ..integrations.bkash import BkashIntegration
        from ..integrations.nagad import NagadIntegration
        from ..integrations.sslcommerz import SSLCommerzIntegration
        from ..integrations.sms import BulkSMSBD, SSLWirelessSMS, TwilioSMSIntegration
        from ..integrations.email import DjangoSMTPEmail, SendGridIntegration, MailgunIntegration
        from ..integrations.push_notification import FCMPushService
        from ..integrations.ocr import GoogleVisionOCR
        from ..integrations.cpalead import CPALeadIntegration

        integrations = [
            ('bkash',       BkashIntegration,       'bKash Payment Gateway'),
            ('nagad',       NagadIntegration,        'Nagad Mobile Wallet'),
            ('sslcommerz',  SSLCommerzIntegration,   'SSLCommerz Payment Gateway'),
            ('bulksmsbd',   BulkSMSBD,               'BulkSMSBD SMS Gateway'),
            ('sslwireless', SSLWirelessSMS,           'SSL Wireless SMS'),
            ('twilio',      TwilioSMSIntegration,     'Twilio SMS'),
            ('smtp',        DjangoSMTPEmail,          'Django SMTP Email'),
            ('sendgrid',    SendGridIntegration,      'SendGrid Email'),
            ('mailgun',     MailgunIntegration,       'Mailgun Email'),
            ('fcm',         FCMPushService,           'Firebase FCM Push'),
            ('google_vision', GoogleVisionOCR,        'Google Vision OCR'),
            ('cpalead',     CPALeadIntegration,       'CPAlead Offerwall'),
        ]

        for name, cls, desc in integrations:
            self.register(name, cls, description=desc)

        logger.info('IntegrationRegistry: auto-registered %d integrations', len(integrations))
        return self

    # ─── Access ────────────────────────────────────────────────────

    def get(self, name: str, raise_if_not_configured: bool = False) -> Optional[Any]:
        """Get integration instance by name।"""
        meta = self._integrations.get(name)
        if not meta:
            if raise_if_not_configured:
                raise IntegrationNotConfiguredError(name)
            logger.warning('IntegrationRegistry: %s not registered', name)
            return None

        if hasattr(meta.cls, 'is_configured') and not meta.cls.is_configured():
            if raise_if_not_configured:
                raise IntegrationNotConfiguredError(name)
            return None

        return meta.get_instance()

    def get_or_raise(self, name: str) -> Any:
        """Get integration -- raise if not configured।"""
        return self.get(name, raise_if_not_configured=True)

    def is_available(self, name: str) -> bool:
        """Check if integration is registered and configured।"""
        meta = self._integrations.get(name)
        if not meta:
            return False
        if hasattr(meta.cls, 'is_configured'):
            return meta.cls.is_configured()
        return True

    def list_all(self) -> Dict[str, dict]:
        """List all registered integrations with status।"""
        return {
            name: meta.to_dict()
            for name, meta in self._integrations.items()
        }

    def list_available(self) -> Dict[str, dict]:
        """List only configured/available integrations।"""
        return {
            name: info
            for name, info in self.list_all().items()
            if info.get('configured')
        }

    def update_status(self, name: str, status: IntegrationStatus):
        """Update integration health status।"""
        if name in self._integrations:
            self._integrations[name].status = status
            logger.debug('IntegrationRegistry: %s status -> %s', name, status)

    def get_sms_provider(self) -> Optional[Any]:
        """Get active SMS provider based on settings।"""
        from django.conf import settings
        provider = getattr(settings, 'DJOYALTY_SMS_PROVIDER', 'bulksmsbd')
        return self.get(provider)

    def get_email_provider(self) -> Optional[Any]:
        """Get active email provider based on settings।"""
        from django.conf import settings
        provider = getattr(settings, 'DJOYALTY_EMAIL_PROVIDER', 'smtp')
        return self.get(provider)

    def get_payment_provider(self, method: str) -> Optional[Any]:
        """Get payment provider by method name।"""
        method_map = {
            'bkash': 'bkash',
            'nagad': 'nagad',
            'rocket': 'rocket',
            'sslcommerz': 'sslcommerz',
            'bank_transfer': 'sslcommerz',
            'mobile_wallet': 'bkash',
        }
        return self.get(method_map.get(method, method))

    def __repr__(self):
        available = sum(1 for m in self._integrations.values()
                        if hasattr(m.cls, 'is_configured') and m.cls.is_configured())
        return f'IntegrationRegistry({len(self._integrations)} registered, {available} configured)'


# Module-level convenience
registry = IntegrationRegistry.get_instance()
