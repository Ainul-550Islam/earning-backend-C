"""
Plan Usage Service

This service handles plan usage tracking, monitoring,
and enforcement for tenant subscription plans.
"""

from datetime import timedelta, date
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ..models import Tenant
from ..models.plan import PlanUsage, PlanQuota
from ..models.analytics import TenantMetric, TenantNotification
from ..models.security import TenantAuditLog

User = get_user_model()


class PlanUsageService:
    """
    Service class for plan usage operations.
    
    This service handles usage tracking, quota enforcement,
    and analytics for tenant subscription plans.
    """
    
    @staticmethod
    def track_usage(tenant, metric_type, value, period='daily', date=None):
        """
        Track usage for a specific metric.
        
        Args:
            tenant (Tenant): Tenant to track usage for
            metric_type (str): Type of metric (api_calls, storage, etc.)
            value (int/float): Usage value
            period (str): Period (daily, weekly, monthly, yearly)
            date (date): Date for the usage record
            
        Returns:
            PlanUsage: Created or updated usage record
        """
        if date is None:
            date = timezone.now().date()
        
        # Get or create usage record
        usage, created = PlanUsage.objects.get_or_create(
            tenant=tenant,
            period=period,
            period_start=PlanUsageService._get_period_start(date, period),
            defaults={
                'period_end': PlanUsageService._get_period_end(date, period),
            }
        )
        
        # Update the appropriate metric
        PlanUsageService._update_usage_metric(usage, metric_type, value)
        usage.save()
        
        # Check for quota violations
        PlanUsageService._check_quota_violations(tenant, usage)
        
        return usage
    
    @staticmethod
    def _get_period_start(date, period):
        """Get period start date based on period type."""
        if period == 'daily':
            return date
        elif period == 'weekly':
            return date - timedelta(days=date.weekday())
        elif period == 'monthly':
            return date.replace(day=1)
        elif period == 'yearly':
            return date.replace(month=1, day=1)
        return date
    
    @staticmethod
    def _get_period_end(date, period):
        """Get period end date based on period type."""
        if period == 'daily':
            return date
        elif period == 'weekly':
            return date + timedelta(days=6 - date.weekday())
        elif period == 'monthly':
            if date.month == 12:
                return date.replace(year=date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                return date.replace(month=date.month + 1, day=1) - timedelta(days=1)
        elif period == 'yearly':
            return date.replace(month=12, day=31)
        return date
    
    @staticmethod
    def _update_usage_metric(usage, metric_type, value):
        """Update specific metric in usage record."""
        metric_mapping = {
            'api_calls': 'api_calls_used',
            'storage': 'storage_used_gb',
            'bandwidth': 'bandwidth_used_gb',
            'users': 'users_used',
            'publishers': 'publishers_used',
            'smartlinks': 'smartlinks_used',
            'campaigns': 'campaigns_used',
        }
        
        field_name = metric_mapping.get(metric_type)
        if field_name:
            current_value = getattr(usage, field_name)
            setattr(usage, field_name, current_value + value)
    
    @staticmethod
    def _check_quota_violations(tenant, usage):
        """Check for quota violations and take appropriate action."""
        quotas = PlanQuota.objects.filter(plan=tenant.plan)
        
        violations = []
        
        for quota in quotas:
            current_usage = getattr(usage, f'usage_{quota.feature_key}', 0)
            
            if quota.is_over_limit(current_usage):
                violations.append({
                    'quota': quota,
                    'current_usage': current_usage,
                    'limit': quota.hard_limit or quota.soft_limit,
                })
        
        if violations:
            PlanUsageService._handle_quota_violations(tenant, violations)
    
    @staticmethod
    def _handle_quota_violations(tenant, violations):
        """Handle quota violations."""
        for violation in violations:
            quota = violation['quota']
            current_usage = violation['current_usage']
            limit = violation['limit']
            
            # Log violation
            TenantAuditLog.log_security_event(
                tenant=tenant,
                description=f"Quota violation: {quota.feature_key} ({current_usage} > {limit})",
                severity='medium',
                metadata={
                    'quota_feature': quota.feature_key,
                    'current_usage': current_usage,
                    'limit': limit,
                    'quota_type': quota.quota_type,
                }
            )
            
            # Send notification
            if quota.quota_type == 'hard':
                PlanUsageService._send_quota_exceeded_notification(tenant, quota, current_usage, limit)
            elif quota.quota_type == 'soft':
                if quota.should_warn(current_usage):
                    PlanUsageService._send_quota_warning_notification(tenant, quota, current_usage, limit)
            
            # Calculate overage cost
            overage_cost = quota.calculate_overage_cost(current_usage)
            if overage_cost > 0:
                PlanUsageService._handle_overage_charges(tenant, quota, overage_cost)
    
    @staticmethod
    def _send_quota_exceeded_notification(tenant, quota, current_usage, limit):
        """Send quota exceeded notification."""
        TenantNotification.objects.create(
            tenant=tenant,
            title=_('Quota Limit Exceeded'),
            message=_(
                f'You have exceeded your {quota.feature_key} limit '
                f'({current_usage} > {limit}). Please upgrade your plan.'
            ),
            notification_type='warning',
            priority='high',
            send_email=True,
            send_push=True,
            action_url='/billing/plans',
            action_text=_('Upgrade Plan'),
        )
    
    @staticmethod
    def _send_quota_warning_notification(tenant, quota, current_usage, limit):
        """Send quota warning notification."""
        TenantNotification.objects.create(
            tenant=tenant,
            title=_('Quota Limit Warning'),
            message=_(
                f'You are approaching your {quota.feature_key} limit '
                f'({current_usage} of {limit}). Consider upgrading your plan.'
            ),
            notification_type='info',
            priority='medium',
            send_email=True,
            send_push=False,
            action_url='/billing/usage',
            action_text=_('View Usage'),
        )
    
    @staticmethod
    def _handle_overage_charges(tenant, quota, overage_cost):
        """Handle overage charges for quota violations."""
        # This would integrate with your billing system
        # For now, just log the charge
        TenantAuditLog.log_action(
            tenant=tenant,
            action='billing_event',
            model_name='PlanQuota',
            description=f"Overage charge: ${overage_cost:.2f} for {quota.feature_key}",
            metadata={
                'quota_feature': quota.feature_key,
                'overage_cost': float(overage_cost),
            }
        )
    
    @staticmethod
    def get_current_usage(tenant, period='monthly'):
        """
        Get current usage for a tenant.
        
        Args:
            tenant (Tenant): Tenant to get usage for
            period (str): Period to get usage for
            
        Returns:
            dict: Current usage data
        """
        today = timezone.now().date()
        period_start = PlanUsageService._get_period_start(today, period)
        period_end = PlanUsageService._get_period_end(today, period)
        
        try:
            usage = PlanUsage.objects.get(
                tenant=tenant,
                period=period,
                period_start=period_start
            )
        except PlanUsage.DoesNotExist:
            # Create usage record with defaults
            usage = PlanUsageService.track_usage(tenant, 'api_calls', 0, period, today)
        
        # Get plan limits
        plan = tenant.plan
        limits = {
            'api_calls_limit': plan.api_calls_per_day,
            'storage_limit_gb': plan.storage_gb,
            'users_limit': plan.max_users,
            'publishers_limit': plan.max_publishers,
            'smartlinks_limit': plan.max_smartlinks,
            'campaigns_limit': plan.max_campaigns,
        }
        
        # Override with quota limits if they exist
        quotas = PlanQuota.objects.filter(plan=tenant.plan)
        for quota in quotas:
            if quota.hard_limit:
                limits[f'{quota.feature_key}_limit'] = quota.hard_limit
        
        # Update usage record with limits
        for field, limit in limits.items():
            setattr(usage, field, limit)
        usage.save()
        
        return {
            'period': period,
            'period_start': usage.period_start,
            'period_end': usage.period_end,
            'api_calls': {
                'used': usage.api_calls_used,
                'limit': usage.api_calls_limit,
                'percentage': usage.api_calls_percentage,
                'remaining': max(0, usage.api_calls_limit - usage.api_calls_used),
            },
            'storage': {
                'used': float(usage.storage_used_gb),
                'limit': usage.storage_limit_gb,
                'percentage': usage.storage_percentage,
                'remaining': max(0, usage.storage_limit_gb - usage.storage_used_gb),
            },
            'users': {
                'used': usage.users_used,
                'limit': usage.users_limit,
                'percentage': usage.users_percentage,
                'remaining': max(0, usage.users_limit - usage.users_used),
            },
            'publishers': {
                'used': usage.publishers_used,
                'limit': usage.publishers_limit,
                'percentage': usage.publishers_percentage if hasattr(usage, 'publishers_percentage') else 0,
                'remaining': max(0, usage.publishers_limit - usage.publishers_used),
            },
            'smartlinks': {
                'used': usage.smartlinks_used,
                'limit': usage.smartlinks_limit,
                'percentage': usage.smartlinks_percentage if hasattr(usage, 'smartlinks_percentage') else 0,
                'remaining': max(0, usage.smartlinks_limit - usage.smartlinks_used),
            },
            'campaigns': {
                'used': usage.campaigns_used,
                'limit': usage.campaigns_limit,
                'percentage': usage.campaigns_percentage if hasattr(usage, 'campaigns_percentage') else 0,
                'remaining': max(0, usage.campaigns_limit - usage.campaigns_used),
            },
        }
    
    @staticmethod
    def get_usage_history(tenant, metric_type, period='daily', days=30):
        """
        Get usage history for a specific metric.
        
        Args:
            tenant (Tenant): Tenant to get history for
            metric_type (str): Type of metric
            period (str): Period type
            days (int): Number of days to retrieve
            
        Returns:
            list: Usage history data
        """
        from django.db.models import Sum
        
        # Map metric type to field name
        metric_mapping = {
            'api_calls': 'api_calls_used',
            'storage': 'storage_used_gb',
            'bandwidth': 'bandwidth_used_gb',
            'users': 'users_used',
            'publishers': 'publishers_used',
            'smartlinks': 'smartlinks_used',
            'campaigns': 'campaigns_used',
        }
        
        field_name = metric_mapping.get(metric_type)
        if not field_name:
            raise ValidationError(f'Invalid metric type: {metric_type}')
        
        # Get usage records
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        usage_records = PlanUsage.objects.filter(
            tenant=tenant,
            period=period,
            period_start__gte=start_date,
            period_start__lte=end_date
        ).order_by('period_start')
        
        history = []
        for record in usage_records:
            value = getattr(record, field_name)
            history.append({
                'date': record.period_start,
                'value': value,
                'period': record.period,
            })
        
        return history
    
    @staticmethod
    def get_usage_analytics(tenant, period='monthly'):
        """
        Get comprehensive usage analytics for a tenant.
        
        Args:
            tenant (Tenant): Tenant to get analytics for
            period (str): Period to analyze
            
        Returns:
            dict: Usage analytics data
        """
        current_usage = PlanUsageService.get_current_usage(tenant, period)
        
        # Get historical data for comparison
        from datetime import timedelta
        if period == 'monthly':
            comparison_date = timezone.now().date() - timedelta(days=30)
        elif period == 'daily':
            comparison_date = timezone.now().date() - timedelta(days=1)
        elif period == 'yearly':
            comparison_date = timezone.now().date() - timedelta(days=365)
        else:
            comparison_date = timezone.now().date() - timedelta(days=7)
        
        comparison_usage = PlanUsageService.get_current_usage(tenant, period)
        
        # Calculate trends
        analytics = {
            'current': current_usage,
            'comparison': comparison_usage,
            'trends': {},
        }
        
        # Calculate trends for each metric
        for metric in ['api_calls', 'storage', 'users', 'publishers', 'smartlinks', 'campaigns']:
            current_data = current_usage.get(metric, {})
            comparison_data = comparison_usage.get(metric, {})
            
            if current_data and comparison_data:
                current_value = current_data['used']
                comparison_value = comparison_data['used']
                
                if comparison_value > 0:
                    change_pct = ((current_value - comparison_value) / comparison_value) * 100
                    trend = 'up' if change_pct > 0 else 'down' if change_pct < 0 else 'stable'
                else:
                    change_pct = 0
                    trend = 'stable'
                
                analytics['trends'][metric] = {
                    'change_percentage': round(change_pct, 2),
                    'trend': trend,
                    'current_value': current_value,
                    'comparison_value': comparison_value,
                }
        
        # Get quota violations
        analytics['quota_violations'] = PlanUsageService._get_quota_violations(tenant)
        
        # Get predictions (simple linear extrapolation)
        analytics['predictions'] = PlanUsageService._get_usage_predictions(tenant, period)
        
        return analytics
    
    @staticmethod
    def _get_quota_violations(tenant):
        """Get current quota violations for tenant."""
        current_usage = PlanUsageService.get_current_usage(tenant, 'monthly')
        violations = []
        
        for metric, data in current_usage.items():
            if isinstance(data, dict) and data.get('percentage', 0) > 100:
                violations.append({
                    'metric': metric,
                    'used': data['used'],
                    'limit': data['limit'],
                    'percentage': data['percentage'],
                    'overage': data['used'] - data['limit'],
                })
        
        return violations
    
    @staticmethod
    def _get_usage_predictions(tenant, period='monthly'):
        """
        Get usage predictions based on historical data.
        
        Args:
            tenant (Tenant): Tenant to predict for
            period (str): Period type
            
        Returns:
            dict: Usage predictions
        """
        # This is a simple prediction based on recent trends
        # In production, you might use more sophisticated methods
        
        predictions = {}
        
        # Get last 3 periods of data
        days = 90 if period == 'monthly' else 21 if period == 'weekly' else 3
        history = PlanUsageService.get_usage_history(tenant, 'api_calls', period, days)
        
        if len(history) >= 2:
            # Simple linear prediction
            recent_values = [record['value'] for record in history[-3:]]
            if len(recent_values) >= 2:
                # Calculate average change
                changes = []
                for i in range(1, len(recent_values)):
                    change = recent_values[i] - recent_values[i-1]
                    changes.append(change)
                
                avg_change = sum(changes) / len(changes)
                predicted_value = recent_values[-1] + avg_change
                
                predictions['api_calls'] = {
                    'predicted_value': max(0, int(predicted_value)),
                    'confidence': 'medium',  # Simple heuristic
                    'method': 'linear_extrapolation',
                }
        
        return predictions
    
    @staticmethod
    def reset_usage_period(tenant, period='monthly', reset_date=None):
        """
        Reset usage for a specific period.
        
        Args:
            tenant (Tenant): Tenant to reset usage for
            period (str): Period to reset
            reset_date (date): Date to reset from
            
        Returns:
            bool: True if successful
        """
        if reset_date is None:
            reset_date = timezone.now().date()
        
        period_start = PlanUsageService._get_period_start(reset_date, period)
        
        try:
            usage = PlanUsage.objects.get(
                tenant=tenant,
                period=period,
                period_start=period_start
            )
            
            # Reset all usage metrics to zero
            usage.api_calls_used = 0
            usage.storage_used_gb = 0
            usage.bandwidth_used_gb = 0
            usage.users_used = 0
            usage.publishers_used = 0
            usage.smartlinks_used = 0
            usage.campaigns_used = 0
            usage.save()
            
            # Log reset
            TenantAuditLog.log_action(
                tenant=tenant,
                action='config_change',
                model_name='PlanUsage',
                description=f"Usage reset for {period} period starting {period_start}",
                metadata={
                    'period': period,
                    'period_start': period_start.isoformat(),
                }
            )
            
            return True
            
        except PlanUsage.DoesNotExist:
            return False
    
    @staticmethod
    def export_usage_report(tenant, period='monthly', format='csv'):
        """
        Export usage report for a tenant.
        
        Args:
            tenant (Tenant): Tenant to export for
            period (str): Period to export
            format (str): Export format (csv, json, xlsx)
            
        Returns:
            str/bytes: Exported data
        """
        usage_data = PlanUsageService.get_usage_analytics(tenant, period)
        
        if format == 'json':
            import json
            return json.dumps(usage_data, indent=2, default=str)
        
        elif format == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Metric', 'Used', 'Limit', 'Percentage', 'Remaining'])
            
            # Write data
            current = usage_data['current']
            for metric in ['api_calls', 'storage', 'users', 'publishers', 'smartlinks', 'campaigns']:
                data = current.get(metric, {})
                if data:
                    writer.writerow([
                        metric,
                        data['used'],
                        data['limit'],
                        f"{data['percentage']:.2f}%",
                        data['remaining']
                    ])
            
            return output.getvalue()
        
        elif format == 'xlsx':
            # This would require a library like openpyxl
            # For now, return CSV as fallback
            return PlanUsageService.export_usage_report(tenant, period, 'csv')
        
        else:
            raise ValidationError(f'Unsupported export format: {format}')
    
    @staticmethod
    def get_tenant_usage_summary():
        """
        Get usage summary for all tenants (admin function).
        
        Returns:
            dict: Usage summary statistics
        """
        from django.db.models import Count, Sum, Avg, Q
        
        # Get current month usage for all tenants
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        usage_records = PlanUsage.objects.filter(
            period='monthly',
            period_start=month_start
        ).select_related('tenant', 'tenant__plan')
        
        summary = {
            'total_tenants': usage_records.count(),
            'total_api_calls': usage_records.aggregate(Sum('api_calls_used'))['api_calls_used__sum'] or 0,
            'total_storage_used': usage_records.aggregate(Sum('storage_used_gb'))['storage_used_gb__sum'] or 0,
            'avg_api_calls_per_tenant': usage_records.aggregate(Avg('api_calls_used'))['api_calls_used__avg'] or 0,
            'avg_storage_per_tenant': usage_records.aggregate(Avg('storage_used_gb'))['storage_used_gb__avg'] or 0,
        }
        
        # Breakdown by plan
        plan_breakdown = {}
        for record in usage_records:
            plan_name = record.tenant.plan.name
            if plan_name not in plan_breakdown:
                plan_breakdown[plan_name] = {
                    'tenant_count': 0,
                    'total_api_calls': 0,
                    'total_storage': 0,
                }
            
            plan_breakdown[plan_name]['tenant_count'] += 1
            plan_breakdown[plan_name]['total_api_calls'] += record.api_calls_used
            plan_breakdown[plan_name]['total_storage'] += record.storage_used_gb
        
        summary['by_plan'] = plan_breakdown
        
        # Top users by usage
        top_api_users = usage_records.order_by('-api_calls_used')[:10]
        top_storage_users = usage_records.order_by('-storage_used_gb')[:10]
        
        summary['top_api_users'] = [
            {
                'tenant_name': record.tenant.name,
                'api_calls': record.api_calls_used,
                'plan': record.tenant.plan.name,
            }
            for record in top_api_users
        ]
        
        summary['top_storage_users'] = [
            {
                'tenant_name': record.tenant.name,
                'storage_gb': float(record.storage_used_gb),
                'plan': record.tenant.plan.name,
            }
            for record in top_storage_users
        ]
        
        return summary
