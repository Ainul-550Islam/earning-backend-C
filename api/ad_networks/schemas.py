"""
api/ad_networks/schemas.py
Schema definitions for ad networks module
SaaS-ready with tenant support
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from django.utils import timezone
from django.conf import settings
from pydantic import BaseModel, Field, validator, HttpUrl
from pydantic.types import constr, conlist

logger = logging.getLogger(__name__)


# Base schemas
class BaseSchema(BaseModel):
    """Base schema for all ad network schemas"""
    
    tenant_id: Optional[str] = Field(None, description="Tenant ID for multi-tenancy")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    class Config:
        orm_mode = True
        allow_population_by_field_name = True


class PaginationSchema(BaseModel):
    """Pagination schema"""
    
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    total_count: Optional[int] = Field(None, description="Total number of items")
    total_pages: Optional[int] = Field(None, description="Total number of pages")
    has_next: Optional[bool] = Field(None, description="Has next page")
    has_previous: Optional[bool] = Field(None, description="Has previous page")


class ResponseSchema(BaseModel):
    """Standard API response schema"""
    
    success: bool = Field(True, description="Request success status")
    message: Optional[str] = Field(None, description="Response message")
    data: Optional[Any] = Field(None, description="Response data")
    errors: Optional[List[str]] = Field(None, description="Error messages")
    meta: Optional[Dict[str, Any]] = Field(None, description="Metadata")


# Network schemas
class NetworkTypeSchema(BaseModel):
    """Network type schema"""
    
    id: str = Field(..., description="Network type ID")
    name: str = Field(..., description="Network type name")
    category: str = Field(..., description="Network category")
    description: Optional[str] = Field(None, description="Network description")
    icon: Optional[str] = Field(None, description="Network icon URL")
    is_active: bool = Field(True, description="Network active status")


class NetworkCategorySchema(BaseModel):
    """Network category schema"""
    
    id: str = Field(..., description="Category ID")
    name: str = Field(..., description="Category name")
    description: Optional[str] = Field(None, description="Category description")
    icon: Optional[str] = Field(None, description="Category icon URL")
    priority: int = Field(50, description="Category priority")


class AdNetworkSchema(BaseSchema):
    """Ad network schema"""
    
    id: int = Field(..., description="Network ID")
    name: constr(min_length=1, max_length=100) = Field(..., description="Network name")
    network_type: str = Field(..., description="Network type")
    category: str = Field(..., description="Network category")
    description: Optional[str] = Field(None, max_length=500, description="Network description")
    website: Optional[HttpUrl] = Field(None, description="Network website URL")
    base_url: Optional[HttpUrl] = Field(None, description="Base API URL")
    api_key: Optional[constr(min_length=10)] = Field(None, description="API key")
    postback_key: Optional[constr(min_length=10)] = Field(None, description="Postback key")
    
    # Capabilities
    supports_postback: bool = Field(False, description="Supports postback")
    supports_webhook: bool = Field(False, description="Supports webhooks")
    supports_offers: bool = Field(True, description="Supports offers")
    supports_surveys: bool = Field(False, description="Supports surveys")
    supports_video: bool = Field(False, description="Supports video offers")
    supports_gaming: bool = Field(False, description="Supports gaming offers")
    supports_app_install: bool = Field(False, description="Supports app install offers")
    
    # Geographic support
    country_support: str = Field("global", description="Country support level")
    min_payout: Decimal = Field(Decimal('0.01'), ge=Decimal('0.01'), description="Minimum payout")
    max_payout: Optional[Decimal] = Field(None, description="Maximum payout")
    
    # Financial
    commission_rate: Optional[float] = Field(None, ge=0, le=100, description="Commission rate")
    payment_methods: Optional[List[str]] = Field(None, description="Supported payment methods")
    
    # Quality metrics
    rating: Optional[float] = Field(None, ge=0, le=5, description="Network rating")
    trust_score: Optional[float] = Field(None, ge=0, le=100, description="Trust score")
    priority: int = Field(50, description="Network priority")
    
    # Status
    is_active: bool = Field(True, description="Network active status")
    is_verified: bool = Field(False, description="Network verified status")
    is_testing: bool = Field(False, description="Network testing status")
    status: str = Field("active", description="Network status")
    
    # Metadata
    last_sync: Optional[datetime] = Field(None, description="Last sync timestamp")
    last_health_check: Optional[datetime] = Field(None, description="Last health check timestamp")
    
    # Computed fields
    total_offers: Optional[int] = Field(None, description="Total offers count")
    active_offers: Optional[int] = Field(None, description="Active offers count")
    total_conversions: Optional[int] = Field(None, description="Total conversions count")
    total_payout: Optional[Decimal] = Field(None, description="Total payout amount")
    conversion_rate: Optional[float] = Field(None, description="Conversion rate percentage")
    epc: Optional[float] = Field(None, description="Earnings per click")
    uptime_percentage: Optional[float] = Field(None, description="Uptime percentage")
    
    @validator('network_type')
    def validate_network_type(cls, v):
        valid_types = [
            'adscend', 'offertoro', 'adgem', 'ayetstudios', 'pollfish',
            'cpxresearch', 'bitlabs', 'inbrain', 'theoremreach',
            'yoursurveys', 'toluna', 'swagbucks', 'prizerebel'
        ]
        if v not in valid_types:
            raise ValueError(f'Invalid network type: {v}')
        return v
    
    @validator('category')
    def validate_category(cls, v):
        valid_categories = [
            'survey', 'offerwall', 'video', 'gaming', 'app_install',
            'trial', 'purchase', 'lead_generation', 'content_locking'
        ]
        if v not in valid_categories:
            raise ValueError(f'Invalid category: {v}')
        return v


# Offer schemas
class OfferCategorySchema(BaseSchema):
    """Offer category schema"""
    
    id: int = Field(..., description="Category ID")
    name: constr(min_length=1, max_length=50) = Field(..., description="Category name")
    slug: constr(min_length=1, max_length=50) = Field(..., description="Category slug")
    description: Optional[str] = Field(None, max_length=500, description="Category description")
    icon: Optional[str] = Field(None, description="Category icon URL")
    is_active: bool = Field(True, description="Category active status")
    priority: int = Field(50, description="Category priority")
    
    # Computed fields
    offers_count: Optional[int] = Field(None, description="Number of offers in category")


class OfferSchema(BaseSchema):
    """Offer schema"""
    
    id: int = Field(..., description="Offer ID")
    ad_network: AdNetworkSchema = Field(..., description="Ad network")
    category: Optional[OfferCategorySchema] = Field(None, description="Offer category")
    external_id: constr(min_length=1, max_length=100) = Field(..., description="External offer ID")
    title: constr(min_length=1, max_length=200) = Field(..., description="Offer title")
    description: Optional[str] = Field(None, max_length=2000, description="Offer description")
    short_description: Optional[str] = Field(None, max_length=500, description="Short description")
    
    # Reward
    reward_amount: Decimal = Field(..., ge=Decimal('0.01'), description="Reward amount")
    reward_currency: str = Field("USD", description="Reward currency")
    network_payout: Optional[Decimal] = Field(None, ge=Decimal('0.01'), description="Network payout")
    
    # Status
    status: str = Field("active", description="Offer status")
    
    # Targeting
    countries: Optional[List[str]] = Field(None, description="Target countries")
    platforms: Optional[List[str]] = Field(None, description="Target platforms")
    device_type: str = Field("any", description="Device type")
    difficulty: str = Field("easy", description="Difficulty level")
    estimated_time: Optional[int] = Field(None, ge=1, le=1440, description="Estimated time in minutes")
    
    # Content
    requirements: Optional[str] = Field(None, max_length=2000, description="Offer requirements")
    instructions: Optional[str] = Field(None, max_length=2000, description="Offer instructions")
    preview_url: Optional[HttpUrl] = Field(None, description="Preview URL")
    tracking_url: Optional[HttpUrl] = Field(None, description="Tracking URL")
    
    # Flags
    is_featured: bool = Field(False, description="Featured offer")
    is_hot: bool = Field(False, description="Hot offer")
    is_new: bool = Field(False, description="New offer")
    priority: int = Field(50, description="Offer priority")
    
    # Timing
    expires_at: Optional[datetime] = Field(None, description="Expiration date")
    
    # Computed fields
    total_clicks: Optional[int] = Field(None, description="Total clicks count")
    total_conversions: Optional[int] = Field(None, description="Total conversions count")
    conversion_rate: Optional[float] = Field(None, description="Conversion rate percentage")
    total_payout: Optional[Decimal] = Field(None, description="Total payout amount")
    is_expired: Optional[bool] = Field(None, description="Is offer expired")
    days_until_expiry: Optional[int] = Field(None, description="Days until expiry")
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ['active', 'inactive', 'expired', 'pending_review', 'rejected']
        if v not in valid_statuses:
            raise ValueError(f'Invalid status: {v}')
        return v
    
    @validator('device_type')
    def validate_device_type(cls, v):
        valid_types = ['mobile', 'desktop', 'tablet', 'any']
        if v not in valid_types:
            raise ValueError(f'Invalid device type: {v}')
        return v
    
    @validator('difficulty')
    def validate_difficulty(cls, v):
        valid_levels = ['easy', 'medium', 'hard', 'expert']
        if v not in valid_levels:
            raise ValueError(f'Invalid difficulty: {v}')
        return v


# User engagement schemas
class EngagementSchema(BaseSchema):
    """User engagement schema"""
    
    id: int = Field(..., description="Engagement ID")
    user_id: int = Field(..., description="User ID")
    offer: OfferSchema = Field(..., description="Offer")
    status: str = Field("started", description="Engagement status")
    
    # Tracking
    ip_address: Optional[str] = Field(None, description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent")
    country: Optional[str] = Field(None, description="Country")
    device_info: Optional[Dict[str, Any]] = Field(None, description="Device information")
    
    # Timing
    started_at: Optional[datetime] = Field(None, description="Start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
    last_viewed_at: Optional[datetime] = Field(None, description="Last viewed time")
    view_count: int = Field(1, description="View count")
    
    # Data
    conversion_data: Optional[Dict[str, Any]] = Field(None, description="Conversion data")
    fraud_score: Optional[float] = Field(None, ge=0, le=100, description="Fraud score")
    
    # Computed fields
    duration_minutes: Optional[int] = Field(None, description="Duration in minutes")
    has_conversion: Optional[bool] = Field(None, description="Has conversion")
    conversion_amount: Optional[float] = Field(None, description="Conversion amount")
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ['started', 'viewed', 'completed', 'approved', 'rejected']
        if v not in valid_statuses:
            raise ValueError(f'Invalid status: {v}')
        return v


class ConversionSchema(BaseSchema):
    """Conversion schema"""
    
    id: int = Field(..., description="Conversion ID")
    engagement: EngagementSchema = Field(..., description="User engagement")
    payout: Decimal = Field(..., ge=Decimal('0.01'), description="Payout amount")
    conversion_status: str = Field("pending", description="Conversion status")
    
    # Fraud detection
    fraud_score: Optional[float] = Field(None, ge=0, le=100, description="Fraud score")
    
    # Timing
    approved_at: Optional[datetime] = Field(None, description="Approval time")
    rejected_at: Optional[datetime] = Field(None, description="Rejection time")
    chargeback_at: Optional[datetime] = Field(None, description="Chargeback time")
    
    # Verification
    verification_notes: Optional[str] = Field(None, description="Verification notes")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason")
    conversion_data: Optional[Dict[str, Any]] = Field(None, description="Conversion data")
    
    # Computed fields
    risk_level: Optional[str] = Field(None, description="Risk level")
    is_fraudulent: Optional[bool] = Field(None, description="Is fraudulent")
    processing_time_hours: Optional[float] = Field(None, description="Processing time in hours")
    
    @validator('conversion_status')
    def validate_conversion_status(cls, v):
        valid_statuses = ['pending', 'approved', 'rejected', 'chargeback']
        if v not in valid_statuses:
            raise ValueError(f'Invalid conversion status: {v}')
        return v


class RewardSchema(BaseSchema):
    """Reward schema"""
    
    id: int = Field(..., description="Reward ID")
    user_id: int = Field(..., description="User ID")
    offer: OfferSchema = Field(..., description="Offer")
    engagement: Optional[EngagementSchema] = Field(None, description="User engagement")
    amount: Decimal = Field(..., ge=Decimal('0.01'), description="Reward amount")
    currency: str = Field("USD", description="Currency")
    status: str = Field("pending", description="Reward status")
    
    # Payment
    approved_at: Optional[datetime] = Field(None, description="Approval time")
    paid_at: Optional[datetime] = Field(None, description="Payment time")
    payment_reference: Optional[str] = Field(None, description="Payment reference")
    payment_method: Optional[str] = Field(None, description="Payment method")
    transaction_id: Optional[str] = Field(None, description="Transaction ID")
    
    # Cancellation
    reason: Optional[str] = Field(None, description="Reward reason")
    cancellation_reason: Optional[str] = Field(None, description="Cancellation reason")
    
    # Computed fields
    is_paid: Optional[bool] = Field(None, description="Is paid")
    is_cancelled: Optional[bool] = Field(None, description="Is cancelled")
    days_since_created: Optional[int] = Field(None, description="Days since created")
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ['pending', 'approved', 'paid', 'cancelled']
        if v not in valid_statuses:
            raise ValueError(f'Invalid status: {v}')
        return v


class WalletSchema(BaseSchema):
    """User wallet schema"""
    
    id: int = Field(..., description="Wallet ID")
    user_id: int = Field(..., description="User ID")
    balance: Decimal = Field(..., ge=Decimal('0'), description="Current balance")
    total_earned: Decimal = Field(..., ge=Decimal('0'), description="Total earned")
    total_spent: Decimal = Field(..., ge=Decimal('0'), description="Total spent")
    currency: str = Field("USD", description="Currency")
    
    # Activity
    last_activity: Optional[datetime] = Field(None, description="Last activity time")
    
    # Computed fields
    available_balance: Optional[float] = Field(None, description="Available balance")
    pending_rewards: Optional[float] = Field(None, description="Pending rewards amount")


# Click tracking schemas
class ClickSchema(BaseSchema):
    """Click tracking schema"""
    
    id: int = Field(..., description="Click ID")
    user_id: Optional[int] = Field(None, description="User ID")
    offer: OfferSchema = Field(..., description="Offer")
    
    # Tracking data
    ip_address: Optional[str] = Field(None, description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent")
    country: Optional[str] = Field(None, description="Country")
    device: Optional[str] = Field(None, description="Device")
    browser: Optional[str] = Field(None, description="Browser")
    os: Optional[str] = Field(None, description="Operating system")
    
    # Timing
    clicked_at: datetime = Field(..., description="Click timestamp")
    
    # Uniqueness
    is_unique: bool = Field(True, description="Is unique click")
    
    # Fraud detection
    is_fraud: Optional[bool] = Field(False, description="Is fraudulent")
    fraud_score: Optional[float] = Field(None, ge=0, le=100, description="Fraud score")
    
    # Referral
    referrer_url: Optional[str] = Field(None, description="Referrer URL")
    session_id: Optional[str] = Field(None, description="Session ID")
    
    # Location data
    location_data: Optional[Dict[str, Any]] = Field(None, description="Location data")
    
    # Device info
    device_info: Optional[Dict[str, Any]] = Field(None, description="Device information")
    
    # Conversion tracking
    conversion_tracking: Optional[Dict[str, Any]] = Field(None, description="Conversion tracking data")
    
    # Computed fields
    risk_level: Optional[str] = Field(None, description="Risk level")
    is_suspicious: Optional[bool] = Field(None, description="Is suspicious")


# Health check schemas
class HealthCheckSchema(BaseSchema):
    """Health check schema"""
    
    id: int = Field(..., description="Health check ID")
    network: AdNetworkSchema = Field(..., description="Ad network")
    is_healthy: bool = Field(True, description="Is healthy")
    check_type: str = Field("api_call", description="Check type")
    endpoint_checked: Optional[str] = Field(None, description="Endpoint checked")
    response_time_ms: Optional[int] = Field(None, description="Response time in milliseconds")
    status_code: Optional[int] = Field(None, description="HTTP status code")
    error: Optional[str] = Field(None, description="Error message")
    checked_at: datetime = Field(..., description="Check timestamp")
    
    # Computed fields
    performance_level: Optional[str] = Field(None, description="Performance level")
    health_status: Optional[str] = Field(None, description="Health status")
    
    @validator('check_type')
    def validate_check_type(cls, v):
        valid_types = ['api_call', 'webhook', 'offer_sync', 'health_ping']
        if v not in valid_types:
            raise ValueError(f'Invalid check type: {v}')
        return v


# Analytics schemas
class OfferAnalyticsSchema(BaseModel):
    """Offer analytics schema"""
    
    offer_id: int = Field(..., description="Offer ID")
    total_clicks: int = Field(0, description="Total clicks")
    total_conversions: int = Field(0, description="Total conversions")
    conversion_rate: float = Field(0.0, description="Conversion rate percentage")
    total_payout: Decimal = Field(Decimal('0.00'), description="Total payout")
    avg_conversion_time: Optional[float] = Field(None, description="Average conversion time")
    top_countries: List[Dict[str, Any]] = Field([], description="Top countries")
    top_devices: List[Dict[str, Any]] = Field([], description="Top devices")
    daily_stats: List[Dict[str, Any]] = Field([], description="Daily statistics")


class NetworkAnalyticsSchema(BaseModel):
    """Network analytics schema"""
    
    network_id: int = Field(..., description="Network ID")
    total_offers: int = Field(0, description="Total offers")
    active_offers: int = Field(0, description="Active offers")
    total_conversions: int = Field(0, description="Total conversions")
    total_payout: Decimal = Field(Decimal('0.00'), description="Total payout")
    conversion_rate: float = Field(0.0, description="Conversion rate percentage")
    avg_payout: Decimal = Field(Decimal('0.00'), description="Average payout")
    health_status: str = Field("unknown", description="Health status")
    uptime_percentage: float = Field(0.0, description="Uptime percentage")
    last_sync: Optional[datetime] = Field(None, description="Last sync timestamp")


class UserAnalyticsSchema(BaseModel):
    """User analytics schema"""
    
    user_id: int = Field(..., description="User ID")
    total_engagements: int = Field(0, description="Total engagements")
    completed_engagements: int = Field(0, description="Completed engagements")
    total_conversions: int = Field(0, description="Total conversions")
    total_rewards: Decimal = Field(Decimal('0.00'), description="Total rewards")
    conversion_rate: float = Field(0.0, description="Conversion rate percentage")
    avg_reward: Decimal = Field(Decimal('0.00'), description="Average reward")
    favorite_categories: List[str] = Field([], description="Favorite categories")
    activity_by_hour: Dict[str, int] = Field({}, description="Activity by hour")
    recent_activity: List[Dict[str, Any]] = Field([], description="Recent activity")


# API request/response schemas
class OfferListRequestSchema(BaseModel):
    """Offer list request schema"""
    
    status: Optional[str] = Field(None, description="Offer status")
    category_id: Optional[int] = Field(None, description="Category ID")
    network_id: Optional[int] = Field(None, description="Network ID")
    min_reward: Optional[float] = Field(None, ge=0, description="Minimum reward")
    max_reward: Optional[float] = Field(None, ge=0, description="Maximum reward")
    countries: Optional[List[str]] = Field(None, description="Target countries")
    platforms: Optional[List[str]] = Field(None, description="Target platforms")
    device_type: Optional[str] = Field(None, description="Device type")
    difficulty: Optional[str] = Field(None, description="Difficulty level")
    is_featured: Optional[bool] = Field(None, description="Featured offers only")
    sort_by: Optional[str] = Field("created_at", description="Sort field")
    sort_order: Optional[str] = Field("desc", description="Sort order")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Page size")


class OfferListResponseSchema(ResponseSchema):
    """Offer list response schema"""
    
    data: List[OfferSchema] = Field([], description="Offers list")
    meta: Optional[PaginationSchema] = Field(None, description="Pagination metadata")


class ConversionCreateRequestSchema(BaseModel):
    """Conversion creation request schema"""
    
    conversion_id: constr(min_length=1, max_length=100) = Field(..., description="Conversion ID")
    user_id: int = Field(..., description="User ID")
    offer_id: int = Field(..., description="Offer ID")
    payout: Decimal = Field(..., ge=Decimal('0.01'), description="Payout amount")
    currency: str = Field("USD", description="Currency")
    conversion_data: Optional[Dict[str, Any]] = Field(None, description="Conversion data")
    timestamp: Optional[datetime] = Field(None, description="Conversion timestamp")


class ConversionVerifyRequestSchema(BaseModel):
    """Conversion verification request schema"""
    
    conversion_id: str = Field(..., description="Conversion ID")
    approved: bool = Field(..., description="Approval status")
    notes: Optional[str] = Field(None, description="Verification notes")
    fraud_score: Optional[float] = Field(None, ge=0, le=100, description="Fraud score")


class RewardCreateRequestSchema(BaseModel):
    """Reward creation request schema"""
    
    user_id: int = Field(..., description="User ID")
    offer_id: int = Field(..., description="Offer ID")
    engagement_id: Optional[int] = Field(None, description="Engagement ID")
    amount: Decimal = Field(..., ge=Decimal('0.01'), description="Reward amount")
    currency: str = Field("USD", description="Currency")
    reason: Optional[str] = Field(None, description="Reward reason")


class RewardPayoutRequestSchema(BaseModel):
    """Reward payout request schema"""
    
    reward_ids: conlist(int, min_items=1, max_items=50) = Field(..., description="Reward IDs")
    payment_method: str = Field(..., description="Payment method")
    payout_address: str = Field(..., description="Payout address")
    notes: Optional[str] = Field(None, description="Payout notes")


# Export schemas
class ExportRequestSchema(BaseModel):
    """Export request schema"""
    
    export_type: str = Field(..., description="Export type")
    format: str = Field("csv", description="Export format")
    date_from: Optional[datetime] = Field(None, description="Start date")
    date_to: Optional[datetime] = Field(None, description="End date")
    filters: Optional[Dict[str, Any]] = Field(None, description="Export filters")
    include_analytics: bool = Field(False, description="Include analytics")
    email: Optional[str] = Field(None, description="Email to send export")
    
    @validator('export_type')
    def validate_export_type(cls, v):
        valid_types = ['offers', 'conversions', 'rewards', 'networks', 'users']
        if v not in valid_types:
            raise ValueError(f'Invalid export type: {v}')
        return v
    
    @validator('format')
    def validate_format(cls, v):
        valid_formats = ['csv', 'json', 'excel']
        if v not in valid_formats:
            raise ValueError(f'Invalid format: {v}')
        return v


class ExportResponseSchema(ResponseSchema):
    """Export response schema"""
    
    data: Optional[Dict[str, Any]] = Field(None, description="Export data")
    download_url: Optional[str] = Field(None, description="Download URL")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    expires_at: Optional[datetime] = Field(None, description="Export expiration time")


# WebSocket schemas
class WebSocketMessageSchema(BaseModel):
    """WebSocket message schema"""
    
    type: str = Field(..., description="Message type")
    data: Dict[str, Any] = Field(..., description="Message data")
    timestamp: datetime = Field(..., description="Message timestamp")
    user_id: Optional[int] = Field(None, description="Target user ID")
    tenant_id: Optional[str] = Field(None, description="Tenant ID")


class OfferUpdateMessageSchema(WebSocketMessageSchema):
    """Offer update message schema"""
    
    type: str = Field("offer_update", description="Message type")
    data: Dict[str, Any] = Field(..., description="Offer update data")


class ConversionUpdateMessageSchema(WebSocketMessageSchema):
    """Conversion update message schema"""
    
    type: str = Field("conversion_update", description="Message type")
    data: Dict[str, Any] = Field(..., description="Conversion update data")


class RewardUpdateMessageSchema(WebSocketMessageSchema):
    """Reward update message schema"""
    
    type: str = Field("reward_update", description="Message type")
    data: Dict[str, Any] = Field(..., description="Reward update data")


# Configuration schemas
class NetworkConfigSchema(BaseModel):
    """Network configuration schema"""
    
    api_key: Optional[constr(min_length=10)] = Field(None, description="API key")
    postback_key: Optional[constr(min_length=10)] = Field(None, description="Postback key")
    postback_url: Optional[HttpUrl] = Field(None, description="Postback URL")
    webhook_url: Optional[HttpUrl] = Field(None, description="Webhook URL")
    sync_interval: int = Field(3600, ge=60, le=86400, description="Sync interval in seconds")
    max_offers: int = Field(1000, ge=1, le=10000, description="Maximum offers")
    auto_approve_threshold: float = Field(70.0, ge=0, le=100, description="Auto-approve threshold")
    fraud_detection_enabled: bool = Field(True, description="Fraud detection enabled")


class UserPreferencesSchema(BaseModel):
    """User preferences schema"""
    
    preferred_categories: Optional[List[str]] = Field(None, description="Preferred categories")
    preferred_networks: Optional[List[str]] = Field(None, description="Preferred networks")
    preferred_difficulty: Optional[str] = Field(None, description="Preferred difficulty")
    notification_settings: Optional[Dict[str, Any]] = Field(None, description="Notification settings")
    privacy_settings: Optional[Dict[str, Any]] = Field(None, description="Privacy settings")
    language: str = Field("en", description="Language")
    timezone: str = Field("UTC", description="Timezone")


# Error schemas
class ErrorSchema(BaseModel):
    """Error response schema"""
    
    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    timestamp: datetime = Field(..., description="Error timestamp")


class ValidationErrorSchema(ErrorSchema):
    """Validation error schema"""
    
    field_errors: Optional[Dict[str, List[str]]] = Field(None, description="Field-specific errors")


# Export all schemas
__all__ = [
    # Base schemas
    'BaseSchema',
    'PaginationSchema',
    'ResponseSchema',
    
    # Network schemas
    'NetworkTypeSchema',
    'NetworkCategorySchema',
    'AdNetworkSchema',
    
    # Offer schemas
    'OfferCategorySchema',
    'OfferSchema',
    
    # User engagement schemas
    'EngagementSchema',
    'ConversionSchema',
    'RewardSchema',
    'WalletSchema',
    
    # Click tracking schemas
    'ClickSchema',
    
    # Health check schemas
    'HealthCheckSchema',
    
    # Analytics schemas
    'OfferAnalyticsSchema',
    'NetworkAnalyticsSchema',
    'UserAnalyticsSchema',
    
    # API request/response schemas
    'OfferListRequestSchema',
    'OfferListResponseSchema',
    'ConversionCreateRequestSchema',
    'ConversionVerifyRequestSchema',
    'RewardCreateRequestSchema',
    'RewardPayoutRequestSchema',
    
    # Export schemas
    'ExportRequestSchema',
    'ExportResponseSchema',
    
    # WebSocket schemas
    'WebSocketMessageSchema',
    'OfferUpdateMessageSchema',
    'ConversionUpdateMessageSchema',
    'RewardUpdateMessageSchema',
    
    # Configuration schemas
    'NetworkConfigSchema',
    'UserPreferencesSchema',
    
    # Error schemas
    'ErrorSchema',
    'ValidationErrorSchema'
]
