# api/djoyalty/admin/customer_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from django.utils import timezone
from ..models.core import Customer

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['code_badge', 'full_name_display', 'email_display', 'phone_display', 'city_display', 'newsletter_badge', 'txn_count', 'total_spent', 'points_balance_display', 'tier_display', 'created_at_display']
    list_filter = ['newsletter', 'city', 'created_at', 'is_active']
    search_fields = ['code', 'firstname', 'lastname', 'email', 'phone', 'city']
    readonly_fields = ['created_at']
    list_per_page = 25
    ordering = ['-created_at']

    fieldsets = (
        ('🆔 Identity', {'fields': ('code', 'is_active')}),
        ('👤 Personal Info', {'fields': (('firstname', 'lastname'), 'email', 'phone', 'birth_date')}),
        ('📍 Address', {'fields': ('street', 'city', 'zip'), 'classes': ('collapse',)}),
        ('📝 Notes & Settings', {'fields': ('note', 'newsletter')}),
        ('📅 Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )

    def code_badge(self, obj):
        return format_html('<span style="background:#6366f1;color:white;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600;">{}</span>', obj.code or '???')
    code_badge.short_description = 'Code'

    def full_name_display(self, obj):
        return format_html('<span style="font-weight:500;">{}</span>', obj.full_name)
    full_name_display.short_description = 'Name'

    def email_display(self, obj):
        if obj.email:
            return format_html('<a href="mailto:{}" style="color:#6366f1;">{}</a>', obj.email, obj.email)
        return format_html('<span style="color:#aaa;">—</span>')
    email_display.short_description = 'Email'

    def phone_display(self, obj):
        return format_html('<span style="font-family:monospace;">{}</span>', obj.phone or '—')
    phone_display.short_description = 'Phone'

    def city_display(self, obj):
        if obj.city:
            return format_html('<span style="background:#f0fdf4;color:#166534;padding:2px 8px;border-radius:8px;font-size:11px;">📍 {}</span>', obj.city)
        return '—'
    city_display.short_description = 'City'

    def newsletter_badge(self, obj):
        if obj.newsletter:
            return format_html('<span style="background:#dcfce7;color:#166534;padding:2px 8px;border-radius:8px;font-size:11px;">✅ Yes</span>')
        return format_html('<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:8px;font-size:11px;">❌ No</span>')
    newsletter_badge.short_description = 'Newsletter'

    def txn_count(self, obj):
        count = obj.transactions.count()
        return format_html('<span style="background:#ede9fe;color:#5b21b6;padding:2px 8px;border-radius:8px;font-size:11px;">💳 {}</span>', count)
    txn_count.short_description = 'Txns'

    def total_spent(self, obj):
        total = obj.transactions.aggregate(s=Sum('value'))['s'] or 0
        color = '#166534' if total >= 0 else '#991b1b'
        return format_html('<span style="color:{};font-weight:600;">{:.2f}</span>', color, total)
    total_spent.short_description = 'Spent'

    def points_balance_display(self, obj):
        lp = obj.loyalty_points.first()
        bal = lp.balance if lp else 0
        return format_html('<span style="color:#7c3aed;font-weight:600;">⭐ {}</span>', bal)
    points_balance_display.short_description = 'Points'

    def tier_display(self, obj):
        ut = obj.current_tier
        tier_name = ut.tier.name if ut and ut.tier else 'bronze'
        colors = {'bronze': '#92400e', 'silver': '#374151', 'gold': '#92400e', 'platinum': '#1e40af', 'diamond': '#6b21a8'}
        icons = {'bronze': '🥉', 'silver': '🥈', 'gold': '🥇', 'platinum': '💎', 'diamond': '💠'}
        color = colors.get(tier_name, '#374151')
        icon = icons.get(tier_name, '⭐')
        return format_html('<span style="color:{};font-weight:600;">{} {}</span>', color, icon, tier_name.title())
    tier_display.short_description = 'Tier'

    def created_at_display(self, obj):
        if obj.created_at:
            return format_html('<span style="color:#666;font-size:12px;">{}</span>', timezone.localtime(obj.created_at).strftime('%Y-%m-%d'))
        return '—'
    created_at_display.short_description = 'Joined'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('transactions', 'loyalty_points', 'user_tiers__tier')

    actions = ['export_newsletter_subscribers', 'mark_newsletter_on', 'mark_newsletter_off']

    def export_newsletter_subscribers(self, request, queryset):
        count = queryset.filter(newsletter=True).count()
        self.message_user(request, f'📧 {count} newsletter subscribers selected.')
    export_newsletter_subscribers.short_description = 'Export newsletter subscribers'

    def mark_newsletter_on(self, request, queryset):
        updated = queryset.update(newsletter=True)
        self.message_user(request, f'✅ {updated} customers subscribed.')
    mark_newsletter_on.short_description = 'Subscribe to newsletter'

    def mark_newsletter_off(self, request, queryset):
        updated = queryset.update(newsletter=False)
        self.message_user(request, f'❌ {updated} customers unsubscribed.')
    mark_newsletter_off.short_description = 'Unsubscribe from newsletter'
