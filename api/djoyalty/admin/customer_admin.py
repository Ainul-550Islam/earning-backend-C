# api/djoyalty/admin/customer_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.core import Customer, Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'plan', 'is_active', 'created_at']
    list_filter = ['is_active', 'plan']
    search_fields = ['name', 'slug']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'full_name_display', 'email', 'phone', 'city',
        'is_active', 'is_verified', 'newsletter',
        'points_balance_display', 'current_tier_display',
        'created_at',
    ]
    list_filter = ['is_active', 'is_verified', 'newsletter', 'gender', 'tenant']
    search_fields = ['code', 'firstname', 'lastname', 'email', 'phone', 'loyalty_number']
    readonly_fields = [
        'loyalty_number', 'full_name_display', 'points_balance_display',
        'current_tier_display', 'created_at', 'updated_at',
    ]
    ordering = ['-created_at']
    list_per_page = 50
    date_hierarchy = 'created_at'
    fieldsets = (
        ('Identity', {
            'fields': (
                'code', 'loyalty_number', 'user', 'tenant',
                'firstname', 'lastname', 'email', 'phone',
                'date_of_birth', 'gender',
            ),
        }),
        ('Location', {
            'fields': ('city', 'country', 'address'),
            'classes': ('collapse',),
        }),
        ('Preferences', {
            'fields': ('newsletter', 'sms_opt_in', 'push_opt_in'),
        }),
        ('Status', {
            'fields': ('is_active', 'is_verified', 'referral_code', 'referred_by'),
        }),
        ('Metadata', {
            'fields': ('metadata', 'notes'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_activity_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Full Name')
    def full_name_display(self, obj):
        return obj.full_name

    @admin.display(description='Points Balance')
    def points_balance_display(self, obj):
        bal = obj.points_balance
        color = 'green' if bal > 0 else 'gray'
        return format_html('<b style="color:{}">{}</b>', color, bal)

    @admin.display(description='Tier')
    def current_tier_display(self, obj):
        ut = obj.current_tier
        if ut and ut.tier:
            colors = {
                'bronze': '#cd7f32', 'silver': '#c0c0c0',
                'gold': '#ffd700', 'platinum': '#e5e4e2', 'diamond': '#b9f2ff',
            }
            color = colors.get(ut.tier.name, '#888')
            return format_html('<span style="color:{};font-weight:bold">{}</span>', color, ut.tier.name.title())
        return '--'

    actions = ['deactivate_customers', 'activate_customers']

    @admin.action(description='Deactivate selected customers')
    def deactivate_customers(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} customer(s) deactivated.')

    @admin.action(description='Activate selected customers')
    def activate_customers(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} customer(s) activated.')
