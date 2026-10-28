# publisher_tools/app_management/app_sdk.py
"""
App SDK Configuration — publisher app-এর SDK integration settings।

Import করা হয়:
    views_app_management_full.py → sdk_config() action
"""
import logging
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel

logger = logging.getLogger(__name__)


class AppSDKConfig(TimeStampedModel):
    """SDK integration settings — প্রতিটি app-এর জন্য OneToOne।"""

    PLATFORM_ANDROID      = 'android'
    PLATFORM_IOS          = 'ios'
    PLATFORM_WEB          = 'web'
    PLATFORM_UNITY        = 'unity'
    PLATFORM_FLUTTER      = 'flutter'
    PLATFORM_REACT_NATIVE = 'react_native'

    PLATFORM_CHOICES = [
        (PLATFORM_ANDROID,      _('Android')),
        (PLATFORM_IOS,          _('iOS')),
        (PLATFORM_WEB,          _('Web')),
        (PLATFORM_UNITY,        _('Unity')),
        (PLATFORM_FLUTTER,      _('Flutter')),
        (PLATFORM_REACT_NATIVE, _('React Native')),
    ]

    STATUS_ACTIVE   = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_PENDING  = 'pending'
    STATUS_ERROR    = 'error'

    STATUS_CHOICES = [
        (STATUS_ACTIVE,   _('Active')),
        (STATUS_INACTIVE, _('Inactive')),
        (STATUS_PENDING,  _('Pending Integration')),
        (STATUS_ERROR,    _('Integration Error')),
    ]

    # ── Fields ────────────────────────────────────────────────────────────────
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='publisher_tools_appsdk_tenant', db_index=True,
    )
    app = models.OneToOneField(
        'publisher_tools.App', on_delete=models.CASCADE,
        related_name='sdk_config', verbose_name=_('App'),
    )
    sdk_version = models.CharField(
        max_length=20, blank=True, default='', verbose_name=_('SDK Version'),
    )
    sdk_platform = models.CharField(
        max_length=20, choices=PLATFORM_CHOICES,
        default=PLATFORM_ANDROID, db_index=True, verbose_name=_('SDK Platform'),
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default=STATUS_PENDING, db_index=True, verbose_name=_('Status'),
    )
    is_sdk_integrated = models.BooleanField(
        default=False, db_index=True, verbose_name=_('Is SDK Integrated'),
    )
    sdk_key = models.CharField(
        max_length=128, blank=True, verbose_name=_('SDK Key'),
        help_text=_('Public SDK identifier key sent to app'),
    )
    sdk_secret = models.CharField(
        max_length=256, blank=True, verbose_name=_('SDK Secret'),
        help_text=_('Secret key used for SDK authentication (never expose to client)'),
    )
    last_sdk_ping = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name=_('Last SDK Ping'),
    )
    sdk_config_json = models.JSONField(
        default=dict, blank=True, verbose_name=_('SDK Config JSON'),
        help_text=_('Additional SDK configuration parameters'),
    )
    initialization_options = models.JSONField(
        default=dict, blank=True, verbose_name=_('Initialization Options'),
    )
    allowed_ad_formats = models.JSONField(
        default=list, blank=True, verbose_name=_('Allowed Ad Formats'),
    )
    mediation_config = models.JSONField(
        default=dict, blank=True, verbose_name=_('Mediation Config'),
    )
    test_mode = models.BooleanField(
        default=False, verbose_name=_('Test Mode'),
        help_text=_('Enable test mode — shows test ads only'),
    )
    auto_init = models.BooleanField(
        default=True, verbose_name=_('Auto Initialize'),
        help_text=_('Automatically initialize SDK on app start'),
    )
    consent_required = models.BooleanField(
        default=True, verbose_name=_('Consent Required'),
        help_text=_('Require user consent before showing ads'),
    )
    coppa_compliant = models.BooleanField(
        default=False, verbose_name=_('COPPA Compliant'),
    )
    gdpr_compliant = models.BooleanField(
        default=True, verbose_name=_('GDPR Compliant'),
    )
    integration_notes = models.TextField(blank=True, verbose_name=_('Integration Notes'))
    error_message = models.TextField(
        blank=True, verbose_name=_('Error Message'),
        help_text=_('Last integration error, cleared on success'),
    )

    class Meta:
        app_label  = 'publisher_tools'
        db_table   = 'publisher_tools_app_sdk_configs'
        verbose_name        = _('App SDK Config')
        verbose_name_plural = _('App SDK Configs')
        indexes = [
            models.Index(
                fields=['sdk_platform', 'is_sdk_integrated'],
                name='sdk_platform_integrated_1604',
            ),
            models.Index(
                fields=['status', 'last_sdk_ping'],
                name='idx_sdk_status_ping_1605',
            ),
        ]

    def __str__(self):
        return (
            f"SDKConfig(app={self.app_id}, "
            f"platform={self.sdk_platform}, "
            f"v{self.sdk_version or '?'}, "
            f"status={self.status})"
        )

    # ── Instance helpers ──────────────────────────────────────────────────────

    def mark_integrated(self, version: str = ''):
        """SDK successfully integrated হলে call করো।"""
        self.is_sdk_integrated = True
        self.status            = self.STATUS_ACTIVE
        self.last_sdk_ping     = timezone.now()
        self.error_message     = ''
        if version:
            self.sdk_version = version
        self.save(update_fields=[
            'is_sdk_integrated', 'status', 'last_sdk_ping',
            'error_message', 'sdk_version', 'updated_at',
        ])
        logger.info('AppSDKConfig: app=%s SDK integrated v%s', self.app_id, self.sdk_version)

    def record_ping(self):
        """SDK heartbeat ping এলে call করো।"""
        self.last_sdk_ping = timezone.now()
        if self.status == self.STATUS_ERROR:
            self.status = self.STATUS_ACTIVE
        self.save(update_fields=['last_sdk_ping', 'status', 'updated_at'])

    def mark_error(self, error_msg: str = ''):
        """Integration error হলে call করো।"""
        self.status        = self.STATUS_ERROR
        self.error_message = error_msg
        self.save(update_fields=['status', 'error_message', 'updated_at'])
        logger.warning('AppSDKConfig: app=%s integration error: %s', self.app_id, error_msg)

    def deactivate(self):
        """SDK integration বন্ধ করো।"""
        self.status            = self.STATUS_INACTIVE
        self.is_sdk_integrated = False
        self.save(update_fields=['status', 'is_sdk_integrated', 'updated_at'])

    @property
    def is_active(self) -> bool:
        return self.status == self.STATUS_ACTIVE and self.is_sdk_integrated

    def get_config_for_sdk(self) -> dict:
        """
        SDK-কে পাঠানোর জন্য clean config dict।
        views_app_management_full.py → sdk_config() এ return করা হয়।
        """
        return {
            'sdk_key':          self.sdk_key,
            'platform':         self.sdk_platform,
            'version':          self.sdk_version,
            'test_mode':        self.test_mode,
            'auto_init':        self.auto_init,
            'consent_required': self.consent_required,
            'coppa_compliant':  self.coppa_compliant,
            'gdpr_compliant':   self.gdpr_compliant,
            'allowed_formats':  self.allowed_ad_formats,
            'mediation':        self.mediation_config,
            **self.initialization_options,
        }
