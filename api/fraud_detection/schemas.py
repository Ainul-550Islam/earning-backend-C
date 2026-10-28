# =============================================================================
# fraud_detection/schemas.py
# =============================================================================
"""
Data Schemas for Fraud Detection System.

Provides comprehensive data schemas, validation schemas,
and serialization schemas for fraud detection data structures.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal

from pydantic import BaseModel, Field, validator, constr, EmailStr
from pydantic.types import UUID4

from api.fraud_detection.constants import RISK_THRESHOLDS, FRAUD_SCORE_WEIGHTS


logger = logging.getLogger(__name__)


# Base schemas
class BaseSchema(BaseModel):
    """Base schema for all fraud detection schemas."""
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True
        extra = 'forbid'
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


# Enum schemas
class SeverityLevel(str, Enum):
    """Severity levels for fraud detection."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FraudType(str, Enum):
    """Types of fraud."""
    IDENTITY_THEFT = "identity_theft"
    ACCOUNT_TAKEOVER = "account_takeover"
    CREDIT_CARD_FRAUD = "credit_card_fraud"
    MONEY_LAUNDERING = "money_laundering"
    TERRORIST_FINANCING = "terrorist_financing"
    INSIDER_FRAUD = "insider_fraud"
    INSURANCE_FRAUD = "insurance_fraud"
    INVESTMENT_FRAUD = "investment_fraud"
    PHISHING = "phishing"
    SYNTHETIC_IDENTITY = "synthetic_identity"
    OTHER = "other"


class DetectionMethod(str, Enum):
    """Fraud detection methods."""
    RULE_BASED = "rule_based"
    MACHINE_LEARNING = "machine_learning"
    PATTERN_ANALYSIS = "pattern_analysis"
    MANUAL_REVIEW = "manual_review"
    EXTERNAL_INTELLIGENCE = "external_intelligence"
    USER_REPORT = "user_report"
    SYSTEM_ALERT = "system_alert"
    HYBRID = "hybrid"


class CaseStatus(str, Enum):
    """Fraud case statuses."""
    OPEN = "open"
    INVESTIGATING = "investigating"
    PENDING_REVIEW = "pending_review"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ARCHIVED = "archived"


class AlertType(str, Enum):
    """Alert types."""
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    HIGH_RISK_TRANSACTION = "high_risk_transaction"
    UNUSUAL_PATTERN = "unusual_pattern"
    SANCTIONS_HIT = "sanctions_hit"
    COMPLIANCE_BREACH = "compliance_breach"
    SYSTEM_ANOMALY = "system_anomaly"
    EXTERNAL_ALERT = "external_alert"


# Core data schemas
class AddressSchema(BaseSchema):
    """Address information schema."""
    street: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, description="City")
    state: Optional[str] = Field(None, description="State/Province")
    postal_code: Optional[str] = Field(None, description="Postal/ZIP code")
    country: Optional[str] = Field(None, description="Country code")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Latitude")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Longitude")


class DeviceSchema(BaseSchema):
    """Device information schema."""
    device_id: Optional[str] = Field(None, description="Device identifier")
    device_type: Optional[str] = Field(None, description="Device type")
    operating_system: Optional[str] = Field(None, description="Operating system")
    browser: Optional[str] = Field(None, description="Browser information")
    screen_resolution: Optional[str] = Field(None, description="Screen resolution")
    language: Optional[str] = Field(None, description="Language setting")
    timezone: Optional[str] = Field(None, description="Timezone")
    fingerprint: Optional[str] = Field(None, description="Device fingerprint hash")


class TransactionSchema(BaseSchema):
    """Transaction data schema."""
    transaction_id: str = Field(..., description="Unique transaction identifier")
    user_id: Union[int, str] = Field(..., description="User identifier")
    amount: Decimal = Field(..., gt=0, description="Transaction amount")
    currency: str = Field(..., min_length=3, max_length=3, description="Currency code")
    timestamp: datetime = Field(..., description="Transaction timestamp")
    merchant_id: Optional[str] = Field(None, description="Merchant identifier")
    merchant_name: Optional[str] = Field(None, description="Merchant name")
    payment_method: Optional[str] = Field(None, description="Payment method type")
    payment_instrument: Optional[str] = Field(None, description="Payment instrument identifier")
    description: Optional[str] = Field(None, description="Transaction description")
    category: Optional[str] = Field(None, description="Transaction category")
    ip_address: Optional[str] = Field(None, description="IP address")
    device: Optional[DeviceSchema] = Field(None, description="Device information")
    billing_address: Optional[AddressSchema] = Field(None, description="Billing address")
    shipping_address: Optional[AddressSchema] = Field(None, description="Shipping address")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    @validator('amount')
    def validate_amount(cls, v):
        """Validate transaction amount."""
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v
    
    @validator('currency')
    def validate_currency(cls, v):
        """Validate currency code."""
        if len(v) != 3:
            raise ValueError("Currency must be 3-character code")
        return v.upper()


class UserProfileSchema(BaseSchema):
    """User profile schema."""
    user_id: Union[int, str] = Field(..., description="User identifier")
    email: Optional[EmailStr] = Field(None, description="Email address")
    phone_number: Optional[str] = Field(None, description="Phone number")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    date_of_birth: Optional[datetime] = Field(None, description="Date of birth")
    account_created: datetime = Field(..., description="Account creation date")
    last_login: Optional[datetime] = Field(None, description="Last login date")
    account_status: str = Field(..., description="Account status")
    verification_status: Optional[str] = Field(None, description="Verification status")
    risk_score: Optional[int] = Field(None, ge=0, le=100, description="Current risk score")
    risk_level: Optional[SeverityLevel] = Field(None, description="Risk level")
    addresses: Optional[List[AddressSchema]] = Field(None, description="User addresses")
    devices: Optional[List[DeviceSchema]] = Field(None, description="User devices")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class FraudDetectionResultSchema(BaseSchema):
    """Fraud detection result schema."""
    detection_id: str = Field(..., description="Detection identifier")
    user_id: Union[int, str] = Field(..., description="User identifier")
    transaction_id: Optional[str] = Field(None, description="Transaction identifier")
    timestamp: datetime = Field(..., description="Detection timestamp")
    final_risk_score: int = Field(..., ge=0, le=100, description="Final risk score")
    risk_level: SeverityLevel = Field(..., description="Risk level")
    fraud_detected: bool = Field(..., description="Whether fraud was detected")
    confidence_score: float = Field(..., ge=0, le=1, description="Detection confidence")
    detection_method: DetectionMethod = Field(..., description="Detection method used")
    fraud_indicators: List[str] = Field(default_factory=list, description="Fraud indicators found")
    suspicious_patterns: List[str] = Field(default_factory=list, description="Suspicious patterns")
    risk_factors: Dict[str, Any] = Field(default_factory=dict, description="Risk factor breakdown")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    action_required: bool = Field(..., description="Whether action is required")
    suggested_actions: List[str] = Field(default_factory=list, description="Suggested actions")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    @validator('final_risk_score')
    def validate_risk_score(cls, v):
        """Validate risk score."""
        if v < 0 or v > 100:
            raise ValueError("Risk score must be between 0 and 100")
        return v
    
    @validator('confidence_score')
    def validate_confidence_score(cls, v):
        """Validate confidence score."""
        if v < 0 or v > 1:
            raise ValueError("Confidence score must be between 0 and 1")
        return v


class FraudCaseSchema(BaseSchema):
    """Fraud case schema."""
    case_id: str = Field(..., description="Case identifier")
    user_id: Union[int, str] = Field(..., description="User identifier")
    case_type: FraudType = Field(..., description="Type of fraud")
    severity: SeverityLevel = Field(..., description="Case severity")
    status: CaseStatus = Field(..., description="Case status")
    risk_score: int = Field(..., ge=0, le=100, description="Risk score")
    title: str = Field(..., description="Case title")
    description: str = Field(..., description="Case description")
    created_at: datetime = Field(..., description="Case creation date")
    updated_at: datetime = Field(..., description="Last update date")
    assigned_to: Optional[Union[int, str]] = Field(None, description="Assigned analyst")
    detection_method: DetectionMethod = Field(..., description="Detection method")
    related_transactions: List[str] = Field(default_factory=list, description="Related transaction IDs")
    related_alerts: List[str] = Field(default_factory=list, description="Related alert IDs")
    evidence_summary: Dict[str, Any] = Field(default_factory=dict, description="Evidence summary")
    investigation_notes: Optional[str] = Field(None, description="Investigation notes")
    resolution: Optional[str] = Field(None, description="Case resolution")
    action_taken: Optional[str] = Field(None, description="Action taken")
    financial_impact: Optional[Decimal] = Field(None, description="Financial impact")
    regulatory_impact: bool = Field(False, description="Regulatory impact")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class FraudAlertSchema(BaseSchema):
    """Fraud alert schema."""
    alert_id: str = Field(..., description="Alert identifier")
    user_id: Union[int, str] = Field(..., description="User identifier")
    case_id: Optional[str] = Field(None, description="Related case ID")
    alert_type: AlertType = Field(..., description="Alert type")
    severity_score: int = Field(..., ge=0, le=100, description="Severity score")
    title: str = Field(..., description="Alert title")
    description: str = Field(..., description="Alert description")
    created_at: datetime = Field(..., description="Alert creation date")
    acknowledged: bool = Field(False, description="Whether alert is acknowledged")
    acknowledged_by: Optional[Union[int, str]] = Field(None, description="Acknowledged by")
    acknowledged_at: Optional[datetime] = Field(None, description="Acknowledgment date")
    resolved: bool = Field(False, description="Whether alert is resolved")
    resolved_by: Optional[Union[int, str]] = Field(None, description="Resolved by")
    resolved_at: Optional[datetime] = Field(None, description="Resolution date")
    trigger_data: Dict[str, Any] = Field(default_factory=dict, description="Trigger data")
    context: Dict[str, Any] = Field(default_factory=dict, description="Alert context")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class RiskProfileSchema(BaseSchema):
    """Risk profile schema."""
    profile_id: str = Field(..., description="Profile identifier")
    user_id: Union[int, str] = Field(..., description="User identifier")
    current_risk_score: int = Field(..., ge=0, le=100, description="Current risk score")
    risk_level: SeverityLevel = Field(..., description="Risk level")
    previous_risk_score: Optional[int] = Field(None, ge=0, le=100, description="Previous risk score")
    risk_trend: str = Field(..., description="Risk trend direction")
    last_updated: datetime = Field(..., description="Last update date")
    risk_factors: Dict[str, Any] = Field(default_factory=dict, description="Risk factors")
    behavioral_patterns: Dict[str, Any] = Field(default_factory=dict, description="Behavioral patterns")
    transaction_patterns: Dict[str, Any] = Field(default_factory=dict, description="Transaction patterns")
    device_patterns: Dict[str, Any] = Field(default_factory=dict, description="Device patterns")
    location_patterns: Dict[str, Any] = Field(default_factory=dict, description="Location patterns")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    monitoring_level: str = Field(..., description="Monitoring level")
    next_review_date: Optional[datetime] = Field(None, description="Next review date")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SanctionsScreeningSchema(BaseSchema):
    """Sanctions screening result schema."""
    screening_id: str = Field(..., description="Screening identifier")
    entity_id: Union[int, str] = Field(..., description="Entity identifier")
    entity_type: str = Field(..., description="Entity type")
    screened_at: datetime = Field(..., description="Screening timestamp")
    lists_checked: List[str] = Field(default_factory=list, description="Lists checked")
    matches: List[Dict[str, Any]] = Field(default_factory=list, description="Matches found")
    risk_score: int = Field(..., ge=0, le=100, description="Risk score")
    passed: bool = Field(..., description="Whether screening passed")
    requires_review: bool = Field(..., description="Whether manual review required")
    review_deadline: Optional[datetime] = Field(None, description="Review deadline")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ComplianceReportSchema(BaseSchema):
    """Compliance report schema."""
    report_id: str = Field(..., description="Report identifier")
    report_type: str = Field(..., description="Report type")
    period_start: datetime = Field(..., description="Period start date")
    period_end: datetime = Field(..., description="Period end date")
    generated_at: datetime = Field(..., description="Report generation date")
    generated_by: Union[int, str] = Field(..., description="Generated by")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Report summary")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Report metrics")
    findings: List[Dict[str, Any]] = Field(default_factory=list, description="Key findings")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    regulatory_requirements: List[Dict[str, Any]] = Field(default_factory=list, description="Regulatory requirements")
    compliance_score: Optional[float] = Field(None, ge=0, le=100, description="Compliance score")
    file_path: Optional[str] = Field(None, description="Report file path")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


# Request/Response schemas
class FraudDetectionRequestSchema(BaseSchema):
    """Fraud detection request schema."""
    user_id: Union[int, str] = Field(..., description="User identifier")
    transaction_data: TransactionSchema = Field(..., description="Transaction data")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    detection_methods: Optional[List[DetectionMethod]] = Field(None, description="Detection methods to use")
    priority: str = Field("normal", description="Detection priority")


class FraudDetectionResponseSchema(BaseSchema):
    """Fraud detection response schema."""
    success: bool = Field(..., description="Request success")
    detection_id: str = Field(..., description="Detection identifier")
    result: FraudDetectionResultSchema = Field(..., description="Detection result")
    processing_time_ms: float = Field(..., description="Processing time")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class CaseCreationRequestSchema(BaseSchema):
    """Case creation request schema."""
    user_id: Union[int, str] = Field(..., description="User identifier")
    case_type: FraudType = Field(..., description="Case type")
    severity: SeverityLevel = Field(..., description="Case severity")
    title: str = Field(..., description="Case title")
    description: str = Field(..., description="Case description")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Evidence")
    detection_method: DetectionMethod = Field(..., description="Detection method")
    related_transactions: List[str] = Field(default_factory=list, description="Related transactions")
    auto_assign: bool = Field(True, description="Auto-assign case")


class CaseCreationResponseSchema(BaseSchema):
    """Case creation response schema."""
    success: bool = Field(..., description="Creation success")
    case_id: str = Field(..., description="Created case ID")
    case: FraudCaseSchema = Field(..., description="Created case")
    message: str = Field(..., description="Response message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class RiskProfileUpdateRequestSchema(BaseSchema):
    """Risk profile update request schema."""
    user_id: Union[int, str] = Field(..., description="User identifier")
    update_trigger: str = Field(..., description="Update trigger")
    trigger_data: Optional[Dict[str, Any]] = Field(None, description="Trigger data")
    force_update: bool = Field(False, description="Force update")


class RiskProfileUpdateResponseSchema(BaseSchema):
    """Risk profile update response schema."""
    success: bool = Field(..., description="Update success")
    profile_id: str = Field(..., description="Profile ID")
    old_risk_score: Optional[int] = Field(None, description="Previous risk score")
    new_risk_score: int = Field(..., description="New risk score")
    risk_level: SeverityLevel = Field(..., description="Risk level")
    update_reason: str = Field(..., description="Update reason")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


# Analytics schemas
class FraudOverviewSchema(BaseSchema):
    """Fraud overview analytics schema."""
    period_days: int = Field(..., description="Analysis period in days")
    total_cases: int = Field(..., description="Total fraud cases")
    total_alerts: int = Field(..., description="Total fraud alerts")
    total_financial_loss: Decimal = Field(..., description="Total financial loss")
    average_risk_score: float = Field(..., description="Average risk score")
    cases_by_type: Dict[str, int] = Field(default_factory=dict, description="Cases by type")
    cases_by_severity: Dict[str, int] = Field(default_factory=dict, description="Cases by severity")
    trend_analysis: Dict[str, Any] = Field(default_factory=dict, description="Trend analysis")
    generated_at: datetime = Field(..., description="Generation timestamp")


class RiskDistributionSchema(BaseSchema):
    """Risk distribution analytics schema."""
    period_days: int = Field(..., description="Analysis period")
    distribution: Dict[str, int] = Field(default_factory=dict, description="Risk score distribution")
    percentiles: Dict[str, float] = Field(default_factory=dict, description="Risk score percentiles")
    changes: Dict[str, float] = Field(default_factory=dict, description="Risk score changes")
    generated_at: datetime = Field(..., description="Generation timestamp")


class AlertFrequencySchema(BaseSchema):
    """Alert frequency analytics schema."""
    period_days: int = Field(..., description="Analysis period")
    total_alerts: int = Field(..., description="Total alerts")
    alerts_by_type: Dict[str, int] = Field(default_factory=dict, description="Alerts by type")
    alerts_by_severity: Dict[str, int] = Field(default_factory=dict, description="Alerts by severity")
    hourly_distribution: Dict[str, int] = Field(default_factory=dict, description="Hourly distribution")
    daily_distribution: Dict[str, int] = Field(default_factory=dict, description="Daily distribution")
    generated_at: datetime = Field(..., description="Generation timestamp")


# Configuration schemas
class FraudRuleSchema(BaseSchema):
    """Fraud rule configuration schema."""
    rule_id: str = Field(..., description="Rule identifier")
    name: str = Field(..., description="Rule name")
    description: str = Field(..., description="Rule description")
    rule_type: str = Field(..., description="Rule type")
    conditions: Dict[str, Any] = Field(..., description="Rule conditions")
    actions: List[str] = Field(default_factory=list, description="Rule actions")
    priority: int = Field(..., ge=1, le=100, description="Rule priority")
    enabled: bool = Field(True, description="Rule enabled status")
    created_at: datetime = Field(..., description="Creation date")
    updated_at: datetime = Field(..., description="Last update date")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SystemConfigSchema(BaseSchema):
    """System configuration schema."""
    config_id: str = Field(..., description="Configuration identifier")
    config_type: str = Field(..., description="Configuration type")
    settings: Dict[str, Any] = Field(..., description="Configuration settings")
    enabled: bool = Field(True, description="Configuration enabled")
    version: str = Field(..., description="Configuration version")
    created_at: datetime = Field(..., description="Creation date")
    updated_at: datetime = Field(..., description="Last update date")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


# Utility schemas
class ErrorSchema(BaseSchema):
    """Error response schema."""
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Error message")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    timestamp: datetime = Field(..., description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request identifier")


class SuccessSchema(BaseSchema):
    """Success response schema."""
    success: bool = Field(True, description="Success status")
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    timestamp: datetime = Field(..., description="Response timestamp")
    request_id: Optional[str] = Field(None, description="Request identifier")


class PaginationSchema(BaseSchema):
    """Pagination schema."""
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Page size")
    total_count: int = Field(..., ge=0, description="Total count")
    total_pages: int = Field(..., ge=0, description="Total pages")
    has_next: bool = Field(..., description="Has next page")
    has_previous: bool = Field(..., description="Has previous page")


# Schema validation utilities
class SchemaValidator:
    """Schema validation utilities."""
    
    @staticmethod
    def validate_transaction(data: Dict[str, Any]) -> TransactionSchema:
        """Validate transaction data."""
        return TransactionSchema(**data)
    
    @staticmethod
    def validate_user_profile(data: Dict[str, Any]) -> UserProfileSchema:
        """Validate user profile data."""
        return UserProfileSchema(**data)
    
    @staticmethod
    def validate_fraud_detection_result(data: Dict[str, Any]) -> FraudDetectionResultSchema:
        """Validate fraud detection result."""
        return FraudDetectionResultSchema(**data)
    
    @staticmethod
    def validate_fraud_case(data: Dict[str, Any]) -> FraudCaseSchema:
        """Validate fraud case data."""
        return FraudCaseSchema(**data)
    
    @staticmethod
    def validate_fraud_alert(data: Dict[str, Any]) -> FraudAlertSchema:
        """Validate fraud alert data."""
        return FraudAlertSchema(**data)
    
    @staticmethod
    def validate_risk_profile(data: Dict[str, Any]) -> RiskProfileSchema:
        """Validate risk profile data."""
        return RiskProfileSchema(**data)
    
    @staticmethod
    def validate_sanctions_screening(data: Dict[str, Any]) -> SanctionsScreeningSchema:
        """Validate sanctions screening data."""
        return SanctionsScreeningSchema(**data)
    
    @staticmethod
    def validate_compliance_report(data: Dict[str, Any]) -> ComplianceReportSchema:
        """Validate compliance report data."""
        return ComplianceReportSchema(**data)


# Schema conversion utilities
class SchemaConverter:
    """Schema conversion utilities."""
    
    @staticmethod
    def to_dict(schema: BaseSchema) -> Dict[str, Any]:
        """Convert schema to dictionary."""
        return schema.dict()
    
    @staticmethod
    def to_json(schema: BaseSchema) -> str:
        """Convert schema to JSON string."""
        return schema.json()
    
    @staticmethod
    def from_dict(data: Dict[str, Any], schema_class: type) -> BaseSchema:
        """Create schema from dictionary."""
        return schema_class(**data)
    
    @staticmethod
    def from_json(json_str: str, schema_class: type) -> BaseSchema:
        """Create schema from JSON string."""
        return schema_class.parse_raw(json_str)


# Global instances
schema_validator = SchemaValidator()
schema_converter = SchemaConverter()


# Export all schemas
__all__ = [
    # Base schemas
    'BaseSchema',
    
    # Enum schemas
    'SeverityLevel',
    'FraudType',
    'DetectionMethod',
    'CaseStatus',
    'AlertType',
    
    # Core data schemas
    'AddressSchema',
    'DeviceSchema',
    'TransactionSchema',
    'UserProfileSchema',
    'FraudDetectionResultSchema',
    'FraudCaseSchema',
    'FraudAlertSchema',
    'RiskProfileSchema',
    'SanctionsScreeningSchema',
    'ComplianceReportSchema',
    
    # Request/Response schemas
    'FraudDetectionRequestSchema',
    'FraudDetectionResponseSchema',
    'CaseCreationRequestSchema',
    'CaseCreationResponseSchema',
    'RiskProfileUpdateRequestSchema',
    'RiskProfileUpdateResponseSchema',
    
    # Analytics schemas
    'FraudOverviewSchema',
    'RiskDistributionSchema',
    'AlertFrequencySchema',
    
    # Configuration schemas
    'FraudRuleSchema',
    'SystemConfigSchema',
    
    # Utility schemas
    'ErrorSchema',
    'SuccessSchema',
    'PaginationSchema',
    
    # Validation and conversion utilities
    'SchemaValidator',
    'SchemaConverter',
    'schema_validator',
    'schema_converter',
]
