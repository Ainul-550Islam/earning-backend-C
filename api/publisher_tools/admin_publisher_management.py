# publisher_tools/admin_publisher_management.py
"""
Admin registrations for all publisher_management/ subfolder models।

admin.py-এ import করো:
    from .admin_publisher_management import *   # noqa

অথবা admin.py-এর শেষে যোগ করো:
    from .admin_publisher_management import (
        PublisherBankAccountAdmin,
        PublisherKYCAdmin,
        KYCDocumentAdmin,
        PayoutRequestAdmin,
        PayoutScheduleAdmin,
        SubscriptionPlanAdmin,
        PublisherSubscriptionAdmin,
        SubscriptionPaymentHistoryAdmin,
        PublisherVerificationAdmin,
        PublisherBusinessAdmin,
        PublisherBrandAdmin,
        PublisherBlacklistEntryAdmin,
        GlobalBlacklistAdmin,
        CommissionTierAdmin,
        PublisherCommissionAdmin,
        PublisherReferralAdmin,
        PublisherPerformanceTargetAdmin,
        PublisherLeaderboardAdmin,
        PublisherRatingRecordAdmin,
    )

Registered models (19):
  01. PublisherBankAccount
  02. PublisherKYC
  03. KYCDocument
  04. PayoutRequest
  05. PayoutSchedule
  06. SubscriptionPlan
  07. PublisherSubscription
  08. SubscriptionPaymentHistory
  09. PublisherVerification
  10. PublisherBusiness
  11. PublisherBrand
  12. PublisherBlacklistEntry
  13. GlobalBlacklist
  14. CommissionTier
  15. PublisherCommission
  16. PublisherReferral
  17. PublisherPerformanceTarget
  18. PublisherLeaderboard
  19. PublisherRatingRecord
"""

from django.contrib import admin
from django.utils.html import format_html

try:
    from .publisher_management.publisher_bank_account import PublisherBankAccount
    from .publisher_management.publisher_kyc import PublisherKYC, KYCDocument
    from .publisher_management.publisher_payout import PayoutRequest, PayoutSchedule
    from .publisher_management.publisher_subscription import (
        SubscriptionPlan,
        PublisherSubscription,
        SubscriptionPaymentHistory,
    )
    from .publisher_management.publisher_verification import PublisherVerification
    from .publisher_management.publisher_business import PublisherBusiness
    from .publisher_management.publisher_brand import PublisherBrand
    from .publisher_management.publisher_blacklist import PublisherBlacklistEntry, GlobalBlacklist
    from .publisher_management.publisher_commission import CommissionTier, PublisherCommission
    from .publisher_management.publisher_performance import (
        PublisherPerformanceTarget,
        PublisherLeaderboard,
    )
    from .publisher_management.publisher_rating import PublisherRatingRecord
    try:
        from .publisher_management.publisher_referral import PublisherReferral
        _HAS_REFERRAL = True
    except ImportError:
        _HAS_REFERRAL = False
    _MODELS_AVAILABLE = True
except ImportError as _e:
    import warnings
    warnings.warn(
        f'publisher_management admin skipped — migration 0009 not yet applied: {_e}',
        stacklevel=2,
    )
    _MODELS_AVAILABLE = False


if _MODELS_AVAILABLE:

    # ──────────────────────────────────────────────────────────────────────────
    # 01 — PublisherBankAccount
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(PublisherBankAccount)
    class PublisherBankAccountAdmin(admin.ModelAdmin):
        list_display  = (
            'get_publisher_id', 'account_type', 'account_label',
            'currency', 'verification_status', 'is_primary', 'is_active',
            'total_received', 'created_at',
        )
        list_filter   = ('account_type', 'currency', 'verification_status', 'is_primary', 'is_active')
        search_fields = ('publisher__publisher_id', 'account_holder_name', 'account_label',
                         'paypal_email', 'bank_name')
        readonly_fields  = ('created_at', 'updated_at', 'verified_at', 'last_payment_at',
                            'total_received', 'payment_count')
        ordering = ('-created_at',)
        date_hierarchy = 'created_at'

        fieldsets = (
            ('Publisher', {'fields': ('publisher', 'tenant')}),
            ('Account Core', {'fields': (
                'account_type', 'account_label', 'currency',
                'account_number', 'account_holder_name',
            )}),
            ('Bank Details', {'fields': (
                'bank_name', 'bank_branch', 'routing_number',
                'swift_code', 'iban', 'bank_address', 'bank_country',
            ), 'classes': ('collapse',)}),
            ('Mobile Banking', {'fields': (
                'mobile_number', 'mobile_account_type',
            ), 'classes': ('collapse',)}),
            ('Crypto', {'fields': (
                'crypto_network', 'crypto_wallet_address', 'crypto_memo_tag',
            ), 'classes': ('collapse',)}),
            ('PayPal / Payoneer / Wise', {'fields': (
                'paypal_email', 'payoneer_id', 'wise_email',
            ), 'classes': ('collapse',)}),
            ('Status', {'fields': (
                'verification_status', 'is_primary', 'is_active',
                'verified_at', 'verified_by', 'verification_notes',
            )}),
            ('Fees', {'fields': (
                'minimum_payout_amount', 'payout_frequency',
                'processing_fee_flat', 'processing_fee_pct', 'withholding_tax_pct',
            ), 'classes': ('collapse',)}),
            ('History', {'fields': (
                'total_received', 'payment_count', 'last_payment_at',
                'created_at', 'updated_at',
            ), 'classes': ('collapse',)}),
        )

        def get_publisher_id(self, obj):
            return obj.publisher.publisher_id
        get_publisher_id.short_description = 'Publisher'
        get_publisher_id.admin_order_field = 'publisher__publisher_id'

        actions = ['mark_verified', 'mark_suspended']

        @admin.action(description='Mark selected as Verified')
        def mark_verified(self, request, queryset):
            from django.utils import timezone
            updated = queryset.update(
                verification_status='verified',
                verified_at=timezone.now(),
                verified_by=request.user,
            )
            self.message_user(request, f'{updated} accounts marked as verified.')

        @admin.action(description='Mark selected as Suspended')
        def mark_suspended(self, request, queryset):
            updated = queryset.update(verification_status='suspended')
            self.message_user(request, f'{updated} accounts suspended.')

    # ──────────────────────────────────────────────────────────────────────────
    # 02 — PublisherKYC
    # ──────────────────────────────────────────────────────────────────────────

    class KYCDocumentInline(admin.TabularInline):
        model        = KYCDocument
        extra        = 0
        readonly_fields = ('created_at', 'verified_at')
        fields       = (
            'document_type', 'document_number', 'document_file',
            'verification_status', 'expiry_date', 'verified_at',
        )
        show_change_link = True

    @admin.register(PublisherKYC)
    class PublisherKYCAdmin(admin.ModelAdmin):
        list_display  = (
            'get_publisher_id', 'kyc_type', 'full_legal_name',
            'status', 'risk_level', 'risk_score', 'submitted_at', 'reviewed_at',
        )
        list_filter   = ('status', 'kyc_type', 'risk_level')
        search_fields = ('publisher__publisher_id', 'full_legal_name',
                         'nid_number', 'passport_number', 'business_name')
        readonly_fields  = (
            'created_at', 'updated_at', 'submitted_at',
            'reviewed_at', 'approved_at', 'expires_at',
        )
        ordering     = ('-created_at',)
        date_hierarchy = 'created_at'
        inlines      = [KYCDocumentInline]

        fieldsets = (
            ('Publisher', {'fields': ('publisher', 'tenant', 'kyc_type')}),
            ('Personal Info', {'fields': (
                'full_legal_name', 'date_of_birth', 'nationality',
                'gender', 'nid_number', 'passport_number', 'tin_number',
            )}),
            ('Address', {'fields': (
                'address_line1', 'address_line2', 'city',
                'state', 'postal_code', 'country',
                'phone', 'secondary_phone',
            ), 'classes': ('collapse',)}),
            ('Business (if applicable)', {'fields': (
                'business_name', 'business_registration_number', 'business_tin',
            ), 'classes': ('collapse',)}),
            ('Review', {'fields': (
                'status', 'risk_level', 'risk_score', 'risk_factors',
                'reviewed_by', 'rejection_reason', 'admin_notes',
                'submitted_at', 'reviewed_at', 'approved_at', 'expires_at',
            )}),
            ('Selfie', {'fields': ('selfie_with_id',), 'classes': ('collapse',)}),
            ('AML', {'fields': ('is_aml_cleared', 'aml_check_date', 'ip_address'),
                     'classes': ('collapse',)}),
            ('Timestamps', {'fields': ('created_at', 'updated_at'),
                            'classes': ('collapse',)}),
        )

        def get_publisher_id(self, obj):
            return obj.publisher.publisher_id
        get_publisher_id.short_description = 'Publisher'
        get_publisher_id.admin_order_field = 'publisher__publisher_id'

        actions = ['approve_kyc', 'reject_kyc', 'put_on_hold']

        @admin.action(description='Approve selected KYC records')
        def approve_kyc(self, request, queryset):
            from django.utils import timezone
            updated = queryset.filter(status='submitted').update(
                status='approved',
                reviewed_by=request.user,
                approved_at=timezone.now(),
                reviewed_at=timezone.now(),
            )
            self.message_user(request, f'{updated} KYC records approved.')

        @admin.action(description='Reject selected KYC records')
        def reject_kyc(self, request, queryset):
            from django.utils import timezone
            updated = queryset.update(
                status='rejected',
                reviewed_by=request.user,
                reviewed_at=timezone.now(),
            )
            self.message_user(request, f'{updated} KYC records rejected.')

        @admin.action(description='Put selected KYC on hold')
        def put_on_hold(self, request, queryset):
            updated = queryset.update(status='on_hold')
            self.message_user(request, f'{updated} KYC records put on hold.')

    # ──────────────────────────────────────────────────────────────────────────
    # 03 — KYCDocument  (standalone — also shown inline above)
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(KYCDocument)
    class KYCDocumentAdmin(admin.ModelAdmin):
        list_display  = (
            'get_publisher_id', 'document_type', 'document_number',
            'verification_status', 'expiry_date', 'verified_at',
        )
        list_filter   = ('document_type', 'verification_status')
        search_fields = ('kyc__publisher__publisher_id', 'document_number')
        readonly_fields  = ('created_at', 'updated_at', 'verified_at')

        def get_publisher_id(self, obj):
            return obj.kyc.publisher.publisher_id
        get_publisher_id.short_description = 'Publisher'

    # ──────────────────────────────────────────────────────────────────────────
    # 04 — PayoutRequest
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(PayoutRequest)
    class PayoutRequestAdmin(admin.ModelAdmin):
        list_display  = (
            'request_id', 'get_publisher_id',
            'requested_amount', 'net_amount', 'currency',
            'status', 'priority', 'created_at',
        )
        list_filter   = ('status', 'priority', 'currency')
        search_fields = ('request_id', 'publisher__publisher_id',
                         'payment_reference', 'payment_gateway_ref')
        readonly_fields  = (
            'request_id', 'net_amount', 'created_at', 'updated_at',
            'approved_at', 'processed_at', 'completed_at',
        )
        ordering     = ('-created_at',)
        date_hierarchy = 'created_at'

        fieldsets = (
            ('Core', {'fields': (
                'publisher', 'invoice', 'bank_account', 'request_id',
            )}),
            ('Amounts', {'fields': (
                'requested_amount', 'approved_amount',
                'processing_fee', 'withholding_tax', 'net_amount', 'currency',
            )}),
            ('Status', {'fields': (
                'status', 'priority',
                'approved_by', 'approved_at', 'processed_at', 'completed_at',
            )}),
            ('Notes', {'fields': (
                'publisher_notes', 'admin_notes', 'rejection_reason',
            ), 'classes': ('collapse',)}),
            ('Payment', {'fields': (
                'payment_reference', 'payment_gateway_ref', 'gateway_response',
            ), 'classes': ('collapse',)}),
            ('Timestamps', {'fields': ('created_at', 'updated_at'),
                            'classes': ('collapse',)}),
        )

        def get_publisher_id(self, obj):
            return obj.publisher.publisher_id
        get_publisher_id.short_description = 'Publisher'
        get_publisher_id.admin_order_field = 'publisher__publisher_id'

        actions = ['approve_payouts', 'reject_payouts']

        @admin.action(description='Approve selected payout requests')
        def approve_payouts(self, request, queryset):
            from django.utils import timezone
            updated = queryset.filter(status='pending').update(
                status='approved',
                approved_by=request.user,
                approved_at=timezone.now(),
            )
            self.message_user(request, f'{updated} payout requests approved.')

        @admin.action(description='Reject selected payout requests')
        def reject_payouts(self, request, queryset):
            from django.utils import timezone
            updated = queryset.filter(status__in=['pending', 'approved']).update(
                status='rejected',
                approved_by=request.user,
            )
            self.message_user(request, f'{updated} payout requests rejected.')

    # ──────────────────────────────────────────────────────────────────────────
    # 05 — PayoutSchedule
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(PayoutSchedule)
    class PayoutScheduleAdmin(admin.ModelAdmin):
        list_display  = (
            'get_publisher_id', 'frequency', 'is_automatic',
            'min_threshold', 'payout_day', 'next_payout_date',
            'last_payout_date', 'is_paused',
        )
        list_filter   = ('frequency', 'is_automatic', 'is_paused')
        search_fields = ('publisher__publisher_id',)
        readonly_fields = ('created_at', 'updated_at')

        def get_publisher_id(self, obj):
            return obj.publisher.publisher_id
        get_publisher_id.short_description = 'Publisher'

    # ──────────────────────────────────────────────────────────────────────────
    # 06 — SubscriptionPlan
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(SubscriptionPlan)
    class SubscriptionPlanAdmin(admin.ModelAdmin):
        list_display  = (
            'id', 'name', 'plan_type',
            'monthly_price', 'revenue_share_pct',
            'trial_days', 'is_active', 'sort_order',
        )
        list_filter   = ('plan_type', 'is_active')
        search_fields = ('plan_id', 'name')
        readonly_fields = ('created_at', 'updated_at')
        ordering = ('sort_order', 'monthly_price')

    # ──────────────────────────────────────────────────────────────────────────
    # 07 — PublisherSubscription
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(PublisherSubscription)
    class PublisherSubscriptionAdmin(admin.ModelAdmin):
        list_display  = (
            'get_publisher_id', 'get_plan_name', 'billing_cycle',
            'status', 'current_period_start', 'current_period_end',
            'current_price', 'auto_renew',
        )
        list_filter   = ('status', 'billing_cycle', 'auto_renew')
        search_fields = ('publisher__publisher_id', 'plan__name', 'coupon_code')
        readonly_fields  = ('created_at', 'updated_at', 'downgraded_at')
        ordering = ('-created_at',)
        date_hierarchy = 'current_period_start'

        def get_publisher_id(self, obj):
            return obj.publisher.publisher_id
        get_publisher_id.short_description = 'Publisher'
        get_publisher_id.admin_order_field = 'publisher__publisher_id'

        def get_plan_name(self, obj):
            return obj.plan.name if obj.plan else '—'
        get_plan_name.short_description = 'Plan'

    # ──────────────────────────────────────────────────────────────────────────
    # 08 — SubscriptionPaymentHistory
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(SubscriptionPaymentHistory)
    class SubscriptionPaymentHistoryAdmin(admin.ModelAdmin):
        list_display  = (
            'get_publisher_id', 'event_type', 'amount', 'currency', 'status', 'paid_at',
        )
        list_filter   = ('status', 'currency')
        search_fields = ('publisher__publisher_id', 'transaction_id')
        readonly_fields  = ('created_at', 'updated_at', 'paid_at')
        ordering = ('-created_at',)

        def get_publisher_id(self, obj):
            return obj.publisher.publisher_id
        get_publisher_id.short_description = 'Publisher'

    # ──────────────────────────────────────────────────────────────────────────
    # 09 — PublisherVerification
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(PublisherVerification)
    class PublisherVerificationAdmin(admin.ModelAdmin):
        list_display  = (
            'get_publisher_id', 'verification_type', 'identifier', 'status', 'verified_at',
        )
        list_filter   = ('verification_type', 'status')
        search_fields = ('publisher__publisher_id',)
        readonly_fields  = (
            'created_at', 'updated_at', 'token', 'verified_at', 'expires_at',
        )

        def get_publisher_id(self, obj):
            return obj.publisher.publisher_id
        get_publisher_id.short_description = 'Publisher'

    # ──────────────────────────────────────────────────────────────────────────
    # 10 — PublisherBusiness
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(PublisherBusiness)
    class PublisherBusinessAdmin(admin.ModelAdmin):
        list_display  = (
            'get_publisher_id', 'company_legal_name',
            'company_type', 'registration_country', 'primary_industry',
        )
        search_fields = ('publisher__publisher_id', 'business_name',
                         'registration_number', 'tin_number')
        readonly_fields  = ('created_at', 'updated_at')

        def get_publisher_id(self, obj):
            return obj.publisher.publisher_id
        get_publisher_id.short_description = 'Publisher'

    # ──────────────────────────────────────────────────────────────────────────
    # 11 — PublisherBrand
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(PublisherBrand)
    class PublisherBrandAdmin(admin.ModelAdmin):
        list_display  = (
            'get_publisher_id', 'brand_name', 'is_store_public',
            'website_url', 'updated_at',
        )
        list_filter   = ('is_store_public',)
        search_fields = ('publisher__publisher_id', 'brand_name')
        readonly_fields  = ('created_at', 'updated_at')

        def get_publisher_id(self, obj):
            return obj.publisher.publisher_id
        get_publisher_id.short_description = 'Publisher'

    # ──────────────────────────────────────────────────────────────────────────
    # 12 — PublisherBlacklistEntry
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(PublisherBlacklistEntry)
    class PublisherBlacklistEntryAdmin(admin.ModelAdmin):
        list_display  = (
            'get_publisher_id', 'list_type', 'value',
            'is_active', 'expires_at', 'created_at',
        )
        list_filter   = ('list_type', 'is_active')
        search_fields = ('publisher__publisher_id', 'value')
        readonly_fields  = ('created_at', 'updated_at')
        ordering = ('-created_at',)

        def get_publisher_id(self, obj):
            return obj.publisher.publisher_id
        get_publisher_id.short_description = 'Publisher'

    # ──────────────────────────────────────────────────────────────────────────
    # 13 — GlobalBlacklist
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(GlobalBlacklist)
    class GlobalBlacklistAdmin(admin.ModelAdmin):
        list_display  = (
            'entry_type', 'value', 'reason', 'severity',
            'is_active', 'expires_at', 'source',
        )
        list_filter   = ('entry_type', 'severity', 'is_active')
        search_fields = ('value', 'reason')
        readonly_fields  = ('created_at', 'updated_at')
        ordering = ('-created_at',)

    # ──────────────────────────────────────────────────────────────────────────
    # 14 — CommissionTier
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(CommissionTier)
    class CommissionTierAdmin(admin.ModelAdmin):
        list_display  = (
            'tier_name', 'tier_level', 'base_revenue_share',
            'min_monthly_revenue', 'max_monthly_revenue',
            'referral_commission_pct', 'is_active', 'priority_support',
        )
        list_filter   = ('is_active',)
        search_fields = ('tier_name',)
        readonly_fields  = ('created_at', 'updated_at')
        ordering = ('tier_level',)

    # ──────────────────────────────────────────────────────────────────────────
    # 15 — PublisherCommission
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(PublisherCommission)
    class PublisherCommissionAdmin(admin.ModelAdmin):
        list_display  = (
            'get_publisher_id', 'commission_type',
            'commission_rate', 'commission_amount', 'status',
        )
        search_fields = ('publisher__publisher_id',)
        readonly_fields  = ('created_at', 'updated_at')

        def get_publisher_id(self, obj):
            return obj.publisher.publisher_id
        get_publisher_id.short_description = 'Publisher'

    # ──────────────────────────────────────────────────────────────────────────
    # 16 — PublisherReferral
    # ──────────────────────────────────────────────────────────────────────────

    if _HAS_REFERRAL:
        @admin.register(PublisherReferral)
        class PublisherReferralAdmin(admin.ModelAdmin):
            list_display  = (
                'get_referrer_id', 'get_referred_id',
                'referral_code', 'status', 'referrer_bonus_pct',
                'bonus_paid', 'qualified_at',
            )
            list_filter   = ('status',)
            search_fields = (
                'referrer__publisher_id', 'referred__publisher_id', 'referral_code',
            )
            readonly_fields  = ('created_at', 'updated_at', 'bonus_paid_at', 'qualified_at')
            ordering = ('-created_at',)

            def get_referrer_id(self, obj):
                return obj.referrer.publisher_id
            get_referrer_id.short_description = 'Referrer'

            def get_referred_id(self, obj):
                return obj.referred.publisher_id
            get_referred_id.short_description = 'Referred'

    # ──────────────────────────────────────────────────────────────────────────
    # 17 — PublisherPerformanceTarget
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(PublisherPerformanceTarget)
    class PublisherPerformanceTargetAdmin(admin.ModelAdmin):
        list_display  = (
            'get_publisher_id', 'year', 'month',
            'target_revenue', 'target_impressions', 'target_ecpm', 'target_fill_rate',
        )
        list_filter   = ('year', 'month')
        search_fields = ('publisher__publisher_id',)
        readonly_fields  = ('created_at', 'updated_at')
        ordering = ('-year', '-month')

        def get_publisher_id(self, obj):
            return obj.publisher.publisher_id
        get_publisher_id.short_description = 'Publisher'

    # ──────────────────────────────────────────────────────────────────────────
    # 18 — PublisherLeaderboard
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(PublisherLeaderboard)
    class PublisherLeaderboardAdmin(admin.ModelAdmin):
        list_display  = (
            'year', 'month', 'total_publishers', 'is_published', 'published_at',
        )
        list_filter   = ('year', 'month', 'is_published')
        readonly_fields  = ('created_at', 'updated_at', 'published_at')
        ordering = ('-year', '-month')

    # ──────────────────────────────────────────────────────────────────────────
    # 19 — PublisherRatingRecord
    # ──────────────────────────────────────────────────────────────────────────

    @admin.register(PublisherRatingRecord)
    class PublisherRatingRecordAdmin(admin.ModelAdmin):
        list_display  = (
            'get_publisher_id', 'get_rated_by_tenant',
            'weighted_score', 'content_quality_rating', 'traffic_quality_rating',
            'compliance_rating', 'is_public', 'created_at',
        )
        list_filter   = ('is_public',)
        search_fields = ('publisher__publisher_id',)
        readonly_fields  = ('created_at', 'updated_at', 'weighted_score')
        ordering = ('-created_at',)

        def get_publisher_id(self, obj):
            return obj.publisher.publisher_id
        get_publisher_id.short_description = 'Publisher'

        def get_rated_by_tenant(self, obj):
            return obj.rated_by_tenant
        get_rated_by_tenant.short_description = 'Rated By Tenant'
