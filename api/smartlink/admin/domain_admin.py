from django.contrib import admin
from django.utils.html import format_html
from ..models.publisher import PublisherDomain
from ..choices import DomainVerificationStatus


@admin.register(PublisherDomain)
class PublisherDomainAdmin(admin.ModelAdmin):
    list_display = [
        'domain', 'publisher', 'verification_status_badge',
        'is_primary', 'ssl_enabled', 'ssl_expires_at',
        'verified_at', 'last_checked_at', 'created_at',
    ]
    list_filter = ['verification_status', 'is_primary', 'ssl_enabled']
    search_fields = ['domain', 'publisher__username', 'publisher__email']
    readonly_fields = [
        'verification_token', 'verified_at', 'ssl_expires_at',
        'last_checked_at', 'created_at', 'updated_at', 'dns_txt_record_display',
    ]
    raw_id_fields = ['publisher']
    actions = ['verify_selected', 'check_ssl_selected']

    fieldsets = (
        ('Domain Info', {
            'fields': ('publisher', 'domain', 'is_primary', 'is_active'),
        }),
        ('Verification', {
            'fields': (
                'verification_status', 'verification_token',
                'dns_txt_record_display', 'verified_at', 'last_checked_at',
            ),
        }),
        ('SSL', {
            'fields': ('ssl_enabled', 'ssl_expires_at'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def verification_status_badge(self, obj):
        colors = {
            DomainVerificationStatus.VERIFIED: 'green',
            DomainVerificationStatus.PENDING: 'orange',
            DomainVerificationStatus.FAILED: 'red',
            DomainVerificationStatus.EXPIRED: 'gray',
        }
        color = colors.get(obj.verification_status, 'gray')
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color, obj.get_verification_status_display()
        )
    verification_status_badge.short_description = 'Status'

    def dns_txt_record_display(self, obj):
        return obj.dns_txt_record
    dns_txt_record_display.short_description = 'DNS TXT Record Value'

    @admin.action(description='🔍 Verify selected domains via DNS')
    def verify_selected(self, request, queryset):
        from ..services.core.DomainService import DomainService
        svc = DomainService()
        verified = failed = 0
        for domain_obj in queryset:
            try:
                svc.verify(domain_obj)
                verified += 1
            except Exception:
                failed += 1
        self.message_user(request, f'Verified: {verified}, Failed: {failed}')

    @admin.action(description='🔒 Check SSL for selected domains')
    def check_ssl_selected(self, request, queryset):
        from ..services.core.DomainService import DomainService
        svc = DomainService()
        for domain_obj in queryset:
            try:
                svc.check_ssl(domain_obj)
            except Exception:
                pass
        self.message_user(request, f'SSL checked for {queryset.count()} domains.')
