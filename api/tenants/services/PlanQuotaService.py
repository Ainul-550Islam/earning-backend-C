"""
Plan Quota Service

This module provides business logic for managing plan quotas
including quota enforcement, monitoring, and alerts.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Count
from ..models.plan import PlanQuota, PlanUsage
from ..models.core import Tenant
from .base import BaseService


class PlanQuotaService(BaseService):
    """
    Service class for managing plan quotas.
    
    Provides business logic for quota operations including:
    - Quota enforcement and validation
    - Usage tracking and monitoring
    - Quota alerts and notifications
    - Quota management and adjustments
    """
    
    @staticmethod
    def create_quota(plan, quota_data):
        """
        Create a new quota for a plan.
        
        Args:
            plan (Plan): Plan to add quota to
            quota_data (dict): Quota data
            
        Returns:
            PlanQuota: Created quota
            
        Raises:
            ValidationError: If quota data is invalid
        """
        try:
            with transaction.atomic():
                # Validate quota data
                PlanQuotaService._validate_quota_data(quota_data, plan)
                
                # Check for duplicate quotas
                if PlanQuota.objects.filter(
                    plan=plan,
                    quota_key=quota_data.get('quota_key')
                ).exists():
                    raise ValidationError(_('Quota already exists for this plan'))
                
                # Create quota
                quota = PlanQuota.objects.create(
                    plan=plan,
                    quota_key=quota_data['quota_key'],
                    quota_name=quota_data.get('quota_name', quota_data['quota_key']),
                    quota_type=quota_data.get('quota_type', 'numeric'),
                    limit_value=quota_data.get('limit_value', 0),
                    period=quota_data.get('period', 'monthly'),
                    is_active=quota_data.get('is_active', True),
                    is_hard_limit=quota_data.get('is_hard_limit', True),
                    alert_threshold=quota_data.get('alert_threshold', 80),
                    reset_day=quota_data.get('reset_day', 1),
                    description=quota_data.get('description', ''),
                    metadata=quota_data.get('metadata', {})
                )
                
                return quota
                
        except Exception as e:
            raise ValidationError(f"Failed to create quota: {str(e)}")
    
    @staticmethod
    def update_quota(quota, quota_data):
        """
        Update an existing quota.
        
        Args:
            quota (PlanQuota): Quota to update
            quota_data (dict): Updated quota data
            
        Returns:
            PlanQuota: Updated quota
            
        Raises:
            ValidationError: If quota data is invalid
        """
        try:
            with transaction.atomic():
                # Validate quota data
                PlanQuotaService._validate_quota_data(quota_data, quota.plan, update=True)
                
                # Update quota fields
                for field, value in quota_data.items():
                    if hasattr(quota, field) and field not in ['id', 'plan', 'created_at']:
                        setattr(quota, field, value)
                
                quota.save()
                return quota
                
        except Exception as e:
            raise ValidationError(f"Failed to update quota: {str(e)}")
    
    @staticmethod
    def check_quota_usage(tenant, quota_key, usage_amount=1):
        """
        Check if tenant has sufficient quota for a request.
        
        Args:
            tenant (Tenant): Tenant to check quota for
            quota_key (str): Quota key to check
            usage_amount (int): Amount of usage to check
            
        Returns:
            dict: Quota check result
        """
        try:
            # Get quota for tenant's plan
            quota = PlanQuotaService._get_tenant_quota(tenant, quota_key)
            
            if not quota:
                return {
                    'allowed': True,
                    'reason': 'No quota limit found',
                    'quota': None,
                    'current_usage': 0,
                    'remaining': None
                }
            
            if not quota.is_active:
                return {
                    'allowed': True,
                    'reason': 'Quota is not active',
                    'quota': quota,
                    'current_usage': 0,
                    'remaining': quota.limit_value
                }
            
            # Get current usage
            current_usage = PlanQuotaService._get_current_usage(tenant, quota)
            
            # Check if usage would exceed limit
            if quota.is_hard_limit and (current_usage + usage_amount) > quota.limit_value:
                return {
                    'allowed': False,
                    'reason': f'Quota limit exceeded ({current_usage + usage_amount} > {quota.limit_value})',
                    'quota': quota,
                    'current_usage': current_usage,
                    'remaining': max(0, quota.limit_value - current_usage)
                }
            
            # Check alert threshold
            remaining = quota.limit_value - (current_usage + usage_amount)
            usage_percentage = ((current_usage + usage_amount) / quota.limit_value) * 100
            
            return {
                'allowed': True,
                'reason': 'Quota available',
                'quota': quota,
                'current_usage': current_usage,
                'remaining': remaining,
                'usage_percentage': usage_percentage,
                'alert_threshold_exceeded': usage_percentage >= quota.alert_threshold
            }
            
        except Exception as e:
            # If there's an error, allow the request but log it
            return {
                'allowed': True,
                'reason': f'Error checking quota: {str(e)}',
                'quota': None,
                'current_usage': 0,
                'remaining': None
            }
    
    @staticmethod
    def record_usage(tenant, quota_key, usage_amount, metadata=None):
        """
        Record usage against a quota.
        
        Args:
            tenant (Tenant): Tenant to record usage for
            quota_key (str): Quota key to record usage against
            usage_amount (int): Amount of usage to record
            metadata (dict): Additional metadata
            
        Returns:
            dict: Usage recording result
        """
        try:
            with transaction.atomic():
                # Get quota for tenant's plan
                quota = PlanQuotaService._get_tenant_quota(tenant, quota_key)
                
                if not quota:
                    return {
                        'success': True,
                        'reason': 'No quota limit found',
                        'quota': None
                    }
                
                # Get or create usage record
                usage, created = PlanUsage.objects.get_or_create(
                    tenant=tenant,
                    period=quota.period,
                    quota_key=quota_key,
                    defaults={
                        'usage_value': 0,
                        'limit_value': quota.limit_value,
                        'reset_date': PlanQuotaService._get_next_reset_date(quota)
                    }
                )
                
                # Update usage
                usage.usage_value += usage_amount
                usage.limit_value = quota.limit_value
                usage.usage_percentage = (usage.usage_value / quota.limit_value) * 100 if quota.limit_value > 0 else 0
                usage.last_used_at = timezone.now()
                usage.metadata = metadata or {}
                usage.save()
                
                return {
                    'success': True,
                    'reason': 'Usage recorded successfully',
                    'quota': quota,
                    'usage': usage
                }
                
        except Exception as e:
            return {
                'success': False,
                'reason': f'Failed to record usage: {str(e)}',
                'quota': None
            }
    
    @staticmethod
    def get_quota_usage(tenant, quota_key=None, period=None):
        """
        Get quota usage information for a tenant.
        
        Args:
            tenant (Tenant): Tenant to get usage for
            quota_key (str): Specific quota key (optional)
            period (str): Specific period (optional)
            
        Returns:
            dict: Quota usage information
        """
        try:
            queryset = PlanUsage.objects.filter(tenant=tenant)
            
            if quota_key:
                queryset = queryset.filter(quota_key=quota_key)
            
            if period:
                queryset = queryset.filter(period=period)
            
            usage_data = {}
            for usage in queryset:
                quota = PlanQuotaService._get_tenant_quota(tenant, usage.quota_key)
                
                usage_data[usage.quota_key] = {
                    'quota': quota,
                    'usage': usage,
                    'current_usage': usage.usage_value,
                    'limit_value': usage.limit_value,
                    'usage_percentage': usage.usage_percentage,
                    'remaining': max(0, quota.limit_value - usage.usage_value) if quota else None,
                    'over_limit': usage.usage_value > quota.limit_value if quota else False,
                    'alert_threshold_exceeded': usage.usage_percentage >= (quota.alert_threshold if quota else 80)
                }
            
            return usage_data
            
        except Exception as e:
            return {}
    
    @staticmethod
    def reset_quota_usage(tenant, quota_key=None, period=None):
        """
        Reset quota usage for a tenant.
        
        Args:
            tenant (Tenant): Tenant to reset usage for
            quota_key (str): Specific quota key (optional)
            period (str): Specific period (optional)
            
        Returns:
            int: Number of usage records reset
        """
        try:
            with transaction.atomic():
                queryset = PlanUsage.objects.filter(tenant=tenant)
                
                if quota_key:
                    queryset = queryset.filter(quota_key=quota_key)
                
                if period:
                    queryset = queryset.filter(period=period)
                
                count = queryset.count()
                queryset.update(usage_value=0, usage_percentage=0, last_used_at=None)
                
                return count
                
        except Exception as e:
            raise ValidationError(f"Failed to reset quota usage: {str(e)}")
    
    @staticmethod
    def get_quota_alerts(tenant=None):
        """
        Get quota alerts for tenants.
        
        Args:
            tenant (Tenant): Specific tenant (optional)
            
        Returns:
            list: Quota alerts
        """
        alerts = []
        
        try:
            queryset = PlanUsage.objects.all()
            if tenant:
                queryset = queryset.filter(tenant=tenant)
            
            for usage in queryset:
                quota = PlanQuotaService._get_tenant_quota(usage.tenant, usage.quota_key)
                
                if not quota or not quota.is_active:
                    continue
                
                # Check for over limit
                if usage.usage_value > quota.limit_value:
                    alerts.append({
                        'type': 'over_limit',
                        'tenant': usage.tenant,
                        'quota_key': usage.quota_key,
                        'current_usage': usage.usage_value,
                        'limit_value': quota.limit_value,
                        'percentage': usage.usage_percentage,
                        'severity': 'critical' if quota.is_hard_limit else 'warning'
                    })
                
                # Check for alert threshold
                elif usage.usage_percentage >= quota.alert_threshold:
                    alerts.append({
                        'type': 'threshold_warning',
                        'tenant': usage.tenant,
                        'quota_key': usage.quota_key,
                        'current_usage': usage.usage_value,
                        'limit_value': quota.limit_value,
                        'percentage': usage.usage_percentage,
                        'threshold': quota.alert_threshold,
                        'severity': 'warning'
                    })
            
            return alerts
            
        except Exception as e:
            return []
    
    @staticmethod
    def get_quota_statistics(plan=None, period=None):
        """
        Get quota statistics.
        
        Args:
            plan (Plan): Specific plan (optional)
            period (str): Specific period (optional)
            
        Returns:
            dict: Quota statistics
        """
        try:
            queryset = PlanQuota.objects.all()
            if plan:
                queryset = queryset.filter(plan=plan)
            
            stats = {
                'total_quotas': queryset.count(),
                'active_quotas': queryset.filter(is_active=True).count(),
                'hard_limits': queryset.filter(is_hard_limit=True).count(),
                'soft_limits': queryset.filter(is_hard_limit=False).count(),
                'quotas_by_type': {},
                'quotas_by_period': {},
                'usage_summary': {}
            }
            
            # Count by type
            for quota_type in ['numeric', 'boolean', 'text']:
                stats['quotas_by_type'][quota_type] = queryset.filter(
                    quota_type=quota_type
                ).count()
            
            # Count by period
            for period_type in ['daily', 'weekly', 'monthly', 'yearly']:
                stats['quotas_by_period'][period_type] = queryset.filter(
                    period=period_type
                ).count()
            
            # Usage summary
            usage_queryset = PlanUsage.objects.all()
            if period:
                usage_queryset = usage_queryset.filter(period=period)
            
            stats['usage_summary'] = {
                'total_usage_records': usage_queryset.count(),
                'total_usage_value': usage_queryset.aggregate(
                    total=Sum('usage_value')
                )['total'] or 0,
                'over_limit_usage': usage_queryset.filter(
                    usage_value__gt=models.F('limit_value')
                ).count(),
                'tenants_with_usage': usage_queryset.values('tenant').distinct().count()
            }
            
            return stats
            
        except Exception as e:
            return {}
    
    @staticmethod
    def _get_tenant_quota(tenant, quota_key):
        """
        Get quota for a tenant's plan.
        
        Args:
            tenant (Tenant): Tenant to get quota for
            quota_key (str): Quota key
            
        Returns:
            PlanQuota or None: Quota if found
        """
        try:
            return PlanQuota.objects.get(
                plan=tenant.plan,
                quota_key=quota_key,
                is_active=True
            )
        except PlanQuota.DoesNotExist:
            return None
    
    @staticmethod
    def _get_current_usage(tenant, quota):
        """
        Get current usage for a quota.
        
        Args:
            tenant (Tenant): Tenant to get usage for
            quota (PlanQuota): Quota to check
            
        Returns:
            int: Current usage value
        """
        try:
            usage = PlanUsage.objects.get(
                tenant=tenant,
                quota_key=quota.quota_key,
                period=quota.period
            )
            return usage.usage_value
        except PlanUsage.DoesNotExist:
            return 0
    
    @staticmethod
    def _get_next_reset_date(quota):
        """
        Get next reset date for a quota.
        
        Args:
            quota (PlanQuota): Quota to get reset date for
            
        Returns:
            datetime: Next reset date
        """
        now = timezone.now()
        
        if quota.period == 'daily':
            return now.replace(hour=0, minute=0, second=0, microsecond=0) + timezone.timedelta(days=1)
        elif quota.period == 'weekly':
            days_until_monday = (7 - now.weekday()) % 7 or 7
            return (now + timezone.timedelta(days=days_until_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif quota.period == 'monthly':
            if now.day >= quota.reset_day:
                # Next month
                if now.month == 12:
                    return now.replace(year=now.year + 1, month=1, day=quota.reset_day, hour=0, minute=0, second=0, microsecond=0)
                else:
                    return now.replace(month=now.month + 1, day=quota.reset_day, hour=0, minute=0, second=0, microsecond=0)
            else:
                # This month
                return now.replace(day=quota.reset_day, hour=0, minute=0, second=0, microsecond=0)
        elif quota.period == 'yearly':
            return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0) + timezone.timedelta(years=1)
        
        return now + timezone.timedelta(days=30)
    
    @staticmethod
    def _validate_quota_data(quota_data, plan, update=False):
        """
        Validate quota data.
        
        Args:
            quota_data (dict): Quota data to validate
            plan (Plan): Plan the quota belongs to
            update (bool): Whether this is an update operation
            
        Raises:
            ValidationError: If validation fails
        """
        required_fields = ['quota_key', 'limit_value']
        if not update:
            required_fields.extend(['quota_name'])
        
        for field in required_fields:
            if field not in quota_data:
                raise ValidationError(f"'{field}' is required")
        
        # Validate quota key format
        quota_key = quota_data['quota_key']
        if not isinstance(quota_key, str) or not quota_key.strip():
            raise ValidationError("Quota key must be a non-empty string")
        
        # Validate quota type
        quota_type = quota_data.get('quota_type', 'numeric')
        valid_types = ['numeric', 'boolean', 'text']
        if quota_type not in valid_types:
            raise ValidationError(f"Quota type must be one of: {', '.join(valid_types)}")
        
        # Validate limit value
        limit_value = quota_data['limit_value']
        if quota_type == 'numeric' and not isinstance(limit_value, (int, float)):
            raise ValidationError("Numeric quota limit must be a number")
        elif quota_type == 'boolean' and not isinstance(limit_value, bool):
            raise ValidationError("Boolean quota limit must be True or False")
        
        # Validate period
        period = quota_data.get('period', 'monthly')
        valid_periods = ['daily', 'weekly', 'monthly', 'yearly']
        if period not in valid_periods:
            raise ValidationError(f"Period must be one of: {', '.join(valid_periods)}")
        
        # Validate alert threshold
        alert_threshold = quota_data.get('alert_threshold', 80)
        if not isinstance(alert_threshold, (int, float)) or alert_threshold < 0 or alert_threshold > 100:
            raise ValidationError("Alert threshold must be a number between 0 and 100")
        
        # Validate reset day for monthly periods
        if period == 'monthly':
            reset_day = quota_data.get('reset_day', 1)
            if not isinstance(reset_day, int) or reset_day < 1 or reset_day > 31:
                raise ValidationError("Reset day must be an integer between 1 and 31")
