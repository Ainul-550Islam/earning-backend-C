# api/djoyalty/admin/offerwall_admin.py
"""Django Admin for OfferWall models।"""
from django.contrib import admin
from django.utils.html import format_html
from ..models.offerwall import OfferWall, Offer, OfferCompletion, ContentLock, OfferPostbackLog


@admin.register(OfferWall)
class OfferWallAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider', 'currency_name', 'currency_ratio', 'is_active']
    list_filter = ['provider', 'is_active']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'offer_wall', 'offer_type', 'points_reward',
        'advertiser_payout', 'status', 'is_featured', 'total_completions',
    ]
    list_filter = ['offer_type', 'status', 'is_featured', 'difficulty']
    search_fields = ['title', 'external_offer_id', 'advertiser_name']
    list_editable = ['status', 'is_featured']
    readonly_fields = ['total_completions', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic', {'fields': ('offer_wall', 'title', 'description', 'offer_type', 'status')}),
        ('Rewards', {'fields': ('points_reward', 'advertiser_payout', 'currency')}),
        ('Targeting', {'fields': ('geo_targets', 'device_targets', 'min_tier')}),
        ('Limits', {'fields': ('max_completions_per_user', 'max_total_completions', 'total_completions')}),
        ('Schedule', {'fields': ('valid_from', 'valid_until', 'is_featured', 'sort_order')}),
    )


@admin.register(OfferCompletion)
class OfferCompletionAdmin(admin.ModelAdmin):
    list_display = [
        'customer', 'offer', 'status', 'points_awarded',
        'advertiser_payout_received', 'postback_received', 'completed_at',
    ]
    list_filter = ['status', 'postback_received', 'is_flagged']
    search_fields = ['customer__code', 'provider_transaction_id']
    readonly_fields = ['created_at', 'updated_at', 'postback_data']
    date_hierarchy = 'completed_at'


@admin.register(ContentLock)
class ContentLockAdmin(admin.ModelAdmin):
    list_display = ['title', 'offer_wall', 'content_type', 'unlock_method', 'total_unlocks', 'is_active']
    list_filter = ['content_type', 'unlock_method', 'is_active']
    search_fields = ['title']


@admin.register(OfferPostbackLog)
class OfferPostbackLogAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id', 'offer_wall', 'payout', 'signature_valid',
        'processed', 'points_credited', 'received_at',
    ]
    list_filter = ['processed', 'signature_valid']
    search_fields = ['transaction_id', 'customer_ref']
    readonly_fields = ['raw_data', 'received_at']
    date_hierarchy = 'received_at'
