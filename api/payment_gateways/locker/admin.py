# api/payment_gateways/locker/admin.py
from django.contrib import admin
from .models import ContentLocker, LockerSession, OfferWall, UserVirtualBalance, VirtualReward

@admin.register(ContentLocker)
class ContentLockerAdmin(admin.ModelAdmin):
    list_display   = ('name','locker_type','publisher','status','total_impressions','total_unlocks','total_earnings','created_at')
    list_filter    = ('locker_type','status')
    search_fields  = ('name','publisher__email','locker_key')
    readonly_fields= ('locker_key','total_impressions','total_unlocks','total_earnings','embed_code','unlock_rate')
    fieldsets = (
        ('Basic', {'fields': ('name','locker_type','status','publisher','locker_key')}),
        ('Content', {'fields': ('destination_url','file_upload','overlay_selector','page_url')}),
        ('Settings', {'fields': ('unlock_duration_hours','show_offer_count','require_specific_offer')}),
        ('Customization', {'fields': ('title','description','theme','primary_color','logo_url')}),
        ('Stats', {'fields': ('total_impressions','total_unlocks','total_earnings','embed_code')}),
    )

@admin.register(OfferWall)
class OfferWallAdmin(admin.ModelAdmin):
    list_display   = ('name','publisher','currency_name','exchange_rate','total_completions','total_earnings','status')
    list_filter    = ('status',)
    search_fields  = ('name','publisher__email','wall_key')
    readonly_fields= ('wall_key','total_completions','total_earnings','api_url','embed_script')

@admin.register(UserVirtualBalance)
class UserVirtualBalanceAdmin(admin.ModelAdmin):
    list_display   = ('user','offer_wall','balance','total_earned','total_spent')
    search_fields  = ('user__email',)

@admin.register(VirtualReward)
class VirtualRewardAdmin(admin.ModelAdmin):
    list_display   = ('user','offer_wall','reward_type','amount','usd_equivalent','created_at')
    list_filter    = ('reward_type',)
    search_fields  = ('user__email',)
    readonly_fields= ('created_at',)
