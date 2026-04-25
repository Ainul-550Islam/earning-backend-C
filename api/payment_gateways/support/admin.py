# api/payment_gateways/support/admin.py
from django.contrib import admin
from .models import SupportTicket, TicketMessage

class TicketMessageInline(admin.TabularInline):
    model          = TicketMessage
    extra          = 1
    readonly_fields= ('created_at',)

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display   = ('ticket_number','subject','user','category','priority','status','assigned_to','created_at')
    list_filter    = ('status','priority','category')
    search_fields  = ('ticket_number','subject','user__email')
    readonly_fields= ('ticket_number','created_at','resolved_at')
    inlines        = [TicketMessageInline]
    actions        = ['mark_resolved','mark_in_progress']

    @admin.action(description='Mark as resolved')
    def mark_resolved(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='resolved', resolved_at=timezone.now())

    @admin.action(description='Mark as in progress')
    def mark_in_progress(self, request, queryset):
        queryset.update(status='in_progress')
