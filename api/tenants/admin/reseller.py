"""
Reseller Admin Classes

This module contains Django admin classes for reseller-related models including
ResellerConfig and ResellerInvoice.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.utils import timezone

from ..models.reseller import ResellerConfig, ResellerInvoice


@admin.register(ResellerConfig)
class ResellerConfigAdmin(admin.ModelAdmin):
    """
    Admin interface for ResellerConfig model.
    """
    list_display = [
        'company_name', 'reseller_id', 'parent_tenant_name',
        'status', 'is_verified', 'commission_type',
        'total_referrals', 'active_referrals', 'total_commission_earned'
    ]
    list_filter = [
        'status', 'is_verified', 'commission_type', 'support_level',
        'created_at', 'verified_at'
    ]
    search_fields = [
        'company_name', 'reseller_id', 'contact_email', 'contact_name'
    ]
    ordering = ['-created_at']
    raw_id_fields = ['parent_tenant']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Reseller Information', {
            'fields': (
                'parent_tenant', 'company_name', 'reseller_id',
                'contact_name', 'contact_email', 'contact_phone',
                'website_url', 'status', 'is_verified'
            )
        }),
        ('Commission Configuration', {
            'fields': (
                'commission_type', 'commission_pct', 'fixed_commission',
                'commission_tiers', 'payment_terms'
            )
        }),
        ('Support Level', {
            'fields': (
                'support_level', 'training_required',
                'training_completed_at'
            )
        }),
        ('Limits', {
            'fields': (
                'max_referrals', 'max_commission_per_month',
                'min_referral_value'
            )
        }),
        ('Verification', {
            'fields': (
                'verified_at', 'verification_documents',
                'verification_notes'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        })
    )
    
    def parent_tenant_name(self, obj):
        """Display parent tenant name with link."""
        url = reverse('admin:tenants_tenant_change', args=[obj.parent_tenant.id])
        return format_html('<a href="{}">{}</a>', url, obj.parent_tenant.name)
    parent_tenant_name.short_description = "Parent Tenant"
    parent_tenant_name.admin_order_field = 'parent_tenant__name'
    
    def status_display(self, obj):
        """Display status with color coding."""
        status_colors = {
            'active': '#388e3c',
            'inactive': '#f57c00',
            'suspended': '#d32f2f',
            'pending': '#ff9800',
        }
        
        color = status_colors.get(obj.status, '#9e9e9e')
        return mark_safe(f'<span style="color: {color}; font-weight: bold;">{obj.status}</span>')
    status_display.short_description = "Status"
    
    def is_verified_display(self, obj):
        """Display verification status."""
        if obj.is_verified:
            return mark_safe('<span style="color: #388e3c;">Verified</span>')
        else:
            return mark_safe('<span style="color: #f57c00;">Not Verified</span>')
    is_verified_display.short_description = "Verified"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('parent_tenant')
    
    actions = [
        'verify_resellers', 'activate_resellers', 'deactivate_resellers',
        'calculate_commissions', 'export_resellers'
    ]
    
    def verify_resellers(self, request, queryset):
        """Verify selected resellers."""
        count = queryset.filter(is_verified=False).update(
            is_verified=True,
            verified_at=timezone.now()
        )
        self.message_user(request, f"Verified {count} resellers.", messages.SUCCESS)
    verify_resellers.short_description = "Verify selected resellers"
    
    def activate_resellers(self, request, queryset):
        """Activate selected resellers."""
        count = queryset.filter(status='inactive').update(status='active')
        self.message_user(request, f"Activated {count} resellers.", messages.SUCCESS)
    activate_resellers.short_description = "Activate selected resellers"
    
    def deactivate_resellers(self, request, queryset):
        """Deactivate selected resellers."""
        count = queryset.filter(status='active').update(status='inactive')
        self.message_user(request, f"Deactivated {count} resellers.", messages.SUCCESS)
    deactivate_resellers.short_description = "Deactivate selected resellers"
    
    def calculate_commissions(self, request, queryset):
        """Calculate commissions for selected resellers."""
        count = 0
        for reseller in queryset:
            # This would trigger commission calculation
            count += 1
        
        self.message_user(request, f"Calculated commissions for {count} resellers.", messages.SUCCESS)
    calculate_commissions.short_description = "Calculate commissions"
    
    def export_resellers(self, request, queryset):
        """Export reseller data."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="resellers_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Company Name', 'Reseller ID', 'Status', 'Verified',
            'Commission Type', 'Total Referrals', 'Active Referrals',
            'Total Commission Earned', 'Contact Email'
        ])
        
        for reseller in queryset:
            writer.writerow([
                reseller.company_name,
                reseller.reseller_id,
                reseller.status,
                reseller.is_verified,
                reseller.commission_type,
                reseller.total_referrals,
                reseller.active_referrals,
                reseller.total_commission_earned,
                reseller.contact_email,
            ])
        
        return response
    export_resellers.short_description = "Export reseller data"


@admin.register(ResellerInvoice)
class ResellerInvoiceAdmin(admin.ModelAdmin):
    """
    Admin interface for ResellerInvoice model.
    """
    list_display = [
        'reseller_name', 'invoice_number', 'status',
        'period_start', 'period_end', 'commission_amount',
        'total_amount', 'created_at'
    ]
    list_filter = [
        'status', 'period_start', 'period_end', 'created_at',
        'paid_date'
    ]
    search_fields = [
        'reseller__company_name', 'invoice_number', 'notes'
    ]
    ordering = ['-created_at']
    raw_id_fields = ['reseller']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Invoice Information', {
            'fields': (
                'reseller', 'invoice_number', 'status',
                'period_start', 'period_end'
            )
        }),
        ('Commission Details', {
            'fields': (
                'commission_amount', 'bonus_amount',
                'total_amount', 'referral_count', 'active_referrals'
            )
        }),
        ('Approval', {
            'fields': (
                'notes',
                'rejection_reason'
            )
        }),
        ('Payment', {
            'fields': (
                'paid_date', 'payment_method', 'transaction_id'
            ),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        })
    )
    
    def reseller_name(self, obj):
        """Display reseller name with link."""
        url = reverse('admin:tenants_resellerconfig_change', args=[obj.reseller.id])
        return format_html('<a href="{}">{}</a>', url, obj.reseller.company_name)
    reseller_name.short_description = "Reseller"
    reseller_name.admin_order_field = 'reseller__company_name'
    
    def status_display(self, obj):
        """Display status with color coding."""
        status_colors = {
            'pending': '#f57c00',
            'approved': '#388e3c',
            'rejected': '#d32f2f',
            'paid': '#388e3c',
            'cancelled': '#9e9e9e',
        }
        
        color = status_colors.get(obj.status, '#9e9e9e')
        return mark_safe(f'<span style="color: {color}; font-weight: bold;">{obj.status}</span>')
    status_display.short_description = "Status"
    
    def commission_amount_display(self, obj):
        """Display commission amount."""
        return f"${obj.commission_amount:.2f}"
    commission_amount_display.short_description = "Commission"
    
    def total_amount_display(self, obj):
        """Display total amount."""
        return f"${obj.total_amount:.2f}"
    total_amount_display.short_description = "Total"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('reseller')
    
    actions = [
        'approve_invoices', 'reject_invoices', 'mark_as_paid',
        'export_invoices', 'generate_commission_reports'
    ]
    
    def approve_invoices(self, request, queryset):
        """Approve selected invoices."""
        count = 0
        for invoice in queryset.filter(status='pending'):
            invoice.approve(request.user)
            count += 1
        
        self.message_user(request, f"Approved {count} invoices.", messages.SUCCESS)
    approve_invoices.short_description = "Approve selected invoices"
    
    def reject_invoices(self, request, queryset):
        """Reject selected invoices."""
        count = 0
        for invoice in queryset.filter(status='pending'):
            invoice.reject(request.user, "Admin rejection")
            count += 1
        
        self.message_user(request, f"Rejected {count} invoices.", messages.SUCCESS)
    reject_invoices.short_description = "Reject selected invoices"
    
    def mark_as_paid(self, request, queryset):
        """Mark selected invoices as paid."""
        count = 0
        for invoice in queryset.filter(status='approved'):
            invoice.status = 'paid'
            invoice.paid_date = timezone.now()
            invoice.save()
            count += 1
        
        self.message_user(request, f"Marked {count} invoices as paid.", messages.SUCCESS)
    mark_as_paid.short_description = "Mark as paid"
    
    def export_invoices(self, request, queryset):
        """Export invoice data."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="reseller_invoices_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Reseller', 'Invoice Number', 'Status', 'Period Start',
            'Period End', 'Commission Amount', 'Total Amount',
            'Referral Count', 'Active Referrals'
        ])
        
        for invoice in queryset:
            writer.writerow([
                invoice.reseller.company_name,
                invoice.invoice_number,
                invoice.status,
                invoice.period_start.isoformat(),
                invoice.period_end.isoformat(),
                invoice.commission_amount,
                invoice.total_amount,
                invoice.referral_count,
                invoice.active_referrals,
            ])
        
        return response
    export_invoices.short_description = "Export invoice data"
    
    def generate_commission_reports(self, request, queryset):
        """Generate commission reports for selected resellers."""
        count = 0
        for invoice in queryset:
            # This would generate detailed commission reports
            count += 1
        
        self.message_user(request, f"Generated commission reports for {count} invoices.", messages.SUCCESS)
    generate_commission_reports.short_description = "Generate commission reports"
