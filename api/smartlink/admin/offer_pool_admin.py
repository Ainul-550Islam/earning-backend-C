from django.contrib import admin
from ..models import OfferPool, OfferPoolEntry, OfferCapTracker, OfferBlacklist, OfferRotationLog, OfferScoreCache


class OfferPoolEntryInline(admin.TabularInline):
    model = OfferPoolEntry
    extra = 0
    fields = ['offer', 'weight', 'priority', 'cap_per_day', 'is_active', 'epc_override']
    raw_id_fields = ['offer']


@admin.register(OfferPool)
class OfferPoolAdmin(admin.ModelAdmin):
    list_display = ['smartlink', 'active_entries_count', 'is_active', 'min_epc_threshold', 'created_at']
    search_fields = ['smartlink__slug']
    inlines = [OfferPoolEntryInline]

    def active_entries_count(self, obj):
        return obj.entries.filter(is_active=True).count()
    active_entries_count.short_description = 'Active Offers'


@admin.register(OfferPoolEntry)
class OfferPoolEntryAdmin(admin.ModelAdmin):
    list_display = ['pool', 'offer', 'weight', 'priority', 'cap_per_day', 'is_active', 'epc_override']
    list_filter = ['is_active']
    search_fields = ['pool__smartlink__slug', 'offer__name']
    raw_id_fields = ['offer', 'pool']


@admin.register(OfferCapTracker)
class OfferCapTrackerAdmin(admin.ModelAdmin):
    list_display = ['pool_entry', 'period', 'period_date', 'clicks_count', 'cap_limit', 'is_capped']
    list_filter = ['period', 'is_capped', 'period_date']
    search_fields = ['pool_entry__offer__name']
    readonly_fields = ['clicks_count', 'is_capped', 'last_updated']


@admin.register(OfferBlacklist)
class OfferBlacklistAdmin(admin.ModelAdmin):
    list_display = ['smartlink', 'offer', 'added_by', 'created_at']
    search_fields = ['smartlink__slug', 'offer__name']
    raw_id_fields = ['smartlink', 'offer', 'added_by']


@admin.register(OfferRotationLog)
class OfferRotationLogAdmin(admin.ModelAdmin):
    list_display = ['smartlink', 'offer', 'selected_reason', 'country', 'device_type', 'created_at']
    list_filter = ['selected_reason', 'country', 'device_type']
    search_fields = ['smartlink__slug']
    readonly_fields = list_display

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OfferScoreCache)
class OfferScoreCacheAdmin(admin.ModelAdmin):
    list_display = ['offer', 'country', 'device_type', 'score', 'epc', 'total_clicks', 'calculated_at']
    list_filter = ['country', 'device_type']
    search_fields = ['offer__name']
    ordering = ['-score']
