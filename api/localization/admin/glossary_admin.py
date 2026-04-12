# admin/glossary_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.translation import TranslationGlossary, TranslationGlossaryEntry

class GlossaryEntryInline(admin.TabularInline):
    model = TranslationGlossaryEntry
    extra = 1
    fields = ['language', 'translated_term', 'alternative_terms', 'is_approved']

@admin.register(TranslationGlossary)
class TranslationGlossaryAdmin(admin.ModelAdmin):
    list_display = ['source_term', 'source_language', 'domain', 'dnt_badge', 'brand_badge', 'usage_count']
    list_filter = ['source_language', 'domain', 'is_do_not_translate', 'is_brand_term', 'is_forbidden']
    search_fields = ['source_term', 'definition', 'domain']
    inlines = [GlossaryEntryInline]

    def dnt_badge(self, obj):
        if obj.is_do_not_translate:
            return format_html('<span style="background:#dc3545;color:white;padding:2px 6px;border-radius:8px;font-size:11px;">DNT</span>')
        return ''
    dnt_badge.short_description = 'Do Not Translate'

    def brand_badge(self, obj):
        if obj.is_brand_term:
            return format_html('<span style="background:#6f42c1;color:white;padding:2px 6px;border-radius:8px;font-size:11px;">Brand</span>')
        return ''
    brand_badge.short_description = 'Brand'
