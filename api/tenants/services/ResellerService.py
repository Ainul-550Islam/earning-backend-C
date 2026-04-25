"""
Reseller Service

This module provides business logic for managing reseller operations
including reseller configuration, commission tracking, and hierarchy management.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from ..models.reseller import ResellerConfig, ResellerInvoice
from ..models.core import Tenant
from ..models.plan import Plan
from .base import BaseService


class ResellerService(BaseService):
    """
    Service class for managing reseller operations.
    
    Provides business logic for reseller operations including:
    - Reseller configuration and management
    - Commission calculation and tracking
    - Reseller hierarchy management
    - Reseller analytics and reporting
    """
    
    @staticmethod
    def create_reseller_config(tenant, reseller_data):
        """
        Create a new reseller configuration.
        
        Args:
            tenant (Tenant): Tenant to create reseller config for
            reseller_data (dict): Reseller configuration data
            
        Returns:
            ResellerConfig: Created reseller config
            
        Raises:
            ValidationError: If reseller data is invalid
        """
        try:
            with transaction.atomic():
                # Validate reseller data
                ResellerService._validate_reseller_data(reseller_data, tenant)
                
                # Check for existing reseller config
                if ResellerConfig.objects.filter(parent_tenant=tenant).exists():
                    raise ValidationError(_('Reseller configuration already exists for this tenant'))
                
                # Generate unique reseller ID
                reseller_id = ResellerService._generate_reseller_id(reseller_data.get('company_name'))
                
                # Create reseller config
                reseller = ResellerConfig.objects.create(
                    parent_tenant=tenant,
                    company_name=reseller_data['company_name'],
                    reseller_id=reseller_id,
                    contact_person=reseller_data.get('contact_person', ''),
                    contact_email=reseller_data.get('contact_email', ''),
                    contact_phone=reseller_data.get('contact_phone', ''),
                    address=reseller_data.get('address', ''),
                    website=reseller_data.get('website', ''),
                    commission_type=reseller_data.get('commission_type', 'percentage'),
                    commission_pct=reseller_data.get('commission_pct', 10.0),
                    commission_fixed=reseller_data.get('commission_fixed', 0.0),
                    commission_tiers=reseller_data.get('commission_tiers', {}),
                    max_tenants=reseller_data.get('max_tenants', 100),
                    max_sub_resellers=reseller_data.get('max_sub_resellers', 5),
                    status=reseller_data.get('status', 'pending'),
                    contract_start_date=reseller_data.get('contract_start_date'),
                    contract_end_date=reseller_data.get('contract_end_date'),
                    payment_terms=reseller_data.get('payment_terms', 'monthly'),
                    metadata=reseller_data.get('metadata', {})
                )
                
                return reseller
                
        except Exception as e:
            raise ValidationError(f"Failed to create reseller config: {str(e)}")
    
    @staticmethod
    def update_reseller_config(reseller, reseller_data):
        """
        Update an existing reseller configuration.
        
        Args:
            reseller (ResellerConfig): Reseller config to update
            reseller_data (dict): Updated reseller data
            
        Returns:
            ResellerConfig: Updated reseller config
            
        Raises:
            ValidationError: If reseller data is invalid
        """
        try:
            with transaction.atomic():
                # Validate reseller data
                ResellerService._validate_reseller_data(reseller_data, reseller.parent_tenant, update=True)
                
                # Update reseller fields
                for field, value in reseller_data.items():
                    if hasattr(reseller, field) and field not in ['id', 'parent_tenant', 'reseller_id', 'created_at']:
                        setattr(reseller, field, value)
                
                reseller.save()
                return reseller
                
        except Exception as e:
            raise ValidationError(f"Failed to update reseller config: {str(e)}")
    
    @staticmethod
    def activate_reseller(reseller, activated_by=None):
        """
        Activate a reseller.
        
        Args:
            reseller (ResellerConfig): Reseller to activate
            activated_by (User): User activating reseller
            
        Returns:
            ResellerConfig: Activated reseller
        """
        reseller.status = 'active'
        reseller.activated_at = timezone.now()
        reseller.activated_by = activated_by
        reseller.save()
        return reseller
    
    @staticmethod
    def deactivate_reseller(reseller, deactivated_by=None, reason=None):
        """
        Deactivate a reseller.
        
        Args:
            reseller (ResellerConfig): Reseller to deactivate
            deactivated_by (User): User deactivating reseller
            reason (str): Deactivation reason
            
        Returns:
            ResellerConfig: Deactivated reseller
        """
        reseller.status = 'inactive'
        reseller.deactivated_at = timezone.now()
        reseller.deactivated_by = deactivated_by
        reseller.deactivation_reason = reason or ''
        reseller.save()
        return reseller
    
    @staticmethod
    def verify_reseller(reseller, verified_by=None):
        """
        Verify a reseller.
        
        Args:
            reseller (ResellerConfig): Reseller to verify
            verified_by (User): User verifying reseller
            
        Returns:
            ResellerConfig: Verified reseller
        """
        reseller.is_verified = True
        reseller.verified_at = timezone.now()
        reseller.verified_by = verified_by
        reseller.save()
        return reseller
    
    @staticmethod
    def get_reseller_tenants(reseller, active_only=True):
        """
        Get all tenants for a reseller.
        
        Args:
            reseller (ResellerConfig): Reseller to get tenants for
            active_only (bool): Whether to get only active tenants
            
        Returns:
            QuerySet: Reseller tenants
        """
        queryset = Tenant.objects.filter(parent_tenant=reseller.parent_tenant)
        if active_only:
            queryset = queryset.filter(is_active=True, is_deleted=False)
        return queryset.order_by('-created_at')
    
    @staticmethod
    def calculate_commission(reseller, period='monthly'):
        """
        Calculate commission for a reseller.
        
        Args:
            reseller (ResellerConfig): Reseller to calculate commission for
            period (str): Period for calculation
            
        Returns:
            dict: Commission calculation result
        """
        try:
            # Get reseller tenants
            tenants = ResellerService.get_reseller_tenants(reseller)
            
            # Calculate total revenue from tenants
            total_revenue = 0
            tenant_revenue = {}
            
            for tenant in tenants:
                tenant_revenue = ResellerService._get_tenant_revenue(tenant, period)
                total_revenue += tenant_revenue
                tenant_revenue[tenant.id] = tenant_revenue
            
            # Calculate commission based on type
            if reseller.commission_type == 'percentage':
                commission_amount = total_revenue * (reseller.commission_pct / 100)
            elif reseller.commission_type == 'fixed':
                commission_amount = reseller.commission_fixed * len(tenants)
            elif reseller.commission_type == 'tiered':
                commission_amount = ResellerService._calculate_tiered_commission(
                    reseller, total_revenue, reseller.commission_tiers
                )
            else:  # hybrid
                percentage_commission = total_revenue * (reseller.commission_pct / 100)
                fixed_commission = reseller.commission_fixed * len(tenants)
                commission_amount = percentage_commission + fixed_commission
            
            return {
                'reseller': reseller,
                'period': period,
                'total_revenue': total_revenue,
                'commission_amount': commission_amount,
                'commission_type': reseller.commission_type,
                'tenant_count': len(tenants),
                'tenant_revenue': tenant_revenue,
                'calculated_at': timezone.now()
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'commission_amount': 0
            }
    
    @staticmethod
    def create_commission_invoice(reseller, commission_data):
        """
        Create a commission invoice for a reseller.
        
        Args:
            reseller (ResellerConfig): Reseller to create invoice for
            commission_data (dict): Commission data
            
        Returns:
            ResellerInvoice: Created commission invoice
        """
        try:
            with transaction.atomic():
                # Generate invoice number
                invoice_number = ResellerService._generate_commission_invoice_number(reseller)
                
                # Create commission invoice
                invoice = ResellerInvoice.objects.create(
                    reseller=reseller,
                    invoice_number=invoice_number,
                    period=commission_data.get('period', 'monthly'),
                    total_revenue=commission_data.get('total_revenue', 0),
                    commission_amount=commission_data.get('commission_amount', 0),
                    commission_type=reseller.commission_type,
                    commission_rate=reseller.commission_pct if reseller.commission_type == 'percentage' else None,
                    status='pending',
                    issue_date=timezone.now().date(),
                    due_date=timezone.now().date() + timezone.timedelta(days=30),
                    metadata=commission_data.get('metadata', {})
                )
                
                return invoice
                
        except Exception as e:
            raise ValidationError(f"Failed to create commission invoice: {str(e)}")
    
    @staticmethod
    def get_reseller_statistics(reseller=None, days=30):
        """
        Get reseller statistics.
        
        Args:
            reseller (ResellerConfig): Specific reseller (optional)
            days (int): Number of days to analyze
            
        Returns:
            dict: Reseller statistics
        """
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        try:
            queryset = ResellerConfig.objects.all()
            if reseller:
                queryset = queryset.filter(id=reseller.id)
            
            stats = {
                'period': {
                    'start_date': start_date.date(),
                    'end_date': timezone.now().date(),
                    'days': days,
                },
                'total_resellers': queryset.count(),
                'active_resellers': queryset.filter(status='active').count(),
                'verified_resellers': queryset.filter(is_verified=True).count(),
                'pending_resellers': queryset.filter(status='pending').count(),
                'total_tenants': 0,
                'total_revenue': 0,
                'total_commission': 0,
                'resellers_by_status': {},
                'commission_by_type': {}
            }
            
            # Count by status
            for status in ['active', 'inactive', 'pending', 'suspended']:
                stats['resellers_by_status'][status] = queryset.filter(status=status).count()
            
            # Count by commission type
            for commission_type in ['percentage', 'fixed', 'tiered', 'hybrid']:
                stats['commission_by_type'][commission_type] = queryset.filter(
                    commission_type=commission_type
                ).count()
            
            # Calculate aggregate statistics
            for reseller_obj in queryset:
                tenants = ResellerService.get_reseller_tenants(reseller_obj)
                stats['total_tenants'] += tenants.count()
                
                # Calculate revenue and commission
                commission_result = ResellerService.calculate_commission(reseller_obj)
                stats['total_revenue'] += commission_result.get('total_revenue', 0)
                stats['total_commission'] += commission_result.get('commission_amount', 0)
            
            return stats
            
        except Exception as e:
            return {
                'error': str(e)
            }
    
    @staticmethod
    def get_commission_report(reseller, start_date, end_date):
        """
        Get commission report for a reseller.
        
        Args:
            reseller (ResellerConfig): Reseller to get report for
            start_date (date): Report start date
            end_date (date): Report end date
            
        Returns:
            dict: Commission report
        """
        try:
            invoices = ResellerInvoice.objects.filter(
                reseller=reseller,
                issue_date__gte=start_date,
                issue_date__lte=end_date
            ).order_by('issue_date')
            
            report = {
                'reseller': reseller,
                'period': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'total_invoices': invoices.count(),
                'total_revenue': 0,
                'total_commission': 0,
                'paid_commission': 0,
                'pending_commission': 0,
                'overdue_commission': 0,
                'invoices': []
            }
            
            for invoice in invoices:
                report['total_revenue'] += invoice.total_revenue
                report['total_commission'] += invoice.commission_amount
                
                if invoice.status == 'paid':
                    report['paid_commission'] += invoice.commission_amount
                elif invoice.status == 'pending':
                    report['pending_commission'] += invoice.commission_amount
                elif invoice.status == 'overdue':
                    report['overdue_commission'] += invoice.commission_amount
                
                report['invoices'].append({
                    'invoice_number': invoice.invoice_number,
                    'period': invoice.period,
                    'total_revenue': invoice.total_revenue,
                    'commission_amount': invoice.commission_amount,
                    'status': invoice.status,
                    'issue_date': invoice.issue_date,
                    'due_date': invoice.due_date,
                    'paid_date': invoice.paid_date
                })
            
            return report
            
        except Exception as e:
            return {
                'error': str(e)
            }
    
    @staticmethod
    def _validate_reseller_data(reseller_data, tenant, update=False):
        """
        Validate reseller configuration data.
        
        Args:
            reseller_data (dict): Reseller data to validate
            tenant (Tenant): Tenant the reseller belongs to
            update (bool): Whether this is an update operation
            
        Raises:
            ValidationError: If validation fails
        """
        required_fields = ['company_name']
        if not update:
            required_fields.extend(['contact_email'])
        
        for field in required_fields:
            if field not in reseller_data:
                raise ValidationError(f"'{field}' is required")
        
        # Validate company name
        company_name = reseller_data['company_name']
        if not isinstance(company_name, str) or not company_name.strip():
            raise ValidationError("Company name must be a non-empty string")
        
        # Validate email
        contact_email = reseller_data.get('contact_email')
        if contact_email and '@' not in contact_email:
            raise ValidationError("Invalid email address")
        
        # Validate commission type
        commission_type = reseller_data.get('commission_type', 'percentage')
        valid_types = ['percentage', 'fixed', 'tiered', 'hybrid']
        if commission_type not in valid_types:
            raise ValidationError(f"Commission type must be one of: {', '.join(valid_types)}")
        
        # Validate commission values
        if commission_type == 'percentage':
            commission_pct = reseller_data.get('commission_pct', 10.0)
            if not isinstance(commission_pct, (int, float)) or commission_pct < 0 or commission_pct > 100:
                raise ValidationError("Commission percentage must be between 0 and 100")
        
        elif commission_type == 'fixed':
            commission_fixed = reseller_data.get('commission_fixed', 0.0)
            if not isinstance(commission_fixed, (int, float)) or commission_fixed < 0:
                raise ValidationError("Commission fixed amount must be a positive number")
        
        # Validate limits
        max_tenants = reseller_data.get('max_tenants', 100)
        if not isinstance(max_tenants, int) or max_tenants < 1:
            raise ValidationError("Max tenants must be a positive integer")
        
        max_sub_resellers = reseller_data.get('max_sub_resellers', 5)
        if not isinstance(max_sub_resellers, int) or max_sub_resellers < 0:
            raise ValidationError("Max sub-resellers must be a non-negative integer")
    
    @staticmethod
    def _generate_reseller_id(company_name):
        """
        Generate a unique reseller ID.
        
        Args:
            company_name (str): Company name
            
        Returns:
            str: Generated reseller ID
        """
        import re
        import uuid
        
        # Clean company name
        clean_name = re.sub(r'[^a-zA-Z0-9]', '', company_name.upper())
        
        # Generate unique suffix
        suffix = str(uuid.uuid4())[:8].upper()
        
        # Combine and ensure uniqueness
        base_id = f"RES-{clean_name[:6]}-{suffix}"
        
        # Ensure uniqueness
        counter = 1
        while ResellerConfig.objects.filter(reseller_id=base_id).exists():
            base_id = f"RES-{clean_name[:6]}-{suffix}-{counter}"
            counter += 1
        
        return base_id
    
    @staticmethod
    def _generate_commission_invoice_number(reseller):
        """
        Generate a commission invoice number.
        
        Args:
            reseller (ResellerConfig): Reseller to generate invoice for
            
        Returns:
            str: Generated invoice number
        """
        from datetime import datetime
        
        # Get current count for this reseller
        count = ResellerInvoice.objects.filter(reseller=reseller).count() + 1
        
        # Generate invoice number
        date_str = datetime.now().strftime("%Y%m")
        return f"COMM-{reseller.reseller_id}-{date_str}-{count:04d}"
    
    @staticmethod
    def _get_tenant_revenue(tenant, period):
        """
        Get revenue for a tenant in a period.
        
        Args:
            tenant (Tenant): Tenant to get revenue for
            period (str): Period for revenue calculation
            
        Returns:
            float: Tenant revenue
        """
        try:
            from ..models.core import TenantInvoice
            
            # Define period date range
            from datetime import timedelta
            if period == 'daily':
                start_date = timezone.now().date() - timedelta(days=1)
                end_date = timezone.now().date()
            elif period == 'weekly':
                start_date = timezone.now().date() - timedelta(weeks=1)
                end_date = timezone.now().date()
            elif period == 'monthly':
                start_date = timezone.now().date() - timedelta(days=30)
                end_date = timezone.now().date()
            else:
                start_date = timezone.now().date() - timedelta(days=30)
                end_date = timezone.now().date()
            
            # Calculate revenue from paid invoices
            revenue = TenantInvoice.objects.filter(
                tenant=tenant,
                status='paid',
                issue_date__gte=start_date,
                issue_date__lte=end_date
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            return float(revenue)
            
        except Exception:
            return 0.0
    
    @staticmethod
    def _calculate_tiered_commission(reseller, total_revenue, tiers):
        """
        Calculate tiered commission.
        
        Args:
            reseller (ResellerConfig): Reseller configuration
            total_revenue (float): Total revenue
            tiers (dict): Commission tiers
            
        Returns:
            float: Calculated commission
        """
        if not tiers:
            # Default tiers
            tiers = {
                'tier1': {'min': 0, 'max': 10000, 'rate': 5.0},
                'tier2': {'min': 10000, 'max': 50000, 'rate': 7.5},
                'tier3': {'min': 50000, 'max': float('inf'), 'rate': 10.0}
            }
        
        commission = 0.0
        remaining_revenue = total_revenue
        
        for tier_name, tier_config in tiers.items():
            tier_min = tier_config['min']
            tier_max = tier_config['max']
            tier_rate = tier_config['rate']
            
            if remaining_revenue <= tier_min:
                continue
            
            # Calculate revenue in this tier
            tier_revenue = min(remaining_revenue, tier_max - tier_min)
            
            # Calculate commission for this tier
            tier_commission = tier_revenue * (tier_rate / 100)
            commission += tier_commission
            
            remaining_revenue -= tier_revenue
            
            if remaining_revenue <= 0:
                break
        
        return commission
