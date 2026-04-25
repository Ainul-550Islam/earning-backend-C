# api/payment_gateways/publisher/admin.py
from django.contrib import admin
from .models import PublisherProfile, AdvertiserProfile

@admin.register(PublisherProfile)
class PublisherProfileAdmin(admin.ModelAdmin):
    list_display   = ('user','status','tier','quality_score','is_fast_pay_eligible',
                      'preferred_payment','lifetime_earnings','lifetime_clicks','created_at')
    list_filter    = ('status','tier','is_fast_pay_eligible','preferred_payment')
    search_fields  = ('user__email','user__username')
    readonly_fields= ('lifetime_earnings','lifetime_clicks','lifetime_conversions','created_at')
    actions        = ['approve_publishers','suspend_publishers','grant_fast_pay','revoke_fast_pay']

    @admin.action(description='Approve publishers')
    def approve_publishers(self, request, queryset):
        queryset.update(status='active')

    @admin.action(description='Suspend publishers')
    def suspend_publishers(self, request, queryset):
        queryset.update(status='suspended')

    @admin.action(description='Grant Fast Pay eligibility')
    def grant_fast_pay(self, request, queryset):
        queryset.update(is_fast_pay_eligible=True)

    @admin.action(description='Revoke Fast Pay eligibility')
    def revoke_fast_pay(self, request, queryset):
        queryset.update(is_fast_pay_eligible=False)

@admin.register(AdvertiserProfile)
class AdvertiserProfileAdmin(admin.ModelAdmin):
    list_display   = ('user','company_name','status','balance','currency','total_spent','credit_limit','created_at')
    list_filter    = ('status','currency')
    search_fields  = ('user__email','company_name')
    readonly_fields= ('total_spent','created_at')
