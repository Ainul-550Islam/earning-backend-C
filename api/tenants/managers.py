"""
Tenant Managers - Custom Django Model Managers

This module contains custom model managers for tenant-related models
with advanced query methods, optimizations, and business logic.
"""

from django.db import models
from django.db.models import Q, Count, Sum, Avg, Max, Min, Prefetch
from django.db.models.functions import Coalesce, TruncDate, TruncHour
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, QuerySet
import logging

from .constants import TENANT_CACHE_TIMEOUT
from .choices import TenantPlanChoices, TenantStatusChoices, BillingStatusChoices

logger = logging.getLogger(__name__)


class TenantManager(models.Manager):
    """
    Custom manager for Tenant model with advanced query methods.
    
    Provides optimized queries for tenant operations including
    filtering, aggregation, and performance optimizations.
    """
    
    def get_queryset(self) -> QuerySet:
        """Get base queryset with common optimizations."""
        return super().get_queryset().select_related('owner').prefetch_related(
            'users',
            'tenantbilling',
            'tenantsettings'
        )
    
    def active(self) -> QuerySet:
        """Get active tenants."""
        return self.get_queryset().filter(
            is_active=True,
            is_deleted=False
        )
    
    def suspended(self) -> QuerySet:
        """Get suspended tenants."""
        return self.get_queryset().filter(
            is_active=True,
            is_deleted=False,
            is_suspended=True
        )
    
    def trial_active(self) -> QuerySet:
        """Get tenants with active trials."""
        return self.get_queryset().filter(
            is_active=True,
            is_deleted=False,
            trial_ends_at__gt=timezone.now(),
            status='trial'
        )
    
    def trial_expired(self) -> QuerySet:
        """Get tenants with expired trials."""
        return self.get_queryset().filter(
            is_active=True,
            is_deleted=False,
            trial_ends_at__lt=timezone.now(),
            status='trial'
        )
    
    def by_plan(self, plan: str) -> QuerySet:
        """Get tenants by subscription plan."""
        return self.get_queryset().filter(plan=plan)
    
    def by_status(self, status: str) -> QuerySet:
        """Get tenants by status."""
        return self.get_queryset().filter(status=status)
    
    def by_country(self, country_code: str) -> QuerySet:
        """Get tenants by country code."""
        return self.get_queryset().filter(country_code__iexact=country_code)
    
    def by_currency(self, currency: str) -> QuerySet:
        """Get tenants by currency."""
        return self.get_queryset().filter(currency_code__iexact=currency)
    
    def with_user_counts(self) -> QuerySet:
        """Get tenants with user count annotations."""
        return self.get_queryset().annotate(
            total_users=Count('users', filter=Q(users__is_active=True)),
            active_users=Count('users', filter=Q(users__is_active=True, users__last_login__isnull=False)),
            new_users=Count('users', filter=Q(users__is_active=True, users__created_at__gte=timezone.now() - timedelta(days=30)))
        )
    
    def with_billing_info(self) -> QuerySet:
        """Get tenants with billing information."""
        return self.get_queryset().select_related('tenantbilling')
    
    def with_settings(self) -> QuerySet:
        """Get tenants with settings."""
        return self.get_queryset().select_related('tenantsettings')
    
    def with_usage_stats(self) -> QuerySet:
        """Get tenants with usage statistics."""
        return self.with_user_counts().annotate(
            storage_usage=Sum('users__file_size', filter=Q(users__is_active=True)),
            api_calls=Count('users__apicall', filter=Q(users__is_active=True)),
            last_activity=Max('users__last_login', filter=Q(users__is_active=True))
        )
    
    def search(self, query: str) -> QuerySet:
        """Search tenants across multiple fields."""
        return self.get_queryset().filter(
            Q(name__icontains=query) |
            Q(slug__icontains=query) |
            Q(admin_email__icontains=query) |
            Q(domain__icontains=query) |
            Q(owner__email__icontains=query)
        )
    
    def by_owner(self, owner_id: int) -> QuerySet:
        """Get tenants by owner ID."""
        return self.get_queryset().filter(owner_id=owner_id)
    
    def by_domain(self, domain: str) -> QuerySet:
        """Get tenants by domain."""
        return self.get_queryset().filter(domain__iexact=domain)
    
    def with_subscriptions(self) -> QuerySet:
        """Get tenants with subscription information."""
        return self.get_queryset().filter(
            tenantbilling__status='active'
        ).select_related('tenantbilling')
    
    def without_subscriptions(self) -> QuerySet:
        """Get tenants without active subscriptions."""
        return self.get_queryset().exclude(
            tenantbilling__status='active'
        )
    
    def expiring_trials(self, days: int = 7) -> QuerySet:
        """Get tenants with trials expiring soon."""
        cutoff_date = timezone.now() + timedelta(days=days)
        return self.get_queryset().filter(
            trial_ends_at__lte=cutoff_date,
            trial_ends_at__gt=timezone.now(),
            status='trial'
        )
    
    def overdue_trials(self) -> QuerySet:
        """Get tenants with overdue trials."""
        return self.get_queryset().filter(
            trial_ends_at__lt=timezone.now(),
            status='trial'
        )
    
    def user_limit_reached(self) -> QuerySet:
        """Get tenants that have reached their user limit."""
        tenants = []
        for tenant in self.with_user_counts():
            if tenant.is_user_limit_reached():
                tenants.append(tenant.id)
        return self.get_queryset().filter(id__in=tenants)
    
    def approaching_user_limit(self, threshold: float = 0.9) -> QuerySet:
        """Get tenants approaching their user limit."""
        tenants = []
        for tenant in self.with_user_counts():
            if tenant.user_usage_percentage >= threshold:
                tenants.append(tenant.id)
        return self.get_queryset().filter(id__in=tenants)
    
    def by_creation_date_range(self, start_date: datetime, end_date: datetime) -> QuerySet:
        """Get tenants by creation date range."""
        return self.get_queryset().filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
    
    def by_trial_end_date_range(self, start_date: datetime, end_date: datetime) -> QuerySet:
        """Get tenants by trial end date range."""
        return self.get_queryset().filter(
            trial_ends_at__date__gte=start_date,
            trial_ends_at__date__lte=end_date
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get tenant statistics."""
        cache_key = 'tenant_statistics'
        stats = cache.get(cache_key)
        
        if not stats:
            stats = {
                'total_tenants': self.get_queryset().count(),
                'active_tenants': self.active().count(),
                'suspended_tenants': self.suspended().count(),
                'trial_tenants': self.trial_active().count(),
                'expired_trials': self.trial_expired().count(),
                'by_plan': {},
                'by_status': {},
                'by_country': {},
                'new_this_month': self.get_queryset().filter(
                    created_at__gte=timezone.now() - timedelta(days=30)
                ).count(),
                'user_limit_reached': self.user_limit_reached().count(),
            }
            
            # Plan statistics
            for plan_choice in TenantPlanChoices:
                stats['by_plan'][plan_choice.value] = self.by_plan(plan_choice.value).count()
            
            # Status statistics
            for status_choice in TenantStatusChoices:
                stats['by_status'][status_choice.value] = self.by_status(status_choice.value).count()
            
            # Country statistics (top 10)
            country_stats = self.get_queryset().values('country_code').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            stats['by_country'] = {item['country_code']: item['count'] for item in country_stats}
            
            cache.set(cache_key, stats, timeout=TENANT_CACHE_TIMEOUT)
        
        return stats
    
    def get_growth_data(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get tenant growth data over time."""
        cache_key = f'tenant_growth_{days}'
        growth_data = cache.get(cache_key)
        
        if not growth_data:
            start_date = timezone.now() - timedelta(days=days)
            
            # Get daily tenant creation counts
            daily_data = self.get_queryset().filter(
                created_at__gte=start_date
            ).annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                count=Count('id')
            ).order_by('date')
            
            # Fill missing dates with zero
            growth_data = []
            current_date = start_date.date()
            end_date = timezone.now().date()
            
            daily_dict = {item['date']: item['count'] for item in daily_data}
            
            while current_date <= end_date:
                growth_data.append({
                    'date': current_date.isoformat(),
                    'count': daily_dict.get(current_date, 0),
                    'cumulative': self.get_queryset().filter(
                        created_at__date__lte=current_date
                    ).count()
                })
                current_date += timedelta(days=1)
            
            cache.set(cache_key, growth_data, timeout=TENANT_CACHE_TIMEOUT)
        
        return growth_data
    
    def get_top_performers(self, metric: str = 'users', limit: int = 10) -> QuerySet:
        """Get top performing tenants by metric."""
        if metric == 'users':
            return self.with_user_counts().order_by('-total_users')[:limit]
        elif metric == 'revenue':
            return self.get_queryset().annotate(
                total_revenue=Sum('tenantinvoice__total_amount', filter=Q(tenantinvoice__status='paid'))
            ).order_by('-total_revenue')[:limit]
        elif metric == 'activity':
            return self.get_queryset().annotate(
                activity_score=Count('users__apicall', filter=Q(users__is_active=True))
            ).order_by('-activity_score')[:limit]
        
        return self.get_queryset()[:limit]
    
    def get_inactive_tenants(self, days: int = 30) -> QuerySet:
        """Get tenants with no recent activity."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.get_queryset().filter(
            Q(users__last_login__lt=cutoff_date) |
            Q(users__last_login__isnull=True)
        ).distinct()
    
    def get_high_usage_tenants(self, metric: str = 'users', threshold: float = 0.8) -> QuerySet:
        """Get tenants with high usage."""
        if metric == 'users':
            return self.approaching_user_limit(threshold)
        elif metric == 'storage':
            # This would require storage tracking implementation
            return self.get_queryset()
        
        return self.get_queryset()
    
    def bulk_update_status(self, tenant_ids: List[int], status: str) -> int:
        """Bulk update tenant status."""
        return self.get_queryset().filter(id__in=tenant_ids).update(status=status)
    
    def bulk_suspend(self, tenant_ids: List[int]) -> int:
        """Bulk suspend tenants."""
        return self.get_queryset().filter(id__in=tenant_ids).update(
            is_suspended=True,
            status='suspended'
        )
    
    def bulk_activate(self, tenant_ids: List[int]) -> int:
        """Bulk activate tenants."""
        return self.get_queryset().filter(id__in=tenant_ids).update(
            is_suspended=False,
            status='active'
        )


class TenantSettingsManager(models.Manager):
    """
    Custom manager for TenantSettings model.
    """
    
    def get_queryset(self) -> QuerySet:
        """Get base queryset with optimizations."""
        return super().get_queryset().select_related('tenant')
    
    def with_feature_flags(self) -> QuerySet:
        """Get settings with feature flag annotations."""
        return self.get_queryset().annotate(
            enabled_features=Count(
                'id',
                filter=Q(
                    Q(enable_referral=True) |
                    Q(enable_offerwall=True) |
                    Q(enable_kyc=True) |
                    Q(enable_leaderboard=True) |
                    Q(enable_chat=True) |
                    Q(enable_push_notifications=True) |
                    Q(enable_analytics=True) |
                    Q(enable_api_access=True)
                )
            )
        )
    
    def by_feature(self, feature: str) -> QuerySet:
        """Get settings with specific feature enabled."""
        feature_filter = {feature: True}
        return self.get_queryset().filter(**feature_filter)
    
    def by_withdrawal_limits(self, min_amount: float = None, max_amount: float = None) -> QuerySet:
        """Get settings by withdrawal limits."""
        queryset = self.get_queryset()
        
        if min_amount:
            queryset = queryset.filter(min_withdrawal__gte=min_amount)
        if max_amount:
            queryset = queryset.filter(max_withdrawal__lte=max_amount)
        
        return queryset
    
    def by_fee_settings(self, fee_percent_min: float = None, fee_percent_max: float = None) -> QuerySet:
        """Get settings by fee configuration."""
        queryset = self.get_queryset()
        
        if fee_percent_min:
            queryset = queryset.filter(withdrawal_fee_percent__gte=fee_percent_min)
        if fee_percent_max:
            queryset = queryset.filter(withdrawal_fee_percent__lte=fee_percent_max)
        
        return queryset
    
    def with_security_settings(self) -> QuerySet:
        """Get settings with security annotations."""
        return self.get_queryset().annotate(
            security_level=Count(
                'id',
                filter=Q(
                    Q(require_email_verification=True) |
                    Q(require_phone_verification=True) |
                    Q(enable_two_factor_auth=True)
                )
            )
        )


class TenantBillingManager(models.Manager):
    """
    Custom manager for TenantBilling model.
    """
    
    def get_queryset(self) -> QuerySet:
        """Get base queryset with optimizations."""
        return super().get_queryset().select_related('tenant')
    
    def active(self) -> QuerySet:
        """Get active billing records."""
        return self.get_queryset().filter(status='active')
    
    def trial(self) -> QuerySet:
        """Get trial billing records."""
        return self.get_queryset().filter(status='trial')
    
    def past_due(self) -> QuerySet:
        """Get past due billing records."""
        return self.get_queryset().filter(status='past_due')
    
    def cancelled(self) -> QuerySet:
        """Get cancelled billing records."""
        return self.get_queryset().filter(status='cancelled')
    
    def by_status(self, status: str) -> QuerySet:
        """Get billing records by status."""
        return self.get_queryset().filter(status=status)
    
    def by_cycle(self, cycle: str) -> QuerySet:
        """Get billing records by billing cycle."""
        return self.get_queryset().filter(billing_cycle=cycle)
    
    def by_currency(self, currency: str) -> QuerySet:
        """Get billing records by currency."""
        return self.get_queryset().filter(currency__iexact=currency)
    
    def expiring_subscriptions(self, days: int = 7) -> QuerySet:
        """Get subscriptions expiring soon."""
        cutoff_date = timezone.now() + timedelta(days=days)
        return self.get_queryset().filter(
            subscription_ends_at__lte=cutoff_date,
            subscription_ends_at__gt=timezone.now(),
            status='active'
        )
    
    def expired_subscriptions(self) -> QuerySet:
        """Get expired subscriptions."""
        return self.get_queryset().filter(
            subscription_ends_at__lt=timezone.now(),
            status='active'
        )
    
    def with_revenue(self) -> QuerySet:
        """Get billing with revenue annotations."""
        return self.get_queryset().annotate(
            total_revenue=Sum('tenantinvoice__total_amount', filter=Q(tenantinvoice__status='paid')),
            pending_revenue=Sum('tenantinvoice__total_amount', filter=Q(tenantinvoice__status='sent')),
            overdue_revenue=Sum('tenantinvoice__total_amount', filter=Q(tenantinvoice__status='overdue'))
        )
    
    def by_payment_method(self, payment_method: str) -> QuerySet:
        """Get billing records by payment method."""
        return self.get_queryset().filter(payment_method__icontains=payment_method)
    
    def with_payment_methods(self) -> QuerySet:
        """Get billing records with payment method annotations."""
        return self.get_queryset().annotate(
            has_payment_method=Count('payment_method', filter=Q(payment_method__isnull=False))
        )
    
    def get_revenue_statistics(self) -> Dict[str, Any]:
        """Get revenue statistics."""
        cache_key = 'billing_revenue_statistics'
        stats = cache.get(cache_key)
        
        if not stats:
            billing_with_revenue = self.with_revenue()
            
            stats = {
                'total_revenue': billing_with_revenue.aggregate(
                    total=Sum('total_revenue')
                )['total'] or 0,
                'pending_revenue': billing_with_revenue.aggregate(
                    total=Sum('pending_revenue')
                )['total'] or 0,
                'overdue_revenue': billing_with_revenue.aggregate(
                    total=Sum('overdue_revenue')
                )['total'] or 0,
                'by_status': {},
                'by_cycle': {},
                'by_currency': {},
                'mrr': self.calculate_mrr(),
                'arr': self.calculate_arr(),
            }
            
            # Status statistics
            for status_choice in BillingStatusChoices:
                stats['by_status'][status_choice.value] = self.by_status(status_choice.value).count()
            
            # Cycle statistics
            cycles = self.get_queryset().values('billing_cycle').annotate(
                count=Count('id')
            )
            stats['by_cycle'] = {item['billing_cycle']: item['count'] for item in cycles}
            
            # Currency statistics
            currencies = self.get_queryset().values('currency').annotate(
                count=Count('id')
            )
            stats['by_currency'] = {item['currency']: item['count'] for item in currencies}
            
            cache.set(cache_key, stats, timeout=TENANT_CACHE_TIMEOUT)
        
        return stats
    
    def calculate_mrr(self) -> float:
        """Calculate Monthly Recurring Revenue."""
        return self.get_queryset().filter(
            status='active',
            billing_cycle='monthly'
        ).aggregate(
            total=Sum('monthly_price')
        )['total'] or 0
    
    def calculate_arr(self) -> float:
        """Calculate Annual Recurring Revenue."""
        return self.get_queryset().filter(
            status='active'
        ).aggregate(
            total=Sum('monthly_price') * 12
        )['total'] or 0
    
    def get_churn_rate(self, days: int = 30) -> float:
        """Calculate churn rate for the period."""
        start_date = timezone.now() - timedelta(days=days)
        
        # Get customers at start of period
        customers_start = self.get_queryset().filter(
            created_at__lt=start_date,
            status='active'
        ).count()
        
        # Get customers who churned during period
        customers_churned = self.get_queryset().filter(
            status='cancelled',
            cancelled_at__gte=start_date
        ).count()
        
        if customers_start == 0:
            return 0.0
        
        return (customers_churned / customers_start) * 100


class TenantInvoiceManager(models.Manager):
    """
    Custom manager for TenantInvoice model.
    """
    
    def get_queryset(self) -> QuerySet:
        """Get base queryset with optimizations."""
        return super().get_queryset().select_related('tenant')
    
    def paid(self) -> QuerySet:
        """Get paid invoices."""
        return self.get_queryset().filter(status='paid')
    
    def unpaid(self) -> QuerySet:
        """Get unpaid invoices."""
        return self.get_queryset().filter(
            status__in=['draft', 'sent', 'overdue']
        )
    
    def overdue(self) -> QuerySet:
        """Get overdue invoices."""
        return self.get_queryset().filter(
            status='overdue',
            due_date__lt=timezone.now()
        )
    
    def by_status(self, status: str) -> QuerySet:
        """Get invoices by status."""
        return self.get_queryset().filter(status=status)
    
    def by_currency(self, currency: str) -> QuerySet:
        """Get invoices by currency."""
        return self.get_queryset().filter(currency__iexact=currency)
    
    def by_payment_method(self, payment_method: str) -> QuerySet:
        """Get invoices by payment method."""
        return self.get_queryset().filter(payment_method__icontains=payment_method)
    
    def by_date_range(self, start_date: datetime, end_date: datetime) -> QuerySet:
        """Get invoices by date range."""
        return self.get_queryset().filter(
            issue_date__gte=start_date,
            issue_date__lte=end_date
        )
    
    def due_soon(self, days: int = 7) -> QuerySet:
        """Get invoices due soon."""
        cutoff_date = timezone.now() + timedelta(days=days)
        return self.get_queryset().filter(
            due_date__lte=cutoff_date,
            due_date__gt=timezone.now(),
            status__in=['sent', 'overdue']
        )
    
    def by_amount_range(self, min_amount: float, max_amount: float) -> QuerySet:
        """Get invoices by amount range."""
        return self.get_queryset().filter(
            total_amount__gte=min_amount,
            total_amount__lte=max_amount
        )
    
    def with_age(self) -> QuerySet:
        """Get invoices with age annotations."""
        return self.get_queryset().annotate(
            age_days=Extract('created_at') - Extract(timezone.now().date()),
            days_overdue=Coalesce(
                Extract(timezone.now().date()) - Extract('due_date'),
                0
            )
        )
    
    def get_revenue_summary(self, start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """Get revenue summary for date range."""
        queryset = self.paid()
        
        if start_date:
            queryset = queryset.filter(paid_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(paid_at__lte=end_date)
        
        return queryset.aggregate(
            total_revenue=Sum('total_amount'),
            total_invoices=Count('id'),
            average_invoice=Avg('total_amount'),
            min_invoice=Min('total_amount'),
            max_invoice=Max('total_amount')
        )
    
    def get_outstanding_summary(self) -> Dict[str, Any]:
        """Get outstanding invoices summary."""
        return self.unpaid().aggregate(
            total_outstanding=Sum('total_amount'),
            total_invoices=Count('id'),
            overdue_amount=Sum('total_amount', filter=Q(status='overdue')),
            overdue_count=Count('id', filter=Q(status='overdue'))
        )


class TenantAuditLogManager(models.Manager):
    """
    Custom manager for TenantAuditLog model.
    """
    
    def get_queryset(self) -> QuerySet:
        """Get base queryset with optimizations."""
        return super().get_queryset().select_related('tenant', 'user')
    
    def by_action(self, action: str) -> QuerySet:
        """Get audit logs by action."""
        return self.get_queryset().filter(action=action)
    
    def by_user(self, user_id: int) -> QuerySet:
        """Get audit logs by user."""
        return self.get_queryset().filter(user_id=user_id)
    
    def by_ip_address(self, ip_address: str) -> QuerySet:
        """Get audit logs by IP address."""
        return self.get_queryset().filter(ip_address=ip_address)
    
    def by_date_range(self, start_date: datetime, end_date: datetime) -> QuerySet:
        """Get audit logs by date range."""
        return self.get_queryset().filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
    
    def recent(self, hours: int = 24) -> QuerySet:
        """Get recent audit logs."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(created_at__gte=cutoff_time)
    
    def security_events(self) -> QuerySet:
        """Get security-related audit logs."""
        security_actions = [
            'security_login_attempt',
            'security_file_uploaded',
            'security_rate_limit_exceeded',
            'login_attempt',
        ]
        return self.get_queryset().filter(action__in=security_actions)
    
    def failed_actions(self) -> QuerySet:
        """Get failed audit logs."""
        return self.get_queryset().filter(success=False)
    
    def successful_actions(self) -> QuerySet:
        """Get successful audit logs."""
        return self.get_queryset().filter(success=True)
    
    def by_request_id(self, request_id: str) -> QuerySet:
        """Get audit logs by request ID."""
        return self.get_queryset().filter(request_id=request_id)
    
    def with_user_info(self) -> QuerySet:
        """Get audit logs with user information."""
        return self.get_queryset().annotate(
            user_email=Coalesce('user__email', 'user_email'),
            user_role=Coalesce('user__role', 'user_role')
        )
    
    def get_activity_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get activity summary for time period."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        queryset = self.get_queryset().filter(created_at__gte=cutoff_time)
        
        return {
            'total_actions': queryset.count(),
            'successful_actions': queryset.filter(success=True).count(),
            'failed_actions': queryset.filter(success=False).count(),
            'unique_users': queryset.values('user_id').distinct().count(),
            'unique_ips': queryset.values('ip_address').distinct().count(),
            'by_action': dict(queryset.values('action').annotate(count=Count('id')).order_by('-count')[:10]),
            'security_events': queryset.filter(action__startswith='security').count(),
        }
    
    def get_security_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get security events summary."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        security_events = self.security_events().filter(created_at__gte=cutoff_time)
        
        return {
            'total_security_events': security_events.count(),
            'failed_logins': security_events.filter(action='login_attempt', success=False).count(),
            'successful_logins': security_events.filter(action='login_attempt', success=True).count(),
            'rate_limit_exceeded': security_events.filter(action='security_rate_limit_exceeded').count(),
            'file_uploads': security_events.filter(action='security_file_uploaded').count(),
            'by_ip': dict(security_events.values('ip_address').annotate(count=Count('id')).order_by('-count')[:10]),
        }
    
    def cleanup_old_logs(self, days: int = 90) -> int:
        """Clean up old audit logs."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.get_queryset().filter(created_at__lt=cutoff_date).delete()[0]


# Soft delete manager for Tenant model
class TenantSoftDeleteManager(TenantManager):
    """
    Manager that excludes soft-deleted tenants by default.
    """
    
    def get_queryset(self) -> QuerySet:
        """Get queryset excluding soft-deleted tenants."""
        return super().get_queryset().filter(is_deleted=False)
    
    def all_with_deleted(self) -> QuerySet:
        """Get all tenants including deleted ones."""
        return super(TenantSoftDeleteManager, self).get_queryset()
    
    def deleted(self) -> QuerySet:
        """Get only deleted tenants."""
        return super(TenantSoftDeleteManager, self).get_queryset().filter(is_deleted=True)
    
    def restore(self, tenant_id: int) -> int:
        """Restore a soft-deleted tenant."""
        return self.all_with_deleted().filter(id=tenant_id).update(is_deleted=False)
