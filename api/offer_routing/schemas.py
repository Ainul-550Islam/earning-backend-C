"""
Data Schemas for Offer Routing System

This module contains data schemas and validation rules for the offer routing system,
including request/response schemas, data validation schemas, and API schemas.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, validator, ValidationError
from datetime import datetime, date, time
from decimal import Decimal
from enum import Enum

logger = logging.getLogger(__name__)


# Enums for schema validation

class CapType(str, Enum):
    """Cap type enumeration."""
    DAILY = "daily"
    HOURLY = "hourly"
    TOTAL = "total"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class RouteStatus(str, Enum):
    """Route status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"
    PAUSED = "paused"
    ARCHIVED = "archived"


class ConditionOperator(str, Enum):
    """Condition operator enumeration."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN = "in"
    NOT_IN = "not_in"


class ActionType(str, Enum):
    """Action type enumeration."""
    SHOW_OFFER = "show_offer"
    HIDE_OFFER = "hide_offer"
    BOOST_PRIORITY = "boost_priority"
    REDIRECT_TO = "redirect_to"
    LOG_EVENT = "log_event"
    SEND_NOTIFICATION = "send_notification"


class AlertSeverity(str, Enum):
    """Alert severity enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Base Schemas

class BaseSchema(BaseModel):
    """Base schema with common fields."""
    
    class Config:
        extra = "forbid"
        validate_assignment = True
        use_enum_values = True


class TimestampedSchema(BaseSchema):
    """Base schema with timestamp fields."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Request Schemas

class RouteConditionSchema(BaseSchema):
    """Schema for route conditions."""
    
    field_name: str = Field(..., min_length=1, max_length=100)
    operator: ConditionOperator = Field(...)
    value: Union[str, int, float, bool, List[str]] = Field(...)
    priority: int = Field(default=1, ge=1, le=100)
    is_active: bool = Field(default=True)
    
    @validator('field_name')
    def validate_field_name(cls, v):
        allowed_fields = [
            'user_status', 'offer_status', 'country', 'device_type',
            'user_segment', 'time_of_day', 'day_of_week', 'custom_field'
        ]
        if v not in allowed_fields:
            raise ValueError(f"Field name must be one of: {allowed_fields}")
        return v


class RouteActionSchema(BaseSchema):
    """Schema for route actions."""
    
    action_type: ActionType = Field(...)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=1, ge=1, le=100)
    is_active: bool = Field(default=True)
    
    @validator('parameters')
    def validate_parameters(cls, v, values):
        action_type = values.get('action_type')
        
        if action_type == ActionType.SHOW_OFFER:
            required_params = ['offer_ids']
        elif action_type == ActionType.HIDE_OFFER:
            required_params = ['offer_ids']
        elif action_type == ActionType.BOOST_PRIORITY:
            required_params = ['boost_amount']
        elif action_type == ActionType.REDIRECT_TO:
            required_params = ['redirect_url']
        else:
            required_params = []
        
        for param in required_params:
            if param not in v:
                raise ValueError(f"Parameter '{param}' is required for action type '{action_type}'")
        
        return v


class OfferRouteSchema(BaseSchema):
    """Schema for offer route creation/update."""
    
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    status: RouteStatus = Field(default=RouteStatus.DRAFT)
    priority: int = Field(default=50, ge=1, le=100)
    is_active: bool = Field(default=True)
    
    # Targeting
    geo_targeting: Optional[Dict[str, Any]] = Field(None)
    device_targeting: Optional[Dict[str, Any]] = Field(None)
    user_segment_targeting: Optional[Dict[str, Any]] = Field(None)
    time_targeting: Optional[Dict[str, Any]] = Field(None)
    
    # Conditions and Actions
    conditions: List[RouteConditionSchema] = Field(default_factory=list)
    actions: List[RouteActionSchema] = Field(default_factory=list)
    
    # Offers
    offer_ids: List[int] = Field(default_factory=list)
    default_offer_ids: List[int] = Field(default_factory=list)
    
    @validator('priority')
    def validate_priority(cls, v):
        if v < 1 or v > 100:
            raise ValueError("Priority must be between 1 and 100")
        return v


class OfferRoutingCapSchema(BaseSchema):
    """Schema for offer routing cap creation/update."""
    
    offer_id: int = Field(...)
    cap_type: CapType = Field(...)
    max_count: int = Field(..., gt=0)
    current_count: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)
    expires_at: Optional[datetime] = Field(None)
    
    @validator('max_count')
    def validate_max_count(cls, v):
        if v <= 0:
            raise ValueError("Max count must be greater than 0")
        return v
    
    @validator('current_count')
    def validate_current_count(cls, v, values):
        max_count = values.get('max_count')
        if max_count and v > max_count:
            raise ValueError("Current count cannot exceed max count")
        return v


class UserOfferCapSchema(BaseSchema):
    """Schema for user offer cap creation/update."""
    
    user_id: int = Field(...)
    offer_id: int = Field(...)
    cap_type: CapType = Field(...)
    max_count: int = Field(..., gt=0)
    current_count: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)
    expires_at: Optional[datetime] = Field(None)
    
    @validator('max_count')
    def validate_max_count(cls, v):
        if v <= 0:
            raise ValueError("Max count must be greater than 0")
        return v
    
    @validator('current_count')
    def validate_current_count(cls, v, values):
        max_count = values.get('max_count')
        if max_count and v > max_count:
            raise ValueError("Current count cannot exceed max count")
        return v


class RoutingRequestSchema(BaseSchema):
    """Schema for routing requests."""
    
    user_id: int = Field(...)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    offer_preferences: Optional[List[int]] = Field(None)
    exclude_offers: Optional[List[int]] = Field(None)
    max_results: int = Field(default=5, ge=1, le=50)
    personalized: bool = Field(default=True)
    
    @validator('max_results')
    def validate_max_results(cls, v):
        if v < 1 or v > 50:
            raise ValueError("Max results must be between 1 and 50")
        return v


# Response Schemas

class RoutingDecisionSchema(BaseSchema):
    """Schema for routing decision response."""
    
    success: bool
    route_id: Optional[int]
    route_name: Optional[str]
    offers: List[int]
    score: float
    action_results: List[Dict[str, Any]]
    response_time: float
    context: Dict[str, Any]
    timestamp: datetime
    error: Optional[str] = None


class CapStatusSchema(BaseSchema):
    """Schema for cap status response."""
    
    cap_type: CapType
    cap_id: int
    current_count: int
    max_count: int
    utilization_rate: float
    is_active: bool
    is_limit_reached: bool
    last_reset: Optional[datetime]
    expires_at: Optional[datetime]


class CapAnalyticsSchema(BaseSchema):
    """Schema for cap analytics response."""
    
    cap_type: CapType
    cap_id: int
    period_start: datetime
    period_end: datetime
    total_usage: int
    max_usage: int
    utilization_rate: float
    hit_rate: float
    average_reset_time: Optional[float]
    violation_count: int
    insights: List[str]
    recommendations: List[str]


class RoutePerformanceSchema(BaseSchema):
    """Schema for route performance response."""
    
    route_id: int
    route_name: str
    total_decisions: int
    successful_decisions: int
    success_rate: float
    average_response_time: float
    average_score: float
    last_updated: datetime


class AlertSchema(BaseSchema):
    """Schema for alert response."""
    
    alert_id: str
    alert_type: str
    severity: AlertSeverity
    message: str
    data: Dict[str, Any]
    timestamp: datetime
    is_resolved: bool
    resolved_at: Optional[datetime]


# Validation Schemas

class GeoTargetingSchema(BaseSchema):
    """Schema for geographic targeting validation."""
    
    countries: List[str] = Field(default_factory=list)
    regions: List[str] = Field(default_factory=list)
    cities: List[str] = Field(default_factory=list)
    excluded_countries: List[str] = Field(default_factory=list)
    excluded_regions: List[str] = Field(default_factory=list)
    excluded_cities: List[str] = Field(default_factory=list)
    
    @validator('countries')
    def validate_countries(cls, v):
        if v and len(v) > 50:
            raise ValueError("Cannot specify more than 50 countries")
        return v


class DeviceTargetingSchema(BaseSchema):
    """Schema for device targeting validation."""
    
    device_types: List[str] = Field(default_factory=list)
    operating_systems: List[str] = Field(default_factory=list)
    browsers: List[str] = Field(default_factory=list)
    excluded_device_types: List[str] = Field(default_factory=list)
    excluded_operating_systems: List[str] = Field(default_factory=list)
    excluded_browsers: List[str] = Field(default_factory=list)
    
    @validator('device_types')
    def validate_device_types(cls, v):
        allowed_devices = ['mobile', 'desktop', 'tablet', 'smart_tv', 'wearable']
        for device in v:
            if device not in allowed_devices:
                raise ValueError(f"Invalid device type: {device}. Allowed types: {allowed_devices}")
        return v


class UserSegmentTargetingSchema(BaseSchema):
    """Schema for user segment targeting validation."""
    
    required_segments: List[str] = Field(default_factory=list)
    excluded_segments: List[str] = Field(default_factory=list)
    user_tiers: List[str] = Field(default_factory=list)
    activity_levels: List[str] = Field(default_factory=list)
    
    @validator('required_segments')
    def validate_required_segments(cls, v):
        if v and len(v) > 10:
            raise ValueError("Cannot specify more than 10 required segments")
        return v


class TimeTargetingSchema(BaseSchema):
    """Schema for time targeting validation."""
    
    hours: List[int] = Field(default_factory=list)
    days_of_week: List[int] = Field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    timezone: str = Field(default="UTC")
    
    @validator('hours')
    def validate_hours(cls, v):
        for hour in v:
            if hour < 0 or hour > 23:
                raise ValueError(f"Invalid hour: {hour}. Must be between 0 and 23")
        return v
    
    @validator('days_of_week')
    def validate_days_of_week(cls, v):
        for day in v:
            if day < 0 or day > 6:
                raise ValueError(f"Invalid day of week: {day}. Must be between 0 and 6")
        return v
    
    @validator('end_date')
    def validate_end_date(cls, v, values):
        start_date = values.get('start_date')
        if start_date and v and v < start_date:
            raise ValueError("End date must be after start date")
        return v


# API Schemas

class PaginationSchema(BaseSchema):
    """Schema for pagination parameters."""
    
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    
    @validator('page_size')
    def validate_page_size(cls, v):
        if v < 1 or v > 100:
            raise ValueError("Page size must be between 1 and 100")
        return v


class PaginatedResponseSchema(BaseSchema):
    """Schema for paginated responses."""
    
    items: List[Dict[str, Any]]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class ErrorResponseSchema(BaseSchema):
    """Schema for error responses."""
    
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SuccessResponseSchema(BaseSchema):
    """Schema for success responses."""
    
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Bulk Operation Schemas

class BulkCapCreateSchema(BaseSchema):
    """Schema for bulk cap creation."""
    
    caps: List[Union[OfferRoutingCapSchema, UserOfferCapSchema]] = Field(...)
    
    @validator('caps')
    def validate_caps(cls, v):
        if not v:
            raise ValueError("At least one cap must be provided")
        if len(v) > 100:
            raise ValueError("Cannot create more than 100 caps in bulk")
        return v


class BulkCapUpdateSchema(BaseSchema):
    """Schema for bulk cap updates."""
    
    updates: List[Dict[str, Any]] = Field(...)
    
    @validator('updates')
    def validate_updates(cls, v):
        if not v:
            raise ValueError("At least one update must be provided")
        if len(v) > 100:
            raise ValueError("Cannot update more than 100 caps in bulk")
        
        for update in v:
            if 'cap_id' not in update:
                raise ValueError("Each update must include 'cap_id'")
        
        return v


class BulkCapDeleteSchema(BaseSchema):
    """Schema for bulk cap deletion."""
    
    cap_ids: List[int] = Field(...)
    
    @validator('cap_ids')
    def validate_cap_ids(cls, v):
        if not v:
            raise ValueError("At least one cap ID must be provided")
        if len(v) > 100:
            raise ValueError("Cannot delete more than 100 caps in bulk")
        return v


# Configuration Schemas

class CapConfigSchema(BaseSchema):
    """Schema for cap configuration."""
    
    default_daily_cap: int = Field(default=100, gt=0)
    default_hourly_cap: int = Field(default=10, gt=0)
    auto_reset_enabled: bool = Field(default=True)
    warning_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    emergency_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    monitoring_enabled: bool = Field(default=True)
    analytics_retention_days: int = Field(default=30, ge=1, le=365)
    
    @validator('warning_threshold')
    def validate_warning_threshold(cls, v):
        if v < 0 or v > 1:
            raise ValueError("Warning threshold must be between 0 and 1")
        return v
    
    @validator('emergency_threshold')
    def validate_emergency_threshold(cls, v):
        if v < 0 or v > 1:
            raise ValueError("Emergency threshold must be between 0 and 1")
        return v


class RoutingConfigSchema(BaseSchema):
    """Schema for routing configuration."""
    
    default_priority: int = Field(default=50, ge=1, le=100)
    max_route_conditions: int = Field(default=10, ge=1, le=50)
    max_route_actions: int = Field(default=5, ge=1, le=20)
    cache_enabled: bool = Field(default=True)
    cache_timeout: int = Field(default=300, ge=60, le=3600)
    performance_tracking_enabled: bool = Field(default=True)
    personalization_enabled: bool = Field(default=True)
    
    @validator('max_route_conditions')
    def validate_max_route_conditions(cls, v):
        if v < 1 or v > 50:
            raise ValueError("Max route conditions must be between 1 and 50")
        return v
    
    @validator('max_route_actions')
    def validate_max_route_actions(cls, v):
        if v < 1 or v > 20:
            raise ValueError("Max route actions must be between 1 and 20")
        return v


# Validation Functions

def validate_route_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate route data."""
    try:
        route_schema = OfferRouteSchema(**data)
        return route_schema.dict()
    except ValidationError as e:
        logger.error(f"Route validation error: {e}")
        raise


def validate_cap_data(data: Dict[str, Any], cap_type: str) -> Dict[str, Any]:
    """Validate cap data."""
    try:
        if cap_type == 'offer':
            cap_schema = OfferRoutingCapSchema(**data)
        elif cap_type == 'user':
            cap_schema = UserOfferCapSchema(**data)
        else:
            raise ValueError(f"Invalid cap type: {cap_type}")
        
        return cap_schema.dict()
    except ValidationError as e:
        logger.error(f"Cap validation error: {e}")
        raise


def validate_routing_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate routing request data."""
    try:
        request_schema = RoutingRequestSchema(**data)
        return request_schema.dict()
    except ValidationError as e:
        logger.error(f"Routing request validation error: {e}")
        raise


# Schema Registry

class SchemaRegistry:
    """Registry for managing schemas."""
    
    def __init__(self):
        self._schemas = {}
        self._register_default_schemas()
    
    def _register_default_schemas(self):
        """Register default schemas."""
        self._schemas.update({
            'route': OfferRouteSchema,
            'offer_cap': OfferRoutingCapSchema,
            'user_cap': UserOfferCapSchema,
            'routing_request': RoutingRequestSchema,
            'routing_decision': RoutingDecisionSchema,
            'cap_status': CapStatusSchema,
            'cap_analytics': CapAnalyticsSchema,
            'route_performance': RoutePerformanceSchema,
            'alert': AlertSchema,
            'pagination': PaginationSchema,
            'error_response': ErrorResponseSchema,
            'success_response': SuccessResponseSchema,
        })
    
    def register_schema(self, name: str, schema_class: type):
        """Register a new schema."""
        self._schemas[name] = schema_class
    
    def get_schema(self, name: str) -> Optional[type]:
        """Get a schema by name."""
        return self._schemas.get(name)
    
    def validate_data(self, schema_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data using a registered schema."""
        schema_class = self.get_schema(schema_name)
        if not schema_class:
            raise ValueError(f"Schema '{schema_name}' not found")
        
        try:
            schema_instance = schema_class(**data)
            return schema_instance.dict()
        except ValidationError as e:
            logger.error(f"Validation error for schema '{schema_name}': {e}")
            raise
    
    def list_schemas(self) -> List[str]:
        """List all registered schemas."""
        return list(self._schemas.keys())


# Global schema registry instance
schema_registry = SchemaRegistry()


# Export all schemas and utilities
__all__ = [
    # Enums
    'CapType',
    'RouteStatus',
    'ConditionOperator',
    'ActionType',
    'AlertSeverity',
    
    # Base schemas
    'BaseSchema',
    'TimestampedSchema',
    
    # Request schemas
    'RouteConditionSchema',
    'RouteActionSchema',
    'OfferRouteSchema',
    'OfferRoutingCapSchema',
    'UserOfferCapSchema',
    'RoutingRequestSchema',
    
    # Response schemas
    'RoutingDecisionSchema',
    'CapStatusSchema',
    'CapAnalyticsSchema',
    'RoutePerformanceSchema',
    'AlertSchema',
    
    # Validation schemas
    'GeoTargetingSchema',
    'DeviceTargetingSchema',
    'UserSegmentTargetingSchema',
    'TimeTargetingSchema',
    
    # API schemas
    'PaginationSchema',
    'PaginatedResponseSchema',
    'ErrorResponseSchema',
    'SuccessResponseSchema',
    
    # Bulk operation schemas
    'BulkCapCreateSchema',
    'BulkCapUpdateSchema',
    'BulkCapDeleteSchema',
    
    # Configuration schemas
    'CapConfigSchema',
    'RoutingConfigSchema',
    
    # Validation functions
    'validate_route_data',
    'validate_cap_data',
    'validate_routing_request',
    
    # Schema registry
    'SchemaRegistry',
    'schema_registry',
]
