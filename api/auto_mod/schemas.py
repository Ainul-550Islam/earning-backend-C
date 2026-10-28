# =============================================================================
# auto_mod/schemas.py
# =============================================================================

"""
Data schemas and validation for auto moderation system.
Provides JSON schemas, validation rules, and data contracts.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
from django.utils import timezone

logger = logging.getLogger(__name__)


class BaseSchema(BaseModel):
    """Base schema with common fields."""
    
    class Config:
        extra = 'forbid'
        use_enum_values = True
        validate_assignment = True


class SubmissionSchema(BaseSchema):
    """Schema for submission data."""
    
    id: str = Field(..., description="Submission ID")
    user_id: str = Field(..., description="User ID")
    submission_type: str = Field(..., description="Type of submission")
    content: str = Field(..., description="Content text")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    risk_score: float = Field(ge=0.0, le=1.0, description="Risk score (0-1)")
    ai_confidence: float = Field(ge=0.0, le=1.0, description="AI confidence (0-1)")
    flag_reason: Optional[str] = Field(None, description="Reason for flag")
    status: str = Field(default="pending", description="Submission status")
    created_at: datetime = Field(default_factory=timezone.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=timezone.now, description="Update timestamp")
    
    @validator('submission_type')
    def validate_submission_type(cls, v):
        allowed_types = ['text', 'image', 'video', 'audio', 'document', 'comment', 'profile']
        if v not in allowed_types:
            raise ValueError(f"Invalid submission type: {v}")
        return v
    
    @validator('status')
    def validate_status(cls, v):
        allowed_statuses = ['pending', 'processing', 'approved', 'rejected', 'escalated', 'error']
        if v not in allowed_statuses:
            raise ValueError(f"Invalid status: {v}")
        return v


class DecisionSchema(BaseSchema):
    """Schema for moderation decision."""
    
    id: str = Field(..., description="Decision ID")
    submission_id: str = Field(..., description="Submission ID")
    decider_id: Optional[str] = Field(None, description="Decider ID")
    decision_type: str = Field(..., description="Decision type")
    confidence: float = Field(ge=0.0, le=1.0, description="Decision confidence")
    is_automated: bool = Field(default=True, description="Is automated decision")
    reason: Optional[str] = Field(None, description="Decision reason")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    decided_at: datetime = Field(default_factory=timezone.now, description="Decision timestamp")
    
    @validator('decision_type')
    def validate_decision_type(cls, v):
        allowed_types = ['approve', 'reject', 'escalate', 'flag', 'quarantine']
        if v not in allowed_types:
            raise ValueError(f"Invalid decision type: {v}")
        return v


class AppealSchema(BaseSchema):
    """Schema for appeal data."""
    
    id: str = Field(..., description="Appeal ID")
    original_decision_id: str = Field(..., description="Original decision ID")
    user_id: str = Field(..., description="User ID")
    reviewer_id: Optional[str] = Field(None, description="Reviewer ID")
    appeal_type: str = Field(..., description="Appeal type")
    status: str = Field(default="pending", description="Appeal status")
    reason: str = Field(..., description="Appeal reason")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Appeal evidence")
    created_at: datetime = Field(default_factory=timezone.now, description="Creation timestamp")
    reviewed_at: Optional[datetime] = Field(None, description="Review timestamp")
    review_reason: Optional[str] = Field(None, description="Review reason")
    
    @validator('appeal_type')
    def validate_appeal_type(cls, v):
        allowed_types = ['reconsider', 'escalation', 'procedural', 'content_review']
        if v not in allowed_types:
            raise ValueError(f"Invalid appeal type: {v}")
        return v
    
    @validator('status')
    def validate_status(cls, v):
        allowed_statuses = ['pending', 'under_review', 'approved', 'rejected', 'escalated']
        if v not in allowed_statuses:
            raise ValueError(f"Invalid status: {v}")
        return v


class QueueItemSchema(BaseSchema):
    """Schema for queue item."""
    
    id: str = Field(..., description="Queue item ID")
    submission_id: str = Field(..., description="Submission ID")
    decision_id: Optional[str] = Field(None, description="Decision ID")
    assigned_to_id: Optional[str] = Field(None, description="Assignee ID")
    assigned_by_id: Optional[str] = Field(None, description="Assigner ID")
    status: str = Field(default="pending", description="Queue status")
    priority: str = Field(default="normal", description="Priority level")
    escalation_level: int = Field(ge=1, le=5, default=1, description="Escalation level")
    due_date: Optional[datetime] = Field(None, description="Due date")
    created_at: datetime = Field(default_factory=timezone.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=timezone.now, description="Update timestamp")
    
    @validator('status')
    def validate_status(cls, v):
        allowed_statuses = ['pending', 'assigned', 'in_progress', 'completed', 'escalated', 'cancelled']
        if v not in allowed_statuses:
            raise ValueError(f"Invalid status: {v}")
        return v
    
    @validator('priority')
    def validate_priority(cls, v):
        allowed_priorities = ['low', 'normal', 'high', 'critical', 'urgent']
        if v not in allowed_priorities:
            raise ValueError(f"Invalid priority: {v}")
        return v


class TaskBotSchema(BaseSchema):
    """Schema for task bot."""
    
    id: str = Field(..., description="Bot ID")
    name: str = Field(..., description="Bot name")
    bot_type: str = Field(..., description="Bot type")
    status: str = Field(default="idle", description="Bot status")
    is_active: bool = Field(default=True, description="Is bot active")
    performance_score: float = Field(ge=0.0, le=1.0, default=0.5, description="Performance score")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Bot configuration")
    created_at: datetime = Field(default_factory=timezone.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=timezone.now, description="Update timestamp")
    
    @validator('bot_type')
    def validate_bot_type(cls, v):
        allowed_types = ['scanner', 'analyzer', 'reviewer', 'escalator', 'reporter']
        if v not in allowed_types:
            raise ValueError(f"Invalid bot type: {v}")
        return v
    
    @validator('status')
    def validate_status(cls, v):
        allowed_statuses = ['idle', 'running', 'stopped', 'error', 'maintenance']
        if v not in allowed_statuses:
            raise ValueError(f"Invalid status: {v}")
        return v


class AutoApprovalRuleSchema(BaseSchema):
    """Schema for auto-approval rule."""
    
    id: str = Field(..., description="Rule ID")
    name: str = Field(..., description="Rule name")
    rule_type: str = Field(..., description="Rule type")
    conditions: Dict[str, Any] = Field(..., description="Rule conditions")
    confidence_threshold: float = Field(ge=0.0, le=1.0, description="Confidence threshold")
    submission_type: Optional[str] = Field(None, description="Applicable submission type")
    is_active: bool = Field(default=True, description="Is rule active")
    priority: int = Field(ge=1, le=10, default=5, description="Rule priority")
    created_at: datetime = Field(default_factory=timezone.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=timezone.now, description="Update timestamp")
    
    @validator('rule_type')
    def validate_rule_type(cls, v):
        allowed_types = ['threshold', 'pattern', 'keyword', 'ml_model', 'composite']
        if v not in allowed_types:
            raise ValueError(f"Invalid rule type: {v}")
        return v


class ContentSignalSchema(BaseSchema):
    """Schema for content signal."""
    
    id: str = Field(..., description="Signal ID")
    submission_id: str = Field(..., description="Submission ID")
    signal_type: str = Field(..., description="Signal type")
    severity: str = Field(..., description="Signal severity")
    confidence: float = Field(ge=0.0, le=1.0, description="Signal confidence")
    details: Dict[str, Any] = Field(default_factory=dict, description="Signal details")
    created_at: datetime = Field(default_factory=timezone.now, description="Creation timestamp")
    
    @validator('signal_type')
    def validate_signal_type(cls, v):
        allowed_types = ['spam', 'hate_speech', 'violence', 'adult_content', 'harassment', 'fake_news']
        if v not in allowed_types:
            raise ValueError(f"Invalid signal type: {v}")
        return v
    
    @validator('severity')
    def validate_severity(cls, v):
        allowed_severities = ['low', 'medium', 'high', 'critical']
        if v not in allowed_severities:
            raise ValueError(f"Invalid severity: {v}")
        return v


class MLModelVersionSchema(BaseSchema):
    """Schema for ML model version."""
    
    id: str = Field(..., description="Model version ID")
    model_name: str = Field(..., description="Model name")
    version: str = Field(..., description="Model version")
    model_type: str = Field(..., description="Model type")
    is_active: bool = Field(default=True, description="Is model active")
    accuracy: Optional[float] = Field(ge=0.0, le=1.0, description="Model accuracy")
    precision: Optional[float] = Field(ge=0.0, le=1.0, description="Model precision")
    recall: Optional[float] = Field(ge=0.0, le=1.0, description="Model recall")
    f1_score: Optional[float] = Field(ge=0.0, le=1.0, description="F1 score")
    training_data_size: Optional[int] = Field(ge=0, description="Training data size")
    created_at: datetime = Field(default_factory=timezone.now, description="Creation timestamp")
    
    @validator('model_type')
    def validate_model_type(cls, v):
        allowed_types = ['text_classifier', 'image_classifier', 'hybrid', 'ensemble']
        if v not in allowed_types:
            raise ValueError(f"Invalid model type: {v}")
        return v


class WebhookSchema(BaseSchema):
    """Schema for webhook configuration."""
    
    id: str = Field(..., description="Webhook ID")
    name: str = Field(..., description="Webhook name")
    url: str = Field(..., description="Webhook URL")
    events: List[str] = Field(..., description="Events to trigger on")
    secret: Optional[str] = Field(None, description="Webhook secret")
    is_active: bool = Field(default=True, description="Is webhook active")
    retry_count: int = Field(ge=0, le=10, default=3, description="Retry count")
    timeout: int = Field(ge=1, le=300, default=30, description="Timeout in seconds")
    created_at: datetime = Field(default_factory=timezone.now, description="Creation timestamp")
    
    @validator('events')
    def validate_events(cls, v):
        allowed_events = [
            'submission_received', 'decision_made', 'appeal_created',
            'queue_assigned', 'bot_status_changed', 'rule_matched'
        ]
        for event in v:
            if event not in allowed_events:
                raise ValueError(f"Invalid event: {event}")
        return v


class FilterSchema(BaseSchema):
    """Schema for filter parameters."""
    
    status: Optional[str] = Field(None, description="Status filter")
    user_id: Optional[str] = Field(None, description="User ID filter")
    submission_type: Optional[str] = Field(None, description="Submission type filter")
    decision_type: Optional[str] = Field(None, description="Decision type filter")
    start_date: Optional[datetime] = Field(None, description="Start date filter")
    end_date: Optional[datetime] = Field(None, description="End date filter")
    min_risk_score: Optional[float] = Field(ge=0.0, le=1.0, description="Minimum risk score")
    max_risk_score: Optional[float] = Field(ge=0.0, le=1.0, description="Maximum risk score")
    page: int = Field(ge=1, default=1, description="Page number")
    page_size: int = Field(ge=1, le=100, default=20, description="Page size")
    ordering: Optional[str] = Field(None, description="Ordering field")
    
    @validator('ordering')
    def validate_ordering(cls, v):
        if v:
            allowed_fields = [
                'created_at', 'updated_at', 'risk_score', 'ai_confidence',
                '-created_at', '-updated_at', '-risk_score', '-ai_confidence'
            ]
            if v not in allowed_fields:
                raise ValueError(f"Invalid ordering field: {v}")
        return v


class BulkActionSchema(BaseSchema):
    """Schema for bulk actions."""
    
    action: str = Field(..., description="Action to perform")
    item_ids: List[str] = Field(..., min_items=1, description="Item IDs")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    
    @validator('action')
    def validate_action(cls, v):
        allowed_actions = [
            'approve', 'reject', 'escalate', 'assign', 'unassign', 'delete'
        ]
        if v not in allowed_actions:
            raise ValueError(f"Invalid action: {v}")
        return v


class AnalyticsQuerySchema(BaseSchema):
    """Schema for analytics queries."""
    
    metric: str = Field(..., description="Metric to query")
    dimension: Optional[str] = Field(None, description="Dimension for grouping")
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Additional filters")
    
    @validator('metric')
    def validate_metric(cls, v):
        allowed_metrics = [
            'submissions_count', 'decisions_count', 'approval_rate', 'rejection_rate',
            'avg_processing_time', 'error_rate', 'bot_performance', 'rule_effectiveness'
        ]
        if v not in allowed_metrics:
            raise ValueError(f"Invalid metric: {v}")
        return v


class ExportSchema(BaseSchema):
    """Schema for export requests."""
    
    scope: str = Field(..., description="Export scope")
    format: str = Field(..., description="Export format")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Export filters")
    start_date: Optional[datetime] = Field(None, description="Start date")
    end_date: Optional[datetime] = Field(None, description="End date")
    limit: Optional[int] = Field(ge=1, le=10000, description="Record limit")
    
    @validator('scope')
    def validate_scope(cls, v):
        allowed_scopes = [
            'submissions', 'decisions', 'appeals', 'queue', 'bots', 'rules', 'analytics', 'full_system'
        ]
        if v not in allowed_scopes:
            raise ValueError(f"Invalid scope: {v}")
        return v
    
    @validator('format')
    def validate_format(cls, v):
        allowed_formats = ['json', 'csv', 'xlsx', 'pdf']
        if v not in allowed_formats:
            raise ValueError(f"Invalid format: {v}")
        return v


# Schema registry for easy access
class SchemaRegistry:
    """Registry for all schemas."""
    
    SUBMISSION = SubmissionSchema
    DECISION = DecisionSchema
    APPEAL = AppealSchema
    QUEUE_ITEM = QueueItemSchema
    TASK_BOT = TaskBotSchema
    AUTO_APPROVAL_RULE = AutoApprovalRuleSchema
    CONTENT_SIGNAL = ContentSignalSchema
    ML_MODEL_VERSION = MLModelVersionSchema
    WEBHOOK = WebhookSchema
    FILTER = FilterSchema
    BULK_ACTION = BulkActionSchema
    ANALYTICS_QUERY = AnalyticsQuerySchema
    EXPORT = ExportSchema


# Utility functions
def validate_schema(schema_class: type, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate data against schema.
    
    Args:
        schema_class: Schema class to validate against
        data: Data to validate
        
    Returns:
        Validated data
    """
    try:
        return schema_class(**data).dict()
    except Exception as exc:
        logger.error(f"Schema validation failed: {exc}")
        raise ValueError(f"Validation error: {exc}")


def get_schema_info(schema_class: type) -> Dict[str, Any]:
    """
    Get schema information.
    
    Args:
        schema_class: Schema class
        
    Returns:
        Schema information
    """
    return {
        'name': schema_class.__name__,
        'fields': schema_class.__fields__,
        'config': schema_class.__config__,
    }


# Initialize logging
logger.info("Schemas module initialized with comprehensive data validation")
