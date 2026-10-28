# api/support/admin/faq_admin.py  — WORLD #1
from django.contrib import admin
from api.support.models import FAQ

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display  = ['question_preview','category','is_active','order','view_count','helpful_yes','helpful_no','helpful_ratio','created_at']
    list_filter   = ['category','is_active']
    search_fields = ['question','answer']
    readonly_fields = ['helpful_yes','helpful_no','view_count','created_at']
    ordering      = ['order','-created_at']

    def question_preview(self, obj):
        q = obj.question or ''
        return q[:60] + '…' if len(q) > 60 else q
    question_preview.short_description = 'Question'