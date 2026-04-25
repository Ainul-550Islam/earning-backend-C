# api/payment_gateways/blacklist/admin.py
from django.contrib import admin
from .models import TrafficBlacklist, OfferQualityScore

@admin.register(TrafficBlacklist)
class TrafficBlacklistAdmin(admin.ModelAdmin):
    list_display   = ('block_type','value','owner','created_by_type','is_active','block_count','created_at')
    list_filter    = ('block_type','created_by_type','is_active')
    search_fields  = ('value','owner__email')
    actions        = ['deactivate_rules','activate_rules']

    @admin.action(description='Deactivate selected rules')
    def deactivate_rules(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description='Activate selected rules')
    def activate_rules(self, request, queryset):
        queryset.update(is_active=True)

@admin.register(OfferQualityScore)
class OfferQualityScoreAdmin(admin.ModelAdmin):
    list_display   = ('publisher','offer','quality_score','conversion_rate','fraud_rate','is_blacklisted','last_updated')
    list_filter    = ('is_blacklisted',)
    search_fields  = ('publisher__email','offer__name')
    readonly_fields= ('last_updated',)
