# api/payment_gateways/referral/admin.py
from django.contrib import admin
from .models import ReferralProgram, ReferralLink, Referral, ReferralCommission

@admin.register(ReferralProgram)
class ReferralProgramAdmin(admin.ModelAdmin):
    list_display   = ('commission_percent','commission_months','minimum_payout','cookie_duration_days','is_active')

@admin.register(ReferralLink)
class ReferralLinkAdmin(admin.ModelAdmin):
    list_display   = ('user','code','total_clicks','total_signups','total_earned','is_active','created_at')
    search_fields  = ('user__email','code')
    readonly_fields= ('code','full_url','created_at')

@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display   = ('referrer','referred_user','is_active','commission_start','commission_end','total_commission_paid')
    list_filter    = ('is_active',)
    search_fields  = ('referrer__email','referred_user__email')

@admin.register(ReferralCommission)
class ReferralCommissionAdmin(admin.ModelAdmin):
    list_display   = ('referrer','referred_user','commission_amount','commission_percent','status','paid_at','created_at')
    list_filter    = ('status',)
    search_fields  = ('referrer__email','referred_user__email')
    readonly_fields= ('created_at','paid_at')
