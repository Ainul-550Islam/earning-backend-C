"""
api/offerwall/b2b/admin.py
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import B2BPlan, B2BClient, B2BUsageRecord, B2BInvoice, B2BOnboarding


@admin.register(B2BPlan)
class B2BPlanAdmin(admin.ModelAdmin):
    list_display  = ['name', 'plan_type', 'monthly_price_bdt', 'monthly_price_usd',
                     'monthly_api_calls', 'revenue_share_pct', 'is_active', 'is_public']
    list_filter   = ['plan_type', 'is_active', 'is_public']
    list_editable = ['monthly_price_bdt', 'revenue_share_pct', 'is_active', 'is_public']
    fieldsets = [
        ('Basic',    {'fields': ['name', 'plan_type', 'monthly_price_bdt',
                                  'monthly_price_usd', 'is_active', 'is_public']}),
        ('Limits',   {'fields': ['monthly_api_calls', 'monthly_conversions',
                                  'max_active_walls', 'max_api_keys']}),
        ('Revenue',  {'fields': ['revenue_share_pct']}),
        ('Features', {'fields': ['allow_content_lock', 'allow_bulk_webhook',
                                  'allow_custom_domain', 'allow_white_label',
                                  'allow_survey_offers', 'allow_analytics_api',
                                  'support_level']}),
    ]


class B2BOnboardingInline(admin.StackedInline):
    model        = B2BOnboarding
    can_delete   = False
    readonly_fields = ['completed_steps', 'current_step', 'is_complete',
                       'completed_at', 'signup_at', 'profile_at', 'plan_at',
                       'api_key_at', 'integration_at', 'test_conv_at', 'live_at']
    extra = 0


class B2BUsageInline(admin.TabularInline):
    model          = B2BUsageRecord
    extra          = 0
    max_num        = 6
    readonly_fields = ['period_year', 'period_month', 'api_calls', 'conversions',
                       'offer_views', 'offer_clicks', 'gross_revenue_usd',
                       'publisher_share_usd']
    can_delete     = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(B2BClient)
class B2BClientAdmin(admin.ModelAdmin):
    list_display  = ['company_name', 'owner_link', 'plan_badge', 'status_badge',
                     'effective_rev_share', 'created_at']
    list_filter   = ['status', 'plan__plan_type', 'business_type', 'country']
    search_fields = ['company_name', 'owner__username', 'owner__email', 'contact_email']
    readonly_fields = ['id', 'effective_rev_share', 'verified_at', 'suspended_at',
                       'created_at', 'updated_at']
    raw_id_fields   = ['owner', 'plan']
    inlines         = [B2BOnboardingInline, B2BUsageInline]
    actions         = ['action_verify', 'action_activate', 'action_suspend']

    fieldsets = [
        ('Company',   {'fields': ['id', 'owner', 'company_name', 'company_website',
                                   'business_type', 'country', 'vat_number', 'description']}),
        ('Plan',      {'fields': ['plan', 'plan_started_at', 'plan_expires_at', 'billing_cycle']}),
        ('Revenue',   {'fields': ['custom_revenue_share_pct', 'effective_rev_share']}),
        ('Status',    {'fields': ['status', 'verified_at', 'suspended_at', 'suspension_reason']}),
        ('Contact',   {'fields': ['contact_email', 'contact_phone']}),
        ('Internal',  {'fields': ['notes', 'internal_tags', 'created_at', 'updated_at']}),
    ]

    def owner_link(self, obj):
        return format_html('<a href="/admin/auth/user/{}/change/">{}</a>',
                           obj.owner_id, obj.owner.username)
    owner_link.short_description = 'Owner'

    def plan_badge(self, obj):
        if not obj.plan:
            return '—'
        colors = {'free': '#888', 'starter': '#185FA5',
                  'pro': '#639922', 'enterprise': '#7F77DD'}
        color = colors.get(obj.plan.plan_type, '#888')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px">{}</span>',
            color, obj.plan.name)
    plan_badge.short_description = 'Plan'

    def status_badge(self, obj):
        colors = {'pending': '#BA7517', 'verified': '#185FA5',
                  'active': '#3B6D11', 'suspended': '#A32D2D', 'churned': '#888'}
        color = colors.get(obj.status, '#888')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px">{}</span>',
            color, obj.status.title())
    status_badge.short_description = 'Status'

    def effective_rev_share(self, obj):
        return f'{obj.effective_revenue_share}%'
    effective_rev_share.short_description = 'Rev share'

    @admin.action(description='✓ Verify selected clients')
    def action_verify(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='verified', verified_at=timezone.now())
        self.message_user(request, f'{updated} client(s) verified.')

    @admin.action(description='▶ Activate selected clients')
    def action_activate(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} client(s) activated.')

    @admin.action(description='⏸ Suspend selected clients')
    def action_suspend(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='suspended', suspended_at=timezone.now())
        self.message_user(request, f'{updated} client(s) suspended.')


@admin.register(B2BUsageRecord)
class B2BUsageRecordAdmin(admin.ModelAdmin):
    list_display  = ['client', 'period_year', 'period_month',
                     'api_calls', 'conversions', 'gross_revenue_usd',
                     'publisher_share_usd', 'updated_at']
    list_filter   = ['period_year', 'period_month']
    search_fields = ['client__company_name']
    readonly_fields = ['id', 'updated_at']

    def has_add_permission(self, request):
        return False


@admin.register(B2BInvoice)
class B2BInvoiceAdmin(admin.ModelAdmin):
    list_display  = ['invoice_number', 'client', 'period_year', 'period_month',
                     'plan_fee_bdt', 'total_payable_bdt', 'status_badge', 'issued_at']
    list_filter   = ['status', 'period_year', 'period_month']
    search_fields = ['invoice_number', 'client__company_name']
    readonly_fields = ['id', 'invoice_number', 'created_at']
    actions       = ['action_mark_paid']

    def status_badge(self, obj):
        colors = {'draft': '#888', 'issued': '#185FA5', 'paid': '#3B6D11',
                  'overdue': '#A32D2D', 'cancelled': '#888'}
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px">{}</span>',
            colors.get(obj.status, '#888'), obj.status.title())
    status_badge.short_description = 'Status'

    @admin.action(description='✓ Mark selected invoices as paid')
    def action_mark_paid(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='paid', paid_at=timezone.now())
        self.message_user(request, f'{updated} invoice(s) marked as paid.')


@admin.register(B2BOnboarding)
class B2BOnboardingAdmin(admin.ModelAdmin):
    list_display  = ['client', 'current_step', 'completion_pct_display',
                     'is_complete', 'completed_at']
    list_filter   = ['is_complete', 'current_step']
    search_fields = ['client__company_name']
    readonly_fields = ['id', 'completed_at', 'signup_at', 'profile_at',
                       'plan_at', 'api_key_at', 'integration_at',
                       'test_conv_at', 'live_at']

    def completion_pct_display(self, obj):
        pct = obj.completion_pct()
        color = '#3B6D11' if pct == 100 else '#185FA5' if pct >= 50 else '#BA7517'
        return format_html(
            '<span style="color:{};font-weight:500">{}%</span>', color, pct)
    completion_pct_display.short_description = 'Progress'
