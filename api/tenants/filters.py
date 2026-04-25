"""
Tenant Filters - Django Filter Classes

This module contains comprehensive filter classes for tenant-related models
with advanced filtering, searching, and sorting capabilities.
"""

import django_filters
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from rest_framework import filters

from .models_improved import (
    Tenant, TenantSettings, TenantBilling, TenantInvoice, TenantAuditLog
)
from .choices import (
    TenantPlanChoices, TenantStatusChoices, BillingStatusChoices,
    InvoiceStatusChoices, AuditActionChoices
)


class TenantFilter(django_filters.FilterSet):
    """
    Comprehensive filter for Tenant model.
    
    Provides filtering by various tenant attributes including
    plan, status, creation date, and custom search.
    """
    
    # Basic filters
    plan = django_filters.ChoiceFilter(
        choices=TenantPlanChoices.choices(),
        method='filter_plan',
        label=_('Subscription Plan')
    )
    
    status = django_filters.ChoiceFilter(
        choices=TenantStatusChoices.choices(),
        method='filter_status',
        label=_('Tenant Status')
    )
    
    is_active = django_filters.BooleanFilter(
        method='filter_is_active',
        label=_('Is Active')
    )
    
    is_suspended = django_filters.BooleanFilter(
        method='filter_is_suspended',
        label=_('Is Suspended')
    )
    
    is_deleted = django_filters.BooleanFilter(
        method='filter_is_deleted',
        label=_('Is Deleted')
    )
    
    # Date filters
    created_at = django_filters.DateFromToRangeFilter(
        method='filter_created_at',
        label=_('Creation Date Range')
    )
    
    created_at_gte = django_filters.DateFilter(
        method='filter_created_at_gte',
        label=_('Created After')
    )
    
    created_at_lte = django_filters.DateFilter(
        method='filter_created_at_lte',
        label=_('Created Before')
    )
    
    trial_ends_at = django_filters.DateFromToRangeFilter(
        method='filter_trial_ends_at',
        label=_('Trial End Date Range')
    )
    
    # User count filters
    user_count_min = django_filters.NumberFilter(
        method='filter_user_count_min',
        label=_('Minimum User Count')
    )
    
    user_count_max = django_filters.NumberFilter(
        method='filter_user_count_max',
        label=_('Maximum User Count')
    )
    
    user_limit_reached = django_filters.BooleanFilter(
        method='filter_user_limit_reached',
        label=_('User Limit Reached')
    )
    
    # Geographic filters
    country_code = django_filters.CharFilter(
        method='filter_country_code',
        label=_('Country Code')
    )
    
    currency_code = django_filters.CharFilter(
        method='filter_currency_code',
        label=_('Currency Code')
    )
    
    data_region = django_filters.CharFilter(
        method='filter_data_region',
        label=_('Data Region')
    )
    
    # Search filters
    search = django_filters.CharFilter(
        method='filter_search',
        label=_('Search')
    )
    
    owner_email = django_filters.CharFilter(
        method='filter_owner_email',
        label=_('Owner Email')
    )
    
    admin_email = django_filters.CharFilter(
        method='filter_admin_email',
        label=_('Admin Email')
    )
    
    # Domain filters
    domain = django_filters.CharFilter(
        method='filter_domain',
        label=_('Domain')
    )
    
    has_domain = django_filters.BooleanFilter(
        method='filter_has_domain',
        label=_('Has Custom Domain')
    )
    
    # Billing filters
    billing_status = django_filters.ChoiceFilter(
        choices=BillingStatusChoices.choices(),
        method='filter_billing_status',
        label=_('Billing Status')
    )
    
    has_active_subscription = django_filters.BooleanFilter(
        method='filter_has_active_subscription',
        label=_('Has Active Subscription')
    )
    
    trial_active = django_filters.BooleanFilter(
        method='filter_trial_active',
        label=_('Trial Active')
    )
    
    trial_expired = django_filters.BooleanFilter(
        method='filter_trial_expired',
        label=_('Trial Expired')
    )
    
    # Ordering
    ordering = django_filters.OrderingFilter(
        fields=(
            'name', 'slug', 'created_at', 'updated_at', 'plan', 'status',
            'max_users', 'trial_ends_at'
        ),
        field_labels={
            'name': _('Name'),
            'slug': _('Slug'),
            'created_at': _('Created At'),
            'updated_at': _('Updated At'),
            'plan': _('Plan'),
            'status': _('Status'),
            'max_users': _('Max Users'),
            'trial_ends_at': _('Trial Ends At'),
        }
    )
    
    class Meta:
        model = Tenant
        fields = []
    
    def filter_plan(self, queryset, name, value):
        """Filter by subscription plan."""
        if value:
            return queryset.filter(plan=value)
        return queryset
    
    def filter_status(self, queryset, name, value):
        """Filter by tenant status."""
        if value:
            return queryset.filter(status=value)
        return queryset
    
    def filter_is_active(self, queryset, name, value):
        """Filter by active status."""
        if value is not None:
            return queryset.filter(is_active=value)
        return queryset
    
    def filter_is_suspended(self, queryset, name, value):
        """Filter by suspension status."""
        if value is not None:
            return queryset.filter(is_suspended=value)
        return queryset
    
    def filter_is_deleted(self, queryset, name, value):
        """Filter by deletion status."""
        if value is not None:
            return queryset.filter(is_deleted=value)
        return queryset
    
    def filter_created_at(self, queryset, name, value):
        """Filter by creation date range."""
        if value:
            if value.start:
                queryset = queryset.filter(created_at__date__gte=value.start)
            if value.stop:
                queryset = queryset.filter(created_at__date__lte=value.stop)
        return queryset
    
    def filter_created_at_gte(self, queryset, name, value):
        """Filter by creation date (greater than or equal)."""
        if value:
            return queryset.filter(created_at__date__gte=value)
        return queryset
    
    def filter_created_at_lte(self, queryset, name, value):
        """Filter by creation date (less than or equal)."""
        if value:
            return queryset.filter(created_at__date__lte=value)
        return queryset
    
    def filter_trial_ends_at(self, queryset, name, value):
        """Filter by trial end date range."""
        if value:
            if value.start:
                queryset = queryset.filter(trial_ends_at__date__gte=value.start)
            if value.stop:
                queryset = queryset.filter(trial_ends_at__date__lte=value.stop)
        return queryset
    
    def filter_user_count_min(self, queryset, name, value):
        """Filter by minimum user count."""
        if value:
            queryset = queryset.annotate(
                user_count=Count('users', filter=Q(users__is_active=True))
            ).filter(user_count__gte=value)
        return queryset
    
    def filter_user_count_max(self, queryset, name, value):
        """Filter by maximum user count."""
        if value:
            queryset = queryset.annotate(
                user_count=Count('users', filter=Q(users__is_active=True))
            ).filter(user_count__lte=value)
        return queryset
    
    def filter_user_limit_reached(self, queryset, name, value):
        """Filter by user limit reached status."""
        if value is not None:
            if value:
                # Filter tenants that have reached their user limit
                filtered_tenants = []
                for tenant in queryset:
                    if tenant.is_user_limit_reached():
                        filtered_tenants.append(tenant.id)
                return queryset.filter(id__in=filtered_tenants)
            else:
                # Filter tenants that have not reached their user limit
                filtered_tenants = []
                for tenant in queryset:
                    if not tenant.is_user_limit_reached():
                        filtered_tenants.append(tenant.id)
                return queryset.filter(id__in=filtered_tenants)
        return queryset
    
    def filter_country_code(self, queryset, name, value):
        """Filter by country code."""
        if value:
            return queryset.filter(country_code__iexact=value)
        return queryset
    
    def filter_currency_code(self, queryset, name, value):
        """Filter by currency code."""
        if value:
            return queryset.filter(currency_code__iexact=value)
        return queryset
    
    def filter_data_region(self, queryset, name, value):
        """Filter by data region."""
        if value:
            return queryset.filter(data_region__iexact=value)
        return queryset
    
    def filter_search(self, queryset, name, value):
        """Search across multiple fields."""
        if value:
            return queryset.filter(
                Q(name__icontains=value) |
                Q(slug__icontains=value) |
                Q(admin_email__icontains=value) |
                Q(domain__icontains=value) |
                Q(owner__email__icontains=value)
            )
        return queryset
    
    def filter_owner_email(self, queryset, name, value):
        """Filter by owner email."""
        if value:
            return queryset.filter(owner__email__icontains=value)
        return queryset
    
    def filter_admin_email(self, queryset, name, value):
        """Filter by admin email."""
        if value:
            return queryset.filter(admin_email__icontains=value)
        return queryset
    
    def filter_domain(self, queryset, name, value):
        """Filter by domain."""
        if value:
            return queryset.filter(domain__icontains=value)
        return queryset
    
    def filter_has_domain(self, queryset, name, value):
        """Filter by custom domain presence."""
        if value is not None:
            if value:
                return queryset.filter(domain__isnull=False).exclude(domain='')
            else:
                return queryset.filter(Q(domain__isnull=True) | Q(domain=''))
        return queryset
    
    def filter_billing_status(self, queryset, name, value):
        """Filter by billing status."""
        if value:
            return queryset.filter(tenantbilling__status=value)
        return queryset
    
    def filter_has_active_subscription(self, queryset, name, value):
        """Filter by active subscription presence."""
        if value is not None:
            if value:
                return queryset.filter(
                    tenantbilling__status='active'
                ).filter(
                    Q(tenantbilling__subscription_ends_at__gt=timezone.now()) |
                    Q(tenantbilling__subscription_ends_at__isnull=True)
                )
            else:
                return queryset.exclude(
                    tenantbilling__status='active'
                ).filter(
                    Q(tenantbilling__subscription_ends_at__lte=timezone.now()) |
                    Q(tenantbilling__subscription_ends_at__isnull=True)
                )
        return queryset
    
    def filter_trial_active(self, queryset, name, value):
        """Filter by trial active status."""
        if value is not None:
            if value:
                return queryset.filter(
                    trial_ends_at__gt=timezone.now(),
                    status='trial'
                )
            else:
                return queryset.exclude(
                    trial_ends_at__gt=timezone.now(),
                    status='trial'
                )
        return queryset
    
    def filter_trial_expired(self, queryset, name, value):
        """Filter by trial expired status."""
        if value is not None:
            if value:
                return queryset.filter(
                    trial_ends_at__lt=timezone.now(),
                    status='trial'
                )
            else:
                return queryset.exclude(
                    trial_ends_at__lt=timezone.now(),
                    status='trial'
                )
        return queryset


class TenantSettingsFilter(django_filters.FilterSet):
    """
    Filter for TenantSettings model.
    
    Provides filtering by feature flags and configuration options.
    """
    
    # Feature flag filters
    enable_referral = django_filters.BooleanFilter(
        method='filter_enable_referral',
        label=_('Enable Referral')
    )
    
    enable_offerwall = django_filters.BooleanFilter(
        method='filter_enable_offerwall',
        label=_('Enable Offerwall')
    )
    
    enable_kyc = django_filters.BooleanFilter(
        method='filter_enable_kyc',
        label=_('Enable KYC')
    )
    
    enable_leaderboard = django_filters.BooleanFilter(
        method='filter_enable_leaderboard',
        label=_('Enable Leaderboard')
    )
    
    enable_chat = django_filters.BooleanFilter(
        method='filter_enable_chat',
        label=_('Enable Chat')
    )
    
    enable_push_notifications = django_filters.BooleanFilter(
        method='filter_enable_push_notifications',
        label=_('Enable Push Notifications')
    )
    
    enable_analytics = django_filters.BooleanFilter(
        method='filter_enable_analytics',
        label=_('Enable Analytics')
    )
    
    enable_api_access = django_filters.BooleanFilter(
        method='filter_enable_api_access',
        label=_('Enable API Access')
    )
    
    # Configuration filters
    min_withdrawal_min = django_filters.NumberFilter(
        method='filter_min_withdrawal_min',
        label=_('Minimum Withdrawal Amount')
    )
    
    min_withdrawal_max = django_filters.NumberFilter(
        method='filter_min_withdrawal_max',
        label=_('Maximum Withdrawal Amount')
    )
    
    max_withdrawal_min = django_filters.NumberFilter(
        method='filter_max_withdrawal_min',
        label=_('Maximum Withdrawal Amount')
    )
    
    max_withdrawal_max = django_filters.NumberFilter(
        method='filter_max_withdrawal_max',
        label=_('Maximum Withdrawal Amount')
    )
    
    withdrawal_fee_percent_min = django_filters.NumberFilter(
        method='filter_withdrawal_fee_percent_min',
        label=_('Minimum Withdrawal Fee Percent')
    )
    
    withdrawal_fee_percent_max = django_filters.NumberFilter(
        method='filter_withdrawal_fee_percent_max',
        label=_('Maximum Withdrawal Fee Percent')
    )
    
    # Security filters
    require_email_verification = django_filters.BooleanFilter(
        method='filter_require_email_verification',
        label=_('Require Email Verification')
    )
    
    require_phone_verification = django_filters.BooleanFilter(
        method='filter_require_phone_verification',
        label=_('Require Phone Verification')
    )
    
    enable_two_factor_auth = django_filters.BooleanFilter(
        method='filter_enable_two_factor_auth',
        label=_('Enable Two-Factor Authentication')
    )
    
    password_min_length_min = django_filters.NumberFilter(
        method='filter_password_min_length_min',
        label=_('Minimum Password Length')
    )
    
    password_min_length_max = django_filters.NumberFilter(
        method='filter_password_min_length_max',
        label=_('Maximum Password Length')
    )
    
    # Tenant filters
    tenant_plan = django_filters.ChoiceFilter(
        choices=TenantPlanChoices.choices(),
        method='filter_tenant_plan',
        label=_('Tenant Plan')
    )
    
    tenant_status = django_filters.ChoiceFilter(
        choices=TenantStatusChoices.choices(),
        method='filter_tenant_status',
        label=_('Tenant Status')
    )
    
    class Meta:
        model = TenantSettings
        fields = []
    
    def filter_enable_referral(self, queryset, name, value):
        """Filter by referral feature enabled."""
        if value is not None:
            return queryset.filter(enable_referral=value)
        return queryset
    
    def filter_enable_offerwall(self, queryset, name, value):
        """Filter by offerwall feature enabled."""
        if value is not None:
            return queryset.filter(enable_offerwall=value)
        return queryset
    
    def filter_enable_kyc(self, queryset, name, value):
        """Filter by KYC feature enabled."""
        if value is not None:
            return queryset.filter(enable_kyc=value)
        return queryset
    
    def filter_enable_leaderboard(self, queryset, name, value):
        """Filter by leaderboard feature enabled."""
        if value is not None:
            return queryset.filter(enable_leaderboard=value)
        return queryset
    
    def filter_enable_chat(self, queryset, name, value):
        """Filter by chat feature enabled."""
        if value is not None:
            return queryset.filter(enable_chat=value)
        return queryset
    
    def filter_enable_push_notifications(self, queryset, name, value):
        """Filter by push notifications feature enabled."""
        if value is not None:
            return queryset.filter(enable_push_notifications=value)
        return queryset
    
    def filter_enable_analytics(self, queryset, name, value):
        """Filter by analytics feature enabled."""
        if value is not None:
            return queryset.filter(enable_analytics=value)
        return queryset
    
    def filter_enable_api_access(self, queryset, name, value):
        """Filter by API access feature enabled."""
        if value is not None:
            return queryset.filter(enable_api_access=value)
        return queryset
    
    def filter_min_withdrawal_min(self, queryset, name, value):
        """Filter by minimum withdrawal amount (minimum)."""
        if value:
            return queryset.filter(min_withdrawal__gte=value)
        return queryset
    
    def filter_min_withdrawal_max(self, queryset, name, value):
        """Filter by minimum withdrawal amount (maximum)."""
        if value:
            return queryset.filter(min_withdrawal__lte=value)
        return queryset
    
    def filter_max_withdrawal_min(self, queryset, name, value):
        """Filter by maximum withdrawal amount (minimum)."""
        if value:
            return queryset.filter(max_withdrawal__gte=value)
        return queryset
    
    def filter_max_withdrawal_max(self, queryset, name, value):
        """Filter by maximum withdrawal amount (maximum)."""
        if value:
            return queryset.filter(max_withdrawal__lte=value)
        return queryset
    
    def filter_withdrawal_fee_percent_min(self, queryset, name, value):
        """Filter by withdrawal fee percent (minimum)."""
        if value:
            return queryset.filter(withdrawal_fee_percent__gte=value)
        return queryset
    
    def filter_withdrawal_fee_percent_max(self, queryset, name, value):
        """Filter by withdrawal fee percent (maximum)."""
        if value:
            return queryset.filter(withdrawal_fee_percent__lte=value)
        return queryset
    
    def filter_require_email_verification(self, queryset, name, value):
        """Filter by email verification requirement."""
        if value is not None:
            return queryset.filter(require_email_verification=value)
        return queryset
    
    def filter_require_phone_verification(self, queryset, name, value):
        """Filter by phone verification requirement."""
        if value is not None:
            return queryset.filter(require_phone_verification=value)
        return queryset
    
    def filter_enable_two_factor_auth(self, queryset, name, value):
        """Filter by two-factor authentication enabled."""
        if value is not None:
            return queryset.filter(enable_two_factor_auth=value)
        return queryset
    
    def filter_password_min_length_min(self, queryset, name, value):
        """Filter by minimum password length (minimum)."""
        if value:
            return queryset.filter(password_min_length__gte=value)
        return queryset
    
    def filter_password_min_length_max(self, queryset, name, value):
        """Filter by minimum password length (maximum)."""
        if value:
            return queryset.filter(password_min_length__lte=value)
        return queryset
    
    def filter_tenant_plan(self, queryset, name, value):
        """Filter by tenant plan."""
        if value:
            return queryset.filter(tenant__plan=value)
        return queryset
    
    def filter_tenant_status(self, queryset, name, value):
        """Filter by tenant status."""
        if value:
            return queryset.filter(tenant__status=value)
        return queryset


class TenantBillingFilter(django_filters.FilterSet):
    """
    Filter for TenantBilling model.
    
    Provides filtering by billing status, dates, and amounts.
    """
    
    # Status filters
    status = django_filters.ChoiceFilter(
        choices=BillingStatusChoices.choices(),
        method='filter_status',
        label=_('Billing Status')
    )
    
    # Date filters
    created_at = django_filters.DateFromToRangeFilter(
        method='filter_created_at',
        label=_('Creation Date Range')
    )
    
    trial_ends_at = django_filters.DateFromToRangeFilter(
        method='filter_trial_ends_at',
        label=_('Trial End Date Range')
    )
    
    subscription_starts_at = django_filters.DateFromToRangeFilter(
        method='filter_subscription_starts_at',
        label=_('Subscription Start Date Range')
    )
    
    subscription_ends_at = django_filters.DateFromToRangeFilter(
        method='filter_subscription_ends_at',
        label=_('Subscription End Date Range')
    )
    
    last_payment_at = django_filters.DateFromToRangeFilter(
        method='filter_last_payment_at',
        label=_('Last Payment Date Range')
    )
    
    next_payment_at = django_filters.DateFromToRangeFilter(
        method='filter_next_payment_at',
        label=_('Next Payment Date Range')
    )
    
    # Amount filters
    monthly_price_min = django_filters.NumberFilter(
        method='filter_monthly_price_min',
        label=_('Minimum Monthly Price')
    )
    
    monthly_price_max = django_filters.NumberFilter(
        method='filter_monthly_price_max',
        label=_('Maximum Monthly Price')
    )
    
    setup_fee_min = django_filters.NumberFilter(
        method='filter_setup_fee_min',
        label=_('Minimum Setup Fee')
    )
    
    setup_fee_max = django_filters.NumberFilter(
        method='filter_setup_fee_max',
        label=_('Maximum Setup Fee')
    )
    
    # Cycle filters
    billing_cycle = django_filters.ChoiceFilter(
        method='filter_billing_cycle',
        label=_('Billing Cycle')
    )
    
    # Currency filters
    currency = django_filters.CharFilter(
        method='filter_currency',
        label=_('Currency')
    )
    
    # Payment method filters
    has_payment_method = django_filters.BooleanFilter(
        method='filter_has_payment_method',
        label=_('Has Payment Method')
    )
    
    # Tenant filters
    tenant_plan = django_filters.ChoiceFilter(
        choices=TenantPlanChoices.choices(),
        method='filter_tenant_plan',
        label=_('Tenant Plan')
    )
    
    # Status calculation filters
    is_active = django_filters.BooleanFilter(
        method='filter_is_active',
        label=_('Is Active')
    )
    
    is_past_due = django_filters.BooleanFilter(
        method='filter_is_past_due',
        label=_('Is Past Due')
    )
    
    days_until_expiry_min = django_filters.NumberFilter(
        method='filter_days_until_expiry_min',
        label=_('Minimum Days Until Expiry')
    )
    
    days_until_expiry_max = django_filters.NumberFilter(
        method='filter_days_until_expiry_max',
        label=_('Maximum Days Until Expiry')
    )
    
    class Meta:
        model = TenantBilling
        fields = []
    
    def filter_status(self, queryset, name, value):
        """Filter by billing status."""
        if value:
            return queryset.filter(status=value)
        return queryset
    
    def filter_created_at(self, queryset, name, value):
        """Filter by creation date range."""
        if value:
            if value.start:
                queryset = queryset.filter(created_at__date__gte=value.start)
            if value.stop:
                queryset = queryset.filter(created_at__date__lte=value.stop)
        return queryset
    
    def filter_trial_ends_at(self, queryset, name, value):
        """Filter by trial end date range."""
        if value:
            if value.start:
                queryset = queryset.filter(trial_ends_at__date__gte=value.start)
            if value.stop:
                queryset = queryset.filter(trial_ends_at__date__lte=value.stop)
        return queryset
    
    def filter_subscription_starts_at(self, queryset, name, value):
        """Filter by subscription start date range."""
        if value:
            if value.start:
                queryset = queryset.filter(subscription_starts_at__date__gte=value.start)
            if value.stop:
                queryset = queryset.filter(subscription_starts_at__date__lte=value.stop)
        return queryset
    
    def filter_subscription_ends_at(self, queryset, name, value):
        """Filter by subscription end date range."""
        if value:
            if value.start:
                queryset = queryset.filter(subscription_ends_at__date__gte=value.start)
            if value.stop:
                queryset = queryset.filter(subscription_ends_at__date__lte=value.stop)
        return queryset
    
    def filter_last_payment_at(self, queryset, name, value):
        """Filter by last payment date range."""
        if value:
            if value.start:
                queryset = queryset.filter(last_payment_at__date__gte=value.start)
            if value.stop:
                queryset = queryset.filter(last_payment_at__date__lte=value.stop)
        return queryset
    
    def filter_next_payment_at(self, queryset, name, value):
        """Filter by next payment date range."""
        if value:
            if value.start:
                queryset = queryset.filter(next_payment_at__date__gte=value.start)
            if value.stop:
                queryset = queryset.filter(next_payment_at__date__lte=value.stop)
        return queryset
    
    def filter_monthly_price_min(self, queryset, name, value):
        """Filter by minimum monthly price."""
        if value:
            return queryset.filter(monthly_price__gte=value)
        return queryset
    
    def filter_monthly_price_max(self, queryset, name, value):
        """Filter by maximum monthly price."""
        if value:
            return queryset.filter(monthly_price__lte=value)
        return queryset
    
    def filter_setup_fee_min(self, queryset, name, value):
        """Filter by minimum setup fee."""
        if value:
            return queryset.filter(setup_fee__gte=value)
        return queryset
    
    def filter_setup_fee_max(self, queryset, name, value):
        """Filter by maximum setup fee."""
        if value:
            return queryset.filter(setup_fee__lte=value)
        return queryset
    
    def filter_billing_cycle(self, queryset, name, value):
        """Filter by billing cycle."""
        if value:
            return queryset.filter(billing_cycle=value)
        return queryset
    
    def filter_currency(self, queryset, name, value):
        """Filter by currency."""
        if value:
            return queryset.filter(currency__iexact=value)
        return queryset
    
    def filter_has_payment_method(self, queryset, name, value):
        """Filter by payment method presence."""
        if value is not None:
            if value:
                return queryset.filter(payment_method_id__isnull=False).exclude(payment_method_id='')
            else:
                return queryset.filter(Q(payment_method_id__isnull=True) | Q(payment_method_id=''))
        return queryset
    
    def filter_tenant_plan(self, queryset, name, value):
        """Filter by tenant plan."""
        if value:
            return queryset.filter(tenant__plan=value)
        return queryset
    
    def filter_is_active(self, queryset, name, value):
        """Filter by active status."""
        if value is not None:
            if value:
                # Filter active subscriptions
                return queryset.filter(
                    status='active'
                ).filter(
                    Q(subscription_ends_at__gt=timezone.now()) |
                    Q(subscription_ends_at__isnull=True)
                )
            else:
                # Filter inactive subscriptions
                return queryset.exclude(
                    status='active'
                ).filter(
                    Q(subscription_ends_at__lte=timezone.now()) |
                    Q(subscription_ends_at__isnull=True)
                )
        return queryset
    
    def filter_is_past_due(self, queryset, name, value):
        """Filter by past due status."""
        if value is not None:
            filtered_billing = []
            for billing in queryset:
                if billing.is_past_due == value:
                    filtered_billing.append(billing.id)
            return queryset.filter(id__in=filtered_billing)
        return queryset
    
    def filter_days_until_expiry_min(self, queryset, name, value):
        """Filter by minimum days until expiry."""
        if value:
            filtered_billing = []
            for billing in queryset:
                days = billing.days_until_expiry
                if days is not None and days >= value:
                    filtered_billing.append(billing.id)
            return queryset.filter(id__in=filtered_billing)
        return queryset
    
    def filter_days_until_expiry_max(self, queryset, name, value):
        """Filter by maximum days until expiry."""
        if value:
            filtered_billing = []
            for billing in queryset:
                days = billing.days_until_expiry
                if days is not None and days <= value:
                    filtered_billing.append(billing.id)
            return queryset.filter(id__in=filtered_billing)
        return queryset


class TenantInvoiceFilter(django_filters.FilterSet):
    """
    Filter for TenantInvoice model.
    
    Provides filtering by invoice status, dates, amounts, and payment details.
    """
    
    # Status filters
    status = django_filters.ChoiceFilter(
        choices=InvoiceStatusChoices.choices(),
        method='filter_status',
        label=_('Invoice Status')
    )
    
    # Date filters
    created_at = django_filters.DateFromToRangeFilter(
        method='filter_created_at',
        label=_('Creation Date Range')
    )
    
    issue_date = django_filters.DateFromToRangeFilter(
        method='filter_issue_date',
        label=_('Issue Date Range')
    )
    
    due_date = django_filters.DateFromToRangeFilter(
        method='filter_due_date',
        label=_('Due Date Range')
    )
    
    paid_at = django_filters.DateFromToRangeFilter(
        method='filter_paid_at',
        label=_('Paid Date Range')
    )
    
    # Amount filters
    amount_min = django_filters.NumberFilter(
        method='filter_amount_min',
        label=_('Minimum Amount')
    )
    
    amount_max = django_filters.NumberFilter(
        method='filter_amount_max',
        label=_('Maximum Amount')
    )
    
    total_amount_min = django_filters.NumberFilter(
        method='filter_total_amount_min',
        label=_('Minimum Total Amount')
    )
    
    total_amount_max = django_filters.NumberFilter(
        method='filter_total_amount_max',
        label=_('Maximum Total Amount')
    )
    
    # Currency filters
    currency = django_filters.CharFilter(
        method='filter_currency',
        label=_('Currency')
    )
    
    # Payment method filters
    payment_method = django_filters.CharFilter(
        method='filter_payment_method',
        label=_('Payment Method')
    )
    
    has_transaction_id = django_filters.BooleanFilter(
        method='filter_has_transaction_id',
        label=_('Has Transaction ID')
    )
    
    # Status calculation filters
    is_overdue = django_filters.BooleanFilter(
        method='filter_is_overdue',
        label=_('Is Overdue')
    )
    
    days_overdue_min = django_filters.NumberFilter(
        method='filter_days_overdue_min',
        label=_('Minimum Days Overdue')
    )
    
    days_overdue_max = django_filters.NumberFilter(
        method='filter_days_overdue_max',
        label=_('Maximum Days Overdue')
    )
    
    # Search filters
    search = django_filters.CharFilter(
        method='filter_search',
        label=_('Search')
    )
    
    invoice_number = django_filters.CharFilter(
        method='filter_invoice_number',
        label=_('Invoice Number')
    )
    
    description = django_filters.CharFilter(
        method='filter_description',
        label=_('Description')
    )
    
    # Tenant filters
    tenant_plan = django_filters.ChoiceFilter(
        choices=TenantPlanChoices.choices(),
        method='filter_tenant_plan',
        label=_('Tenant Plan')
    )
    
    class Meta:
        model = TenantInvoice
        fields = []
    
    def filter_status(self, queryset, name, value):
        """Filter by invoice status."""
        if value:
            return queryset.filter(status=value)
        return queryset
    
    def filter_created_at(self, queryset, name, value):
        """Filter by creation date range."""
        if value:
            if value.start:
                queryset = queryset.filter(created_at__date__gte=value.start)
            if value.stop:
                queryset = queryset.filter(created_at__date__lte=value.stop)
        return queryset
    
    def filter_issue_date(self, queryset, name, value):
        """Filter by issue date range."""
        if value:
            if value.start:
                queryset = queryset.filter(issue_date__gte=value.start)
            if value.stop:
                queryset = queryset.filter(issue_date__lte=value.stop)
        return queryset
    
    def filter_due_date(self, queryset, name, value):
        """Filter by due date range."""
        if value:
            if value.start:
                queryset = queryset.filter(due_date__gte=value.start)
            if value.stop:
                queryset = queryset.filter(due_date__lte=value.stop)
        return queryset
    
    def filter_paid_at(self, queryset, name, value):
        """Filter by paid date range."""
        if value:
            if value.start:
                queryset = queryset.filter(paid_at__gte=value.start)
            if value.stop:
                queryset = queryset.filter(paid_at__lte=value.stop)
        return queryset
    
    def filter_amount_min(self, queryset, name, value):
        """Filter by minimum amount."""
        if value:
            return queryset.filter(amount__gte=value)
        return queryset
    
    def filter_amount_max(self, queryset, name, value):
        """Filter by maximum amount."""
        if value:
            return queryset.filter(amount__lte=value)
        return queryset
    
    def filter_total_amount_min(self, queryset, name, value):
        """Filter by minimum total amount."""
        if value:
            return queryset.filter(total_amount__gte=value)
        return queryset
    
    def filter_total_amount_max(self, queryset, name, value):
        """Filter by maximum total amount."""
        if value:
            return queryset.filter(total_amount__lte=value)
        return queryset
    
    def filter_currency(self, queryset, name, value):
        """Filter by currency."""
        if value:
            return queryset.filter(currency__iexact=value)
        return queryset
    
    def filter_payment_method(self, queryset, name, value):
        """Filter by payment method."""
        if value:
            return queryset.filter(payment_method__icontains=value)
        return queryset
    
    def filter_has_transaction_id(self, queryset, name, value):
        """Filter by transaction ID presence."""
        if value is not None:
            if value:
                return queryset.filter(transaction_id__isnull=False).exclude(transaction_id='')
            else:
                return queryset.filter(Q(transaction_id__isnull=True) | Q(transaction_id=''))
        return queryset
    
    def filter_is_overdue(self, queryset, name, value):
        """Filter by overdue status."""
        if value is not None:
            filtered_invoices = []
            for invoice in queryset:
                if invoice.is_overdue == value:
                    filtered_invoices.append(invoice.id)
            return queryset.filter(id__in=filtered_invoices)
        return queryset
    
    def filter_days_overdue_min(self, queryset, name, value):
        """Filter by minimum days overdue."""
        if value:
            filtered_invoices = []
            for invoice in queryset:
                days = invoice.days_overdue
                if days is not None and days >= value:
                    filtered_invoices.append(invoice.id)
            return queryset.filter(id__in=filtered_invoices)
        return queryset
    
    def filter_days_overdue_max(self, queryset, name, value):
        """Filter by maximum days overdue."""
        if value:
            filtered_invoices = []
            for invoice in queryset:
                days = invoice.days_overdue
                if days is not None and days <= value:
                    filtered_invoices.append(invoice.id)
            return queryset.filter(id__in=filtered_invoices)
        return queryset
    
    def filter_search(self, queryset, name, value):
        """Search across multiple fields."""
        if value:
            return queryset.filter(
                Q(invoice_number__icontains=value) |
                Q(description__icontains=value) |
                Q(transaction_id__icontains=value) |
                Q(payment_method__icontains=value)
            )
        return queryset
    
    def filter_invoice_number(self, queryset, name, value):
        """Filter by invoice number."""
        if value:
            return queryset.filter(invoice_number__icontains=value)
        return queryset
    
    def filter_description(self, queryset, name, value):
        """Filter by description."""
        if value:
            return queryset.filter(description__icontains=value)
        return queryset
    
    def filter_tenant_plan(self, queryset, name, value):
        """Filter by tenant plan."""
        if value:
            return queryset.filter(tenant__plan=value)
        return queryset


class TenantAuditLogFilter(django_filters.FilterSet):
    """
    Filter for TenantAuditLog model.
    
    Provides filtering by action, user, date, and other audit attributes.
    """
    
    # Action filters
    action = django_filters.ChoiceFilter(
        choices=AuditActionChoices.choices(),
        method='filter_action',
        label=_('Action')
    )
    
    # Date filters
    created_at = django_filters.DateFromToRangeFilter(
        method='filter_created_at',
        label=_('Creation Date Range')
    )
    
    created_at_gte = django_filters.DateFilter(
        method='filter_created_at_gte',
        label=_('Created After')
    )
    
    created_at_lte = django_filters.DateFilter(
        method='filter_created_at_lte',
        label=_('Created Before')
    )
    
    # User filters
    user = django_filters.CharFilter(
        method='filter_user',
        label=_('User Email')
    )
    
    user_email = django_filters.CharFilter(
        method='filter_user_email',
        label=_('User Email')
    )
    
    user_role = django_filters.CharFilter(
        method='filter_user_role',
        label=_('User Role')
    )
    
    has_user = django_filters.BooleanFilter(
        method='filter_has_user',
        label=_('Has User')
    )
    
    # IP address filters
    ip_address = django_filters.CharFilter(
        method='filter_ip_address',
        label=_('IP Address')
    )
    
    # Request filters
    request_id = django_filters.CharFilter(
        method='filter_request_id',
        label=_('Request ID')
    )
    
    # Geographic filters
    country = django_filters.CharFilter(
        method='filter_country',
        label=_('Country')
    )
    
    city = django_filters.CharFilter(
        method='filter_city',
        label=_('City')
    )
    
    # Success filters
    success = django_filters.BooleanFilter(
        method='filter_success',
        label=_('Success')
    )
    
    # Error filters
    has_error = django_filters.BooleanFilter(
        method='filter_has_error',
        label=_('Has Error')
    )
    
    error_message = django_filters.CharFilter(
        method='filter_error_message',
        label=_('Error Message')
    )
    
    # Details filters
    search_details = django_filters.CharFilter(
        method='filter_search_details',
        label=_('Search Details')
    )
    
    # Tenant filters
    tenant_plan = django_filters.ChoiceFilter(
        choices=TenantPlanChoices.choices(),
        method='filter_tenant_plan',
        label=_('Tenant Plan')
    )
    
    tenant_status = django_filters.ChoiceFilter(
        choices=TenantStatusChoices.choices(),
        method='filter_tenant_status',
        label=_('Tenant Status')
    )
    
    class Meta:
        model = TenantAuditLog
        fields = []
    
    def filter_action(self, queryset, name, value):
        """Filter by action."""
        if value:
            return queryset.filter(action=value)
        return queryset
    
    def filter_created_at(self, queryset, name, value):
        """Filter by creation date range."""
        if value:
            if value.start:
                queryset = queryset.filter(created_at__date__gte=value.start)
            if value.stop:
                queryset = queryset.filter(created_at__date__lte=value.stop)
        return queryset
    
    def filter_created_at_gte(self, queryset, name, value):
        """Filter by creation date (greater than or equal)."""
        if value:
            return queryset.filter(created_at__date__gte=value)
        return queryset
    
    def filter_created_at_lte(self, queryset, name, value):
        """Filter by creation date (less than or equal)."""
        if value:
            return queryset.filter(created_at__date__lte=value)
        return queryset
    
    def filter_user(self, queryset, name, value):
        """Filter by user."""
        if value:
            return queryset.filter(
                Q(user__email__icontains=value) |
                Q(user_email__icontains=value)
            )
        return queryset
    
    def filter_user_email(self, queryset, name, value):
        """Filter by user email."""
        if value:
            return queryset.filter(user_email__icontains=value)
        return queryset
    
    def filter_user_role(self, queryset, name, value):
        """Filter by user role."""
        if value:
            return queryset.filter(user_role__icontains=value)
        return queryset
    
    def filter_has_user(self, queryset, name, value):
        """Filter by user presence."""
        if value is not None:
            if value:
                return queryset.filter(user__isnull=False)
            else:
                return queryset.filter(user__isnull=True)
        return queryset
    
    def filter_ip_address(self, queryset, name, value):
        """Filter by IP address."""
        if value:
            return queryset.filter(ip_address__icontains=value)
        return queryset
    
    def filter_request_id(self, queryset, name, value):
        """Filter by request ID."""
        if value:
            return queryset.filter(request_id__icontains=value)
        return queryset
    
    def filter_country(self, queryset, name, value):
        """Filter by country."""
        if value:
            return queryset.filter(country__icontains=value)
        return queryset
    
    def filter_city(self, queryset, name, value):
        """Filter by city."""
        if value:
            return queryset.filter(city__icontains=value)
        return queryset
    
    def filter_success(self, queryset, name, value):
        """Filter by success status."""
        if value is not None:
            return queryset.filter(success=value)
        return queryset
    
    def filter_has_error(self, queryset, name, value):
        """Filter by error presence."""
        if value is not None:
            if value:
                return queryset.filter(error_message__isnull=False).exclude(error_message='')
            else:
                return queryset.filter(Q(error_message__isnull=True) | Q(error_message=''))
        return queryset
    
    def filter_error_message(self, queryset, name, value):
        """Filter by error message."""
        if value:
            return queryset.filter(error_message__icontains=value)
        return queryset
    
    def filter_search_details(self, queryset, name, value):
        """Search in details JSON field."""
        if value:
            return queryset.filter(details__icontains=value)
        return queryset
    
    def filter_tenant_plan(self, queryset, name, value):
        """Filter by tenant plan."""
        if value:
            return queryset.filter(tenant__plan=value)
        return queryset
    
    def filter_tenant_status(self, queryset, name, value):
        """Filter by tenant status."""
        if value:
            return queryset.filter(tenant__status=value)
        return queryset


# Custom filter backends for DRF
class TenantSearchFilter(filters.SearchFilter):
    """
    Custom search filter for tenant-related models.
    """
    
    def get_search_fields(self, view, request):
        """
        Get search fields based on the model.
        """
        model = view.queryset.model
        
        if model == Tenant:
            return ['name', 'slug', 'admin_email', 'domain', 'owner__email']
        elif model == TenantInvoice:
            return ['invoice_number', 'description', 'transaction_id', 'payment_method']
        elif model == TenantAuditLog:
            return ['action', 'user_email', 'ip_address', 'error_message']
        
        return super().get_search_fields(view, request)


class TenantOrderingFilter(filters.OrderingFilter):
    """
    Custom ordering filter for tenant-related models.
    """
    
    def get_valid_fields(self, queryset, view, context):
        """
        Get valid fields for ordering based on the model.
        """
        model = queryset.model
        
        if model == Tenant:
            return [
                'name', 'slug', 'created_at', 'updated_at', 'plan', 'status',
                'max_users', 'trial_ends_at', 'admin_email', 'domain'
            ]
        elif model == TenantInvoice:
            return [
                'invoice_number', 'created_at', 'issue_date', 'due_date',
                'amount', 'total_amount', 'status', 'paid_at'
            ]
        elif model == TenantAuditLog:
            return [
                'created_at', 'action', 'user_email', 'success', 'ip_address'
            ]
        
        return super().get_valid_fields(queryset, view, context)
