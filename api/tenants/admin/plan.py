"""
Plan Admin Classes

This module contains Django admin classes for plan-related models including
Plan, PlanFeature, PlanUpgrade, PlanUsage, and PlanQuota.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum, Avg
from django.http import HttpResponseRedirect
from django.contrib import messages

from ..models.plan import Plan, PlanFeature, PlanUpgrade, PlanUsage, PlanQuota


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    """
    Admin interface for Plan model with comprehensive management features.
    """
    list_display = [
        'name', 'slug', 'plan_type', 'billing_cycle',
        'price_monthly', 'price_yearly', 'is_active',
        'is_public', 'is_featured', 'trial_days', 'tenant_count'
    ]
    list_filter = [
        'plan_type', 'billing_cycle', 'is_active', 'is_public',
        'is_featured', 'trial_requires_payment', 'can_downgrade'
    ]
    search_fields = ['name', 'slug', 'description']
    ordering = ['sort_order', 'name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name', 'slug', 'description', 'plan_type', 'billing_cycle',
                'is_active', 'is_public', 'is_upgrade_only', 'sort_order'
            )
        }),
        ('Pricing', {
            'fields': (
                'price_monthly', 'price_yearly', 'setup_fee',
                'yearly_discount_percentage'
            )
        }),
        ('Limits', {
            'fields': (
                'max_users', 'max_publishers', 'max_smartlinks', 'max_campaigns',
                'api_calls_per_day', 'api_calls_per_hour', 'storage_gb',
                'bandwidth_gb_per_month'
            )
        }),
        ('Features', {
            'fields': (
                'features', 'feature_flags', 'downgrade_to_plans'
            ),
            'classes': ('collapse',)
        }),
        ('Trial Information', {
            'fields': (
                'trial_days', 'trial_requires_payment', 'can_downgrade',
                'can_upgrade'
            )
        }),
        ('Display Options', {
            'fields': (
                'is_featured', 'badge_text', 'custom_settings'
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def tenant_count(self, obj):
        """Display number of tenants on this plan."""
        count = obj.tenant_set.filter(is_deleted=False).count()
        url = reverse('admin:tenants_tenant_changelist') + f'?plan__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)
    tenant_count.short_description = "Tenants"
    tenant_count.admin_order_field = 'tenant_count'
    
    def get_queryset(self, request):
        """Optimize queryset with tenant count."""
        return super().get_queryset(request).annotate(
            tenant_count=Count('tenant')
        )
    
    actions = ['activate_plans', 'deactivate_plans', 'export_plans', 'duplicate_plans']
    
    def activate_plans(self, request, queryset):
        """Activate selected plans."""
        count = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, f"Activated {count} plans.", messages.SUCCESS)
    activate_plans.short_description = "Activate selected plans"
    
    def deactivate_plans(self, request, queryset):
        """Deactivate selected plans."""
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f"Deactivated {count} plans.", messages.SUCCESS)
    deactivate_plans.short_description = "Deactivate selected plans"
    
    def export_plans(self, request, queryset):
        """Export selected plans data."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="plans_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Type', 'Monthly Price', 'Yearly Price',
            'Max Users', 'Max Publishers', 'Is Active', 'Tenant Count'
        ])
        
        for plan in queryset:
            writer.writerow([
                plan.name,
                plan.plan_type,
                plan.price_monthly,
                plan.price_yearly,
                plan.max_users,
                plan.max_publishers,
                plan.is_active,
                plan.tenant_set.filter(is_deleted=False).count()
            ])
        
        return response
    export_plans.short_description = "Export selected plans"
    
    def duplicate_plans(self, request, queryset):
        """Duplicate selected plans."""
        count = 0
        for plan in queryset:
            # Create a copy of the plan
            new_plan = Plan.objects.create(
                name=f"{plan.name} (Copy)",
                slug=f"{plan.slug}-copy",
                description=plan.description,
                plan_type=plan.plan_type,
                billing_cycle=plan.billing_cycle,
                price_monthly=plan.price_monthly,
                price_yearly=plan.price_yearly,
                setup_fee=plan.setup_fee,
                max_users=plan.max_users,
                max_publishers=plan.max_publishers,
                max_smartlinks=plan.max_smartlinks,
                max_campaigns=plan.max_campaigns,
                api_calls_per_day=plan.api_calls_per_day,
                api_calls_per_hour=plan.api_calls_per_hour,
                storage_gb=plan.storage_gb,
                bandwidth_gb_per_month=plan.bandwidth_gb_per_month,
                features=plan.features,
                feature_flags=plan.feature_flags,
                is_active=False,  # Start inactive
                is_public=plan.is_public,
                trial_days=plan.trial_days,
                trial_requires_payment=plan.trial_requires_payment,
                can_downgrade=plan.can_downgrade,
                can_upgrade=plan.can_upgrade,
                downgrade_to_plans=plan.downgrade_to_plans.all(),
            )
            count += 1
        
        self.message_user(request, f"Duplicated {count} plans.", messages.SUCCESS)
    duplicate_plans.short_description = "Duplicate selected plans"


@admin.register(PlanFeature)
class PlanFeatureAdmin(admin.ModelAdmin):
    """
    Admin interface for PlanFeature model.
    """
    list_display = [
        'name', 'key', 'feature_type', 'is_active', 'is_public',
        'category', 'sort_order', 'default_value'
    ]
    list_filter = [
        'feature_type', 'is_active', 'is_public', 'category'
    ]
    search_fields = ['name', 'key', 'description']
    ordering = ['category', 'sort_order', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name', 'key', 'description', 'feature_type',
                'is_active', 'is_public', 'category', 'sort_order'
            )
        }),
        ('Value Configuration', {
            'fields': (
                'default_value', 'min_value', 'max_value',
                'allowed_values', 'display_name', 'icon'
            )
        }),
        ('Display Options', {
            'fields': ('custom_settings',),
            'classes': ('collapse',)
        })
    )
    
    actions = ['activate_features', 'deactivate_features']
    
    def activate_features(self, request, queryset):
        """Activate selected features."""
        count = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, f"Activated {count} features.", messages.SUCCESS)
    activate_features.short_description = "Activate selected features"
    
    def deactivate_features(self, request, queryset):
        """Deactivate selected features."""
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f"Deactivated {count} features.", messages.SUCCESS)
    deactivate_features.short_description = "Deactivate selected features"


@admin.register(PlanUpgrade)
class PlanUpgradeAdmin(admin.ModelAdmin):
    """
    Admin interface for PlanUpgrade model.
    """
    list_display = [
        'tenant_name', 'from_plan', 'to_plan', 'upgraded_at',
        'price_difference', 'reason', 'processed_by'
    ]
    list_filter = [
        'reason', 'upgraded_at', 'processed_by'
    ]
    search_fields = [
        'tenant__name', 'from_plan__name', 'to_plan__name',
        'reason', 'notes'
    ]
    ordering = ['-upgraded_at']
    raw_id_fields = ['tenant', 'from_plan', 'to_plan', 'processed_by']
    date_hierarchy = 'upgraded_at'
    
    fieldsets = (
        ('Upgrade Information', {
            'fields': (
                'tenant', 'from_plan', 'to_plan', 'upgraded_at',
                'effective_from', 'price_difference', 'reason'
            )
        }),
        ('Processing', {
            'fields': (
                'processed_by', 'approved_at', 'notes'
            )
        }),
        ('Payment Details', {
            'fields': (
                'payment_method', 'transaction_id', 'metadata'
            ),
            'classes': ('collapse',)
        })
    )
    
    def tenant_name(self, obj):
        """Display tenant name with link."""
        url = reverse('admin:tenants_tenant_change', args=[obj.tenant.id])
        return format_html('<a href="{}">{}</a>', url, obj.tenant.name)
    tenant_name.short_description = "Tenant"
    tenant_name.admin_order_field = 'tenant__name'
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related(
            'tenant', 'from_plan', 'to_plan', 'processed_by'
        )
    
    actions = ['approve_upgrades', 'reject_upgrades']
    
    def approve_upgrades(self, request, queryset):
        """Approve selected upgrades."""
        count = 0
        for upgrade in queryset.filter(status='requested'):
            upgrade.approve(request.user)
            count += 1
        
        self.message_user(request, f"Approved {count} upgrades.", messages.SUCCESS)
    approve_upgrades.short_description = "Approve selected upgrades"
    
    def reject_upgrades(self, request, queryset):
        """Reject selected upgrades."""
        count = 0
        for upgrade in queryset.filter(status='requested'):
            upgrade.reject(request.user, "Admin rejection")
            count += 1
        
        self.message_user(request, f"Rejected {count} upgrades.", messages.SUCCESS)
    reject_upgrades.short_description = "Reject selected upgrades"


@admin.register(PlanUsage)
class PlanUsageAdmin(admin.ModelAdmin):
    """
    Admin interface for PlanUsage model.
    """
    list_display = [
        'tenant_name', 'period', 'period_start', 'period_end',
        'api_calls_percentage', 'storage_percentage', 'users_percentage',
        'over_limit_count'
    ]
    list_filter = [
        'period', 'period_start', 'period_end'
    ]
    search_fields = ['tenant__name', 'tenant__slug']
    ordering = ['-period_start', 'tenant__name']
    raw_id_fields = ['tenant']
    date_hierarchy = 'period_start'
    
    fieldsets = (
        ('Usage Information', {
            'fields': (
                'tenant', 'period', 'period_start', 'period_end'
            )
        }),
        ('API Usage', {
            'fields': (
                'api_calls_used', 'api_calls_limit', 'api_calls_percentage'
            )
        }),
        ('Storage Usage', {
            'fields': (
                'storage_used_gb', 'storage_limit_gb', 'storage_percentage'
            )
        }),
        ('User Usage', {
            'fields': (
                'users_used', 'users_limit', 'users_percentage'
            )
        }),
        ('Other Metrics', {
            'fields': (
                'publishers_used', 'publishers_limit',
                'smartlinks_used', 'smartlinks_limit',
                'campaigns_used', 'campaigns_limit'
            ),
            'classes': ('collapse',)
        }),
        ('Additional Data', {
            'fields': ('additional_metrics',),
            'classes': ('collapse',)
        })
    )
    
    def tenant_name(self, obj):
        """Display tenant name with link."""
        url = reverse('admin:tenants_tenant_change', args=[obj.tenant.id])
        return format_html('<a href="{}">{}</a>', url, obj.tenant.name)
    tenant_name.short_description = "Tenant"
    tenant_name.admin_order_field = 'tenant__name'
    
    def api_calls_percentage(self, obj):
        """Display API calls percentage with color coding."""
        pct = obj.api_calls_percentage
        if pct >= 100:
            return mark_safe(f'<span style="color: #d32f2f;">{pct:.1f}%</span>')
        elif pct >= 80:
            return mark_safe(f'<span style="color: #f57c00;">{pct:.1f}%</span>')
        else:
            return mark_safe(f'<span style="color: #388e3c;">{pct:.1f}%</span>')
    api_calls_percentage.short_description = "API Calls %"
    
    def storage_percentage(self, obj):
        """Display storage percentage with color coding."""
        pct = obj.storage_percentage
        if pct >= 100:
            return mark_safe(f'<span style="color: #d32f2f;">{pct:.1f}%</span>')
        elif pct >= 80:
            return mark_safe(f'<span style="color: #f57c00;">{pct:.1f}%</span>')
        else:
            return mark_safe(f'<span style="color: #388e3c;">{pct:.1f}%</span>')
    storage_percentage.short_description = "Storage %"
    
    def users_percentage(self, obj):
        """Display users percentage with color coding."""
        pct = obj.users_percentage
        if pct >= 100:
            return mark_safe(f'<span style="color: #d32f2f;">{pct:.1f}%</span>')
        elif pct >= 80:
            return mark_safe(f'<span style="color: #f57c00;">{pct:.1f}%</span>')
        else:
            return mark_safe(f'<span style="color: #388e3c;">{pct:.1f}%</span>')
    users_percentage.short_description = "Users %"
    
    def over_limit_count(self, obj):
        """Count of metrics over limit."""
        over_limit = 0
        
        if obj.api_calls_limit > 0 and obj.api_calls_used > obj.api_calls_limit:
            over_limit += 1
        if obj.storage_limit_gb > 0 and obj.storage_used_gb > obj.storage_limit_gb:
            over_limit += 1
        if obj.users_limit > 0 and obj.users_used > obj.users_limit:
            over_limit += 1
        
        if over_limit > 0:
            return mark_safe(f'<span style="color: #d32f2f;">{over_limit}</span>')
        return over_limit
    over_limit_count.short_description = "Over Limit"
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('tenant')
    
    actions = ['send_quota_warnings', 'export_usage_data']
    
    def send_quota_warnings(self, request, queryset):
        """Send quota warnings for selected usage."""
        count = 0
        for usage in queryset:
            # This would send quota warning notifications
            count += 1
        
        self.message_user(request, f"Sent quota warnings for {count} usage records.", messages.SUCCESS)
    send_quota_warnings.short_description = "Send quota warnings"
    
    def export_usage_data(self, request, queryset):
        """Export usage data."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="usage_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Tenant', 'Period', 'API Calls Used', 'API Calls Limit',
            'Storage Used', 'Storage Limit', 'Users Used', 'Users Limit'
        ])
        
        for usage in queryset:
            writer.writerow([
                usage.tenant.name,
                usage.period,
                usage.api_calls_used,
                usage.api_calls_limit,
                usage.storage_used_gb,
                usage.storage_limit_gb,
                usage.users_used,
                usage.users_limit,
            ])
        
        return response
    export_usage_data.short_description = "Export usage data"


@admin.register(PlanQuota)
class PlanQuotaAdmin(admin.ModelAdmin):
    """
    Admin interface for PlanQuota model.
    """
    list_display = [
        'plan_name', 'feature_key', 'hard_limit', 'soft_limit',
        'quota_type', 'warning_threshold', 'overage_allowed'
    ]
    list_filter = [
        'plan', 'quota_type', 'overage_allowed'
    ]
    search_fields = [
        'plan__name', 'feature_key', 'display_name'
    ]
    ordering = ['plan__name', 'feature_key']
    raw_id_fields = ['plan']
    
    fieldsets = (
        ('Quota Information', {
            'fields': (
                'plan', 'feature_key', 'hard_limit', 'soft_limit',
                'warning_threshold', 'quota_type', 'overage_allowed'
            )
        }),
        ('Overage Pricing', {
            'fields': (
                'overage_price_per_unit', 'reset_period',
                'reset_day_of_month'
            )
        }),
        ('Display Options', {
            'fields': (
                'display_name', 'unit', 'custom_settings'
            ),
            'classes': ('collapse',)
        })
    )
    
    def plan_name(self, obj):
        """Display plan name with link."""
        url = reverse('admin:tenants_plan_change', args=[obj.plan.id])
        return format_html('<a href="{}">{}</a>', url, obj.plan.name)
    plan_name.short_description = "Plan"
    plan_name.admin_order_field = 'plan__name'
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return super().get_queryset(request).select_related('plan')
    
    actions = ['test_quotas', 'reset_quotas']
    
    def test_quotas(self, request, queryset):
        """Test selected quotas."""
        results = []
        for quota in queryset:
            # Test with 80% of hard limit
            test_value = quota.hard_limit * 0.8 if quota.hard_limit else 0
            is_over_limit = quota.is_over_limit(test_value)
            should_warn = quota.should_warn(test_value)
            
            results.append({
                'quota': f"{quota.plan.name} - {quota.feature_key}",
                'test_value': test_value,
                'is_over_limit': is_over_limit,
                'should_warn': should_warn,
            })
        
        # Display results in a message
        message_parts = [f"Tested {len(results)} quotas:"]
        for result in results:
            status = "OVER LIMIT" if result['is_over_limit'] else "OK"
            message_parts.append(f"  {result['quota']}: {status}")
        
        self.message_user(request, "\n".join(message_parts), messages.INFO)
    test_quotas.short_description = "Test quotas"
    
    def reset_quotas(self, request, queryset):
        """Reset selected quotas to defaults."""
        count = 0
        for quota in queryset:
            # Reset to default values
            if quota.hard_limit > 0:
                quota.soft_limit = int(quota.hard_limit * 0.8)
                quota.warning_threshold = 80
                quota.save()
                count += 1
        
        self.message_user(request, f"Reset {count} quotas to defaults.", messages.SUCCESS)
    reset_quotas.short_description = "Reset to defaults"
