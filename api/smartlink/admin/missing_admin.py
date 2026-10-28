"""
SmartLink — Missing Admin Registrations
=========================================
12 models had no admin class at all. Added here:

  PayoutBatch, PayoutRecord, PublisherAPIKey, PublisherProfile,
  PublisherTier, PublisherWallet, RedirectRule, SmartLinkDomain,
  SmartLinkSchedule, SmartLinkTemplate, SubPublisher, WebhookEndpoint
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .base_admin import ReadOnlyAdmin, AuditAdmin, SmartLinkAdminMixin


# ─────────────────────────────────────────────────────────────────────────────
# Defensive registration helper
# ─────────────────────────────────────────────────────────────────────────────
# Using a decorator factory instead of @admin.register() directly means:
#   1. If a model is ALREADY registered (e.g. by another admin file, or by
#      a partial re-import after an earlier ImportError in THIS module),
#      we skip registration instead of raising AlreadyRegistered and
#      crashing the entire admin app load.
#   2. Re-importing this module (which can happen if an earlier import
#      attempt failed partway through) is now idempotent.

import logging
_logger = logging.getLogger('smartlink.admin.missing_admin')


def register_if_missing(model):
    """Decorator: @register_if_missing(model), but skips if already registered."""
    def _decorator(admin_cls):
        if model in admin.site._registry:
            _logger.debug(
                f"{model.__name__} already registered "
                f"(by {admin.site._registry[model].__class__.__name__}); "
                f"skipping {admin_cls.__name__}"
            )
            return admin_cls
        admin.site.register(model, admin_cls)
        return admin_cls
    return _decorator



# ── Billing ───────────────────────────────────────────────────────────────────

from api.smartlink.models.billing import (
    PayoutBatch, PayoutRecord, PublisherProfile, PublisherWallet,
)


@register_if_missing(PayoutBatch)
class PayoutBatchAdmin(admin.ModelAdmin):
    list_display  = ('label', 'status', 'period_from', 'period_to',
                     'total_records', 'total_net', 'created_by', 'created_at')
    list_filter   = ('status',)
    search_fields = ('label', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at', 'total_net', 'total_records')
    ordering      = ('-created_at',)

    def has_add_permission(self, request):
        return False  # Batches are created programmatically via BillingService

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@register_if_missing(PayoutRecord)
class PayoutRecordAdmin(admin.ModelAdmin):
    list_display  = ('reference_id_short', 'publisher', 'status', 'payment_method',
                     'net_amount', 'currency', 'period_from', 'period_to', 'paid_at')
    list_filter   = ('status', 'payment_method', 'currency')
    search_fields = ('publisher__username', 'publisher__email',
                     'reference_id', 'transaction_ref', 'payment_address')
    readonly_fields = ('reference_id', 'gross_amount', 'net_amount', 'scrub_amount',
                       'total_clicks', 'total_conversions', 'paid_at', 'created_at')
    ordering      = ('-created_at',)
    date_hierarchy = 'period_from'

    @admin.display(description='Ref ID')
    def reference_id_short(self, obj):
        return str(obj.reference_id)[:8].upper()


@register_if_missing(PublisherProfile)
class PublisherProfileAdmin(admin.ModelAdmin):
    list_display  = ('publisher', 'company_name', 'country_code', 'payment_method',
                     'payout_currency', 'is_verified', 'gdpr_consent', 'created_at')
    list_filter   = ('is_verified', 'payment_method', 'payout_currency', 'country_code')
    search_fields = ('publisher__username', 'publisher__email', 'company_name', 'tax_id')
    readonly_fields = ('gdpr_consent_at', 'data_anonymized', 'created_at', 'updated_at')
    ordering      = ('-created_at',)
    fieldsets = (
        (_('Publisher'), {'fields': ('publisher', 'is_verified', 'notes')}),
        (_('Company'), {'fields': ('company_name', 'website', 'country_code',
                                   'timezone', 'phone', 'is_company', 'tax_id', 'w9_submitted')}),
        (_('Payment'), {'fields': ('payment_method', 'payment_email', 'bank_name',
                                   'bank_account_number', 'bank_routing_number',
                                   'payout_currency', 'min_payout',
                                   'crypto_address', 'crypto_currency')}),
        (_('Attribution'), {'fields': ('attribution_window_days',)}),
        (_('Traffic'), {'fields': ('traffic_sources', 'vertical')}),
        (_('GDPR'), {'fields': ('gdpr_consent', 'gdpr_consent_at',
                                'marketing_opt_in', 'data_anonymized')}),
        (_('Preferences'), {'fields': ('notification_preferences',)}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )


@register_if_missing(PublisherWallet)
class PublisherWalletAdmin(ReadOnlyAdmin):
    list_display  = ('publisher', 'balance', 'currency', 'lifetime_earnings',
                     'total_paid_out', 'updated_at')
    list_filter   = ('currency',)
    search_fields = ('publisher__username', 'publisher__email')
    ordering      = ('-balance',)
    readonly_fields = ('publisher', 'balance', 'currency', 'lifetime_earnings',
                       'total_paid_out', 'created_at', 'updated_at')


# ── Publisher ─────────────────────────────────────────────────────────────────

from api.smartlink.models.publisher import SubPublisher
try:
    from api.smartlink.models.extensions.smartlink_schedule import PublisherTier
    _has_tier = True
except ImportError:
    _has_tier = False

try:
    from api.smartlink.models.billing import PublisherAPIKey
    _has_apikey = True
except ImportError:
    _has_apikey = False


if _has_tier:
    @register_if_missing(PublisherTier)
    class PublisherTierAdmin(admin.ModelAdmin):
        list_display  = ('publisher', 'tier', 'revenue_share_percent',
                         'min_monthly_clicks', 'auto_promote', 'updated_at')
        list_filter   = ('tier', 'auto_promote')
        search_fields = ('publisher__username', 'publisher__email')
        readonly_fields = ('publisher', 'created_at', 'updated_at')
        ordering      = ('tier',)


@register_if_missing(SubPublisher)
class SubPublisherAdmin(admin.ModelAdmin):
    list_display  = ('sub_publisher', 'referred_by', 'commission_rate',
                     'total_earned', 'is_active', 'created_at')
    list_filter   = ('is_active',)
    search_fields = ('sub_publisher__username', 'referred_by__username')
    readonly_fields = ('total_earned', 'created_at', 'updated_at')
    ordering      = ('-created_at',)


if _has_apikey:
    @register_if_missing(PublisherAPIKey)
    class PublisherAPIKeyAdmin(AuditAdmin):
        list_display  = ('publisher', 'name', 'key_prefix', 'is_active',
                         'expires_at', 'last_used_at')
        list_filter   = ('is_active',)
        search_fields = ('publisher__username', 'name', 'key_prefix')
        readonly_fields = ('key_prefix', 'created_at', 'last_used_at')


# ── SmartLink models ──────────────────────────────────────────────────────────

from api.smartlink.models import SmartLink
try:
    from api.smartlink.models.smartlink import SmartLinkDomain, SmartLinkSchedule, SmartLinkTemplate
    _has_sl_extras = True
except ImportError:
    _has_sl_extras = False


if _has_sl_extras:
    @register_if_missing(SmartLinkDomain)
    class SmartLinkDomainAdmin(SmartLinkAdminMixin, admin.ModelAdmin):
        list_display  = ('domain', 'smartlink', 'is_primary', 'is_verified',
                         'ssl_enabled', 'created_at')
        list_filter   = ('is_primary', 'is_verified', 'ssl_enabled')
        search_fields = ('domain', 'smartlink__slug')
        readonly_fields = ('created_at', 'updated_at')

    @register_if_missing(SmartLinkSchedule)
    class SmartLinkScheduleAdmin(SmartLinkAdminMixin, admin.ModelAdmin):
        list_display  = ('smartlink', 'is_active', 'days_of_week', 'hour_start',
                         'hour_end', 'timezone', 'created_at')
        list_filter   = ('is_active', 'timezone')
        search_fields = ('smartlink__slug',)
        readonly_fields = ('created_at', 'updated_at')

    @register_if_missing(SmartLinkTemplate)
    class SmartLinkTemplateAdmin(admin.ModelAdmin):
        list_display  = ('name', 'category', 'created_by', 'is_public', 'created_at')
        list_filter   = ('is_public', 'category')
        search_fields = ('name', 'created_by__username')
        readonly_fields = ('created_at', 'updated_at')


# ── Redirect ──────────────────────────────────────────────────────────────────

try:
    from api.smartlink.models.redirect import RedirectRule
    _has_redirect_rule = True
except ImportError:
    _has_redirect_rule = False

if _has_redirect_rule:
    @register_if_missing(RedirectRule)
    class RedirectRuleAdmin(SmartLinkAdminMixin, admin.ModelAdmin):
        list_display  = ('smartlink', 'rule_type', 'priority', 'is_active',
                         'match_value', 'destination_url', 'created_at')
        list_filter   = ('rule_type', 'is_active')
        search_fields = ('smartlink__slug', 'match_value', 'destination_url')
        readonly_fields = ('created_at', 'updated_at')
        ordering      = ('smartlink', 'priority')


# ── Webhooks ──────────────────────────────────────────────────────────────────

try:
    from api.smartlink.models.webhook import WebhookEndpoint
    _has_webhook = True
except ImportError:
    _has_webhook = False

if _has_webhook:
    @register_if_missing(WebhookEndpoint)
    class WebhookEndpointAdmin(admin.ModelAdmin):
        list_display  = ('publisher', 'url_preview', 'is_active', 'event_types',
                         'failure_count', 'last_triggered_at', 'created_at')
        list_filter   = ('is_active',)
        search_fields = ('publisher__username', 'url')
        readonly_fields = ('secret_key', 'failure_count', 'last_triggered_at',
                           'created_at', 'updated_at')

        @admin.display(description='URL')
        def url_preview(self, obj):
            url = obj.url or ''
            return url[:60] + ('…' if len(url) > 60 else '')
