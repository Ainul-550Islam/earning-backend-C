# api/support/admin/chat_admin.py  — WORLD #1
from django.contrib import admin
from api.support.models import ChatSession, ChatMessage

class ChatMessageInline(admin.TabularInline):
    model   = ChatMessage
    extra   = 0
    fields  = ['sender','content','message_type','is_agent','is_read','created_at']
    readonly_fields = ['created_at']

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display  = ['session_id_short','user','agent','status','queue_position','started_at','ended_at']
    list_filter   = ['status']
    search_fields = ['user__username','agent__username']
    readonly_fields = ['session_id','started_at']
    inlines       = [ChatMessageInline]

    def session_id_short(self, obj):
        return str(obj.session_id)[:8]
    session_id_short.short_description = 'Session'