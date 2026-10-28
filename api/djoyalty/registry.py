# api/djoyalty/registry.py
"""
Djoyalty Registry -- Central service and integration registry।

FIXED: setup_defaults() only registered 3 services (notification, catalog,
smartlink) and had NO integration wiring for email, sms, ocr,
push_notification, cpalead -- even though all 5 integration modules existed।
Now registers all integrations via IntegrationRegistry in setup_integrations()।
setup_integrations() is called from AppConfig.ready() so integrations
are available at Django startup।
"""
import logging
import threading
from typing import Any, Optional, Type

logger = logging.getLogger(__name__)
_lock  = threading.Lock()


class ServiceRegistry:
    """
    Central registry for all Djoyalty services।
    Singleton -- one registry for the whole app।

    Usage:
        from djoyalty.registry import service_registry
        earn_svc = service_registry.get('earn')
        earn_svc.award_points(customer, amount=100)
    """
    _instance: Optional['ServiceRegistry'] = None
    _services: dict = {}

    @classmethod
    def get_instance(cls) -> 'ServiceRegistry':
        if cls._instance is None:
            with _lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, name: str, service_class: Type, *args, **kwargs) -> 'ServiceRegistry':
        with _lock:
            self._services[name] = service_class(*args, **kwargs)
        return self

    def register_instance(self, name: str, instance: Any) -> 'ServiceRegistry':
        with _lock:
            self._services[name] = instance
        return self

    def get(self, name: str) -> Optional[Any]:
        return self._services.get(name)

    def get_or_raise(self, name: str) -> Any:
        svc = self._services.get(name)
        if svc is None:
            raise KeyError(
                f'Service "{name}" not registered in Djoyalty ServiceRegistry.'
            )
        return svc

    def list(self) -> list:
        return list(self._services.keys())

    def setup_defaults(self):
        """Register all default Djoyalty services।"""
        try:
            from .services.NotificationService import NotificationService
            from .services.RewardCatalogService import RewardCatalogService
            from .services.SmartLinkService import SmartLinkService

            self.register_instance('notification', NotificationService)
            self.register_instance('catalog',      RewardCatalogService)
            self.register_instance('smartlink',    SmartLinkService)
            logger.debug('ServiceRegistry: default services registered')
        except Exception as e:
            logger.debug('ServiceRegistry.setup_defaults error: %s', e)

    def setup_integrations(self):
        """
        Register all integration providers into IntegrationRegistry।

        FIXED: email, sms, ocr, push_notification, cpalead integrations
        were fully built but never wired into the registry।
        This method is called from AppConfig.ready() so every integration
        is available at startup for services to use via:
            from djoyalty.registry import integration_registry
            sms = integration_registry.get('sms')
            sms.send(phone, message)
        """
        try:
            from .integration_system.registry import IntegrationRegistry as IR
        except Exception as e:
            logger.debug('IntegrationRegistry not available: %s', e)
            return

        # ── Email ──────────────────────────────────────────────────────────────
        # FIXED: integrations/email.py existed but was never auto-wired।
        try:
            from .integrations.email import SendGridIntegration, MailgunIntegration
            import os
            if os.environ.get('SENDGRID_API_KEY'):
                IR.register('email', SendGridIntegration(
                    api_key=os.environ['SENDGRID_API_KEY']
                ))
                logger.info('registry: email -> SendGrid')
            elif os.environ.get('MAILGUN_API_KEY'):
                IR.register('email', MailgunIntegration(
                    api_key=os.environ['MAILGUN_API_KEY'],
                    domain=os.environ.get('MAILGUN_DOMAIN', ''),
                ))
                logger.info('registry: email -> Mailgun')
            else:
                from .integrations.email import DjangoSMTPEmail
                IR.register('email', DjangoSMTPEmail())
                logger.info('registry: email -> Django SMTP (fallback)')
        except Exception as e:
            logger.debug('registry: email integration failed: %s', e)

        # ── SMS ───────────────────────────────────────────────────────────────
        # FIXED: integrations/sms.py existed but was never auto-wired।
        try:
            from .integrations.sms import BulkSMSBD, SSLWirelessSMS, TwilioSMSIntegration
            import os
            if os.environ.get('TWILIO_ACCOUNT_SID'):
                IR.register('sms', TwilioSMSIntegration(
                    account_sid=os.environ['TWILIO_ACCOUNT_SID'],
                    auth_token=os.environ['TWILIO_AUTH_TOKEN'],
                    from_number=os.environ.get('TWILIO_FROM_NUMBER', ''),
                ))
                logger.info('registry: sms -> Twilio')
            elif os.environ.get('SSLWIRELESS_API_KEY'):
                IR.register('sms', SSLWirelessSMS(
                    api_key=os.environ['SSLWIRELESS_API_KEY'],
                    sid=os.environ.get('SSLWIRELESS_SID', ''),
                ))
                logger.info('registry: sms -> SSLWireless')
            else:
                IR.register('sms', BulkSMSBD(
                    api_key=os.environ.get('BULKSMSBD_API_KEY', ''),
                    sender_id=os.environ.get('BULKSMSBD_SENDER_ID', 'DJoyalty'),
                ))
                logger.info('registry: sms -> BulkSMSBD (BD default)')
        except Exception as e:
            logger.debug('registry: sms integration failed: %s', e)

        # ── OCR / Receipt Scanning ─────────────────────────────────────────────
        # FIXED: integrations/ocr.py existed but was never auto-wired।
        try:
            from .integrations.ocr import ReceiptParser
            import os
            parser = ReceiptParser(
                use_google_vision=bool(os.environ.get('GOOGLE_VISION_CREDENTIALS')),
                credentials_path=os.environ.get('GOOGLE_VISION_CREDENTIALS', ''),
            )
            IR.register('ocr', parser)
            logger.info('registry: ocr -> ReceiptParser (Google Vision=%s)',
                        bool(os.environ.get('GOOGLE_VISION_CREDENTIALS')))
        except Exception as e:
            logger.debug('registry: ocr integration failed: %s', e)

        # ── Push Notifications ─────────────────────────────────────────────────
        # FIXED: integrations/push_notification.py existed but was never wired।
        # NOTE: integrations/fcm.py is already wired -- this wires the
        # higher-level FCMPushService wrapper from push_notification.py।
        try:
            from .integrations.push_notification import FCMPushService
            IR.register('push', FCMPushService())
            logger.info('registry: push -> FCMPushService')
        except Exception as e:
            logger.debug('registry: push integration failed: %s', e)

        # ── CPAlead / OfferWall ────────────────────────────────────────────────
        # FIXED: integrations/cpalead.py existed but was never auto-wired।
        try:
            from .integrations.cpalead import CPALeadIntegration
            import os
            api_key = os.environ.get('CPALEAD_API_KEY', '')
            if api_key:
                IR.register('cpalead', CPALeadIntegration(api_key=api_key))
                logger.info('registry: cpalead -> CPALeadIntegration')
        except Exception as e:
            logger.debug('registry: cpalead integration failed: %s', e)

        logger.info(
            'registry: integrations wired -> %s', list(IR.list())
        )


class FeatureFlagRegistry:
    """
    Live feature flags for loyalty features।
    DB-backed via SystemConfig model।
    """
    DEFAULTS = {
        'spin_wheel':         True,
        'scratch_card':       True,
        'lottery':            True,
        'receipt_scan':       True,
        'eco_points':         True,
        'family_accounts':    True,
        'ai_personalization': True,
        'offerwall':          True,
        'digital_wallet':     True,
        'cashout':            True,
        'referral':           True,
        'leaderboard':        True,
        'charity_redemption': True,
        'coalition_earn':     True,
    }

    @classmethod
    def is_enabled(cls, feature: str, tenant=None) -> bool:
        """Check if a feature is enabled (DB or default)।"""
        try:
            from .models.audit import SystemConfig
            cfg = SystemConfig.objects.filter(
                key=f'feature.{feature}', tenant=tenant
            ).first()
            if cfg:
                return cfg.get_typed_value()
        except Exception:
            pass
        return cls.DEFAULTS.get(feature, True)

    @classmethod
    def enable(cls, feature: str, tenant=None):
        cls._set(feature, True, tenant)

    @classmethod
    def disable(cls, feature: str, tenant=None):
        cls._set(feature, False, tenant)

    @classmethod
    def _set(cls, feature: str, value: bool, tenant=None):
        try:
            from .models.audit import SystemConfig
            SystemConfig.objects.update_or_create(
                key=f'feature.{feature}',
                tenant=tenant,
                defaults={'value': str(value), 'value_type': 'boolean'},
            )
        except Exception as e:
            logger.error('FeatureFlagRegistry._set error: %s', e)

    @classmethod
    def all_flags(cls, tenant=None) -> dict:
        flags = dict(cls.DEFAULTS)
        try:
            from .models.audit import SystemConfig
            db_flags = SystemConfig.objects.filter(
                key__startswith='feature.', tenant=tenant,
            )
            for cfg in db_flags:
                feature = cfg.key.replace('feature.', '')
                flags[feature] = cfg.get_typed_value()
        except Exception:
            pass
        return flags


# ─── Module-level singletons ──────────────────────────────────────────────────
service_registry = ServiceRegistry.get_instance()
features         = FeatureFlagRegistry()
