"""
Pydantic Schemas for Advertiser Portal

This module contains Pydantic models for request/response validation,
serialization, and data transfer objects (DTOs).
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, validator, EmailStr, HttpUrl
from uuid import UUID


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    
    class Config:
        orm_mode = True
        validate_assignment = True
        use_enum_values = True
        extra = "forbid"


class TimestampSchema(BaseSchema):
    """Schema with timestamp fields."""
    created_at: datetime
    updated_at: datetime


class UUIDSchema(BaseSchema):
    """Schema with UUID field."""
    id: UUID


class StatusEnum(str, Enum):
    """Common status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class CampaignObjectiveEnum(str, Enum):
    """Campaign objective enumeration."""
    AWARENESS = "awareness"
    TRAFFIC = "traffic"
    ENGAGEMENT = "engagement"
    LEADS = "leads"
    SALES = "sales"
    APP_PROMOTION = "app_promotion"
    STORE_VISITS = "store_visits"
    BRAND_SAFETY = "brand_safety"


class BiddingStrategyEnum(str, Enum):
    """Bidding strategy enumeration."""
    MANUAL_CPC = "manual_cpc"
    ENHANCED_CPC = "enhanced_cpc"
    TARGET_CPA = "target_cpa"
    TARGET_ROAS = "target_roas"
    MAXIMIZE_CLICKS = "maximize_clicks"
    MAXIMIZE_CONVERSIONS = "maximize_conversions"
    TARGET_IMPRESSION_SHARE = "target_impression_share"


class CreativeTypeEnum(str, Enum):
    """Creative type enumeration."""
    BANNER = "banner"
    VIDEO = "video"
    NATIVE = "native"
    PLAYABLE = "playable"
    INTERACTIVE = "interactive"
    RICH_MEDIA = "rich_media"
    HTML5 = "html5"
    DYNAMIC = "dynamic"


class DeviceTypeEnum(str, Enum):
    """Device type enumeration."""
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    CONNECTED_TV = "connected_tv"


class OSFamilyEnum(str, Enum):
    """Operating system family enumeration."""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    IOS = "ios"
    ANDROID = "android"
    OTHER = "other"


class PaymentMethodEnum(str, Enum):
    """Payment method enumeration."""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"
    PAYPAL = "paypal"
    WIRE_TRANSFER = "wire_transfer"
    CRYPTO = "crypto"


class BillingCycleEnum(str, Enum):
    """Billing cycle enumeration."""
    PREPAID = "prepaid"
    POSTPAID = "postpaid"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


# Advertiser Schemas
class AdvertiserBase(BaseSchema):
    """Base advertiser schema."""
    company_name: str = Field(..., min_length=2, max_length=255)
    industry: str = Field(..., min_length=2, max_length=100)
    website: Optional[HttpUrl] = None
    contact_email: EmailStr
    contact_phone: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = Field(None, max_length=1000)
    status: StatusEnum = StatusEnum.PENDING


class AdvertiserCreate(AdvertiserBase):
    """Schema for creating advertiser."""
    api_key: Optional[str] = None


class AdvertiserUpdate(BaseSchema):
    """Schema for updating advertiser."""
    company_name: Optional[str] = Field(None, min_length=2, max_length=255)
    industry: Optional[str] = Field(None, min_length=2, max_length=100)
    website: Optional[HttpUrl] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[StatusEnum] = None


class AdvertiserResponse(AdvertiserBase, UUIDSchema, TimestampSchema):
    """Schema for advertiser response."""
    api_key: Optional[str] = None
    is_verified: bool
    verification_date: Optional[datetime] = None


# Campaign Schemas
class CampaignBase(BaseSchema):
    """Base campaign schema."""
    name: str = Field(..., min_length=2, max_length=255)
    objective: CampaignObjectiveEnum
    description: Optional[str] = Field(None, max_length=1000)
    daily_budget: Decimal = Field(..., ge=0, decimal_places=2)
    total_budget: Decimal = Field(..., ge=0, decimal_places=2)
    start_date: date
    end_date: Optional[date] = None
    status: StatusEnum = StatusEnum.PENDING
    bidding_strategy: BiddingStrategyEnum = BiddingStrategyEnum.MANUAL_CPC
    target_cpa: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    target_roas: Optional[Decimal] = Field(None, ge=0, decimal_places=2)

    @validator('end_date')
    def validate_end_date(cls, v, values):
        if v and 'start_date' in values and v < values['start_date']:
            raise ValueError('End date must be after start date')
        return v

    @validator('total_budget')
    def validate_total_budget(cls, v, values):
        if 'daily_budget' in values and v < values['daily_budget']:
            raise ValueError('Total budget must be greater than or equal to daily budget')
        return v


class CampaignCreate(CampaignBase):
    """Schema for creating campaign."""
    advertiser_id: UUID


class CampaignUpdate(BaseSchema):
    """Schema for updating campaign."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    objective: Optional[CampaignObjectiveEnum] = None
    description: Optional[str] = Field(None, max_length=1000)
    daily_budget: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    total_budget: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[StatusEnum] = None
    bidding_strategy: Optional[BiddingStrategyEnum] = None
    target_cpa: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    target_roas: Optional[Decimal] = Field(None, ge=0, decimal_places=2)


class CampaignResponse(CampaignBase, UUIDSchema, TimestampSchema):
    """Schema for campaign response."""
    advertiser_id: UUID
    current_spend: Decimal
    impressions: int
    clicks: int
    conversions: int
    ctr: Decimal
    cpc: Decimal
    conversion_rate: Decimal
    is_active: bool


# Creative Schemas
class CreativeBase(BaseSchema):
    """Base creative schema."""
    name: str = Field(..., min_length=2, max_length=255)
    type: CreativeTypeEnum
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    landing_page_url: HttpUrl
    tracking_url: Optional[HttpUrl] = None
    status: StatusEnum = StatusEnum.PENDING


class CreativeCreate(CreativeBase):
    """Schema for creating creative."""
    campaign_id: UUID
    creative_data: Dict[str, Any] = Field(default_factory=dict)


class CreativeUpdate(BaseSchema):
    """Schema for updating creative."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    landing_page_url: Optional[HttpUrl] = None
    tracking_url: Optional[HttpUrl] = None
    status: Optional[StatusEnum] = None
    creative_data: Optional[Dict[str, Any]] = None


class CreativeResponse(CreativeBase, UUIDSchema, TimestampSchema):
    """Schema for creative response."""
    campaign_id: UUID
    creative_data: Dict[str, Any]
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    is_approved: bool
    approval_date: Optional[datetime] = None
    impressions: int
    clicks: int
    conversions: int
    ctr: Decimal


# Targeting Schemas
class GeoTargetingBase(BaseSchema):
    """Base geo targeting schema."""
    countries: List[str] = Field(default_factory=list)
    regions: List[str] = Field(default_factory=list)
    cities: List[str] = Field(default_factory=list)
    postal_codes: List[str] = Field(default_factory=list)
    include_coordinates: bool = False
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    radius: Optional[int] = Field(None, ge=1, le=1000)


class DeviceTargetingBase(BaseSchema):
    """Base device targeting schema."""
    device_types: List[DeviceTypeEnum] = Field(default_factory=list)
    os_families: List[OSFamilyEnum] = Field(default_factory=list)
    os_versions: List[str] = Field(default_factory=list)
    browsers: List[str] = Field(default_factory=list)
    carriers: List[str] = Field(default_factory=list)


class TargetingBase(BaseSchema):
    """Base targeting schema."""
    campaign_id: UUID
    geo_targeting: GeoTargetingBase
    device_targeting: DeviceTargetingBase
    age_min: Optional[int] = Field(None, ge=13, le=65)
    age_max: Optional[int] = Field(None, ge=13, le=65)
    genders: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    exclude_keywords: List[str] = Field(default_factory=list)

    @validator('age_max')
    def validate_age_range(cls, v, values):
        if v and 'age_min' in values and v < values['age_min']:
            raise ValueError('Age max must be greater than or equal to age min')
        return v


class TargetingCreate(TargetingBase):
    """Schema for creating targeting."""
    pass


class TargetingUpdate(BaseSchema):
    """Schema for updating targeting."""
    geo_targeting: Optional[GeoTargetingBase] = None
    device_targeting: Optional[DeviceTargetingBase] = None
    age_min: Optional[int] = Field(None, ge=13, le=65)
    age_max: Optional[int] = Field(None, ge=13, le=65)
    genders: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    interests: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    exclude_keywords: Optional[List[str]] = None


class TargetingResponse(TargetingBase, UUIDSchema, TimestampSchema):
    """Schema for targeting response."""
    pass


# Analytics Schemas
class AnalyticsQuery(BaseSchema):
    """Schema for analytics query."""
    start_date: date
    end_date: date
    advertiser_ids: Optional[List[UUID]] = None
    campaign_ids: Optional[List[UUID]] = None
    creative_ids: Optional[List[UUID]] = None
    metrics: List[str] = Field(default_factory=list)
    dimensions: List[str] = Field(default_factory=list)
    filters: Optional[Dict[str, Any]] = None
    limit: Optional[int] = Field(None, ge=1, le=10000)
    offset: Optional[int] = Field(None, ge=0)

    @validator('end_date')
    def validate_date_range(cls, v, values):
        if v and 'start_date' in values and v < values['start_date']:
            raise ValueError('End date must be after start date')
        return v


class AnalyticsResponse(BaseSchema):
    """Schema for analytics response."""
    data: List[Dict[str, Any]]
    total_rows: int
    has_more: bool
    query: AnalyticsQuery


# Billing Schemas
class BillingProfileBase(BaseSchema):
    """Base billing profile schema."""
    company_name: str = Field(..., min_length=2, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=50)
    billing_address: str = Field(..., min_length=5, max_length=500)
    billing_city: str = Field(..., min_length=2, max_length=100)
    billing_state: str = Field(..., min_length=2, max_length=100)
    billing_country: str = Field(..., min_length=2, max_length=2)
    billing_postal_code: str = Field(..., min_length=3, max_length=20)
    contact_email: EmailStr
    contact_phone: Optional[str] = Field(None, max_length=20)


class PaymentMethodBase(BaseSchema):
    """Base payment method schema."""
    method_type: PaymentMethodEnum
    provider: str = Field(..., min_length=2, max_length=100)
    account_identifier: str = Field(..., min_length=2, max_length=255)
    expiry_date: Optional[date] = None
    is_default: bool = False
    is_active: bool = True


class InvoiceBase(BaseSchema):
    """Base invoice schema."""
    invoice_number: str = Field(..., min_length=1, max_length=50)
    issue_date: date
    due_date: date
    subtotal: Decimal = Field(..., ge=0, decimal_places=2)
    tax_amount: Decimal = Field(..., ge=0, decimal_places=2)
    total_amount: Decimal = Field(..., ge=0, decimal_places=2)
    status: StatusEnum = StatusEnum.PENDING
    notes: Optional[str] = Field(None, max_length=1000)

    @validator('due_date')
    def validate_due_date(cls, v, values):
        if v and 'issue_date' in values and v < values['issue_date']:
            raise ValueError('Due date must be after issue date')
        return v


# API Response Schemas
class APIResponse(BaseSchema):
    """Generic API response schema."""
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None


class PaginatedResponse(BaseSchema):
    """Paginated response schema."""
    items: List[Any]
    total: int
    page: int
    per_page: int
    pages: int
    has_next: bool
    has_prev: bool


class ErrorDetail(BaseSchema):
    """Error detail schema."""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ErrorResponse(BaseSchema):
    """Error response schema."""
    success: bool = False
    message: str
    errors: List[ErrorDetail] = Field(default_factory=list)
    timestamp: datetime
    request_id: Optional[str] = None
