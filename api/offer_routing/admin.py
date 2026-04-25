"""
Django Admin Configuration for Offer Routing System
"""

from django.contrib import admin
from django.contrib.admin import ModelAdmin, StackedInline, TabularInline
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum, Avg
from django.forms import ModelForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.template.response import TemplateResponse
import json

from .models import (
    OfferRoute, RouteCondition, RouteAction,
    GeoRouteRule, DeviceRouteRule, UserSegmentRule,
    TimeRouteRule, BehaviorRouteRule,
    OfferScore, OfferScoreConfig, GlobalOfferRank,
    UserOfferHistory, OfferAffinityScore,
    UserPreferenceVector, ContextualSignal, PersonalizationConfig,
    OfferRoutingCap, UserOfferCap, CapOverride,
    FallbackRule, DefaultOfferPool, EmptyResultHandler,
    RoutingABTest, ABTestAssignment, ABTestResult,
    RoutingDecisionLog, RoutingInsight, RoutePerformanceStat,
    OfferExposureStat
)

User = get_user_model()


@admin.register(OfferRoute)
class OfferRouteAdmin(ModelAdmin):
    list_display = ['name', 'tenant', 'max_offers', 'created_at', 'route_actions_count']
    list_filter = ['max_offers', 'created_at', 'tenant']
    search_fields = ['name', 'description', 'tenant__username']
    list_editable = ['max_offers']
    ordering = ['-priority', 'name']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'tenant')
        }),
        ('Configuration', {
            'fields': ('max_offers',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    readonly_fields = ['created_at']
    inlines = []

    def route_actions_count(self, obj):
        return obj.actions.count()
    route_actions_count.short_description = 'Actions'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant').prefetch_related(
            'actions', 'conditions', 'geo_rules', 'device_rules'
        )


class RouteConditionInline(TabularInline):
    model = RouteCondition
    extra = 1
    fields = ['field_name', 'operator', 'value', 'is_required']


class RouteActionInline(TabularInline):
    model = RouteAction
    extra = 1
    fields = ['action_type', 'action_value']


class GeoRouteRuleInline(TabularInline):
    model = GeoRouteRule
    extra = 1
    fields = ['country', 'region', 'city', 'is_include']


class DeviceRouteRuleInline(TabularInline):
    model = DeviceRouteRule
    extra = 1
    fields = ['device_type', 'os_type', 'browser_type', 'is_include']


class UserSegmentRuleInline(TabularInline):
    model = UserSegmentRule
    extra = 1
    fields = ['segment_type', 'segment_value', 'operator', 'is_include']


class TimeRouteRuleInline(TabularInline):
    model = TimeRouteRule
    extra = 1
    fields = ['start_time', 'end_time', 'start_hour', 'end_hour', 'days_of_week', 'is_include']


class BehaviorRouteRuleInline(TabularInline):
    model = BehaviorRouteRule
    extra = 1
    fields = ['event_type', 'event_count_min', 'event_count_max', 'time_period_hours', 'is_include']


@admin.register(OfferScore)
class OfferScoreAdmin(ModelAdmin):
    list_display = ['user', 'score', 'epc', 'cr', 'relevance', 'freshness']
    list_filter = ['user']
    search_fields = ['offer__name', 'user__username']
    ordering = ['-id']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(OfferScoreConfig)
class OfferScoreConfigAdmin(ModelAdmin):
    list_display = ['tenant', 'epc_weight', 'cr_weight', 'relevance_weight', 'freshness_weight']
    list_filter = ['tenant', 'created_at']
    search_fields = ['offer__name', 'tenant__username']
    list_editable = ['epc_weight', 'cr_weight', 'relevance_weight', 'freshness_weight']

    def is_active(self, obj):
        return obj.offer.is_active if obj.offer else False
    is_active.boolean = True
    is_active.short_description = 'Active'


@admin.register(GlobalOfferRank)
class GlobalOfferRankAdmin(ModelAdmin):
    list_display = ['tenant', 'rank_score', 'rank_date']
    list_filter = ['rank_date', 'tenant']
    search_fields = ['offer__name', 'tenant__username']
    ordering = ['-rank_date']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')


@admin.register(UserOfferHistory)
class UserOfferHistoryAdmin(ModelAdmin):
    list_display = ['user', 'route', 'viewed_at', 'clicked_at', 'completed_at', 'conversion_value']
    list_filter = ['viewed_at', 'clicked_at', 'completed_at', 'user']
    search_fields = ['user__username', 'offer__name']
    ordering = ['-viewed_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'route')


@admin.register(OfferAffinityScore)
class OfferAffinityScoreAdmin(ModelAdmin):
    list_display = ['user', 'category', 'score', 'confidence']
    list_filter = ['category']
    search_fields = ['user__username', 'category']
    ordering = ['-id']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(UserPreferenceVector)
class UserPreferenceVectorAdmin(ModelAdmin):
    list_display = ['user', 'vector_size']
    list_filter = []
    search_fields = ['user__username']
    ordering = ['-id']

    def vector_size(self, obj):
        try:
            return len(obj.vector) if obj.vector else 0
        except (TypeError, ValueError):
            return 0
    vector_size.short_description = 'Vector Size'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(ContextualSignal)
class ContextualSignalAdmin(ModelAdmin):
    list_display = ['user', 'signal_type', 'value', 'created_at']
    list_filter = ['signal_type', 'created_at']
    search_fields = ['user__username', 'signal_type']
    ordering = ['-created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(PersonalizationConfig)
class PersonalizationConfigAdmin(ModelAdmin):
    list_display = ['tenant', 'user', 'algorithm', 'real_time_enabled', 'context_signals_enabled', 'created_at']
    list_filter = ['algorithm', 'real_time_enabled', 'context_signals_enabled', 'tenant']
    search_fields = ['tenant__username', 'user__username', 'algorithm']
    list_editable = ['real_time_enabled', 'context_signals_enabled']
    ordering = ['-created_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'user', 'algorithm')
        }),
        ('Weights', {
            'fields': (
                'collaborative_weight', 'content_based_weight',
                'hybrid_weight', 'min_affinity_score'
            )
        }),
        ('Settings', {
            'fields': ('max_offers_per_user', 'real_time_enabled', 'context_signals_enabled')
        }),
        ('Status', {
            'fields': ('created_at',)
        })
    )
    readonly_fields = ['created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant', 'user')


@admin.register(OfferRoutingCap)
class OfferRoutingCapAdmin(ModelAdmin):
    list_display = ['tenant', 'cap_type', 'cap_value', 'current_count', 'remaining_capacity']
    list_filter = ['cap_type', 'tenant']
    search_fields = ['offer__name', 'tenant__username']
    list_editable = ['cap_value']
    ordering = ['cap_type']

    def remaining_capacity(self, obj):
        remaining = obj.get_remaining_capacity()
        if remaining == float('inf'):
            return 'Unlimited'
        return remaining
    remaining_capacity.short_description = 'Remaining'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')


@admin.register(UserOfferCap)
class UserOfferCapAdmin(ModelAdmin):
    list_display = ['user', 'cap_type', 'max_shows_per_day', 'shown_today', 'remaining_today', 'reset_at']
    list_filter = ['cap_type', 'created_at']
    search_fields = ['user__username', 'offer__name']
    list_editable = ['max_shows_per_day']
    ordering = ['user']

    def remaining_today(self, obj):
        return max(0, obj.max_shows_per_day - obj.shown_today)
    remaining_today.short_description = 'Remaining Today'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(CapOverride)
class CapOverrideAdmin(ModelAdmin):
    list_display = ['tenant', 'override_type', 'override_cap', 'reason', 'valid_from', 'valid_to']
    list_filter = ['override_type', 'tenant']
    search_fields = ['offer__name', 'tenant__username', 'reason']
    ordering = ['-valid_from']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')


@admin.register(FallbackRule)
class FallbackRuleAdmin(ModelAdmin):
    list_display = ['name', 'tenant', 'fallback_type', 'category', 'network', 'created_at']
    list_filter = ['fallback_type', 'category', 'network', 'tenant']
    search_fields = ['name', 'description', 'tenant__username']
    ordering = ['name']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'tenant')
        }),
        ('Configuration', {
            'fields': ('fallback_type', 'category', 'network', 'promotion_code')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time')
        }),
        ('Status', {
            'fields': ('created_at',)
        })
    )
    readonly_fields = ['created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')


@admin.register(DefaultOfferPool)
class DefaultOfferPoolAdmin(ModelAdmin):
    list_display = ['name', 'tenant', 'pool_type', 'max_offers', 'rotation_strategy', 'offer_count']
    list_filter = ['pool_type', 'rotation_strategy', 'tenant']
    search_fields = ['name', 'description', 'tenant__username']
    list_editable = ['max_offers', 'rotation_strategy']
    ordering = ['name']
    filter_horizontal = ['offers']

    def offer_count(self, obj):
        return obj.offers.count()
    offer_count.short_description = 'Offers'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant').prefetch_related('offers')


@admin.register(EmptyResultHandler)
class EmptyResultHandlerAdmin(ModelAdmin):
    list_display = ['name', 'tenant', 'action_type', 'created_at']
    list_filter = ['action_type', 'tenant']
    search_fields = ['name', 'description', 'tenant__username']
    ordering = ['name']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')


@admin.register(RoutingABTest)
class RoutingABTestAdmin(ModelAdmin):
    list_display = ['name', 'tenant', 'control_route', 'variant_route', 'split_percentage', 'started_at', 'winner']
    list_filter = ['success_metric', 'split_percentage', 'started_at', 'ended_at', 'tenant']
    search_fields = ['name', 'description', 'tenant__username']
    list_editable = ['split_percentage']
    ordering = ['-created_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'tenant')
        }),
        ('Test Configuration', {
            'fields': (
                'control_route', 'variant_route', 'split_percentage',
                'success_metric', 'min_sample_size', 'confidence_level'
            )
        }),
        ('Timing', {
            'fields': ('started_at', 'ended_at', 'duration_hours')
        }),
        ('Results', {
            'fields': ('winner', 'confidence'),
            'classes': ('collapse',)
        })
    )
    readonly_fields = ['created_at']
    inlines = []

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'control_route', 'variant_route', 'created_by'
        ).prefetch_related('assignments', 'results')


class ABTestAssignmentInline(TabularInline):
    model = ABTestAssignment
    extra = 0
    fields = ['user', 'variant', 'impressions', 'clicks', 'conversions', 'revenue']
    readonly_fields = ['user', 'variant']

    def has_add_permission(self, request, obj=None):
        return False


class ABTestResultInline(TabularInline):
    model = ABTestResult
    extra = 0
    fields = [
        'control_impressions', 'control_clicks', 'control_conversions',
        'variant_impressions', 'variant_clicks', 'variant_conversions',
        'winner', 'confidence_level', 'analyzed_at'
    ]
    readonly_fields = ['analyzed_at']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ABTestAssignment)
class ABTestAssignmentAdmin(ModelAdmin):
    list_display = ['user', 'test', 'variant', 'impressions', 'clicks', 'conversions', 'conversion_rate', 'assigned_at']
    list_filter = ['variant', 'assigned_at', 'test']
    search_fields = ['user__username', 'test__name']
    ordering = ['-assigned_at']

    def conversion_rate(self, obj):
        if obj.impressions == 0:
            return 0.0
        return (obj.conversions / obj.impressions) * 100
    conversion_rate.short_description = 'CR %'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'test')


@admin.register(ABTestResult)
class ABTestResultAdmin(ModelAdmin):
    list_display = ['test', 'winner', 'confidence_level', 'is_significant', 'control_cr', 'variant_cr', 'cr_difference', 'analyzed_at']
    list_filter = ['winner', 'is_significant', 'analyzed_at']
    search_fields = ['test__name']
    ordering = ['-analyzed_at']

    def control_cr(self, obj):
        if obj.control_impressions == 0:
            return 0.0
        return (obj.control_conversions / obj.control_impressions) * 100
    control_cr.short_description = 'Control CR %'

    def variant_cr(self, obj):
        if obj.variant_impressions == 0:
            return 0.0
        return (obj.variant_conversions / obj.variant_impressions) * 100
    variant_cr.short_description = 'Variant CR %'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('test')


@admin.register(RoutingDecisionLog)
class RoutingDecisionLogAdmin(ModelAdmin):
    list_display = ['user', 'offer_id', 'score', 'rank', 'response_time_ms', 'cache_hit', 'personalization_applied', 'created_at']
    list_filter = ['cache_hit', 'personalization_applied', 'caps_checked', 'fallback_used', 'created_at']
    search_fields = ['user__username']
    ordering = ['-created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    def has_add_permission(self, request):
        return False


@admin.register(RoutingInsight)
class RoutingInsightAdmin(ModelAdmin):
    list_display = ['tenant', 'insight_type', 'title', 'severity', 'is_actionable', 'created_at']
    list_filter = ['insight_type', 'severity', 'is_actionable', 'created_at']
    search_fields = ['title', 'description', 'tenant__username']
    ordering = ['-created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')


@admin.register(RoutePerformanceStat)
class RoutePerformanceStatAdmin(ModelAdmin):
    list_display = ['tenant', 'date', 'impressions', 'clicks', 'conversions', 'revenue', 'conversion_rate', 'avg_response_time_ms']
    list_filter = ['date', 'tenant']
    search_fields = ['offer__name', 'tenant__username']
    ordering = ['-date']

    def conversion_rate(self, obj):
        if obj.impressions == 0:
            return 0.0
        return (obj.conversions / obj.impressions) * 100
    conversion_rate.short_description = 'CR %'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')

    def has_add_permission(self, request):
        return False


@admin.register(OfferExposureStat)
class OfferExposureStatAdmin(ModelAdmin):
    list_display = ['tenant', 'date', 'aggregation_type', 'unique_users_exposed', 'total_exposures', 'avg_exposures_per_user']
    list_filter = ['date', 'aggregation_type', 'tenant']
    search_fields = ['offer__name', 'tenant__username']
    ordering = ['-date']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')

    def has_add_permission(self, request):
        return False


class OfferRoutingAdminSite(admin.AdminSite):
    site_header = 'Offer Routing Administration'
    site_title = 'Offer Routing Admin'
    index_title = 'Welcome to Offer Routing Admin Portal'

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('routing-dashboard/', self.admin_view(self.routing_dashboard), name='routing_dashboard'),
            path('performance-stats/', self.admin_view(self.performance_stats), name='performance_stats'),
        ]
        return custom_urls + urls

    def routing_dashboard(self, request):
        context = {
            **self.each_context(request),
            'title': 'Routing Dashboard',
            'total_routes': OfferRoute.objects.count(),
            'active_tests': RoutingABTest.objects.filter(is_active=True).count(),
            'total_decisions_today': RoutingDecisionLog.objects.filter(
                created_at__date=timezone.now().date()
            ).count(),
        }
        return TemplateResponse(request, 'admin/routing_dashboard.html', context)

    def performance_stats(self, request):
        context = {
            **self.each_context(request),
            'title': 'Performance Statistics',
        }
        return TemplateResponse(request, 'admin/performance_stats.html', context)


offer_routing_admin = OfferRoutingAdminSite(name='offer_routing_admin')

for model, admin_class in [
    (OfferRoute, OfferRouteAdmin),
    (RoutingABTest, RoutingABTestAdmin),
    (RoutingDecisionLog, RoutingDecisionLogAdmin),
    (RoutePerformanceStat, RoutePerformanceStatAdmin),
]:
    offer_routing_admin.register(model, admin_class)


@admin.action(description='Reset selected caps')
def reset_caps(modeladmin, request, queryset):
    count = 0
    for cap in queryset:
        if hasattr(cap, 'reset_daily_cap'):
            cap.reset_daily_cap()
            count += 1
    modeladmin.message_user(request, f'{count} caps reset successfully.')


@admin.action(description='Mark selected insights as resolved')
def resolve_insights(modeladmin, request, queryset):
    updated = queryset.update(is_resolved=True)
    modeladmin.message_user(request, f'{updated} insights marked as resolved.')


@admin.action(description='Export selected decision logs')
def export_decision_logs(modeladmin, request, queryset):
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="decision_logs.csv"'

    writer = csv.writer(response)
    writer.writerow(['User', 'Offer ID', 'Score', 'Response Time (ms)', 'Created At'])

    for log in queryset:
        writer.writerow([
            log.user.username,
            log.offer_id,
            log.score,
            log.response_time_ms,
            log.created_at.isoformat()
        ])

    return response


OfferRoutingCapAdmin.actions = [reset_caps]
RoutingInsightAdmin.actions = [resolve_insights]
RoutingDecisionLogAdmin.actions = [export_decision_logs]
