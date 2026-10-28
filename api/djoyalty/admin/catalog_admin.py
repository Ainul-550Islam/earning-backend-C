# api/djoyalty/admin/catalog_admin.py
"""Django Admin for Catalog, SmartLink, Webhook, DigitalWallet models।"""
from django.contrib import admin
from ..models.catalog import (
    RewardCatalogCategory, RewardCatalogItem,
    SmartLink, SmartLinkClick,
    WebhookSubscription, WebhookDeliveryLog, DigitalWalletCard,
)


@admin.register(RewardCatalogCategory)
class RewardCatalogCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'sort_order', 'is_active', 'parent']
    list_filter = ['is_active']
    list_editable = ['sort_order', 'is_active']


@admin.register(RewardCatalogItem)
class RewardCatalogItemAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'reward_type', 'points_cost', 'cash_value',
        'stock_quantity', 'redeemed_count', 'is_featured', 'is_active',
    ]
    list_filter = ['reward_type', 'is_featured', 'is_active', 'fulfillment_type']
    search_fields = ['name', 'supplier_name']
    list_editable = ['is_featured', 'is_active']
    readonly_fields = ['redeemed_count', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Info', {'fields': ('name', 'description', 'reward_type', 'category')}),
        ('Pricing', {'fields': ('points_cost', 'cash_value', 'original_price', 'currency')}),
        ('Stock & Limits', {'fields': ('stock_quantity', 'redeemed_count', 'max_per_customer')}),
        ('Media', {'fields': ('image_url', 'gallery')}),
        ('Status', {'fields': ('is_active', 'is_featured', 'valid_from', 'valid_until', 'sort_order')}),
        ('Fulfillment', {'fields': ('supplier_name', 'fulfillment_type', 'terms')}),
    )


@admin.register(SmartLink)
class SmartLinkAdmin(admin.ModelAdmin):
    list_display = [
        'slug', 'name', 'total_clicks', 'unique_clicks',
        'total_conversions', 'is_active', 'created_at',
    ]
    list_filter = ['is_active']
    search_fields = ['slug', 'name']
    readonly_fields = ['total_clicks', 'unique_clicks', 'total_conversions', 'created_at']


@admin.register(WebhookSubscription)
class WebhookSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'url_preview', 'total_deliveries', 'successful_deliveries',
        'failed_deliveries', 'is_active', 'is_verified',
    ]
    list_filter = ['is_active', 'is_verified']
    search_fields = ['name', 'url']
    readonly_fields = [
        'total_deliveries', 'successful_deliveries', 'failed_deliveries',
        'last_delivery_at', 'last_success_at',
    ]

    def url_preview(self, obj):
        return obj.url[:60]
    url_preview.short_description = 'URL'


@admin.register(WebhookDeliveryLog)
class WebhookDeliveryLogAdmin(admin.ModelAdmin):
    list_display = [
        'subscription', 'event_type', 'attempt_number',
        'http_status', 'duration_ms', 'success', 'delivered_at',
    ]
    list_filter = ['success', 'event_type']
    search_fields = ['event_type', 'error_message']
    readonly_fields = ['payload', 'delivered_at']
    date_hierarchy = 'delivered_at'


@admin.register(DigitalWalletCard)
class DigitalWalletCardAdmin(admin.ModelAdmin):
    list_display = [
        'customer', 'wallet_type', 'card_number',
        'barcode_type', 'is_active', 'created_at',
    ]
    list_filter = ['wallet_type', 'barcode_type', 'is_active']
    search_fields = ['customer__code', 'card_number', 'barcode_value']
    readonly_fields = ['created_at', 'updated_at']
