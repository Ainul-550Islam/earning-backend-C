# admin.py - Customer, Txn, Event - Beautiful & Bulletproof

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from .models import Customer, Txn, Event


# ==================== CUSTOMER ADMIN ====================

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = [
        'code_badge', 'full_name_display', 'email_display',
        'phone_display', 'city_display', 'newsletter_badge',
        'txn_count', 'total_spent', 'created_at_display'
    ]
    list_filter = ['newsletter', 'city', 'created_at']
    search_fields = ['code', 'firstname', 'lastname', 'email', 'phone', 'city']
    readonly_fields = ['created_at']
    list_per_page = 25
    ordering = ['-created_at']

    fieldsets = (
        ('🆔 Identity', {
            'fields': ('code',),
        }),
        ('👤 Personal Info', {
            'fields': (('firstname', 'lastname'), 'email', 'phone'),
        }),
        ('📍 Address', {
            'fields': ('street', 'city', 'zip'),
            'classes': ('collapse',),
        }),
        ('[NOTE] Notes & Settings', {
            'fields': ('note', 'newsletter'),
        }),
        ('📅 Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def code_badge(self, obj):
        code = obj.code or '???'
        return format_html(
            '<span style="background:#6366f1;color:white;padding:3px 10px;'
            'border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            code
        )
    code_badge.short_description = 'Code'

    def full_name_display(self, obj):
        name = ' '.join(filter(None, [obj.firstname, obj.lastname])) or '—'
        return format_html('<span style="font-weight:500;">{}</span>', name)
    full_name_display.short_description = 'Name'

    def email_display(self, obj):
        if obj.email:
            return format_html(
                '<a href="mailto:{}" style="color:#6366f1;">{}</a>', obj.email, obj.email
            )
        return format_html('<span style="color:#aaa;">—</span>')
    email_display.short_description = 'Email'

    def phone_display(self, obj):
        return format_html(
            '<span style="font-family:monospace;">{}</span>', obj.phone or '—'
        )
    phone_display.short_description = 'Phone'

    def city_display(self, obj):
        if obj.city:
            return format_html(
                '<span style="background:#f0fdf4;color:#166534;padding:2px 8px;'
                'border-radius:8px;font-size:11px;">📍 {}</span>', obj.city
            )
        return '—'
    city_display.short_description = 'City'

    def newsletter_badge(self, obj):
        if obj.newsletter:
            return format_html(
                '<span style="background:#dcfce7;color:#166534;padding:2px 8px;'
                'border-radius:8px;font-size:11px;">[OK] Yes</span>'
            )
        return format_html(
            '<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;'
            'border-radius:8px;font-size:11px;">[ERROR] No</span>'
        )
    newsletter_badge.short_description = 'Newsletter'
    newsletter_badge.boolean = False

    def txn_count(self, obj):
        count = getattr(obj, '_txn_count', None)
        if count is None:
            count = obj.transactions.count()
        return format_html(
            '<span style="background:#ede9fe;color:#5b21b6;padding:2px 8px;'
            'border-radius:8px;font-size:11px;">💳 {}</span>', count
        )
    txn_count.short_description = 'Transactions'

    def total_spent(self, obj):
        total = obj.transactions.aggregate(s=Sum('value'))['s'] or 0
        color = '#166534' if total >= 0 else '#991b1b'
        return format_html(
            '<span style="color:{};font-weight:600;">{:.2f}</span>', color, total
        )
    total_spent.short_description = 'Total Spent'

    def created_at_display(self, obj):
        if obj.created_at:
            return format_html(
                '<span style="color:#666;font-size:12px;">{}</span>',
                timezone.localtime(obj.created_at).strftime('%Y-%m-%d')
            )
        return '—'
    created_at_display.short_description = 'Joined'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('transactions')

    actions = ['export_newsletter_subscribers', 'mark_newsletter_on', 'mark_newsletter_off']

    def export_newsletter_subscribers(self, request, queryset):
        count = queryset.filter(newsletter=True).count()
        self.message_user(request, f'📧 {count} newsletter subscribers selected.')
    export_newsletter_subscribers.short_description = "Export newsletter subscribers"

    def mark_newsletter_on(self, request, queryset):
        updated = queryset.update(newsletter=True)
        self.message_user(request, f'[OK] {updated} customers subscribed to newsletter.')
    mark_newsletter_on.short_description = "Subscribe to newsletter"

    def mark_newsletter_off(self, request, queryset):
        updated = queryset.update(newsletter=False)
        self.message_user(request, f'[ERROR] {updated} customers unsubscribed from newsletter.')
    mark_newsletter_off.short_description = "Unsubscribe from newsletter"


# ==================== TXN ADMIN ====================

@admin.register(Txn)
class TxnAdmin(admin.ModelAdmin):
    list_display = [
        'id_badge', 'customer_link', 'value_display',
        'discount_badge', 'timestamp_display'
    ]
    list_filter = ['is_discount', 'timestamp']
    search_fields = ['customer__code', 'customer__firstname', 'customer__lastname', 'customer__email']
    readonly_fields = ['timestamp']
    raw_id_fields = ['customer']
    list_per_page = 30
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

    fieldsets = (
        ('💳 Transaction Info', {
            'fields': ('customer', 'value', 'is_discount'),
        }),
        ('📅 Timestamp', {
            'fields': ('timestamp',),
            'classes': ('collapse',),
        }),
    )

    def id_badge(self, obj):
        return format_html(
            '<span style="background:#f3f4f6;color:#374151;padding:3px 8px;'
            'border-radius:8px;font-size:11px;font-family:monospace;">#{}</span>',
            obj.id
        )
    id_badge.short_description = 'ID'

    def customer_link(self, obj):
        if obj.customer:
            return format_html(
                '<a href="/admin/yourapp/customer/{}/change/" style="color:#6366f1;font-weight:500;">'
                '👤 {}</a>',
                obj.customer.id, str(obj.customer)
            )
        return format_html('<span style="color:#aaa;">—</span>')
    customer_link.short_description = 'Customer'

    def value_display(self, obj):
        val = obj.value or 0
        if val >= 0:
            return format_html(
                '<span style="color:#166534;font-weight:600;font-size:14px;">+{:.2f}</span>', val
            )
        return format_html(
            '<span style="color:#991b1b;font-weight:600;font-size:14px;">{:.2f}</span>', val
        )
    value_display.short_description = 'Value'

    def discount_badge(self, obj):
        if obj.is_discount:
            return format_html(
                '<span style="background:#fef3c7;color:#92400e;padding:2px 8px;'
                'border-radius:8px;font-size:11px;">🏷️ Discount</span>'
            )
        return format_html(
            '<span style="background:#ede9fe;color:#5b21b6;padding:2px 8px;'
            'border-radius:8px;font-size:11px;">[MONEY] Full Price</span>'
        )
    discount_badge.short_description = 'Type'

    def timestamp_display(self, obj):
        if obj.timestamp:
            return format_html(
                '<span style="color:#666;font-size:12px;">{}</span>',
                timezone.localtime(obj.timestamp).strftime('%Y-%m-%d %H:%M')
            )
        return '—'
    timestamp_display.short_description = 'Time'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer')

    actions = ['mark_as_discount', 'mark_as_full_price']

    def mark_as_discount(self, request, queryset):
        updated = queryset.update(is_discount=True)
        self.message_user(request, f'🏷️ {updated} transactions marked as discounted.')
    mark_as_discount.short_description = "Mark as discount"

    def mark_as_full_price(self, request, queryset):
        updated = queryset.update(is_discount=False)
        self.message_user(request, f'[MONEY] {updated} transactions marked as full price.')
    mark_as_full_price.short_description = "Mark as full price"


# ==================== EVENT ADMIN ====================

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        'id_badge', 'customer_link', 'action_badge',
        'description_preview', 'timestamp_display'
    ]
    list_filter = ['action', 'timestamp']
    search_fields = ['action', 'description', 'customer__code', 'customer__email']
    readonly_fields = ['timestamp']
    raw_id_fields = ['customer']
    list_per_page = 30
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

    fieldsets = (
        ('📌 Event Info', {
            'fields': ('customer', 'action', 'description'),
        }),
        ('📅 Timestamp', {
            'fields': ('timestamp',),
            'classes': ('collapse',),
        }),
    )

    def id_badge(self, obj):
        return format_html(
            '<span style="background:#f3f4f6;color:#374151;padding:3px 8px;'
            'border-radius:8px;font-size:11px;font-family:monospace;">#{}</span>',
            obj.id
        )
    id_badge.short_description = 'ID'

    def customer_link(self, obj):
        if obj.customer:
            return format_html(
                '<a href="/admin/yourapp/customer/{}/change/" style="color:#6366f1;font-weight:500;">'
                '👤 {}</a>',
                obj.customer.id, str(obj.customer)
            )
        return format_html(
            '<span style="background:#fef3c7;color:#92400e;padding:2px 8px;'
            'border-radius:8px;font-size:11px;">🌐 Anonymous</span>'
        )
    customer_link.short_description = 'Customer'

    def action_badge(self, obj):
        action = obj.action or 'unknown'
        colors = {
            'login': ('#dbeafe', '#1e40af'),
            'logout': ('#f3f4f6', '#374151'),
            'purchase': ('#dcfce7', '#166534'),
            'register': ('#ede9fe', '#5b21b6'),
            'error': ('#fee2e2', '#991b1b'),
        }
        bg, fg = colors.get(action.lower(), ('#f3f4f6', '#374151'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:8px;font-size:11px;font-weight:500;">⚡ {}</span>',
            bg, fg, action
        )
    action_badge.short_description = 'Action'

    def description_preview(self, obj):
        desc = obj.description or ''
        preview = desc[:60] + '...' if len(desc) > 60 else desc or '—'
        return format_html('<span style="color:#555;font-size:12px;">{}</span>', preview)
    description_preview.short_description = 'Description'

    def timestamp_display(self, obj):
        if obj.timestamp:
            return format_html(
                '<span style="color:#666;font-size:12px;">{}</span>',
                timezone.localtime(obj.timestamp).strftime('%Y-%m-%d %H:%M')
            )
        return '—'
    timestamp_display.short_description = 'Time'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer')

    actions = ['delete_anonymous_events']

    def delete_anonymous_events(self, request, queryset):
        deleted_count, _ = queryset.filter(customer=None).delete()
        self.message_user(request, f'[DELETE] {deleted_count} anonymous events deleted.')
    delete_anonymous_events.short_description = "Delete anonymous events"

def _force_register_djoyalty():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(Customer, CustomerAdmin), (Txn, TxnAdmin), (Event, EventAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] djoyalty registered {registered} models")
    except Exception as e:
        print(f"[WARN] djoyalty: {e}")
