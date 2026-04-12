"""
Advertiser Portal Django Admin Configuration

This module contains the Django admin configuration for the Advertiser Portal,
including admin classes for all models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum, Avg
from django.utils.safestring import mark_safe

from .models import *
from .database_models import *


@admin.register(Advertiser)
class AdvertiserAdmin(admin.ModelAdmin):
    """Admin configuration for Advertiser model."""
    
    list_display = [
        'company_name', 'trade_name', 'contact_email', 'contact_phone',
        'is_verified', 'status', 'total_campaigns', 'total_spend',
        'quality_score', 'created_at'
    ]
    list_filter = [
        'status', 'is_verified', 'account_type', 'industry',
        'created_at', 'verification_date'
    ]
    search_fields = [
        'company_name', 'trade_name', 'contact_email', 'contact_name',
        'website', 'description'
    ]
    readonly_fields = [
        'id', 'total_spend', 'total_campaigns', 'active_campaigns',
        'quality_score', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'company_name', 'trade_name', 'industry', 'sub_industry',
                'contact_email', 'contact_phone', 'contact_name', 'contact_title',
                'website', 'description'
            )
        }),
        ('Business Details', {
            'fields': (
                'company_size', 'annual_revenue', 'account_type',
                'account_manager', 'timezone', 'currency', 'language'
            )
        }),
        ('Address Information', {
            'fields': (
                'billing_address', 'billing_city', 'billing_state',
                'billing_country', 'billing_postal_code'
            )
        }),
        ('Verification', {
            'fields': (
                'is_verified', 'verified_by', 'verification_date',
                'verification_documents'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'total_spend', 'total_campaigns', 'active_campaigns',
                'quality_score'
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                'id', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def total_campaigns(self, obj):
        """Get total campaigns count."""
        return obj.total_campaigns
    
    def total_spend(self, obj):
        """Get total spend."""
        return f"${obj.total_spend:.2f}"
    
    def quality_score(self, obj):
        """Display quality score with color coding."""
        score = obj.quality_score
        if score >= 80:
            color = 'green'
        elif score >= 60:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, score
        )


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    """Admin configuration for Campaign model."""
    
    list_display = [
        'name', 'advertiser', 'objective', 'bidding_strategy',
        'status', 'daily_budget', 'total_budget', 'current_spend',
        'performance_score', 'created_at'
    ]
    list_filter = [
        'status', 'objective', 'bidding_strategy', 'delivery_method',
        'created_at', 'start_date'
    ]
    search_fields = [
        'name', 'description', 'advertiser__company_name'
    ]
    readonly_fields = [
        'id', 'current_spend', 'remaining_budget', 'budget_utilization',
        'quality_score', 'performance_score', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'advertiser', 'name', 'description', 'objective',
                'bidding_strategy', 'target_cpa', 'target_roas'
            )
        }),
        ('Budget Settings', {
            'fields': (
                'daily_budget', 'total_budget', 'budget_delivery_method',
                'auto_pause_on_budget_exhaust', 'auto_restart_on_budget_refill'
            )
        }),
        ('Schedule', {
            'fields': (
                'start_date', 'end_date', 'start_time', 'end_time',
                'days_of_week', 'timezone'
            )
        }),
        ('Targeting', {
            'fields': (
                'device_targeting', 'platform_targeting', 'geo_targeting',
                'audience_targeting', 'language_targeting', 'content_targeting'
            ),
            'classes': ('collapse',)
        }),
        ('Optimization', {
            'fields': (
                'auto_optimize', 'optimization_goals', 'learning_phase',
                'bid_adjustments', 'bid_floor', 'bid_ceiling'
            ),
            'classes': ('collapse',)
        }),
        ('Performance Metrics', {
            'fields': (
                'current_spend', 'remaining_budget', 'budget_utilization',
                'total_impressions', 'total_clicks', 'total_conversions',
                'quality_score', 'performance_score'
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                'id', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def current_spend(self, obj):
        """Get current spend."""
        return f"${obj.current_spend:.2f}"
    
    def performance_score(self, obj):
        """Display performance score with color coding."""
        score = obj.performance_score
        if score >= 80:
            color = 'green'
        elif score >= 60:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, score
        )


@admin.register(Creative)
class CreativeAdmin(admin.ModelAdmin):
    """Admin configuration for Creative model."""
    
    list_display = [
        'name', 'campaign', 'creative_type',
        'status', 'quality_score',
        'performance_score', 'file_size', 'created_at'
    ]
    list_filter = [
        'status', 'creative_type',
        'created_at'
    ]
    search_fields = [
        'name', 'description', 'advertiser__company_name',
        'campaign__name'
    ]
    readonly_fields = [
        'id', 'file_hash', 'quality_score', 'performance_score',
        'created_at', 'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'advertiser', 'campaign', 'name', 'description',
                'creative_type', 'file_path', 'file_name'
            )
        }),
        ('File Information', {
            'fields': (
                'file_size', 'file_mime_type', 'file_hash',
                'width', 'height', 'duration', 'aspect_ratio'
            )
        }),
        ('Content', {
            'fields': (
                'text_content', 'call_to_action', 'landing_page_url',
                'display_url', 'third_party_tracking_urls'
            )
        }),
        ('Dynamic Creative', {
            'fields': (
                'dynamic_creative', 'template_id', 'template_data',
                'personalization_rules', 'ad_variations'
            ),
            'classes': ('collapse',)
        }),
        ('Approval', {
            'fields': (
                'status', 'approval_status', 'require_approval'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'quality_score', 'performance_score'
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                'id', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def file_size(self, obj):
        """Display file size in human readable format."""
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        else:
            return f"{obj.file_size / (1024 * 1024):.1f} MB"


@admin.register(Targeting)
class TargetingAdmin(admin.ModelAdmin):
    """Admin configuration for Targeting model."""
    
    list_display = [
        'name', 'campaign', 'geo_targeting_type',
        'age_range', 'genders', 'languages', 'created_at'
    ]
    list_filter = [
        'geo_targeting_type', 'campaign', 'created_at'
    ]
    search_fields = [
        'name', 'description', 'campaign__name'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'campaign', 'name', 'description'
            )
        }),
        ('Geographic Targeting', {
            'fields': (
                'geo_targeting_type', 'countries', 'regions', 'cities',
                'postal_codes', 'coordinates', 'radius', 'geo_fencing'
            ),
            'classes': ('collapse',)
        }),
        ('Device Targeting', {
            'fields': (
                'device_targeting', 'os_families', 'browsers',
                'carriers', 'device_models', 'connection_types'
            ),
            'classes': ('collapse',)
        }),
        ('Demographic Targeting', {
            'fields': (
                'age_min', 'age_max', 'genders', 'languages'
            ),
            'classes': ('collapse',)
        }),
        ('Behavioral Targeting', {
            'fields': (
                'interests', 'keywords', 'custom_audiences',
                'lookalike_audiences', 'exclude_audiences'
            ),
            'classes': ('collapse',)
        }),
        ('Advanced Targeting', {
            'fields': (
                'contextual_targeting', 'site_targeting', 'app_targeting',
                'content_categories', 'placement_targeting'
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                'id', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def age_range(self, obj):
        """Display age range."""
        if obj.age_min and obj.age_max:
            return f"{obj.age_min} - {obj.age_max}"
        elif obj.age_min:
            return f"{obj.age_min}+"
        else:
            return "All"


@admin.register(BillingProfile)
class BillingProfileAdmin(admin.ModelAdmin):
    """Admin configuration for BillingProfile model."""
    
    list_display = [
        'company_name', 'billing_email', 'billing_cycle',
        'credit_limit', 'credit_available', 'auto_charge',
        'is_verified', 'status', 'created_at'
    ]
    list_filter = [
        'status', 'is_verified', 'billing_cycle', 'payment_terms',
        'auto_charge', 'created_at'
    ]
    search_fields = [
        'company_name', 'trade_name', 'billing_email',
        'billing_contact', 'billing_phone'
    ]
    readonly_fields = [
        'id', 'credit_available', 'verification_date',
        'created_at', 'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'advertiser', 'company_name', 'trade_name',
                'billing_email', 'billing_phone', 'billing_contact',
                'billing_title'
            )
        }),
        ('Address Information', {
            'fields': (
                'billing_address_line1', 'billing_address_line2',
                'billing_city', 'billing_state', 'billing_country',
                'billing_postal_code'
            )
        }),
        ('Billing Settings', {
            'fields': (
                'billing_cycle', 'payment_terms', 'auto_charge',
                'auto_charge_threshold', 'credit_limit', 'spending_limit'
            )
        }),
        ('Tax Settings', {
            'fields': (
                'tax_exempt', 'tax_rate', 'tax_region', 'default_currency',
                'pricing_model'
            )
        }),
        ('Verification', {
            'fields': (
                'is_verified', 'verification_date'
            )
        }),
        ('Status', {
            'fields': (
                'status',
            )
        }),
        ('System Information', {
            'fields': (
                'id', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def credit_available(self, obj):
        """Display credit available with color coding."""
        available = obj.credit_available
        if available < 0:
            color = 'red'
        elif available < obj.credit_limit * 0.2:
            color = 'orange'
        else:
            color = 'green'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">${:.2f}</span>',
            color, available
        )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Admin configuration for Invoice model."""

    list_display = [
        'invoice_number', 'advertiser',
        'total_amount', 'currency', 'status', 'due_date', 'created_at'
    ]
    list_filter = [
        'status', 'currency', 'due_date', 'created_at'
    ]
    search_fields = [
        'invoice_number', 'advertiser__company_name'
    ]
    readonly_fields = [
        'id', 'invoice_number', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'advertiser', 'billing_profile', 'invoice_number',
                'invoice_date', 'due_date'
            )
        }),
        ('Amounts', {
            'fields': (
                'amount', 'tax_amount', 'total_amount', 'currency'
            )
        }),
        ('Content', {
            'fields': ('line_items', 'notes'),
            'classes': ('collapse',)
        }),
        ('Status', {'fields': ('status',)}),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def total_amount(self, obj):
        """Display total amount."""
        return f"{obj.currency} {obj.total_amount:.2f}"


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    """Admin configuration for PaymentTransaction model."""
    
    list_display = [
        'transaction_id', 'advertiser', 'payment_method',
        'transaction_type', 'amount', 'currency',
        'status', 'completed_at', 'created_at'
    ]
    list_filter = [
        'status', 'transaction_type', 'currency', 'payment_method',
        'created_at', 'completed_at'
    ]
    search_fields = [
        'transaction_id', 'gateway_transaction_id',
        'advertiser__company_name'
    ]
    readonly_fields = [
        'id', 'transaction_id', 'gateway_transaction_id',
        'completed_at', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'advertiser', 'billing_profile', 'payment_method',
                'transaction_id', 'gateway_transaction_id'
            )
        }),
        ('Transaction Details', {
            'fields': (
                'amount', 'transaction_type', 'currency', 'status'
            )
        }),
        ('Gateway Information', {
            'fields': (
                'gateway_response', 'error_message'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'completed_at', 'created_at', 'updated_at'
            )
        })
    )
    
    def amount(self, obj):
        """Display amount."""
        return f"{obj.currency} {obj.amount:.2f}"


# Register other models with basic admin configuration

class CampaignSpendAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(CampaignSpend, CampaignSpendAdmin)
except Exception:
    pass

class CampaignGroupAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(CampaignGroup, CampaignGroupAdmin)
except Exception:
    pass

class CreativeAssetAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(CreativeAsset, CreativeAssetAdmin)
except Exception:
    pass

class CreativeApprovalLogAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(CreativeApprovalLog, CreativeApprovalLogAdmin)
except Exception:
    pass

class ImpressionAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(Impression, ImpressionAdmin)
except Exception:
    pass

class ImpressionAggregationAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(ImpressionAggregation, ImpressionAggregationAdmin)
except Exception:
    pass

class ImpressionPixelAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(ImpressionPixel, ImpressionPixelAdmin)
except Exception:
    pass

class ClickAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(Click, ClickAdmin)
except Exception:
    pass

class ClickAggregationAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(ClickAggregation, ClickAggregationAdmin)
except Exception:
    pass

class ClickPixelAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(ClickPixel, ClickPixelAdmin)
except Exception:
    pass

class ConversionAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(Conversion, ConversionAdmin)
except Exception:
    pass

class ConversionAggregationAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(ConversionAggregation, ConversionAggregationAdmin)
except Exception:
    pass

class ConversionPathAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(ConversionPath, ConversionPathAdmin)
except Exception:
    pass

class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(PaymentMethod, PaymentMethodAdmin)
except Exception:
    pass

class AnalyticsReportAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(AnalyticsReport, AnalyticsReportAdmin)
except Exception:
    pass

class AnalyticsDashboardAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(AnalyticsDashboard, AnalyticsDashboardAdmin)
except Exception:
    pass

class AnalyticsAlertAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(AnalyticsAlert, AnalyticsAlertAdmin)
except Exception:
    pass

class AnalyticsMetricAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(AnalyticsMetric, AnalyticsMetricAdmin)
except Exception:
    pass

class AnalyticsDataPointAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(AnalyticsDataPoint, AnalyticsDataPointAdmin)
except Exception:
    pass

class AudienceSegmentAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(AudienceSegment, AudienceSegmentAdmin)
except Exception:
    pass

class TargetingRuleAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(TargetingRule, TargetingRuleAdmin)
except Exception:
    pass

class FraudDetectionRuleAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(FraudDetectionRule, FraudDetectionRuleAdmin)
except Exception:
    pass

class FraudDetectionAlertAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(FraudDetectionAlert, FraudDetectionAlertAdmin)
except Exception:
    pass

class FraudDetectionLogAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(FraudDetectionLog, FraudDetectionLogAdmin)
except Exception:
    pass

class FraudDetectionReportAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(FraudDetectionReport, FraudDetectionReportAdmin)
except Exception:
    pass

class ABTestAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(ABTest, ABTestAdmin)
except Exception:
    pass

class ABTestVariantAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(ABTestVariant, ABTestVariantAdmin)
except Exception:
    pass

class ABTestResultAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(ABTestResult, ABTestResultAdmin)
except Exception:
    pass

class ABTestInsightAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(ABTestInsight, ABTestInsightAdmin)
except Exception:
    pass

class IntegrationAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(Integration, IntegrationAdmin)
except Exception:
    pass

class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(IntegrationLog, IntegrationLogAdmin)
except Exception:
    pass

class IntegrationWebhookAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(IntegrationWebhook, IntegrationWebhookAdmin)
except Exception:
    pass

class IntegrationMappingAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(IntegrationMapping, IntegrationMappingAdmin)
except Exception:
    pass

class IntegrationCredentialAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(IntegrationCredential, IntegrationCredentialAdmin)
except Exception:
    pass

class ReportAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(Report, ReportAdmin)
except Exception:
    pass

class DashboardAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(Dashboard, DashboardAdmin)
except Exception:
    pass

class WidgetAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(Widget, WidgetAdmin)
except Exception:
    pass

class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(ReportTemplate, ReportTemplateAdmin)
except Exception:
    pass

class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(ReportSchedule, ReportScheduleAdmin)
except Exception:
    pass

class NotificationAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(Notification, NotificationAdmin)
except Exception:
    pass

class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(NotificationTemplate, NotificationTemplateAdmin)
except Exception:
    pass

class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(NotificationPreference, NotificationPreferenceAdmin)
except Exception:
    pass

class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(NotificationLog, NotificationLogAdmin)
except Exception:
    pass

class AdvertiserUserAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(AdvertiserUser, AdvertiserUserAdmin)
except Exception:
    pass

class UserSessionAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(UserSession, UserSessionAdmin)
except Exception:
    pass

class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(UserActivityLog, UserActivityLogAdmin)
except Exception:
    pass

class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(AuditLog, AuditLogAdmin)
except Exception:
    pass

class ComplianceReportAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(ComplianceReport, ComplianceReportAdmin)
except Exception:
    pass

class RetentionPolicyAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(RetentionPolicy, RetentionPolicyAdmin)
except Exception:
    pass

class ConfigurationAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(Configuration, ConfigurationAdmin)
except Exception:
    pass

class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(FeatureFlag, FeatureFlagAdmin)
except Exception:
    pass

class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(SystemSetting, SystemSettingAdmin)
except Exception:
    pass

class ThemeConfigurationAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

try:
    admin.site.register(ThemeConfiguration, ThemeConfigurationAdmin)
except Exception:
    pass



# Custom admin site configuration
admin.site.site_header = "Advertiser Portal Administration"
admin.site.site_title = "Advertiser Portal Admin"
admin.site.index_title = "Welcome to Advertiser Portal Admin"

# Customize admin site appearance
admin.site.site_header = "Advertiser Portal"
admin.site.site_title = "Advertiser Portal Admin"
admin.site.index_title = "Advertiser Portal Administration"
