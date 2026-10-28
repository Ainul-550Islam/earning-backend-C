# api/support/admin/ticket_admin.py  — WORLD #1
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from api.support.models import SupportTicket, TicketMessage, TicketAttachment

class TicketMessageInline(admin.TabularInline):
    model   = TicketMessage
    extra   = 0
    fields  = ['sender','content','is_agent','is_internal','created_at']
    readonly_fields = ['created_at']
    ordering = ['created_at']

class TicketAttachmentInline(admin.TabularInline):
    model  = TicketAttachment
    extra  = 0
    fields = ['filename','mime_type','size_bytes','created_at']
    readonly_fields = ['created_at']

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display   = ['ticket_id','user_display','category','priority_badge','status_badge','assigned_display','message_count','escalated','created_at']
    list_filter    = ['status','priority','category','channel','escalated']
    search_fields  = ['ticket_id','user__username','user__email','subject']
    readonly_fields= ['ticket_id','created_at','updated_at','resolved_at','admin_responded_at','first_response_at']
    inlines        = [TicketMessageInline, TicketAttachmentInline]
    date_hierarchy = 'created_at'
    ordering       = ['-created_at']

    def user_display(self, obj):
        return format_html('<b>{}</b><br><small>{}</small>', obj.user.username, obj.user.email) if obj.user else '-'
    user_display.short_description = 'User'

    def priority_badge(self, obj):
        colors = {'urgent':'#dc2626','high':'#ea580c','medium':'#ca8a04','low':'#16a34a'}
        color = colors.get(obj.priority, '#6b7280')
        return format_html('<span style="background:{};color:white;padding:2px 8px;border-radius:12px;font-size:11px">{}</span>', color, obj.priority.upper())
    priority_badge.short_description = 'Priority'

    def status_badge(self, obj):
        colors = {'open':'#ca8a04','in_progress':'#2563eb','waiting_user':'#ea580c','resolved':'#16a34a','closed':'#6b7280','spam':'#dc2626'}
        emojis = {'open':'🟡','in_progress':'🔵','waiting_user':'🟠','resolved':'✅','closed':'⛔','spam':'🚫'}
        color = colors.get(obj.status,'#6b7280')
        emoji = emojis.get(obj.status,'')
        return format_html('<span style="color:{}">{} {}</span>', color, emoji, obj.get_status_display())
    status_badge.short_description = 'Status'

    def assigned_display(self, obj):
        return obj.assigned_to.username if obj.assigned_to else '—'
    assigned_display.short_description = 'Assigned To'

    def save_model(self, request, obj, form, change):
        if obj.admin_response and not obj.admin_responded_at:
            obj.admin_responded_at = timezone.now()
        if obj.status in ('resolved','closed') and not obj.resolved_at:
            obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)