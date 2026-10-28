"""
Pydantic schemas for Telemetry Observability.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class MetricType(str, Enum):
    """Metric type enum."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class LogLevel(str, Enum):
    """Log level enum."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class TraceStatus(str, Enum):
    """Trace status enum."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class AlertSeverity(str, Enum):
    """Alert severity enum."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status enum."""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class HealthStatus(str, Enum):
    """Health status enum."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class MetricEventSchema(BaseModel):
    """Schema for metric events."""
    
    name: str = Field(..., max_length=255)
    metric_type: MetricType = MetricType.COUNTER
    value: float
    unit: str = ""
    labels: Dict[str, Any] = {}
    source: str = "application"
    service: str = "default"
    environment: str = "production"
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        schema_extra = {
            "example": {
                "name": "http_request_duration",
                "metric_type": "gauge",
                "value": 123.45,
                "unit": "ms",
                "labels": {"method": "GET", "path": "/api/health"},
                "source": "middleware",
                "service": "django_app",
                "environment": "production"
            }
        }


class LogEntrySchema(BaseModel):
    """Schema for log entries."""
    
    level: LogLevel = LogLevel.INFO
    message: str = Field(..., max_length=10000)
    logger_name: str = ""
    source: str = "application"
    service: str = "default"
    environment: str = "production"
    timestamp: datetime = Field(default_factory=datetime.now)
    stack_trace: str = ""
    context: Dict[str, Any] = {}
    tags: List[str] = []
    
    class Config:
        schema_extra = {
            "example": {
                "level": "info",
                "message": "Request processed successfully",
                "logger_name": "django.request",
                "source": "middleware",
                "service": "django_app",
                "environment": "production",
                "context": {"method": "GET", "path": "/api/health"}
            }
        }


class TraceSpanSchema(BaseModel):
    """Schema for trace spans."""
    
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    operation_name: str = Field(..., max_length=255)
    service: str = "default"
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: TraceStatus = TraceStatus.SUCCESS
    tags: Dict[str, Any] = {}
    logs: List[Dict[str, Any]] = []
    context: Dict[str, Any] = {}
    
    class Config:
        schema_extra = {
            "example": {
                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                "span_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                "operation_name": "GET /api/health",
                "service": "django_app",
                "start_time": "2024-01-01T00:00:00",
                "duration_ms": 123.45,
                "status": "success"
            }
        }


class AlertSchema(BaseModel):
    """Schema for alerts."""
    
    name: str = Field(..., max_length=255)
    alert_type: str = "metric"
    severity: AlertSeverity = AlertSeverity.WARNING
    status: AlertStatus = AlertStatus.OPEN
    condition: Dict[str, Any] = {}
    message: str = Field(..., max_length=1000)
    source: str = "system"
    service: str = "default"
    environment: str = "production"
    triggered_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}
    
    class Config:
        schema_extra = {
            "example": {
                "name": "High Error Rate",
                "alert_type": "metric",
                "severity": "warning",
                "status": "open",
                "condition": {"metric_name": "error_rate", "threshold": 0.05},
                "message": "Error rate exceeded 5%",
                "source": "alerting",
                "service": "django_app"
            }
        }


class HealthStatusSchema(BaseModel):
    """Schema for health status."""
    
    service_name: str = Field(..., max_length=255)
    component_name: Optional[str] = None
    status: HealthStatus = HealthStatus.UNKNOWN
    health_score: int = Field(default=100, ge=0, le=100)
    last_check: datetime = Field(default_factory=datetime.now)
    uptime: float = 0.0
    response_time_ms: Optional[float] = None
    error_rate: float = 0.0
    metadata: Dict[str, Any] = {}
    environment: str = "production"
    
    class Config:
        schema_extra = {
            "example": {
                "service_name": "django_app",
                "status": "healthy",
                "health_score": 100,
                "uptime": 99.99,
                "response_time_ms": 45.67,
                "error_rate": 0.01
            }
        }


class DashboardWidgetSchema(BaseModel):
    """Schema for dashboard widgets."""
    
    name: str = Field(..., max_length=255)
    widget_type: str = "metric_card"
    data_source: str = "metric"
    query: Dict[str, Any] = {}
    config: Dict[str, Any] = {}
    position_x: int = 0
    position_y: int = 0
    width: int = Field(default=4, ge=1, le=12)
    height: int = Field(default=4, ge=1, le=12)
    refresh_interval: int = Field(default=60, ge=0)
    is_active: bool = True
    dashboard_id: Optional[int] = None
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Request Duration",
                "widget_type": "line_chart",
                "data_source": "metric",
                "query": {"metric_name": "http_request_duration"},
                "position_x": 0,
                "position_y": 0,
                "width": 6,
                "height": 4,
                "refresh_interval": 30
            }
        }


class MetricQuerySchema(BaseModel):
    """Schema for metric queries."""
    
    name: Optional[str] = None
    metric_type: Optional[MetricType] = None
    source: Optional[str] = None
    service: Optional[str] = None
    environment: Optional[str] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    aggregation: Optional[str] = "avg"
    
    class Config:
        schema_extra = {
            "example": {
                "name": "http_request_duration",
                "metric_type": "gauge",
                "service": "django_app",
                "aggregation": "avg"
            }
        }


class LogQuerySchema(BaseModel):
    """Schema for log queries."""
    
    level: Optional[LogLevel] = None
    message: Optional[str] = None
    source: Optional[str] = None
    service: Optional[str] = None
    environment: Optional[str] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=1000)
    
    class Config:
        schema_extra = {
            "example": {
                "level": "error",
                "service": "django_app",
                "limit": 50
            }
        }


class AlertQuerySchema(BaseModel):
    """Schema for alert queries."""
    
    alert_type: Optional[str] = None
    severity: Optional[AlertSeverity] = None
    status: Optional[AlertStatus] = None
    source: Optional[str] = None
    service: Optional[str] = None
    environment: Optional[str] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=1000)
    
    class Config:
        schema_extra = {
            "example": {
                "severity": "critical",
                "status": "open",
                "limit": 50
            }
        }


class StatisticsSchema(BaseModel):
    """Schema for statistics."""
    
    total_count: int
    period_hours: int
    breakdown: Dict[str, int] = {}
    
    class Config:
        schema_extra = {
            "example": {
                "total_count": 1000,
                "period_hours": 24,
                "breakdown": {"info": 800, "warning": 150, "error": 50}
            }
        }


class ResponseSchema(BaseModel):
    """Schema for API responses."""
    
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {}
            }
        }


class PaginationSchema(BaseModel):
    """Schema for pagination."""
    
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)
    total_count: int = 0
    total_pages: int = 0
    
    class Config:
        schema_extra = {
            "example": {
                "page": 1,
                "page_size": 50,
                "total_count": 100,
                "total_pages": 2
            }
        }


class PaginatedResponseSchema(BaseModel):
    """Schema for paginated responses."""
    
    success: bool = True
    data: List[Any] = []
    pagination: PaginationSchema
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "data": [],
                "pagination": {
                    "page": 1,
                    "page_size": 50,
                    "total_count": 100,
                    "total_pages": 2
                }
            }
        }
