"""
Offerwall admin configuration
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import *


@admin.register(OfferProvider)
class OfferProviderAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'provider_type', 'status_badge', 'total_offers', 
        'total_conversions', 'total_revenue', 'revenue_share', 
        'last_sync', 'created_at'
    ]
    list_filter = ['provider_type', 'status', 'auto_sync']
    search_fields = ['name', 'app_id', 'publisher_id']
    readonly_fields = ['id', 'total_offers', 'total_conversions', 'total_revenue', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'provider_type', 'status')
        }),
        ('API Configuration', {
            'fields': ('api_key', 'api_secret', 'app_id', 'publisher_id', 'secret_key')
        }),
        ('URLs', {
            'fields': ('api_base_url', 'webhook_url', 'postback_url')
        }),
        ('Security', {
            'fields': ('ip_whitelist',)
        }),
        ('Settings', {
            'fields': ('revenue_share', 'rate_limit_per_minute', 'rate_limit_per_hour')
        }),
        ('Sync Settings', {
            'fields': ('auto_sync', 'sync_interval_minutes', 'last_sync')
        }),
        ('Statistics', {
            'fields': ('total_offers', 'total_conversions', 'total_revenue')
        }),
        ('Additional', {
            'fields': ('config', 'notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['sync_offers', 'activate_providers', 'deactivate_providers']
    
    def status_badge(self, obj):
        colors = {
            'active': 'green',
            'inactive': 'gray',
            'testing': 'orange',
            'suspended': 'red'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def sync_offers(self, request, queryset):
        from .services.OfferProcessor import OfferProcessorFactory
        
        for provider in queryset:
            try:
                processor = OfferProcessorFactory.create(provider)
                results = processor.sync_offers()
                self.message_user(
                    request,
                    f"{provider.name}: Synced {results['synced']} offers "
                    f"({results['created']} new, {results['updated']} updated)"
                )
            except Exception as e:
                self.message_user(request, f"{provider.name}: Error - {str(e)}", level='error')
    
    sync_offers.short_description = "Sync offers from selected providers"
    
    def activate_providers(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f"{updated} providers activated")
    activate_providers.short_description = "Activate selected providers"
    
    def deactivate_providers(self, request, queryset):
        updated = queryset.update(status='inactive')
        self.message_user(request, f"{updated} providers deactivated")
    deactivate_providers.short_description = "Deactivate selected providers"


@admin.register(OfferCategory)
class OfferCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'icon', 'color_preview', 'display_order', 'is_featured', 'is_active', 'offer_count']
    list_filter = ['is_featured', 'is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['offer_count', 'created_at', 'updated_at']
    
    def color_preview(self, obj):
        return format_html(
            '<div style="width: 30px; height: 20px; background-color: {}; border: 1px solid #ccc;"></div>',
            obj.color
        )
    color_preview.short_description = 'Color'


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = [
        'title_short', 'provider', 'category', 'offer_type', 'platform',
        'reward_amount', 'status_badge', 'quality_score', 'conversion_count',
        'is_featured', 'created_at'
    ]
    list_filter = [
        'status', 'offer_type', 'platform', 'provider', 'category',
        'is_featured', 'is_trending', 'difficulty'
    ]
    search_fields = ['title', 'external_offer_id', 'description']
    readonly_fields = [
        'id', 'external_offer_id', 'view_count', 'click_count', 'conversion_count',
        'completion_rate', 'quality_score', 'total_revenue', 'total_payout',
        'created_at', 'updated_at', 'last_synced'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'provider', 'external_offer_id', 'title', 'description', 'short_description')
        }),
        ('Categorization', {
            'fields': ('category', 'offer_type', 'tags')
        }),
        ('Platform & Location', {
            'fields': ('platform', 'countries', 'excluded_countries')
        }),
        ('Media', {
            'fields': ('image_url', 'thumbnail_url', 'icon_url', 'video_url')
        }),
        ('URLs', {
            'fields': ('click_url', 'tracking_url', 'preview_url')
        }),
        ('Payout & Reward', {
            'fields': ('payout', 'currency', 'reward_amount', 'reward_currency', 'bonus_amount', 'bonus_condition')
        }),
        ('Difficulty & Time', {
            'fields': ('difficulty', 'estimated_time_minutes')
        }),
        ('Requirements', {
            'fields': ('min_age', 'requires_signup', 'requires_card', 'requires_purchase', 
                      'instructions', 'requirements_text')
        }),
        ('Limits', {
            'fields': ('daily_cap', 'total_cap', 'user_limit')
        }),
        ('Status & Validity', {
            'fields': ('status', 'is_featured', 'is_trending', 'is_recommended', 'start_date', 'end_date')
        }),
        ('Statistics', {
            'fields': ('view_count', 'click_count', 'conversion_count', 'completion_rate',
                      'total_revenue', 'total_payout', 'quality_score'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata', 'provider_data', 'created_at', 'updated_at', 'last_synced'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_offers', 'deactivate_offers', 'feature_offers', 'unfeature_offers']
    
    def title_short(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Title'
    
    def status_badge(self, obj):
        colors = {
            'active': 'green',
            'paused': 'orange',
            'completed': 'blue',
            'expired': 'red',
            'disabled': 'gray'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def activate_offers(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f"{updated} offers activated")
    activate_offers.short_description = "Activate selected offers"
    
    def deactivate_offers(self, request, queryset):
        updated = queryset.update(status='paused')
        self.message_user(request, f"{updated} offers deactivated")
    deactivate_offers.short_description = "Deactivate selected offers"
    
    def feature_offers(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f"{updated} offers featured")
    feature_offers.short_description = "Feature selected offers"
    
    def unfeature_offers(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f"{updated} offers unfeatured")
    unfeature_offers.short_description = "Unfeature selected offers"


@admin.register(OfferClick)
class OfferClickAdmin(admin.ModelAdmin):
    list_display = ['click_id', 'offer_link', 'user_link', 'device_type', 'country', 'is_converted', 'clicked_at']
    list_filter = ['is_converted', 'device_type', 'country', 'clicked_at']
    search_fields = ['click_id', 'user__username', 'offer__title', 'ip_address']
    readonly_fields = ['id', 'click_id', 'clicked_at', 'converted_at']
    date_hierarchy = 'clicked_at'
    
    def offer_link(self, obj):
        url = reverse('admin:offerwall_offer_change', args=[obj.offer.id])
        return format_html('<a href="{}">{}</a>', url, obj.offer.title[:50])
    offer_link.short_description = 'Offer'
    
    def user_link(self, obj):
        url = reverse('admin:users_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'


@admin.register(OfferConversion)
class OfferConversionAdmin(admin.ModelAdmin):
    list_display = [
        'conversion_id', 'offer_link', 'user_link', 'reward_amount',
        'status_badge', 'is_verified', 'converted_at'
    ]
    list_filter = ['status', 'is_verified', 'converted_at']
    search_fields = ['conversion_id', 'external_transaction_id', 'user__username', 'offer__title']
    readonly_fields = ['id', 'conversion_id', 'converted_at', 'approved_at', 'updated_at']
    date_hierarchy = 'converted_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'offer', 'user', 'click', 'conversion_id', 'external_transaction_id')
        }),
        ('Payout', {
            'fields': ('payout_amount', 'payout_currency', 'reward_amount', 'reward_currency', 'bonus_amount')
        }),
        ('Status', {
            'fields': ('status', 'is_verified', 'verified_at', 'verified_by')
        }),
        ('Transaction', {
            'fields': ('transaction',)
        }),
        ('Notes', {
            'fields': ('notes', 'rejection_reason')
        }),
        ('Metadata', {
            'fields': ('provider_data', 'postback_data', 'converted_at', 'approved_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_conversions', 'reject_conversions']
    
    def offer_link(self, obj):
        url = reverse('admin:offerwall_offer_change', args=[obj.offer.id])
        return format_html('<a href="{}">{}</a>', url, obj.offer.title[:50])
    offer_link.short_description = 'Offer'
    
    def user_link(self, obj):
        url = reverse('admin:users_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'approved': 'green',
            'rejected': 'red',
            'chargeback': 'purple',
            'reversed': 'gray'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def approve_conversions(self, request, queryset):
        count = 0
        for conversion in queryset.filter(status='pending'):
            if conversion.approve(request.user):
                count += 1
        self.message_user(request, f"{count} conversions approved")
    approve_conversions.short_description = "Approve selected conversions"
    
    def reject_conversions(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='rejected')
        self.message_user(request, f"{updated} conversions rejected")
    reject_conversions.short_description = "Reject selected conversions"


@admin.register(OfferWall)
class OfferWallAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'offers_per_page', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ['categories', 'providers']
    
    

# api/offerwall/admin.py - একদম শেষের দিকে এই কোড রাখুন

# ==================== FORCE REGISTER ALL MODELS (WITH DUPLICATE CHECK) ====================
from django.contrib import admin

try:
    from .models import Offer, OfferCategory, OfferClick, OfferConversion, OfferProvider, OfferWall
    
    # Admin classes ইম্পোর্ট করুন
    from .admin import (
        OfferProviderAdmin, OfferCategoryAdmin, OfferAdmin,
        OfferClickAdmin, OfferConversionAdmin, OfferWallAdmin
    )
    
    registered = 0
    skipped = 0
    
    # Dictionary of models and their admin classes
    models_to_register = {
        OfferCategory: OfferCategoryAdmin,
        OfferProvider: OfferProviderAdmin,
        Offer: OfferAdmin,
        OfferClick: OfferClickAdmin,
        OfferConversion: OfferConversionAdmin,
        OfferWall: OfferWallAdmin,
    }
    
    for model, admin_class in models_to_register.items():
        try:
            if not admin.site.is_registered(model):
                admin.site.register(model, admin_class)
                registered += 1
                print(f"[OK] Registered: {model.__name__}")
            else:
                skipped += 1
                print(f"⏩ Already registered: {model.__name__}")
        except Exception as e:
            print(f"[ERROR] Error registering {model.__name__}: {e}")
    
    if registered > 0:
        print(f"[OK][OK][OK] {registered} offerwall models registered, {skipped} already existed")
    else:
        print(f"[OK] All offerwall models already registered ({skipped} models)")
        
except Exception as e:
    print(f"[ERROR] Error in force registration: {e}")

def _force_register_offerwall():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(OfferProvider, OfferProviderAdmin), (OfferCategory, OfferCategoryAdmin), (Offer, OfferAdmin), (OfferClick, OfferClickAdmin), (OfferConversion, OfferConversionAdmin), (OfferWall, OfferWallAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] offerwall registered {registered} models")
    except Exception as e:
        print(f"[WARN] offerwall: {e}")
