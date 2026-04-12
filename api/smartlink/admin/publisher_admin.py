from django.contrib import admin
from ..models.publisher import PublisherSmartLink, PublisherSubID, PublisherAllowList, PublisherBlockList


@admin.register(PublisherSmartLink)
class PublisherSmartLinkAdmin(admin.ModelAdmin):
    list_display = ['publisher', 'smartlink', 'is_active', 'can_edit_targeting', 'can_edit_pool', 'assigned_at']
    list_filter = ['is_active', 'can_edit_targeting', 'can_edit_pool']
    search_fields = ['publisher__username', 'smartlink__slug']
    raw_id_fields = ['publisher', 'smartlink', 'assigned_by']


@admin.register(PublisherSubID)
class PublisherSubIDAdmin(admin.ModelAdmin):
    list_display = ['publisher', 'smartlink', 'sub1_label', 'sub2_label', 'sub3_label']
    search_fields = ['publisher__username']
    raw_id_fields = ['publisher', 'smartlink']


@admin.register(PublisherAllowList)
class PublisherAllowListAdmin(admin.ModelAdmin):
    list_display = ['publisher', 'category', 'advertiser', 'is_active', 'granted_by', 'expires_at']
    list_filter = ['is_active', 'category']
    search_fields = ['publisher__username', 'category']
    raw_id_fields = ['publisher', 'advertiser', 'granted_by']


@admin.register(PublisherBlockList)
class PublisherBlockListAdmin(admin.ModelAdmin):
    list_display = ['publisher', 'advertiser', 'category', 'is_active', 'blocked_by', 'created_at']
    list_filter = ['is_active']
    search_fields = ['publisher__username', 'category']
    raw_id_fields = ['publisher', 'advertiser', 'blocked_by']
