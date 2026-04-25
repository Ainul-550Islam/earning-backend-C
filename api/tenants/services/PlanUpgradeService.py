"""
Plan Upgrade Service

This module provides business logic for managing plan upgrades
including upgrade requests, approvals, and processing.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.utils import timezone
from ..models.plan import PlanUpgrade, Plan, PlanUsage
from ..models.core import Tenant
from .base import BaseService


class PlanUpgradeService(BaseService):
    """
    Service class for managing plan upgrades.
    
    Provides business logic for upgrade operations including:
    - Upgrade request processing
    - Upgrade approval workflow
    - Upgrade execution
    - Upgrade history tracking
    """
    
    @staticmethod
    def request_upgrade(tenant, from_plan, to_plan, reason=None, requested_by=None):
        """
        Request a plan upgrade for a tenant.
        
        Args:
            tenant (Tenant): Tenant requesting upgrade
            from_plan (Plan): Current plan
            to_plan (Plan): Target plan
            reason (str): Reason for upgrade
            requested_by (User): User requesting upgrade
            
        Returns:
            PlanUpgrade: Created upgrade request
            
        Raises:
            ValidationError: If upgrade request is invalid
        """
        try:
            with transaction.atomic():
                # Validate upgrade request
                PlanUpgradeService._validate_upgrade_request(tenant, from_plan, to_plan)
                
                # Check for existing pending upgrade
                existing_upgrade = PlanUpgrade.objects.filter(
                    tenant=tenant,
                    status='pending'
                ).first()
                
                if existing_upgrade:
                    raise ValidationError(_('There is already a pending upgrade request'))
                
                # Calculate price difference
                price_difference = PlanUpgradeService._calculate_price_difference(
                    from_plan, to_plan
                )
                
                # Create upgrade request
                upgrade = PlanUpgrade.objects.create(
                    tenant=tenant,
                    from_plan=from_plan,
                    to_plan=to_plan,
                    reason=reason or '',
                    requested_by=requested_by,
                    price_difference=price_difference,
                    status='pending',
                    requested_at=timezone.now()
                )
                
                return upgrade
                
        except Exception as e:
            raise ValidationError(f"Failed to request upgrade: {str(e)}")
    
    @staticmethod
    def approve_upgrade(upgrade, approved_by=None, notes=None):
        """
        Approve a plan upgrade request.
        
        Args:
            upgrade (PlanUpgrade): Upgrade to approve
            approved_by (User): User approving upgrade
            notes (str): Approval notes
            
        Returns:
            PlanUpgrade: Approved upgrade
        """
        try:
            with transaction.atomic():
                # Validate upgrade can be approved
                if upgrade.status != 'pending':
                    raise ValidationError(_('Only pending upgrades can be approved'))
                
                # Process the upgrade
                PlanUpgradeService._process_upgrade(upgrade)
                
                # Update upgrade status
                upgrade.status = 'approved'
                upgrade.approved_by = approved_by
                upgrade.approved_at = timezone.now()
                upgrade.approval_notes = notes or ''
                upgrade.save()
                
                return upgrade
                
        except Exception as e:
            raise ValidationError(f"Failed to approve upgrade: {str(e)}")
    
    @staticmethod
    def reject_upgrade(upgrade, rejected_by=None, reason=None):
        """
        Reject a plan upgrade request.
        
        Args:
            upgrade (PlanUpgrade): Upgrade to reject
            rejected_by (User): User rejecting upgrade
            reason (str): Rejection reason
            
        Returns:
            PlanUpgrade: Rejected upgrade
        """
        try:
            # Validate upgrade can be rejected
            if upgrade.status != 'pending':
                raise ValidationError(_('Only pending upgrades can be rejected'))
            
            # Update upgrade status
            upgrade.status = 'rejected'
            upgrade.rejected_by = rejected_by
            upgrade.rejected_at = timezone.now()
            upgrade.rejection_reason = reason or ''
            upgrade.save()
            
            return upgrade
            
        except Exception as e:
            raise ValidationError(f"Failed to reject upgrade: {str(e)}")
    
    @staticmethod
    def cancel_upgrade(upgrade, cancelled_by=None, reason=None):
        """
        Cancel a plan upgrade request.
        
        Args:
            upgrade (PlanUpgrade): Upgrade to cancel
            cancelled_by (User): User cancelling upgrade
            reason (str): Cancellation reason
            
        Returns:
            PlanUpgrade: Cancelled upgrade
        """
        try:
            # Validate upgrade can be cancelled
            if upgrade.status not in ['pending', 'approved']:
                raise ValidationError(_('Only pending or approved upgrades can be cancelled'))
            
            # If upgrade was already approved, rollback changes
            if upgrade.status == 'approved' and upgrade.processed_at:
                PlanUpgradeService._rollback_upgrade(upgrade)
            
            # Update upgrade status
            upgrade.status = 'cancelled'
            upgrade.cancelled_by = cancelled_by
            upgrade.cancelled_at = timezone.now()
            upgrade.cancellation_reason = reason or ''
            upgrade.save()
            
            return upgrade
            
        except Exception as e:
            raise ValidationError(f"Failed to cancel upgrade: {str(e)}")
    
    @staticmethod
    def get_pending_upgrades():
        """
        Get all pending upgrade requests.
        
        Returns:
            QuerySet: Pending upgrade requests
        """
        return PlanUpgrade.objects.filter(status='pending').order_by('requested_at')
    
    @staticmethod
    def get_tenant_upgrades(tenant, status=None):
        """
        Get all upgrade requests for a tenant.
        
        Args:
            tenant (Tenant): Tenant to get upgrades for
            status (str): Filter by status (optional)
            
        Returns:
            QuerySet: Tenant upgrade requests
        """
        queryset = PlanUpgrade.objects.filter(tenant=tenant)
        if status:
            queryset = queryset.filter(status=status)
        return queryset.order_by('-requested_at')
    
    @staticmethod
    def get_upgrade_statistics(days=30):
        """
        Get upgrade statistics.
        
        Args:
            days (int): Number of days to analyze
            
        Returns:
            dict: Upgrade statistics
        """
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        queryset = PlanUpgrade.objects.filter(requested_at__gte=start_date)
        
        stats = {
            'period': {
                'start_date': start_date.date(),
                'end_date': timezone.now().date(),
                'days': days,
            },
            'total_requests': queryset.count(),
            'pending_requests': queryset.filter(status='pending').count(),
            'approved_requests': queryset.filter(status='approved').count(),
            'rejected_requests': queryset.filter(status='rejected').count(),
            'cancelled_requests': queryset.filter(status='cancelled').count(),
            'total_revenue': 0,
            'upgrades_by_plan': {},
            'upgrades_by_status': {},
        }
        
        # Calculate total revenue
        approved_upgrades = queryset.filter(status='approved')
        for upgrade in approved_upgrades:
            if upgrade.price_difference:
                stats['total_revenue'] += float(upgrade.price_difference)
        
        # Count by plan
        for plan in Plan.objects.all():
            stats['upgrades_by_plan'][plan.name] = queryset.filter(
                to_plan=plan
            ).count()
        
        # Count by status
        for status in ['pending', 'approved', 'rejected', 'cancelled']:
            stats['upgrades_by_status'][status] = queryset.filter(
                status=status
            ).count()
        
        return stats
    
    @staticmethod
    def _validate_upgrade_request(tenant, from_plan, to_plan):
        """
        Validate an upgrade request.
        
        Args:
            tenant (Tenant): Tenant requesting upgrade
            from_plan (Plan): Current plan
            to_plan (Plan): Target plan
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate tenant has current plan
        if tenant.plan != from_plan:
            raise ValidationError(_('Tenant current plan does not match specified from_plan'))
        
        # Validate plans are different
        if from_plan == to_plan:
            raise ValidationError(_('Cannot upgrade to the same plan'))
        
        # Validate target plan is active
        if not to_plan.is_active:
            raise ValidationError(_('Target plan is not active'))
        
        # Validate upgrade path
        if not PlanUpgradeService._is_valid_upgrade_path(from_plan, to_plan):
            raise ValidationError(_('Invalid upgrade path'))
        
        # Validate tenant can upgrade
        if not PlanUpgradeService._can_upgrade(tenant, to_plan):
            raise ValidationError(_('Tenant cannot upgrade to this plan'))
    
    @staticmethod
    def _is_valid_upgrade_path(from_plan, to_plan):
        """
        Check if upgrade path is valid.
        
        Args:
            from_plan (Plan): Source plan
            to_plan (Plan): Target plan
            
        Returns:
            bool: True if valid upgrade path
        """
        # Allow upgrade to higher tier plans
        tier_hierarchy = ['basic', 'professional', 'enterprise']
        
        from_tier = from_plan.plan_type
        to_tier = to_plan.plan_type
        
        try:
            from_index = tier_hierarchy.index(from_tier)
            to_index = tier_hierarchy.index(to_tier)
            return to_index >= from_index
        except ValueError:
            # Handle custom plan types
            return True
    
    @staticmethod
    def _can_upgrade(tenant, to_plan):
        """
        Check if tenant can upgrade to target plan.
        
        Args:
            tenant (Tenant): Tenant to check
            to_plan (Plan): Target plan
            
        Returns:
            bool: True if tenant can upgrade
        """
        # Check if tenant has any outstanding issues
        if tenant.is_suspended:
            return False
        
        # Check if tenant has overdue invoices
        from ..models.core import TenantInvoice
        overdue_invoices = TenantInvoice.objects.filter(
            tenant=tenant,
            status='overdue'
        ).exists()
        
        if overdue_invoices:
            return False
        
        # Check usage limits (optional)
        # This could be expanded to check if tenant is within current plan limits
        
        return True
    
    @staticmethod
    def _calculate_price_difference(from_plan, to_plan):
        """
        Calculate price difference between plans.
        
        Args:
            from_plan (Plan): Source plan
            to_plan (Plan): Target plan
            
        Returns:
            Decimal: Price difference
        """
        # Use monthly prices for comparison
        from_price = from_plan.price_monthly or 0
        to_price = to_plan.price_monthly or 0
        
        return to_price - from_price
    
    @staticmethod
    def _process_upgrade(upgrade):
        """
        Process an approved upgrade.
        
        Args:
            upgrade (PlanUpgrade): Upgrade to process
        """
        tenant = upgrade.tenant
        to_plan = upgrade.to_plan
        
        # Update tenant plan
        tenant.plan = to_plan
        tenant.save()
        
        # Update billing if needed
        from ..models.core import TenantBilling
        try:
            billing = TenantBilling.objects.get(tenant=tenant)
            billing.base_price = to_plan.price_monthly
            billing.final_price = to_plan.price_monthly
            billing.save()
        except TenantBilling.DoesNotExist:
            # Create billing record if it doesn't exist
            TenantBilling.objects.create(
                tenant=tenant,
                base_price=to_plan.price_monthly,
                final_price=to_plan.price_monthly
            )
        
        # Update upgrade record
        upgrade.processed_at = timezone.now()
        upgrade.save()
    
    @staticmethod
    def _rollback_upgrade(upgrade):
        """
        Rollback a processed upgrade.
        
        Args:
            upgrade (PlanUpgrade): Upgrade to rollback
        """
        tenant = upgrade.tenant
        from_plan = upgrade.from_plan
        
        # Restore original plan
        tenant.plan = from_plan
        tenant.save()
        
        # Restore billing if needed
        from ..models.core import TenantBilling
        try:
            billing = TenantBilling.objects.get(tenant=tenant)
            billing.base_price = from_plan.price_monthly
            billing.final_price = from_plan.price_monthly
            billing.save()
        except TenantBilling.DoesNotExist:
            pass
