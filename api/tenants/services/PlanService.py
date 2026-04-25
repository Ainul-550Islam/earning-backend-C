"""
Plan Service

This service handles subscription plan operations including
upgrades, downgrades, pricing, and plan management.
"""

from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ..models import Tenant
from ..models.plan import Plan, PlanUpgrade, PlanFeature, PlanQuota
from ..models.security import TenantAuditLog

User = get_user_model()


class PlanService:
    """
    Service class for plan management operations.
    
    This service handles plan upgrades, downgrades,
    feature management, and pricing calculations.
    """
    
    @staticmethod
    def upgrade_plan(tenant, new_plan, upgraded_by=None, reason=None):
        """
        Upgrade tenant to a new plan.
        
        Args:
            tenant (Tenant): Tenant to upgrade
            new_plan (Plan): New plan to upgrade to
            upgraded_by (User): User performing the upgrade
            reason (str): Reason for upgrade
            
        Returns:
            dict: Upgrade result
            
        Raises:
            ValidationError: If upgrade is not allowed
        """
        with transaction.atomic():
            # Validate upgrade
            can_upgrade, error = PlanService._can_upgrade_plan(tenant, new_plan)
            if not can_upgrade:
                raise ValidationError(error)
            
            old_plan = tenant.plan
            
            # Create plan upgrade record
            upgrade_record = PlanUpgrade.objects.create(
                tenant=tenant,
                from_plan=old_plan,
                to_plan=new_plan,
                upgraded_at=timezone.now(),
                effective_from=timezone.now(),
                old_price=old_plan.price_monthly,
                new_price=new_plan.price_monthly,
                reason=reason or "Plan upgrade requested",
                processed_by=upgraded_by,
            )
            
            upgrade_record.calculate_price_difference()
            upgrade_record.save()
            
            # Update tenant plan
            tenant.plan = new_plan
            tenant.tier = new_plan.plan_type
            tenant.save(update_fields=['plan', 'tier'])
            
            # Update tenant settings limits
            PlanService._update_tenant_plan_limits(tenant, new_plan)
            
            # Update billing
            PlanService._update_billing_for_plan_change(tenant, old_plan, new_plan)
            
            # Log upgrade
            if upgraded_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='config_change',
                    actor=upgraded_by,
                    model_name='Tenant',
                    object_id=str(tenant.id),
                    object_repr=str(tenant),
                    changes={
                        'plan': {'old': str(old_plan), 'new': str(new_plan)},
                        'tier': {'old': old_plan.plan_type, 'new': new_plan.plan_type},
                    },
                    description=f"Plan upgraded from {old_plan.name} to {new_plan.name}"
                )
            
            # Send notifications
            PlanService._send_plan_upgrade_notifications(tenant, old_plan, new_plan)
            
            return {
                'success': True,
                'message': f'Plan upgraded from {old_plan.name} to {new_plan.name}',
                'upgrade_record': upgrade_record,
                'price_difference': float(upgrade_record.price_difference),
            }
    
    @staticmethod
    def _can_upgrade_plan(tenant, new_plan):
        """Check if tenant can upgrade to the new plan."""
        # Check if new plan is active
        if not new_plan.is_active:
            return False, "Selected plan is not active."
        
        # Check if new plan allows upgrades
        if not new_plan.can_upgrade:
            return False, "Upgrades to this plan are not allowed."
        
        # Check if tenant is not already on this plan
        if tenant.plan == new_plan:
            return False, "Tenant is already on this plan."
        
        # Check if tenant can upgrade from current plan
        if not tenant.plan.can_upgrade:
            return False, "Current plan does not allow upgrades."
        
        # Check if upgrade is allowed based on plan hierarchy
        if not PlanService._is_upgrade_allowed(tenant.plan, new_plan):
            return False, "This upgrade path is not allowed."
        
        return True, None
    
    @staticmethod
    def _is_upgrade_allowed(current_plan, new_plan):
        """Check if upgrade from current to new plan is allowed."""
        # Define plan hierarchy (higher number = higher tier)
        plan_hierarchy = {
            'free': 0,
            'basic': 1,
            'pro': 2,
            'enterprise': 3,
            'custom': 4,
        }
        
        current_tier = plan_hierarchy.get(current_plan.plan_type, 0)
        new_tier = plan_hierarchy.get(new_plan.plan_type, 0)
        
        # Allow upgrade to same or higher tier
        return new_tier >= current_tier
    
    @staticmethod
    def _update_tenant_plan_limits(tenant, new_plan):
        """Update tenant settings limits based on new plan."""
        settings = tenant.settings
        
        settings.max_users = new_plan.max_users
        settings.max_publishers = new_plan.max_publishers
        settings.max_smartlinks = new_plan.max_smartlinks
        settings.max_campaigns = new_plan.max_campaigns
        settings.api_calls_per_day = new_plan.api_calls_per_day
        settings.api_calls_per_hour = new_plan.api_calls_per_hour
        settings.storage_gb = new_plan.storage_gb
        settings.bandwidth_gb_per_month = new_plan.bandwidth_gb_per_month
        
        settings.save()
    
    @staticmethod
    def _update_billing_for_plan_change(tenant, old_plan, new_plan):
        """Update billing information for plan change."""
        billing = tenant.billing
        
        # Update pricing
        billing.base_price = new_plan.price_monthly
        billing.calculate_final_price()
        
        # Adjust next billing date if needed
        if new_plan.price_monthly > old_plan.price_monthly:
            # For upgrades, charge immediately and reset billing cycle
            from datetime import date
            today = date.today()
            billing.next_billing_date = today.replace(day=billing.billing_cycle_start)
        
        billing.save()
    
    @staticmethod
    def _send_plan_upgrade_notifications(tenant, old_plan, new_plan):
        """Send plan upgrade notifications."""
        # Create in-app notification
        from ..models.analytics import TenantNotification
        
        TenantNotification.objects.create(
            tenant=tenant,
            title=_('Plan Upgraded'),
            message=_(f'Your plan has been upgraded from {old_plan.name} to {new_plan.name}.'),
            notification_type='billing',
            priority='medium',
            send_email=True,
            send_push=True,
            action_url='/billing',
            action_text=_('View Plan Details'),
        )
        
        # Send email to tenant owner
        PlanService._send_plan_upgrade_email(tenant, old_plan, new_plan)
        
        # Trigger webhooks
        PlanService._trigger_plan_upgrade_webhooks(tenant, old_plan, new_plan)
    
    @staticmethod
    def _send_plan_upgrade_email(tenant, old_plan, new_plan):
        """Send plan upgrade confirmation email."""
        # This would integrate with your email service
        # Implementation depends on your email system
        pass
    
    @staticmethod
    def _trigger_plan_upgrade_webhooks(tenant, old_plan, new_plan):
        """Trigger plan upgrade webhooks."""
        from ..models.security import TenantWebhookConfig
        
        webhooks = TenantWebhookConfig.objects.filter(
            tenant=tenant,
            is_active=True
        )
        
        for webhook in webhooks:
            if webhook.can_send_event('plan.upgraded'):
                # This would trigger the webhook
                # Implementation depends on your webhook system
                pass
    
    @staticmethod
    def downgrade_plan(tenant, new_plan, downgraded_by=None, reason=None):
        """
        Downgrade tenant to a new plan.
        
        Args:
            tenant (Tenant): Tenant to downgrade
            new_plan (Plan): New plan to downgrade to
            downgraded_by (User): User performing the downgrade
            reason (str): Reason for downgrade
            
        Returns:
            dict: Downgrade result
            
        Raises:
            ValidationError: If downgrade is not allowed
        """
        with transaction.atomic():
            # Validate downgrade
            can_downgrade, error = PlanService._can_downgrade_plan(tenant, new_plan)
            if not can_downgrade:
                raise ValidationError(error)
            
            old_plan = tenant.plan
            
            # Create plan upgrade record (using same model for downgrades)
            upgrade_record = PlanUpgrade.objects.create(
                tenant=tenant,
                from_plan=old_plan,
                to_plan=new_plan,
                upgraded_at=timezone.now(),
                effective_from=timezone.now(),  # Effective immediately
                old_price=old_plan.price_monthly,
                new_price=new_plan.price_monthly,
                reason=reason or "Plan downgrade requested",
                processed_by=downgraded_by,
            )
            
            upgrade_record.calculate_price_difference()
            upgrade_record.save()
            
            # Update tenant plan
            tenant.plan = new_plan
            tenant.tier = new_plan.plan_type
            tenant.save(update_fields=['plan', 'tier'])
            
            # Update tenant settings limits
            PlanService._update_tenant_plan_limits(tenant, new_plan)
            
            # Update billing
            PlanService._update_billing_for_plan_change(tenant, old_plan, new_plan)
            
            # Log downgrade
            if downgraded_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='config_change',
                    actor=downgraded_by,
                    model_name='Tenant',
                    object_id=str(tenant.id),
                    object_repr=str(tenant),
                    changes={
                        'plan': {'old': str(old_plan), 'new': str(new_plan)},
                        'tier': {'old': old_plan.plan_type, 'new': new_plan.plan_type},
                    },
                    description=f"Plan downgraded from {old_plan.name} to {new_plan.name}"
                )
            
            # Send notifications
            PlanService._send_plan_downgrade_notifications(tenant, old_plan, new_plan)
            
            return {
                'success': True,
                'message': f'Plan downgraded from {old_plan.name} to {new_plan.name}',
                'upgrade_record': upgrade_record,
                'price_difference': float(upgrade_record.price_difference),
            }
    
    @staticmethod
    def _can_downgrade_plan(tenant, new_plan):
        """Check if tenant can downgrade to the new plan."""
        # Check if new plan is active
        if not new_plan.is_active:
            return False, "Selected plan is not active."
        
        # Check if new plan allows downgrades
        if not new_plan.can_downgrade:
            return False, "Downgrades to this plan are not allowed."
        
        # Check if tenant is not already on this plan
        if tenant.plan == new_plan:
            return False, "Tenant is already on this plan."
        
        # Check if current plan allows downgrades
        if not tenant.plan.can_downgrade:
            return False, "Current plan does not allow downgrades."
        
        # Check if downgrade is in allowed downgrade paths
        if not PlanService._is_downgrade_allowed(tenant.plan, new_plan):
            return False, "This downgrade path is not allowed."
        
        return True, None
    
    @staticmethod
    def _is_downgrade_allowed(current_plan, new_plan):
        """Check if downgrade from current to new plan is allowed."""
        # Check if new_plan is in current_plan's downgrade_to_plans
        return new_plan in current_plan.downgrade_to_plans.all()
    
    @staticmethod
    def _send_plan_downgrade_notifications(tenant, old_plan, new_plan):
        """Send plan downgrade notifications."""
        # Create in-app notification
        from ..models.analytics import TenantNotification
        
        TenantNotification.objects.create(
            tenant=tenant,
            title=_('Plan Changed'),
            message=_(f'Your plan has been changed from {old_plan.name} to {new_plan.name}.'),
            notification_type='billing',
            priority='medium',
            send_email=True,
            send_push=True,
            action_url='/billing',
            action_text=_('View Plan Details'),
        )
        
        # Send email to tenant owner
        PlanService._send_plan_downgrade_email(tenant, old_plan, new_plan)
        
        # Trigger webhooks
        PlanService._trigger_plan_downgrade_webhooks(tenant, old_plan, new_plan)
    
    @staticmethod
    def _send_plan_downgrade_email(tenant, old_plan, new_plan):
        """Send plan downgrade confirmation email."""
        # This would integrate with your email service
        # Implementation depends on your email system
        pass
    
    @staticmethod
    def _trigger_plan_downgrade_webhooks(tenant, old_plan, new_plan):
        """Trigger plan downgrade webhooks."""
        from ..models.security import TenantWebhookConfig
        
        webhooks = TenantWebhookConfig.objects.filter(
            tenant=tenant,
            is_active=True
        )
        
        for webhook in webhooks:
            if webhook.can_send_event('plan.downgraded'):
                # This would trigger the webhook
                # Implementation depends on your webhook system
                pass
    
    @staticmethod
    def get_available_plans(tenant=None, include_inactive=False):
        """
        Get available plans for tenant or general availability.
        
        Args:
            tenant (Tenant): Tenant to get plans for (optional)
            include_inactive (bool): Whether to include inactive plans
            
        Returns:
            QuerySet: Available plans
        """
        queryset = Plan.objects.all()
        
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        
        if tenant:
            # Filter plans that tenant can upgrade to
            available_plans = []
            for plan in queryset:
                if PlanService._can_upgrade_plan(tenant, plan)[0]:
                    available_plans.append(plan.id)
            
            queryset = queryset.filter(id__in=available_plans)
        
        return queryset.order_by('sort_order', 'name')
    
    @staticmethod
    def get_plan_comparison(plans):
        """
        Get comparison data for multiple plans.
        
        Args:
            plans (list): List of plan objects or plan IDs
            
        Returns:
            dict: Plan comparison data
        """
        if isinstance(plans[0], (int, str)):
            # Convert plan IDs to plan objects
            plan_ids = plans
            plans = Plan.objects.filter(id__in=plan_ids)
        
        comparison = {
            'plans': [],
            'features': set(),
            'quotas': set(),
        }
        
        # Collect all features and quotas
        for plan in plans:
            plan_data = {
                'id': str(plan.id),
                'name': plan.name,
                'slug': plan.slug,
                'plan_type': plan.plan_type,
                'price_monthly': float(plan.price_monthly),
                'price_yearly': float(plan.price_yearly),
                'setup_fee': float(plan.setup_fee),
                'trial_days': plan.trial_days,
                'features': plan.features,
                'quotas': {},
                'is_featured': plan.is_featured,
                'sort_order': plan.sort_order,
            }
            
            # Get quotas for this plan
            quotas = PlanQuota.objects.filter(plan=plan)
            for quota in quotas:
                plan_data['quotas'][quota.feature_key] = {
                    'hard_limit': quota.hard_limit,
                    'soft_limit': quota.soft_limit,
                    'overage_allowed': quota.overage_allowed,
                    'overage_price': float(quota.overage_price_per_unit) if quota.overage_price_per_unit else 0,
                }
                comparison['quotas'].add(quota.feature_key)
            
            # Get all feature keys
            comparison['features'].update(plan.features.keys())
            
            comparison['plans'].append(plan_data)
        
        # Convert sets to lists
        comparison['features'] = list(comparison['features'])
        comparison['quotas'] = list(comparison['quotas'])
        
        return comparison
    
    @staticmethod
    def calculate_proration(tenant, new_plan, days_in_current_cycle=None):
        """
        Calculate proration for plan change.
        
        Args:
            tenant (Tenant): Tenant changing plans
            new_plan (Plan): New plan
            days_in_current_cycle (int): Days in current billing cycle
            
        Returns:
            dict: Proration calculation
        """
        old_plan = tenant.plan
        billing = tenant.billing
        
        if days_in_current_cycle is None:
            # Calculate days in current cycle
            from datetime import date
            today = date.today()
            if today.day >= billing.billing_cycle_start:
                next_cycle = today.replace(month=today.month + 1 if today.month < 12 else 1)
            else:
                next_cycle = today.replace(day=billing.billing_cycle_start)
            days_in_current_cycle = (next_cycle - today).days
        
        days_in_month = 30  # Approximate
        remaining_days_ratio = days_in_current_cycle / days_in_month
        
        # Calculate prorated amounts
        old_plan_remaining = old_plan.price_monthly * remaining_days_ratio
        new_plan_remaining = new_plan.price_monthly * remaining_days_ratio
        
        proration_amount = new_plan_remaining - old_plan_remaining
        
        return {
            'old_plan_price': float(old_plan.price_monthly),
            'new_plan_price': float(new_plan.price_monthly),
            'days_in_current_cycle': days_in_current_cycle,
            'remaining_days_ratio': round(remaining_days_ratio, 4),
            'old_plan_remaining': round(old_plan_remaining, 2),
            'new_plan_remaining': round(new_plan_remaining, 2),
            'proration_amount': round(proration_amount, 2),
            'charge_immediately': proration_amount > 0,
        }
    
    @staticmethod
    def get_plan_usage_stats(tenant):
        """
        Get usage statistics for tenant's current plan.
        
        Args:
            tenant (Tenant): Tenant to get stats for
            
        Returns:
            dict: Usage statistics
        """
        from ..models.plan import PlanUsage
        from django.utils import timezone
        from datetime import date
        
        # Get current month usage
        today = date.today()
        current_month_start = today.replace(day=1)
        
        try:
            usage = PlanUsage.objects.get(
                tenant=tenant,
                period='monthly',
                period_start=current_month_start
            )
        except PlanUsage.DoesNotExist:
            return {
                'error': 'No usage data available for current month'
            }
        
        plan = tenant.plan
        
        stats = {
            'period': usage.period,
            'period_start': usage.period_start,
            'period_end': usage.period_end,
            'usage': {
                'api_calls': {
                    'used': usage.api_calls_used,
                    'limit': usage.api_calls_limit or plan.api_calls_per_day,
                    'percentage': usage.api_calls_percentage,
                },
                'storage': {
                    'used': float(usage.storage_used_gb),
                    'limit': usage.storage_limit_gb or plan.storage_gb,
                    'percentage': usage.storage_percentage,
                },
                'users': {
                    'used': usage.users_used,
                    'limit': usage.users_limit or plan.max_users,
                    'percentage': usage.users_percentage,
                },
                'publishers': {
                    'used': usage.publishers_used,
                    'limit': usage.publishers_limit or plan.max_publishers,
                    'percentage': usage.publishers_percentage if hasattr(usage, 'publishers_percentage') else 0,
                },
                'smartlinks': {
                    'used': usage.smartlinks_used,
                    'limit': usage.smartlinks_limit or plan.max_smartlinks,
                    'percentage': usage.smartlinks_percentage if hasattr(usage, 'smartlinks_percentage') else 0,
                },
                'campaigns': {
                    'used': usage.campaigns_used,
                    'limit': usage.campaigns_limit or plan.max_campaigns,
                    'percentage': usage.campaigns_percentage if hasattr(usage, 'campaigns_percentage') else 0,
                },
            },
            'over_limits': [],
        }
        
        # Check for overages
        for metric, data in stats['usage'].items():
            if usage.is_over_limit(metric):
                stats['over_limits'].append(metric)
        
        return stats
    
    @staticmethod
    def create_custom_plan(data, created_by=None):
        """
        Create a custom plan.
        
        Args:
            data (dict): Plan creation data
            created_by (User): User creating the plan
            
        Returns:
            Plan: Created plan
            
        Raises:
            ValidationError: If data is invalid
        """
        with transaction.atomic():
            # Set plan type to custom
            data['plan_type'] = 'custom'
            
            # Create plan
            plan = Plan.objects.create(**data)
            
            # Create quotas if provided
            if 'quotas' in data:
                for feature_key, quota_data in data['quotas'].items():
                    PlanQuota.objects.create(
                        plan=plan,
                        feature_key=feature_key,
                        **quota_data
                    )
            
            # Log creation
            if created_by:
                TenantAuditLog.log_action(
                    tenant=None,  # System-level action
                    action='create',
                    actor=created_by,
                    model_name='Plan',
                    object_id=str(plan.id),
                    object_repr=str(plan),
                    description=f"Custom plan {plan.name} created"
                )
            
            return plan
    
    @staticmethod
    def validate_plan_data(data, plan=None):
        """
        Validate plan data.
        
        Args:
            data (dict): Plan data to validate
            plan (Plan): Existing plan (for updates)
            
        Returns:
            tuple: (is_valid, errors)
        """
        errors = []
        
        # Validate required fields
        if not plan:  # Creation validation
            required_fields = ['name', 'slug']
            for field in required_fields:
                if field not in data or not data[field]:
                    errors.append(f'{field} is required.')
        
        # Validate slug uniqueness
        if 'slug' in data:
            slug = data['slug']
            queryset = Plan.objects.filter(slug=slug)
            if plan:
                queryset = queryset.exclude(pk=plan.pk)
            if queryset.exists():
                errors.append('Plan slug already exists.')
        
        # Validate pricing
        for field in ['price_monthly', 'price_yearly', 'setup_fee']:
            if field in data:
                try:
                    price = float(data[field])
                    if price < 0:
                        errors.append(f'{field} cannot be negative.')
                except (ValueError, TypeError):
                    errors.append(f'{field} must be a valid number.')
        
        # Validate limits
        for field in ['max_users', 'max_publishers', 'max_smartlinks', 'api_calls_per_day']:
            if field in data:
                try:
                    limit = int(data[field])
                    if limit < 0:
                        errors.append(f'{field} cannot be negative.')
                except (ValueError, TypeError):
                    errors.append(f'{field} must be a valid integer.')
        
        # Validate trial days
        if 'trial_days' in data:
            try:
                trial_days = int(data['trial_days'])
                if trial_days < 0:
                    errors.append('Trial days cannot be negative.')
                if trial_days > 365:
                    errors.append('Trial days cannot exceed 365.')
            except (ValueError, TypeError):
                errors.append('Trial days must be a valid integer.')
        
        return len(errors) == 0, errors
