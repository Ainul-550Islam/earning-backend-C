"""
Reseller Serializers

This module contains serializers for reseller-related models including
ResellerConfig and ResellerInvoice.
"""

from rest_framework import serializers
from django.utils import timezone
from ..models.reseller import ResellerConfig, ResellerInvoice


class ResellerConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for ResellerConfig model.
    """
    status_display = serializers.SerializerMethodField()
    commission_type_display = serializers.SerializerMethodField()
    billing_cycle_display = serializers.SerializerMethodField()
    support_level_display = serializers.SerializerMethodField()
    payment_method_display = serializers.SerializerMethodField()
    is_contract_expired = serializers.SerializerMethodField()
    days_until_contract_expiry = serializers.SerializerMethodField()
    current_referrals = serializers.SerializerMethodField()
    
    class Meta:
        model = ResellerConfig
        fields = [
            'id', 'parent_tenant', 'reseller_id', 'company_name', 'contact_email',
            'contact_phone', 'status', 'status_display', 'is_verified',
            'verified_at', 'commission_type', 'commission_type_display',
            'commission_pct', 'fixed_commission', 'commission_tiers',
            'max_child_tenants', 'max_monthly_signups', 'min_monthly_revenue',
            'billing_cycle', 'billing_cycle_display', 'payment_method',
            'payment_method_display', 'payment_details', 'can_brand',
            'custom_pricing', 'white_label', 'support_level',
            'support_level_display', 'training_required', 'training_completed_at',
            'contract_start', 'contract_end', 'is_contract_expired',
            'days_until_contract_expiry', 'contract_terms', 'total_referrals',
            'active_referrals', 'current_referrals', 'total_commission_earned',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'parent_tenant', 'verified_at', 'total_referrals',
            'active_referrals', 'total_commission_earned', 'created_at',
            'updated_at'
        ]
    
    def get_status_display(self, obj):
        """Get status display name."""
        return obj.get_status_display()
    
    def get_commission_type_display(self, obj):
        """Get commission type display name."""
        return obj.get_commission_type_display()
    
    def get_billing_cycle_display(self, obj):
        """Get billing cycle display name."""
        return obj.get_billing_cycle_display()
    
    def get_support_level_display(self, obj):
        """Get support level display name."""
        return obj.get_support_level_display()
    
    def get_payment_method_display(self, obj):
        """Get payment method display name."""
        return obj.get_payment_method_display()
    
    def get_is_contract_expired(self, obj):
        """Check if contract is expired."""
        return obj.is_contract_expired
    
    def get_days_until_contract_expiry(self, obj):
        """Get days until contract expires."""
        return obj.days_until_contract_expiry
    
    def get_current_referrals(self, obj):
        """Get current referral statistics."""
        return {
            'total': obj.total_referrals,
            'active': obj.active_referrals,
        }
    
    def validate(self, attrs):
        """Validate reseller configuration data."""
        # Validate commission percentage
        commission_pct = attrs.get('commission_pct')
        if commission_pct is not None:
            if commission_pct < 0 or commission_pct > 100:
                raise serializers.ValidationError("Commission percentage must be between 0 and 100.")
        
        # Validate limits
        limit_fields = [
            'max_child_tenants', 'max_monthly_signups', 'min_monthly_revenue'
        ]
        
        for field in limit_fields:
            if field in attrs:
                limit = attrs[field]
                if limit < 0:
                    raise serializers.ValidationError(f"{field} cannot be negative.")
        
        # Validate contract dates
        contract_start = attrs.get('contract_start')
        contract_end = attrs.get('contract_end')
        
        if contract_start and contract_end and contract_start >= contract_end:
            raise serializers.ValidationError("Contract start must be before contract end.")
        
        return attrs


class ResellerConfigCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new reseller configurations.
    """
    class Meta:
        model = ResellerConfig
        fields = [
            'reseller_id', 'company_name', 'contact_email', 'contact_phone',
            'commission_type', 'commission_pct', 'fixed_commission',
            'commission_tiers', 'max_child_tenants', 'max_monthly_signups',
            'min_monthly_revenue', 'billing_cycle', 'payment_method',
            'payment_details', 'can_brand', 'custom_pricing', 'white_label',
            'support_level', 'training_required', 'contract_start',
            'contract_end', 'contract_terms'
        ]
    
    def validate_reseller_id(self, value):
        """Validate reseller ID uniqueness."""
        if ResellerConfig.objects.filter(reseller_id=value).exists():
            raise serializers.ValidationError("Reseller ID already exists.")
        return value
    
    def validate(self, attrs):
        """Validate reseller creation data."""
        commission_type = attrs.get('commission_type')
        
        # Validate commission type requirements
        if commission_type == 'percentage' and not attrs.get('commission_pct'):
            raise serializers.ValidationError("Commission percentage is required for percentage type.")
        
        if commission_type == 'fixed' and not attrs.get('fixed_commission'):
            raise serializers.ValidationError("Fixed commission is required for fixed type.")
        
        if commission_type == 'tiered' and not attrs.get('commission_tiers'):
            raise serializers.ValidationError("Commission tiers are required for tiered type.")
        
        return attrs


class ResellerInvoiceSerializer(serializers.ModelSerializer):
    """
    Serializer for ResellerInvoice model.
    """
    status_display = serializers.SerializerMethodField()
    reseller_details = serializers.SerializerMethodField()
    from_plan_details = serializers.SerializerMethodField()
    to_plan_details = serializers.SerializerMethodField()
    approved_by_details = serializers.SerializerMethodField()
    days_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = ResellerInvoice
        fields = [
            'id', 'reseller', 'reseller_details', 'invoice_number', 'status',
            'status_display', 'period_start', 'period_end', 'commission_amount',
            'bonus_amount', 'tax_amount', 'total_amount', 'due_date',
            'paid_date', 'payment_method', 'transaction_id', 'referral_count',
            'active_referrals', 'referral_details', 'notes', 'metadata',
            'from_plan_details', 'to_plan_details', 'approved_by',
            'approved_by_details', 'approved_at', 'days_overdue', 'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 'reseller', 'invoice_number', 'approved_at', 'created_at',
            'updated_at'
        ]
    
    def get_status_display(self, obj):
        """Get status display name."""
        return obj.get_status_display()
    
    def get_reseller_details(self, obj):
        """Get reseller details."""
        return {
            'id': str(obj.reseller.parent_tenant.id),
            'name': obj.reseller.company_name,
            'reseller_id': obj.reseller.reseller_id,
        }
    
    def get_from_plan_details(self, obj):
        """Get from plan details."""
        if obj.from_plan:
            return {
                'id': str(obj.from_plan.id),
                'name': obj.from_plan.name,
                'slug': obj.from_plan.slug,
            }
        return None
    
    def get_to_plan_details(self, obj):
        """Get to plan details."""
        if obj.to_plan:
            return {
                'id': str(obj.to_plan.id),
                'name': obj.to_plan.name,
                'slug': obj.to_plan.slug,
            }
        return None
    
    def get_approved_by_details(self, obj):
        """Get approved by user details."""
        if obj.approved_by:
            return {
                'id': str(obj.approved_by.id),
                'username': obj.approved_by.username,
                'email': obj.approved_by.email,
            }
        return None
    
    def get_days_overdue(self, obj):
        """Get days overdue."""
        return obj.days_overdue
    
    def validate(self, attrs):
        """Validate invoice data."""
        # Validate period dates
        period_start = attrs.get('period_start')
        period_end = attrs.get('period_end')
        
        if period_start and period_end and period_start > period_end:
            raise serializers.ValidationError("Period start cannot be after period end.")
        
        # Validate amounts
        amount_fields = ['commission_amount', 'bonus_amount', 'tax_amount']
        for field in amount_fields:
            if field in attrs:
                amount = attrs[field]
                if amount < 0:
                    raise serializers.ValidationError(f"{field} cannot be negative.")
        
        # Validate due date
        due_date = attrs.get('due_date')
        if due_date and due_date <= timezone.now().date():
            raise serializers.ValidationError("Due date must be in the future.")
        
        return attrs
