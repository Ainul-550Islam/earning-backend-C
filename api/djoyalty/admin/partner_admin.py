# api/djoyalty/admin/partner_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.advanced import CoalitionEarn


@admin.register(CoalitionEarn)
class CoalitionEarnAdmin(admin.ModelAdmin):
    list_display = ['customer', 'partner', 'spend_amount', 'points_earned', 'earn_rate_applied',
                    'status_badge', 'reference', 'created_at']
    list_filter = ['status', 'partner', 'created_at']
    search_fields = ['customer__code', 'partner__name', 'reference']
    readonly_fields = ['created_at', 'processed_at']
    fieldsets = [
        ('Earn Info', {'fields': ['customer', 'partner', 'tenant']}),
        ('Amount', {'fields': ['spend_amount', 'points_earned', 'earn_rate_applied', 'currency']}),
        ('Status', {'fields': ['status', 'reference', 'description']}),
        ('Metadata', {'fields': ['metadata', 'created_at', 'processed_at']}),
    ]

    def status_badge(self, obj):
        colors = {'pending': '#f59e0b', 'processed': '#10b981', 'reversed': '#ef4444'}
        color = colors.get(obj.status, '#6b7280')
        return format_html('<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;">{}</span>', color, obj.status)
    status_badge.short_description = 'Status'

    actions = ['mark_processed']

    def mark_processed(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(status='pending').update(status='processed', processed_at=timezone.now())
        self.message_user(request, f'{count} coalition earns marked as processed.')
    mark_processed.short_description = 'Mark selected as processed'
