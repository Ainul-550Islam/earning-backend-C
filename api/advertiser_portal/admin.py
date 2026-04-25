"""
Advertiser Portal Django Admin Configuration

This module contains the Django admin configuration for the Advertiser Portal,
including admin classes for all 42 models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum, Avg
from django.utils.safestring import mark_safe

# Import all 42 models from the MODELS directory
from api.advertiser_portal.models.advertiser import (
    Advertiser, AdvertiserProfile, AdvertiserVerification, AdvertiserAgreement
)
from api.advertiser_portal.models.campaign import (
    AdCampaign, CampaignCreative, CampaignTargeting, CampaignBid, CampaignSchedule
)
from api.advertiser_portal.models.offer import (
    AdvertiserOffer, OfferRequirement, OfferCreative, OfferBlacklist
)
from api.advertiser_portal.models.tracking import (
    TrackingPixel, S2SPostback, Conversion, ConversionEvent, TrackingDomain
)
from api.advertiser_portal.models.billing import (
    AdvertiserWallet, AdvertiserTransaction, AdvertiserDeposit, 
    AdvertiserInvoice, CampaignSpend, BillingAlert
)
from api.advertiser_portal.models.reporting import (
    AdvertiserReport, CampaignReport, PublisherBreakdown, 
    GeoBreakdown, CreativePerformance
)
from api.advertiser_portal.models.fraud_protection import (
    ConversionQualityScore, AdvertiserFraudConfig, InvalidClickLog, 
    ClickFraudSignal, OfferQualityScore, RoutingBlacklist
)
from api.advertiser_portal.models.notification import (
    AdvertiserNotification, AdvertiserAlert, NotificationTemplate
)
from api.advertiser_portal.models.ml import (
    UserJourneyStep, NetworkPerformanceCache, MLModel, MLPrediction
)


# Advertiser Admin Classes
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
                'company_name', 'trade_name', 'contact_name', 'contact_email',
                'contact_phone', 'website', 'description', 'logo'
            )
        }),
        ('Account Details', {
            'fields': (
                'account_type', 'industry', 'company_size', 'status',
                'is_verified', 'verification_date'
            )
        }),
        ('Business Information', {
            'fields': (
                'business_registration_number', 'tax_id', 'address',
                'city', 'country', 'postal_code'
            )
        }),
        ('Settings', {
            'fields': (
                'timezone', 'currency', 'language', 'api_access',
                'notification_preferences', 'billing_preferences'
            )
        }),
        ('System Information', {
            'fields': (
                'id', 'total_spend', 'total_campaigns', 'active_campaigns',
                'quality_score', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )


@admin.register(AdvertiserProfile)
class AdvertiserProfileAdmin(admin.ModelAdmin):
    """Admin configuration for AdvertiserProfile model."""
    
    list_display = ['advertiser', 'logo', 'website_url', 'company_size', 'industry', 'created_at']
    list_filter = ['industry', 'company_size', 'created_at']
    search_fields = ['advertiser__company_name', 'website_url']
    
    fieldsets = (
        ('Profile Information', {
            'fields': (
                'advertiser', 'logo', 'website_url', 'company_description',
                'company_size', 'industry', 'target_audience'
            )
        }),
        ('Contact Information', {
            'fields': (
                'primary_contact_name', 'primary_contact_email',
                'primary_contact_phone', 'secondary_contact_name',
                'secondary_contact_email', 'secondary_contact_phone'
            )
        }),
        ('Address Information', {
            'fields': (
                'address_line1', 'address_line2', 'city', 'state',
                'country', 'postal_code'
            )
        }),
        ('Business Details', {
            'fields': (
                'business_type', 'registration_number', 'tax_id',
                'established_year', 'employee_count', 'annual_revenue'
            )
        }),
        ('Marketing Information', {
            'fields': (
                'marketing_budget', 'primary_markets', 'product_categories',
                'competitors', 'unique_selling_proposition'
            )
        })
    )


@admin.register(AdvertiserVerification)
class AdvertiserVerificationAdmin(admin.ModelAdmin):
    """Admin configuration for AdvertiserVerification model."""
    
    list_display = ['advertiser', 'status', 'verified_by', 'verification_date', 'created_at']
    list_filter = ['status', 'verification_date', 'created_at']
    search_fields = ['advertiser__company_name', 'verified_by__username']
    
    fieldsets = (
        ('Verification Details', {
            'fields': (
                'advertiser', 'status', 'verified_by', 'verification_date',
                'verification_method', 'verification_notes'
            )
        }),
        ('Documents', {
            'fields': (
                'business_license', 'tax_document', 'identity_document',
                'address_proof', 'bank_statement', 'other_documents'
            )
        }),
        ('Verification Checks', {
            'fields': (
                'business_verified', 'identity_verified', 'address_verified',
                'bank_verified', 'compliance_checked'
            )
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(AdvertiserAgreement)
class AdvertiserAgreementAdmin(admin.ModelAdmin):
    """Admin configuration for AdvertiserAgreement model."""
    
    list_display = ['advertiser', 'agreement_type', 'status', 'signed_date', 'expiry_date']
    list_filter = ['agreement_type', 'status', 'signed_date', 'expiry_date']
    search_fields = ['advertiser__company_name']
    
    fieldsets = (
        ('Agreement Details', {
            'fields': (
                'advertiser', 'agreement_type', 'agreement_number',
                'status', 'signed_date', 'expiry_date'
            )
        }),
        ('Terms and Conditions', {
            'fields': (
                'terms_text', 'special_conditions', 'payment_terms',
                'cancellation_policy', 'renewal_terms'
            )
        }),
        ('Signatures', {
            'fields': (
                'advertiser_signature', 'advertiser_signatory',
                'company_signature', 'company_signatory'
            )
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


# Campaign Admin Classes
@admin.register(AdCampaign)
class AdCampaignAdmin(admin.ModelAdmin):
    """Admin configuration for AdCampaign model."""
    
    list_display = [
        'name', 'advertiser', 'status', 'objective', 'daily_budget',
        'total_budget', 'start_date', 'end_date', 'created_at'
    ]
    list_filter = [
        'status', 'objective', 'advertiser', 'created_at',
        'start_date', 'end_date'
    ]
    search_fields = ['name', 'advertiser__company_name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'advertiser', 'name', 'description', 'status', 'objective'
            )
        }),
        ('Budget and Schedule', {
            'fields': (
                'daily_budget', 'total_budget', 'start_date', 'end_date',
                'timezone', 'schedule_type'
            )
        }),
        ('Targeting', {
            'fields': (
                'target_audience', 'geographic_targeting', 'device_targeting',
                'age_targeting', 'gender_targeting', 'interest_targeting'
            )
        }),
        ('Creative and Content', {
            'fields': (
                'creative_assets', 'landing_pages', 'ad_copy',
                'call_to_action', 'display_url'
            )
        }),
        ('Bidding and Optimization', {
            'fields': (
                'bid_strategy', 'bid_amount', 'optimization_goal',
                'pacing_type', 'frequency_capping'
            )
        }),
        ('Tracking and Analytics', {
            'fields': (
                'conversion_tracking', 'tracking_pixels', 'attribution_model',
                'analytics_goals', 'custom_events'
            )
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(CampaignCreative)
class CampaignCreativeAdmin(admin.ModelAdmin):
    """Admin configuration for CampaignCreative model."""
    
    list_display = ['campaign', 'name', 'type', 'status', 'is_approved', 'created_at']
    list_filter = ['type', 'status', 'is_approved', 'created_at']
    search_fields = ['campaign__name', 'name', 'description']
    
    fieldsets = (
        ('Creative Details', {
            'fields': (
                'campaign', 'name', 'description', 'type', 'status',
                'is_approved', 'approval_date', 'approved_by'
            )
        }),
        ('Creative Assets', {
            'fields': (
                'image_asset', 'video_asset', 'html_asset', 'text_asset',
                'thumbnail', 'preview_url'
            )
        }),
        ('Specifications', {
            'fields': (
                'width', 'height', 'file_size', 'file_format',
                'aspect_ratio', 'duration'
            )
        }),
        ('Content', {
            'fields': (
                'headline', 'description', 'call_to_action',
                'display_url', 'landing_page_url'
            )
        }),
        ('Performance', {
            'fields': (
                'click_through_rate', 'conversion_rate', 'impression_count',
                'click_count', 'conversion_count'
            )
        })
    )


@admin.register(CampaignTargeting)
class CampaignTargetingAdmin(admin.ModelAdmin):
    """Admin configuration for CampaignTargeting model."""
    
    list_display = ['campaign', 'targeting_type', 'status', 'created_at']
    list_filter = ['targeting_type', 'status', 'created_at']
    search_fields = ['campaign__name']
    
    fieldsets = (
        ('Targeting Details', {
            'fields': (
                'campaign', 'targeting_type', 'status', 'priority'
            )
        }),
        ('Geographic Targeting', {
            'fields': (
                'countries', 'regions', 'cities', 'postal_codes',
                'coordinates', 'radius', 'geo_fencing'
            )
        }),
        ('Demographic Targeting', {
            'fields': (
                'age_min', 'age_max', 'genders', 'languages',
                'education_levels', 'income_levels'
            )
        }),
        ('Interest and Behavior Targeting', {
            'fields': (
                'interests', 'behaviors', 'custom_audiences',
                'lookalike_audiences', 'exclude_audiences'
            )
        }),
        ('Device and Platform Targeting', {
            'fields': (
                'device_types', 'operating_systems', 'browsers',
                'connection_types', 'carriers'
            )
        }),
        ('Content Targeting', {
            'fields': (
                'keywords', 'placements', 'categories', 'topics',
                'content_ratings', 'safe_search'
            )
        })
    )


@admin.register(CampaignBid)
class CampaignBidAdmin(admin.ModelAdmin):
    """Admin configuration for CampaignBid model."""
    
    list_display = ['campaign', 'bid_type', 'bid_amount', 'status', 'created_at']
    list_filter = ['bid_type', 'status', 'created_at']
    search_fields = ['campaign__name']
    
    fieldsets = (
        ('Bid Details', {
            'fields': (
                'campaign', 'bid_type', 'bid_amount', 'status',
                'effective_date', 'expiry_date'
            )
        }),
        ('Bid Strategy', {
            'fields': (
                'bid_strategy', 'optimization_goal', 'target_cpa',
                'target_roas', 'budget_allocation'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'actual_cpc', 'actual_cpm', 'actual_cpa',
                'actual_roas', 'win_rate', 'impression_share'
            )
        })
    )


@admin.register(CampaignSchedule)
class CampaignScheduleAdmin(admin.ModelAdmin):
    """Admin configuration for CampaignSchedule model."""
    
    list_display = ['campaign', 'start_time', 'end_time', 'days_of_week', 'status']
    list_filter = ['status', 'start_time', 'end_time']
    search_fields = ['campaign__name']
    
    fieldsets = (
        ('Schedule Details', {
            'fields': (
                'campaign', 'status', 'timezone', 'start_time', 'end_time'
            )
        }),
        ('Days and Hours', {
            'fields': (
                'days_of_week', 'start_hour', 'end_hour',
                'hourly_distribution', 'peak_hours'
            )
        }),
        ('Special Scheduling', {
            'fields': (
                'holiday_schedule', 'seasonal_adjustments',
                'event_based_scheduling', 'emergency_pause'
            )
        })
    )


# Offer Admin Classes
@admin.register(AdvertiserOffer)
class AdvertiserOfferAdmin(admin.ModelAdmin):
    """Admin configuration for AdvertiserOffer model."""
    
    list_display = [
        'name', 'advertiser', 'offer_type', 'status', 'payout_type',
        'payout_amount', 'created_at'
    ]
    list_filter = [
        'offer_type', 'status', 'payout_type', 'advertiser', 'created_at'
    ]
    search_fields = ['name', 'advertiser__company_name', 'description']
    
    fieldsets = (
        ('Offer Details', {
            'fields': (
                'advertiser', 'name', 'description', 'offer_type',
                'status', 'offer_url', 'preview_url'
            )
        }),
        ('Payout Information', {
            'fields': (
                'payout_type', 'payout_amount', 'currency',
                'payout_structure', 'tiered_payouts', 'bonuses'
            )
        }),
        ('Targeting and Restrictions', {
            'fields': (
                'target_countries', 'allowed_traffic_sources',
                'forbidden_traffic_sources', 'device_restrictions',
                'age_restrictions', 'content_restrictions'
            )
        }),
        ('Conversion Tracking', {
            'fields': (
                'conversion_pixel', 'postback_url', 'server_to_server',
                'cookie_duration', 'attribution_window'
            )
        }),
        ('Quality Control', {
            'fields': (
                'approval_required', 'auto_approve_threshold',
                'quality_score', 'fraud_detection_level'
            )
        })
    )


@admin.register(OfferRequirement)
class OfferRequirementAdmin(admin.ModelAdmin):
    """Admin configuration for OfferRequirement model."""
    
    list_display = ['offer', 'requirement_type', 'is_required', 'created_at']
    list_filter = ['requirement_type', 'is_required', 'created_at']
    search_fields = ['offer__name']
    
    fieldsets = (
        ('Requirement Details', {
            'fields': (
                'offer', 'requirement_type', 'description',
                'is_required', 'validation_rule'
            )
        }),
        ('Field Configuration', {
            'fields': (
                'field_name', 'field_type', 'field_options',
                'default_value', 'placeholder_text'
            )
        }),
        ('Validation', {
            'fields': (
                'min_length', 'max_length', 'pattern',
                'error_message', 'help_text'
            )
        })
    )


@admin.register(OfferCreative)
class OfferCreativeAdmin(admin.ModelAdmin):
    """Admin configuration for OfferCreative model."""
    
    list_display = ['offer', 'name', 'type', 'status', 'created_at']
    list_filter = ['type', 'status', 'created_at']
    search_fields = ['offer__name', 'name']
    
    fieldsets = (
        ('Creative Details', {
            'fields': (
                'offer', 'name', 'description', 'type', 'status',
                'is_default', 'approval_status'
            )
        }),
        ('Creative Assets', {
            'fields': (
                'image_file', 'video_file', 'html_code',
                'text_content', 'landing_page'
            )
        }),
        ('Specifications', {
            'fields': (
                'width', 'height', 'file_size', 'format',
                'duration', 'aspect_ratio'
            )
        }),
        ('Performance', {
            'fields': (
                'click_rate', 'conversion_rate', 'impression_count',
                'click_count', 'conversion_count'
            )
        })
    )


@admin.register(OfferBlacklist)
class OfferBlacklistAdmin(admin.ModelAdmin):
    """Admin configuration for OfferBlacklist model."""
    
    list_display = ['offer', 'blacklist_type', 'value', 'reason', 'created_at']
    list_filter = ['blacklist_type', 'created_at']
    search_fields = ['offer__name', 'value', 'reason']
    
    fieldsets = (
        ('Blacklist Details', {
            'fields': (
                'offer', 'blacklist_type', 'value', 'reason',
                'is_active', 'expiry_date'
            )
        }),
        ('Source Information', {
            'fields': (
                'source_type', 'source_reference', 'added_by',
                'reviewed_by', 'review_date'
            )
        })
    )


# Tracking Admin Classes
@admin.register(TrackingPixel)
class TrackingPixelAdmin(admin.ModelAdmin):
    """Admin configuration for TrackingPixel model."""
    
    list_display = [
        'name', 'advertiser', 'pixel_type', 'status', 'created_at'
    ]
    list_filter = ['pixel_type', 'status', 'advertiser', 'created_at']
    search_fields = ['name', 'advertiser__company_name']
    
    fieldsets = (
        ('Pixel Details', {
            'fields': (
                'advertiser', 'name', 'description', 'pixel_type',
                'status', 'pixel_url', 'pixel_id'
            )
        }),
        ('Configuration', {
            'fields': (
                'conversion_type', 'revenue_tracking', 'currency',
                'custom_parameters', 'callback_url'
            )
        }),
        ('Advanced Settings', {
            'fields': (
                'cookie_domain', 'cookie_duration', 'user_id_parameter',
                'session_id_parameter', 'debug_mode'
            )
        })
    )


@admin.register(S2SPostback)
class S2SPostbackAdmin(admin.ModelAdmin):
    """Admin configuration for S2SPostback model."""
    
    list_display = [
        'name', 'advertiser', 'postback_url', 'status', 'created_at'
    ]
    list_filter = ['status', 'advertiser', 'created_at']
    search_fields = ['name', 'advertiser__company_name', 'postback_url']
    
    fieldsets = (
        ('Postback Details', {
            'fields': (
                'advertiser', 'name', 'description', 'postback_url',
                'status', 'postback_method', 'timeout'
            )
        }),
        ('Parameters', {
            'fields': (
                'click_id_parameter', 'conversion_id_parameter',
                'payout_parameter', 'currency_parameter',
                'custom_parameters', 'security_token'
            )
        }),
        ('Settings', {
            'fields': (
                'retry_count', 'retry_delay', 'success_codes',
                'duplicate_handling', 'ip_whitelist'
            )
        })
    )


@admin.register(Conversion)
class ConversionAdmin(admin.ModelAdmin):
    """Admin configuration for Conversion model."""
    
    list_display = [
        'conversion_id', 'advertiser', 'offer', 'status', 'payout',
        'conversion_date', 'created_at'
    ]
    list_filter = [
        'status', 'advertiser', 'offer', 'conversion_date', 'created_at'
    ]
    search_fields = ['conversion_id', 'advertiser__company_name', 'offer__name']
    
    fieldsets = (
        ('Conversion Details', {
            'fields': (
                'conversion_id', 'advertiser', 'offer', 'status',
                'conversion_date', 'revenue', 'payout', 'currency'
            )
        }),
        ('Tracking Information', {
            'fields': (
                'click_id', 'session_id', 'user_id', 'ip_address',
                'user_agent', 'referrer_url'
            )
        }),
        ('Attribution', {
            'fields': (
                'attribution_model', 'attribution_window',
                'first_click_time', 'last_click_time',
                'touch_points', 'conversion_path'
            )
        }),
        ('Quality', {
            'fields': (
                'quality_score', 'fraud_score', 'validation_status',
                'review_status', 'review_notes'
            )
        })
    )


@admin.register(ConversionEvent)
class ConversionEventAdmin(admin.ModelAdmin):
    """Admin configuration for ConversionEvent model."""
    
    list_display = ['conversion', 'event_type', 'status', 'created_at']
    list_filter = ['event_type', 'status', 'created_at']
    search_fields = ['conversion__conversion_id']
    
    fieldsets = (
        ('Event Details', {
            'fields': (
                'conversion', 'event_type', 'status', 'event_date',
                'event_value', 'event_currency'
            )
        }),
        ('Event Data', {
            'fields': (
                'event_parameters', 'custom_data',
                'tracking_data', 'metadata'
            )
        })
    )


@admin.register(TrackingDomain)
class TrackingDomainAdmin(admin.ModelAdmin):
    """Admin configuration for TrackingDomain model."""
    
    list_display = ['domain', 'advertiser', 'status', 'created_at']
    list_filter = ['status', 'advertiser', 'created_at']
    search_fields = ['domain', 'advertiser__company_name']
    
    fieldsets = (
        ('Domain Details', {
            'fields': (
                'advertiser', 'domain', 'status', 'is_primary',
                'ssl_certificate', 'verification_status'
            )
        }),
        ('Configuration', {
            'fields': (
                'tracking_subdomain', 'custom_headers',
                'redirect_rules', 'fallback_url'
            )
        }),
        ('DNS Settings', {
            'fields': (
                'cname_record', 'txt_record', 'a_record',
                'verification_method', 'last_verified'
            )
        })
    )


# Billing Admin Classes
@admin.register(AdvertiserWallet)
class AdvertiserWalletAdmin(admin.ModelAdmin):
    """Admin configuration for AdvertiserWallet model."""
    
    list_display = [
        'advertiser', 'current_balance', 'total_deposited', 'total_spent',
        'currency', 'status', 'created_at'
    ]
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['advertiser__company_name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Wallet Details', {
            'fields': (
                'advertiser', 'currency', 'status', 'current_balance',
                'available_balance', 'pending_balance'
            )
        }),
        ('Financial Summary', {
            'fields': (
                'total_deposited', 'total_spent', 'total_refunded',
                'last_deposit_date', 'last_charge_date'
            )
        }),
        ('Limits and Alerts', {
            'fields': (
                'credit_limit', 'auto_refill_threshold',
                'low_balance_alert', 'spending_limit',
                'daily_spending_limit'
            )
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(AdvertiserTransaction)
class AdvertiserTransactionAdmin(admin.ModelAdmin):
    """Admin configuration for AdvertiserTransaction model."""
    
    list_display = [
        'transaction_id', 'advertiser', 'transaction_type', 'amount',
        'status', 'created_at'
    ]
    list_filter = [
        'transaction_type', 'status', 'advertiser', 'created_at'
    ]
    search_fields = ['transaction_id', 'advertiser__company_name']
    
    fieldsets = (
        ('Transaction Details', {
            'fields': (
                'advertiser', 'transaction_id', 'transaction_type',
                'amount', 'currency', 'status'
            )
        }),
        ('Payment Information', {
            'fields': (
                'payment_method', 'payment_reference',
                'gateway_transaction_id', 'gateway_response'
            )
        }),
        ('Timing', {
            'fields': (
                'processed_date', 'settled_date', 'failed_date',
                'retry_count', 'next_retry_date'
            )
        }),
        ('Notes', {
            'fields': ('description', 'internal_notes', 'error_message')
        })
    )


@admin.register(AdvertiserDeposit)
class AdvertiserDepositAdmin(admin.ModelAdmin):
    """Admin configuration for AdvertiserDeposit model."""
    
    list_display = [
        'deposit_id', 'advertiser', 'amount', 'payment_method',
        'status', 'created_at'
    ]
    list_filter = ['payment_method', 'status', 'advertiser', 'created_at']
    search_fields = ['deposit_id', 'advertiser__company_name']
    
    fieldsets = (
        ('Deposit Details', {
            'fields': (
                'advertiser', 'deposit_id', 'amount', 'currency',
                'payment_method', 'status'
            )
        }),
        ('Payment Information', {
            'fields': (
                'payment_reference', 'bank_reference',
                'transaction_id', 'confirmation_number'
            )
        }),
        ('Processing', {
            'fields': (
                'processed_date', 'confirmed_date', 'failed_date',
                'processor_response', 'verification_status'
            )
        })
    )


@admin.register(AdvertiserInvoice)
class AdvertiserInvoiceAdmin(admin.ModelAdmin):
    """Admin configuration for AdvertiserInvoice model."""
    
    list_display = [
        'invoice_number', 'advertiser', 'amount', 'status',
        'due_date', 'created_at'
    ]
    list_filter = ['status', 'advertiser', 'due_date', 'created_at']
    search_fields = ['invoice_number', 'advertiser__company_name']
    
    fieldsets = (
        ('Invoice Details', {
            'fields': (
                'advertiser', 'invoice_number', 'invoice_date',
                'due_date', 'amount', 'tax_amount', 'total_amount',
                'currency', 'status'
            )
        }),
        ('Billing Period', {
            'fields': (
                'billing_period_start', 'billing_period_end',
                'service_description', 'line_items'
            )
        }),
        ('Payment Information', {
            'fields': (
                'payment_terms', 'payment_method', 'auto_charge',
                'last_payment_date', 'next_payment_date'
            )
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(CampaignSpend)
class CampaignSpendAdmin(admin.ModelAdmin):
    """Admin configuration for CampaignSpend model."""
    
    list_display = [
        'campaign', 'spend_amount', 'spend_date', 'created_at'
    ]
    list_filter = ['campaign', 'spend_date', 'created_at']
    search_fields = ['campaign__name']
    
    fieldsets = (
        ('Spend Details', {
            'fields': (
                'campaign', 'spend_amount', 'currency', 'spend_date',
                'spend_type', 'billing_period'
            )
        }),
        ('Breakdown', {
            'fields': (
                'impression_spend', 'click_spend', 'conversion_spend',
                'tax_amount', 'fees', 'adjustments'
            )
        })
    )


@admin.register(BillingAlert)
class BillingAlertAdmin(admin.ModelAdmin):
    """Admin configuration for BillingAlert model."""
    
    list_display = [
        'advertiser', 'alert_type', 'threshold', 'is_active', 'created_at'
    ]
    list_filter = ['alert_type', 'is_active', 'advertiser', 'created_at']
    search_fields = ['advertiser__company_name']
    
    fieldsets = (
        ('Alert Details', {
            'fields': (
                'advertiser', 'alert_type', 'threshold', 'currency',
                'is_active', 'notification_method'
            )
        }),
        ('Conditions', {
            'fields': (
                'trigger_condition', 'reset_condition',
                'cooldown_period', 'max_notifications_per_day'
            )
        }),
        ('Recipients', {
            'fields': (
                'email_recipients', 'sms_recipients',
                'webhook_urls', 'notification_template'
            )
        })
    )


# Reporting Admin Classes
@admin.register(AdvertiserReport)
class AdvertiserReportAdmin(admin.ModelAdmin):
    """Admin configuration for AdvertiserReport model."""
    
    list_display = [
        'advertiser', 'report_type', 'report_date', 'status', 'created_at'
    ]
    list_filter = ['report_type', 'status', 'advertiser', 'created_at']
    search_fields = ['advertiser__company_name']
    
    fieldsets = (
        ('Report Details', {
            'fields': (
                'advertiser', 'report_type', 'report_date',
                'status', 'format', 'delivery_method'
            )
        }),
        ('Parameters', {
            'fields': (
                'date_range_start', 'date_range_end',
                'metrics', 'dimensions', 'filters'
            )
        }),
        ('Delivery', {
            'fields': (
                'email_recipients', 'download_url',
                'file_path', 'file_size', 'generated_at'
            )
        })
    )


@admin.register(CampaignReport)
class CampaignReportAdmin(admin.ModelAdmin):
    """Admin configuration for CampaignReport model."""
    
    list_display = [
        'campaign', 'report_type', 'report_date', 'status', 'created_at'
    ]
    list_filter = ['report_type', 'status', 'campaign', 'created_at']
    search_fields = ['campaign__name']
    
    fieldsets = (
        ('Report Details', {
            'fields': (
                'campaign', 'report_type', 'report_date',
                'status', 'format', 'delivery_method'
            )
        }),
        ('Parameters', {
            'fields': (
                'date_range_start', 'date_range_end',
                'metrics', 'dimensions', 'filters'
            )
        }),
        ('Delivery', {
            'fields': (
                'email_recipients', 'download_url',
                'file_path', 'file_size', 'generated_at'
            )
        })
    )


@admin.register(PublisherBreakdown)
class PublisherBreakdownAdmin(admin.ModelAdmin):
    """Admin configuration for PublisherBreakdown model."""
    
    list_display = [
        'advertiser', 'publisher', 'date', 'impressions', 'clicks',
        'conversions', 'revenue', 'created_at'
    ]
    list_filter = ['advertiser', 'publisher', 'date', 'created_at']
    search_fields = ['advertiser__company_name', 'publisher']
    
    fieldsets = (
        ('Breakdown Details', {
            'fields': (
                'advertiser', 'publisher', 'date', 'currency'
            )
        }),
        ('Metrics', {
            'fields': (
                'impressions', 'clicks', 'conversions',
                'revenue', 'cost', 'profit', 'ctr', 'conversion_rate'
            )
        })
    )


@admin.register(GeoBreakdown)
class GeoBreakdownAdmin(admin.ModelAdmin):
    """Admin configuration for GeoBreakdown model."""
    
    list_display = [
        'advertiser', 'country', 'region', 'date', 'impressions',
        'clicks', 'conversions', 'created_at'
    ]
    list_filter = ['advertiser', 'country', 'region', 'date', 'created_at']
    search_fields = ['advertiser__company_name', 'country', 'region']
    
    fieldsets = (
        ('Geographic Details', {
            'fields': (
                'advertiser', 'country', 'region', 'city', 'date'
            )
        }),
        ('Metrics', {
            'fields': (
                'impressions', 'clicks', 'conversions',
                'revenue', 'cost', 'ctr', 'conversion_rate'
            )
        })
    )


@admin.register(CreativePerformance)
class CreativePerformanceAdmin(admin.ModelAdmin):
    """Admin configuration for CreativePerformance model."""
    
    list_display = [
        'creative', 'date', 'impressions', 'clicks', 'conversions',
        'ctr', 'created_at'
    ]
    list_filter = ['creative', 'date', 'created_at']
    search_fields = ['creative__name']
    
    fieldsets = (
        ('Performance Details', {
            'fields': (
                'creative', 'date', 'campaign', 'placement'
            )
        }),
        ('Metrics', {
            'fields': (
                'impressions', 'clicks', 'conversions',
                'revenue', 'cost', 'ctr', 'conversion_rate',
                'cpm', 'cpc', 'cpa'
            )
        })
    )


# Fraud Protection Admin Classes
@admin.register(ConversionQualityScore)
class ConversionQualityScoreAdmin(admin.ModelAdmin):
    """Admin configuration for ConversionQualityScore model."""
    
    list_display = [
        'conversion', 'quality_score', 'risk_score', 'status', 'created_at'
    ]
    list_filter = ['status', 'quality_score', 'risk_score', 'created_at']
    search_fields = ['conversion__conversion_id']
    
    fieldsets = (
        ('Quality Assessment', {
            'fields': (
                'conversion', 'quality_score', 'risk_score',
                'status', 'confidence_level'
            )
        }),
        ('Factors', {
            'fields': (
                'ip_quality', 'device_quality', 'behavior_quality',
                'attribution_quality', 'timing_quality'
            )
        }),
        ('Analysis', {
            'fields': (
                'analysis_details', 'risk_factors',
                'quality_indicators', 'recommendations'
            )
        })
    )


@admin.register(AdvertiserFraudConfig)
class AdvertiserFraudConfigAdmin(admin.ModelAdmin):
    """Admin configuration for AdvertiserFraudConfig model."""
    
    list_display = [
        'advertiser', 'fraud_detection_level', 'is_active', 'created_at'
    ]
    list_filter = ['fraud_detection_level', 'is_active', 'advertiser', 'created_at']
    search_fields = ['advertiser__company_name']
    
    fieldsets = (
        ('Configuration Details', {
            'fields': (
                'advertiser', 'fraud_detection_level', 'is_active',
                'auto_block_suspicious', 'manual_review_threshold'
            )
        }),
        ('Detection Rules', {
            'fields': (
                'ip_rules', 'device_rules', 'behavior_rules',
                'attribution_rules', 'timing_rules'
            )
        }),
        ('Alerts', {
            'fields': (
                'alert_threshold', 'notification_methods',
                'escalation_rules', 'review_team'
            )
        })
    )


@admin.register(InvalidClickLog)
class InvalidClickLogAdmin(admin.ModelAdmin):
    """Admin configuration for InvalidClickLog model."""
    
    list_display = [
        'advertiser', 'click_id', 'reason', 'ip_address', 'created_at'
    ]
    list_filter = ['reason', 'advertiser', 'created_at']
    search_fields = ['click_id', 'ip_address', 'advertiser__company_name']
    
    fieldsets = (
        ('Invalid Click Details', {
            'fields': (
                'advertiser', 'click_id', 'reason', 'severity',
                'ip_address', 'user_agent', 'created_at'
            )
        }),
        ('Detection Information', {
            'fields': (
                'detection_method', 'confidence_score',
                'rule_triggered', 'detection_timestamp'
            )
        }),
        ('Context', {
            'fields': (
                'campaign', 'creative', 'publisher',
                'referrer_url', 'conversion_id'
            )
        })
    )


@admin.register(ClickFraudSignal)
class ClickFraudSignalAdmin(admin.ModelAdmin):
    """Admin configuration for ClickFraudSignal model."""
    
    list_display = [
        'advertiser', 'signal_type', 'confidence_score', 'status', 'created_at'
    ]
    list_filter = ['signal_type', 'status', 'advertiser', 'created_at']
    search_fields = ['advertiser__company_name']
    
    fieldsets = (
        ('Signal Details', {
            'fields': (
                'advertiser', 'signal_type', 'confidence_score',
                'status', 'severity', 'created_at'
            )
        }),
        ('Signal Data', {
            'fields': (
                'signal_source', 'signal_parameters',
                'related_clicks', 'pattern_detected'
            )
        }),
        ('Action Taken', {
            'fields': (
                'action_taken', 'action_timestamp',
                'review_status', 'review_notes'
            )
        })
    )


@admin.register(OfferQualityScore)
class OfferQualityScoreAdmin(admin.ModelAdmin):
    """Admin configuration for OfferQualityScore model."""
    
    list_display = [
        'offer', 'quality_score', 'performance_score', 'created_at'
    ]
    list_filter = ['offer', 'created_at']
    search_fields = ['offer__name']
    
    fieldsets = (
        ('Quality Assessment', {
            'fields': (
                'offer', 'quality_score', 'performance_score',
                'conversion_quality', 'traffic_quality'
            )
        }),
        ('Metrics', {
            'fields': (
                'ctr', 'conversion_rate', 'epc', 'rpc',
                'retention_rate', 'refund_rate'
            )
        }),
        ('Analysis', {
            'fields': (
                'quality_factors', 'performance_factors',
                'recommendations', 'last_updated'
            )
        })
    )


@admin.register(RoutingBlacklist)
class RoutingBlacklistAdmin(admin.ModelAdmin):
    """Admin configuration for RoutingBlacklist model."""
    
    list_display = [
        'advertiser', 'blacklist_type', 'value', 'reason', 'created_at'
    ]
    list_filter = ['blacklist_type', 'advertiser', 'created_at']
    search_fields = ['advertiser__company_name', 'value', 'reason']
    
    fieldsets = (
        ('Blacklist Details', {
            'fields': (
                'advertiser', 'blacklist_type', 'value', 'reason',
                'is_active', 'expiry_date'
            )
        }),
        ('Source Information', {
            'fields': (
                'source_type', 'source_reference', 'added_by',
                'reviewed_by', 'review_date'
            )
        }),
        ('Impact', {
            'fields': (
                'affected_offers', 'traffic_impact',
                'revenue_impact', 'performance_impact'
            )
        })
    )


# Notification Admin Classes
@admin.register(AdvertiserNotification)
class AdvertiserNotificationAdmin(admin.ModelAdmin):
    """Admin configuration for AdvertiserNotification model."""
    
    list_display = [
        'advertiser', 'notification_type', 'title', 'status', 'created_at'
    ]
    list_filter = [
        'notification_type', 'status', 'advertiser', 'created_at'
    ]
    search_fields = ['advertiser__company_name', 'title', 'message']
    
    fieldsets = (
        ('Notification Details', {
            'fields': (
                'advertiser', 'notification_type', 'title', 'message',
                'status', 'priority', 'created_at'
            )
        }),
        ('Content', {
            'fields': (
                'html_content', 'text_content', 'attachments',
                'action_url', 'action_text'
            )
        }),
        ('Delivery', {
            'fields': (
                'delivery_method', 'delivery_status',
                'sent_at', 'read_at', 'clicked_at'
            )
        }),
        ('Settings', {
            'fields': (
                'is_read', 'is_archived', 'expires_at',
                'reminder_sent', 'escalation_sent'
            )
        })
    )


@admin.register(AdvertiserAlert)
class AdvertiserAlertAdmin(admin.ModelAdmin):
    """Admin configuration for AdvertiserAlert model."""
    
    list_display = [
        'advertiser', 'alert_type', 'severity', 'is_active', 'created_at'
    ]
    list_filter = ['alert_type', 'severity', 'is_active', 'advertiser', 'created_at']
    search_fields = ['advertiser__company_name']
    
    fieldsets = (
        ('Alert Details', {
            'fields': (
                'advertiser', 'alert_type', 'severity', 'title',
                'message', 'is_active', 'created_at'
            )
        }),
        ('Trigger Conditions', {
            'fields': (
                'trigger_condition', 'trigger_value',
                'threshold_type', 'threshold_value'
            )
        }),
        ('Notification Settings', {
            'fields': (
                'notification_methods', 'email_recipients',
                'sms_recipients', 'webhook_urls'
            )
        }),
        ('Escalation', {
            'fields': (
                'escalation_enabled', 'escalation_threshold',
                'escalation_recipients', 'escalation_sent'
            )
        })
    )


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    """Admin configuration for NotificationTemplate model."""
    
    list_display = [
        'template_name', 'notification_type', 'language', 'is_active', 'created_at'
    ]
    list_filter = ['notification_type', 'language', 'is_active', 'created_at']
    search_fields = ['template_name', 'subject']
    
    fieldsets = (
        ('Template Details', {
            'fields': (
                'template_name', 'notification_type', 'language',
                'is_active', 'description'
            )
        }),
        ('Content', {
            'fields': (
                'subject', 'html_template', 'text_template',
                'variables', 'default_values'
            )
        }),
        ('Settings', {
            'fields': (
                'priority', 'delivery_method', 'expires_after',
                'can_unsubscribe', 'tracking_enabled'
            )
        }),
        ('Preview', {
            'fields': (
                'preview_data', 'test_recipients',
                'last_tested', 'test_results'
            )
        })
    )


# ML Admin Classes
@admin.register(UserJourneyStep)
class UserJourneyStepAdmin(admin.ModelAdmin):
    """Admin configuration for UserJourneyStep model."""
    
    list_display = [
        'advertiser', 'user_id', 'step_type', 'step_value', 'created_at'
    ]
    list_filter = ['step_type', 'advertiser', 'created_at']
    search_fields = ['advertiser__company_name', 'user_id']
    
    fieldsets = (
        ('Journey Step Details', {
            'fields': (
                'advertiser', 'user_id', 'step_type', 'step_value',
                'session_id', 'created_at'
            )
        }),
        ('Context', {
            'fields': (
                'campaign', 'creative', 'offer', 'landing_page',
                'referrer_url', 'ip_address'
            )
        }),
        ('Data', {
            'fields': (
                'step_data', 'metadata', 'attribution_data',
                'conversion_data'
            )
        })
    )


@admin.register(NetworkPerformanceCache)
class NetworkPerformanceCacheAdmin(admin.ModelAdmin):
    """Admin configuration for NetworkPerformanceCache model."""
    
    list_display = [
        'cache_key', 'network', 'performance_score', 'expires_at', 'created_at'
    ]
    list_filter = ['network', 'created_at', 'expires_at']
    search_fields = ['cache_key', 'network']
    
    fieldsets = (
        ('Cache Details', {
            'fields': (
                'cache_key', 'network', 'performance_score',
                'created_at', 'expires_at', 'last_accessed'
            )
        }),
        ('Cache Data', {
            'fields': (
                'cached_data', 'data_size', 'compression_ratio',
                'hit_count', 'miss_count'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'response_time', 'throughput', 'error_rate',
                'success_rate', 'latency'
            )
        })
    )


@admin.register(MLModel)
class MLModelAdmin(admin.ModelAdmin):
    """Admin configuration for MLModel model."""
    
    list_display = [
        'model_name', 'model_type', 'version', 'is_active', 'created_at'
    ]
    list_filter = ['model_type', 'is_active', 'created_at']
    search_fields = ['model_name', 'description']
    
    fieldsets = (
        ('Model Details', {
            'fields': (
                'model_name', 'model_type', 'version', 'description',
                'is_active', 'created_at', 'updated_at'
            )
        }),
        ('Model Configuration', {
            'fields': (
                'algorithm', 'parameters', 'hyperparameters',
                'feature_columns', 'target_column'
            )
        }),
        ('Training Information', {
            'fields': (
                'training_data_path', 'training_date',
                'training_duration', 'accuracy_score',
                'precision_score', 'recall_score', 'f1_score'
            )
        }),
        ('Deployment', {
            'fields': (
                'deployment_url', 'api_endpoint', 'model_path',
                'deployment_date', 'last_prediction_date'
            )
        }),
        ('Performance', {
            'fields': (
                'prediction_count', 'average_prediction_time',
                'error_rate', 'last_maintenance_date'
            )
        })
    )


@admin.register(MLPrediction)
class MLPredictionAdmin(admin.ModelAdmin):
    """Admin configuration for MLPrediction model."""
    
    list_display = [
        'model', 'prediction_type', 'confidence_score', 'created_at'
    ]
    list_filter = ['prediction_type', 'model', 'created_at']
    search_fields = ['model__model_name']
    
    fieldsets = (
        ('Prediction Details', {
            'fields': (
                'model', 'prediction_type', 'prediction_value',
                'confidence_score', 'created_at'
            )
        }),
        ('Input Data', {
            'fields': (
                'input_features', 'input_data',
                'preprocessing_applied', 'feature_importance'
            )
        }),
        ('Output Analysis', {
            'fields': (
                'prediction_explanation', 'risk_factors',
                'confidence_intervals', 'alternative_predictions'
            )
        }),
        ('Performance', {
            'fields': (
                'prediction_time', 'model_version',
                'accuracy_if_available', 'actual_outcome'
            )
        })
    )
