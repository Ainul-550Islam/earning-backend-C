# admin/user_preference_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from ..models.core import UserLanguagePreference


@admin.register(UserLanguagePreference)
class UserLanguagePreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'user_display', 'ui_language_badge', 'primary_language_badge',
        'currency_badge', 'timezone_display', 'auto_translate',
        'last_used_display', 'created_at',
    ]
    list_filter = ['ui_language', 'auto_translate', 'primary_language']
    search_fields = ['user__email', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'last_used_languages']
    raw_id_fields = ['user', 'ui_language', 'primary_language', 'content_language']
    list_per_page = 50
    ordering = ['-created_at']

    fieldsets = (
        (_('User'), {'fields': ('user',)}),
        (_('Language'), {'fields': (
            'ui_language', 'primary_language', 'content_language',
            'auto_translate', 'detect_language_from_browser', 'detect_language_from_ip',
        )}),
        (_('Currency & Timezone'), {'fields': (
            'preferred_date_format', 'preferred_time_format', 'preferred_number_format',
        )}),
        (_('UI Preferences'), {'fields': (
            'show_translation_hints', 'enable_rtl_support', 'translation_feedback_enabled',
        )}),
        (_('History'), {'fields': ('last_used_languages',), 'classes': ('collapse',)}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def user_display(self, obj):
        email = getattr(obj.user, 'email', '?') if obj.user else '?'
        return format_html('<span style="font-size:12px;">{}</span>', email)
    user_display.short_description = _('User')
    user_display.admin_order_field = 'user__email'

    def ui_language_badge(self, obj):
        if not obj.ui_language:
            return format_html('<span style="color:var(--body-quiet-color);">—</span>')
        flag = obj.ui_language.flag_emoji or ''
        code = obj.ui_language.code
        return format_html(
            '<span style="background:#E6F1FB;color:#185FA5;padding:2px 8px;border-radius:10px;font-size:11px;">'
            '{} {}</span>', flag, code
        )
    ui_language_badge.short_description = _('UI Lang')

    def primary_language_badge(self, obj):
        if not obj.primary_language:
            return '—'
        return format_html(
            '<span style="font-size:11px;">{}</span>',
            obj.primary_language.code
        )
    primary_language_badge.short_description = _('Primary')

    def currency_badge(self, obj):
        if not obj.preferred_currency:
            return '—'
        sym = obj.preferred_currency.symbol or ''
        code = obj.preferred_currency.code
        return format_html(
            '<span style="background:#EAF3DE;color:#3B6D11;padding:2px 6px;border-radius:8px;font-size:11px;">'
            '{} {}</span>', sym, code
        )
    currency_badge.short_description = _('Currency')

    def timezone_display(self, obj):
        if not obj.preferred_timezone:
            return '—'
        return format_html('<span style="font-size:11px;">{}</span>', obj.preferred_timezone.name)
    timezone_display.short_description = _('Timezone')

    def last_used_display(self, obj):
        langs = obj.last_used_languages or []
        if not langs:
            return '—'
        return format_html(
            '<span style="font-size:11px;color:var(--body-quiet-color);">{}</span>',
            ', '.join(str(l) for l in langs[:5])
        )
    last_used_display.short_description = _('Last Used')

    actions = ['reset_to_defaults', 'clear_last_used']

    def reset_to_defaults(self, request, queryset):
        from ..services.services_loca.UserPreferenceService import UserPreferenceService
        service = UserPreferenceService()
        count = 0
        for pref in queryset:
            if pref.user:
                service.reset_to_defaults(pref.user)
                count += 1
        self.message_user(request, f'Reset {count} user preferences to defaults')
    reset_to_defaults.short_description = _('↺ Reset to defaults')

    def clear_last_used(self, request, queryset):
        queryset.update(last_used_languages=[])
        self.message_user(request, f'Cleared last used languages for {queryset.count()} users')
    clear_last_used.short_description = _('✕ Clear last used languages')
