# =============================================================================
# behavior_analytics/exceptions.py
# =============================================================================
"""
Custom exception hierarchy for the behavior_analytics application.

Design principles:
  - Every exception carries a machine-readable `code` for API consumers.
  - Base class inherits from both a domain base AND the appropriate DRF class
    so that DRF's exception handler picks them up automatically.
  - Use specific subclasses; never raise the base directly.
"""

from rest_framework.exceptions import APIException
from rest_framework import status


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class BehaviorAnalyticsError(APIException):
    """
    Root exception for all behavior_analytics domain errors.
    Never raise this directly — use a specific subclass.
    """
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail: str = "An unexpected analytics error occurred."
    default_code: str   = "analytics_error"


# ---------------------------------------------------------------------------
# Validation errors  (400)
# ---------------------------------------------------------------------------

class InvalidSessionError(BehaviorAnalyticsError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "The provided session identifier is invalid or malformed."
    default_code   = "invalid_session"


class InvalidPathDataError(BehaviorAnalyticsError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "User path data is invalid or exceeds maximum node count."
    default_code   = "invalid_path_data"


class InvalidClickMetricError(BehaviorAnalyticsError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Click metric data failed validation."
    default_code   = "invalid_click_metric"


class InvalidEngagementScoreError(BehaviorAnalyticsError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Engagement score must be between 0 and 100."
    default_code   = "invalid_engagement_score"


class StayTimeOutOfRangeError(BehaviorAnalyticsError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Stay time value is outside the acceptable range."
    default_code   = "stay_time_out_of_range"


# ---------------------------------------------------------------------------
# Not-found errors  (404)
# ---------------------------------------------------------------------------

class SessionNotFoundError(BehaviorAnalyticsError):
    status_code  = status.HTTP_404_NOT_FOUND
    default_detail = "The requested session could not be found."
    default_code   = "session_not_found"


class PathNotFoundError(BehaviorAnalyticsError):
    status_code  = status.HTTP_404_NOT_FOUND
    default_detail = "The requested user path does not exist."
    default_code   = "path_not_found"


class ReportNotFoundError(BehaviorAnalyticsError):
    status_code  = status.HTTP_404_NOT_FOUND
    default_detail = "The requested analytics report does not exist."
    default_code   = "report_not_found"


# ---------------------------------------------------------------------------
# Conflict / State errors  (409)
# ---------------------------------------------------------------------------

class DuplicateSessionError(BehaviorAnalyticsError):
    status_code  = status.HTTP_409_CONFLICT
    default_detail = "A session with this identifier already exists."
    default_code   = "duplicate_session"


class ReportAlreadyProcessingError(BehaviorAnalyticsError):
    status_code  = status.HTTP_409_CONFLICT
    default_detail = "A report for this period is already being generated."
    default_code   = "report_already_processing"


# ---------------------------------------------------------------------------
# Business-logic errors  (422)
# ---------------------------------------------------------------------------

class EngagementCalculationError(BehaviorAnalyticsError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Engagement score calculation failed due to insufficient data."
    default_code   = "engagement_calculation_failed"


class PathAnalysisError(BehaviorAnalyticsError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Path analysis could not be completed."
    default_code   = "path_analysis_failed"


# ---------------------------------------------------------------------------
# Rate-limit errors  (429)
# ---------------------------------------------------------------------------

class AnalyticsRateLimitError(BehaviorAnalyticsError):
    status_code  = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Analytics event rate limit exceeded. Please slow down."
    default_code   = "analytics_rate_limit"


# ---------------------------------------------------------------------------
# Internal / dependency errors  (503)
# ---------------------------------------------------------------------------

class AnalyticsStorageError(BehaviorAnalyticsError):
    status_code  = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Analytics storage backend is temporarily unavailable."
    default_code   = "analytics_storage_unavailable"


class ReportGenerationError(BehaviorAnalyticsError):
    status_code  = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Report generation service is currently unavailable."
    default_code   = "report_generation_failed"
