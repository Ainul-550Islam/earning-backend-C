# =============================================================================
# auto_mod/exceptions.py
# =============================================================================
"""
Custom exception hierarchy for the auto_mod application.
Every exception carries a machine-readable code for API consumers.
"""

from rest_framework import status
from rest_framework.exceptions import APIException


class AutoModError(APIException):
    """Root — never raise directly."""
    status_code  = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "An unexpected auto-moderation error occurred."
    default_code   = "auto_mod_error"


# ---------------------------------------------------------------------------
# 400 — Validation
# ---------------------------------------------------------------------------

class InvalidSubmissionError(AutoModError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Submission data is invalid or missing required fields."
    default_code   = "invalid_submission"


class InvalidRuleConfigError(AutoModError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Auto-approval rule configuration is invalid."
    default_code   = "invalid_rule_config"


class UnsupportedFileTypeError(AutoModError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "The uploaded file type is not supported for scanning."
    default_code   = "unsupported_file_type"


class FileTooLargeError(AutoModError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "The uploaded file exceeds the maximum allowed size."
    default_code   = "file_too_large"


class InvalidConfidenceScoreError(AutoModError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Confidence score must be between 0.0 and 1.0."
    default_code   = "invalid_confidence_score"


# ---------------------------------------------------------------------------
# Common exception aliases for backward compatibility
# ---------------------------------------------------------------------------

class ModerationError(AutoModError):
    """General moderation error."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Moderation operation failed."
    default_code = "moderation_error"


class ValidationError(AutoModError):
    """Validation error."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Validation failed."
    default_code = "validation_error"


class ServiceUnavailableError(AutoModError):
    """Service unavailable error."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Service is temporarily unavailable."
    default_code = "service_unavailable"


# ---------------------------------------------------------------------------
# 404 — Not found
# ---------------------------------------------------------------------------

class SubmissionNotFoundError(AutoModError):
    status_code  = status.HTTP_404_NOT_FOUND
    default_detail = "The requested submission could not be found."
    default_code   = "submission_not_found"


class RuleNotFoundError(AutoModError):
    status_code  = status.HTTP_404_NOT_FOUND
    default_detail = "The requested moderation rule does not exist."
    default_code   = "rule_not_found"


class BotNotFoundError(AutoModError):
    status_code  = status.HTTP_404_NOT_FOUND
    default_detail = "The requested TaskBot does not exist."
    default_code   = "bot_not_found"


# ---------------------------------------------------------------------------
# 409 — Conflict
# ---------------------------------------------------------------------------

class SubmissionAlreadyProcessedError(AutoModError):
    status_code  = status.HTTP_409_CONFLICT
    default_detail = "This submission has already been processed."
    default_code   = "submission_already_processed"


class RuleAlreadyExistsError(AutoModError):
    status_code  = status.HTTP_409_CONFLICT
    default_detail = "An active rule with this name/type already exists."
    default_code   = "rule_already_exists"


class BotAlreadyRunningError(AutoModError):
    status_code  = status.HTTP_409_CONFLICT
    default_detail = "A bot with this configuration is already running."
    default_code   = "bot_already_running"


# ---------------------------------------------------------------------------
# 422 — Business logic
# ---------------------------------------------------------------------------

class ScanFailedError(AutoModError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "AI scan could not be completed for this submission."
    default_code   = "scan_failed"


class OCRExtractionError(AutoModError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "OCR text extraction failed or returned no usable text."
    default_code   = "ocr_extraction_failed"


class RuleEvaluationError(AutoModError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Rule evaluation encountered an error."
    default_code   = "rule_evaluation_failed"


class ModelNotReadyError(AutoModError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "The ML model is not loaded or not ready for inference."
    default_code   = "model_not_ready"


# ---------------------------------------------------------------------------
# 429 — Rate limit
# ---------------------------------------------------------------------------

class ScanRateLimitError(AutoModError):
    status_code  = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many scan requests. Please wait before retrying."
    default_code   = "scan_rate_limit"


# ---------------------------------------------------------------------------
# 503 — Dependency failures
# ---------------------------------------------------------------------------

class AIServiceUnavailableError(AutoModError):
    status_code  = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The AI moderation service is temporarily unavailable."
    default_code   = "ai_service_unavailable"


class MLModelLoadError(AutoModError):
    status_code  = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Failed to load the ML model from storage."
    default_code   = "ml_model_load_failed"


# =============================================================================
# New Exception Classes for Enhanced Moderation System
# =============================================================================

# ---------------------------------------------------------------------------
# 400 — Validation Errors for New Models
# ---------------------------------------------------------------------------

class QueueAssignmentError(AutoModError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Cannot assign queue item to the specified moderator."
    default_code   = "queue_assignment_failed"

class InvalidQueuePriorityError(AutoModError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid queue priority specified."
    default_code   = "invalid_queue_priority"

class AppealCreationError(AutoModError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Cannot create appeal for this decision."
    default_code   = "appeal_creation_failed"

class InvalidAppealStatusError(AutoModError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid appeal status transition."
    default_code   = "invalid_appeal_status"

class InvalidDecisionTypeError(AutoModError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid decision type specified."
    default_code   = "invalid_decision_type"

class ModelVersionError(AutoModError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid ML model version configuration."
    default_code   = "model_version_error"

class InvalidSignalTypeError(AutoModError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid signal type specified."
    default_code   = "invalid_signal_type"

class SignalProcessingError(AutoModError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Signal processing failed due to invalid data."
    default_code   = "signal_processing_failed"

# ---------------------------------------------------------------------------
# 403 — Permission Errors for New Models
# ---------------------------------------------------------------------------

class QueueAssignmentPermissionError(AutoModError):
    status_code  = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to assign this queue item."
    default_code   = "queue_assignment_permission_denied"

class AppealReviewPermissionError(AutoModError):
    status_code  = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to review this appeal."
    default_code   = "appeal_review_permission_denied"

class ModelDeploymentPermissionError(AutoModError):
    status_code  = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to deploy ML models."
    default_code   = "model_deployment_permission_denied"

class DecisionOverridePermissionError(AutoModError):
    status_code  = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to override this decision."
    default_code   = "decision_override_permission_denied"

# ---------------------------------------------------------------------------
# 404 — Not Found Errors for New Models
# ---------------------------------------------------------------------------

class QueueItemNotFoundError(AutoModError):
    status_code  = status.HTTP_404_NOT_FOUND
    default_detail = "Queue item not found."
    default_code   = "queue_item_not_found"

class DecisionNotFoundError(AutoModError):
    status_code  = status.HTTP_404_NOT_FOUND
    default_detail = "Moderation decision not found."
    default_code   = "decision_not_found"

class AppealNotFoundError(AutoModError):
    status_code  = status.HTTP_404_NOT_FOUND
    default_detail = "Appeal not found."
    default_code   = "appeal_not_found"

class ModelVersionNotFoundError(AutoModError):
    status_code  = status.HTTP_404_NOT_FOUND
    default_detail = "ML model version not found."
    default_code   = "model_version_not_found"

class SignalNotFoundError(AutoModError):
    status_code  = status.HTTP_404_NOT_FOUND
    default_detail = "Content signal not found."
    default_code   = "signal_not_found"

# ---------------------------------------------------------------------------
# 409 — Conflict Errors for New Models
# ---------------------------------------------------------------------------

class QueueItemAlreadyAssignedError(AutoModError):
    status_code  = status.HTTP_409_CONFLICT
    default_detail = "Queue item is already assigned to another moderator."
    default_code   = "queue_item_already_assigned"

class AppealAlreadyExistsError(AutoModError):
    status_code  = status.HTTP_409_CONFLICT
    default_detail = "An appeal already exists for this decision."
    default_code   = "appeal_already_exists"

class DecisionAlreadyFinalError(AutoModError):
    status_code  = status.HTTP_409_CONFLICT
    default_detail = "Cannot modify a final decision."
    default_code   = "decision_already_final"

class ModelAlreadyDeployedError(AutoModError):
    status_code  = status.HTTP_409_CONFLICT
    default_detail = "Model version is already deployed."
    default_code   = "model_already_deployed"

class SignalAlreadyProcessedError(AutoModError):
    status_code  = status.HTTP_409_CONFLICT
    default_detail = "Signal has already been processed."
    default_code   = "signal_already_processed"

# ---------------------------------------------------------------------------
# 422 — Unprocessable Entity Errors for New Models
# ---------------------------------------------------------------------------

class QueueEscalationError(AutoModError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Cannot escalate queue item to the specified level."
    default_code   = "queue_escalation_failed"

class DecisionCreationError(AutoModError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Failed to create moderation decision."
    default_code   = "decision_creation_failed"

class AppealResolutionError(AutoModError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Failed to resolve appeal."
    default_code   = "appeal_resolution_failed"

class ModelTrainingError(AutoModError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "ML model training failed."
    default_code   = "model_training_failed"

class ModelDeploymentError(AutoModError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "ML model deployment failed."
    default_code   = "model_deployment_failed"

class SignalAggregationError(AutoModError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Failed to aggregate content signals."
    default_code   = "signal_aggregation_failed"

class WorkflowExecutionError(AutoModError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Moderation workflow execution failed."
    default_code   = "workflow_execution_failed"

# ---------------------------------------------------------------------------
# 429 — Rate Limit Errors for New Models
# ---------------------------------------------------------------------------

class QueueAssignmentRateLimitError(AutoModError):
    status_code  = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many queue assignment requests. Please wait before retrying."
    default_code   = "queue_assignment_rate_limit"

class AppealCreationRateLimitError(AutoModError):
    status_code  = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many appeal creation requests. Please wait before retrying."
    default_code   = "appeal_creation_rate_limit"

class ModelTrainingRateLimitError(AutoModError):
    status_code  = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many model training requests. Please wait before retrying."
    default_code   = "model_training_rate_limit"

# ---------------------------------------------------------------------------
# 503 — Service Unavailable Errors for New Models
# ---------------------------------------------------------------------------

class ModerationServiceUnavailableError(AutoModError):
    status_code  = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The moderation service is temporarily unavailable."
    default_code   = "moderation_service_unavailable"

class QueueServiceUnavailableError(AutoModError):
    status_code  = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The queue management service is temporarily unavailable."
    default_code   = "queue_service_unavailable"

class AppealServiceUnavailableError(AutoModError):
    status_code  = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The appeal service is temporarily unavailable."
    default_code   = "appeal_service_unavailable"

class MLServiceUnavailableError(AutoModError):
    status_code  = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The ML model service is temporarily unavailable."
    default_code   = "ml_service_unavailable"

class SignalProcessingServiceUnavailableError(AutoModError):
    status_code  = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The signal processing service is temporarily unavailable."
    default_code   = "signal_processing_service_unavailable"

# ---------------------------------------------------------------------------
# Business Logic Errors
# ---------------------------------------------------------------------------

class InsufficientModeratorCapacityError(AutoModError):
    status_code  = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "No moderators available with sufficient capacity."
    default_code   = "insufficient_moderator_capacity"

class EscalationThresholdExceededError(AutoModError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Maximum escalation level has been exceeded."
    default_code   = "escalation_threshold_exceeded"

class AppealTimeoutError(AutoModError):
    status_code  = status.HTTP_408_REQUEST_TIMEOUT
    default_detail = "Appeal review timeout has been exceeded."
    default_code   = "appeal_timeout"

class ModelPerformanceThresholdError(AutoModError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Model performance does not meet minimum thresholds."
    default_code   = "model_performance_threshold"

class SignalThresholdExceededError(AutoModError):
    status_code  = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Signal threshold has been exceeded."
    default_code   = "signal_threshold_exceeded"


# ---------------------------------------------------------------------------
# Appeal errors
# ---------------------------------------------------------------------------

class AppealProcessingError(AutoModError):
    """Raised when appeal processing fails (duplicate, expired, etc.)."""
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Appeal processing failed."
    default_code   = "appeal_processing_error"


# ---------------------------------------------------------------------------
# Bot errors
# ---------------------------------------------------------------------------

class BotNotReadyError(AutoModError):
    """Raised when a bot is not ready to process tasks."""
    status_code  = status.HTTP_409_CONFLICT
    default_detail = "Bot is not in a ready state to process tasks."
    default_code   = "bot_not_ready"


# ---------------------------------------------------------------------------
# Compliance errors
# ---------------------------------------------------------------------------

class ComplianceError(AutoModError):
    """Raised when a compliance check fails or compliance data is invalid."""
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "A compliance requirement was not met."
    default_code   = "compliance_error"

class ModelVersionError(AutoModError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Model version error."
    default_code = "model_version_error"

class ModelTrainingError(AutoModError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Model training error."
    default_code = "model_training_error"

class ModelAlreadyDeployedError(AutoModError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Model is already deployed."
    default_code = "model_already_deployed"

class ModelPerformanceThresholdError(AutoModError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Model does not meet performance threshold."
    default_code = "model_performance_threshold"

class OCRExtractionError(AutoModError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "OCR extraction failed."
    default_code = "ocr_extraction_error"

class UnsupportedFileTypeError(AutoModError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    default_detail = "Unsupported file type."
    default_code = "unsupported_file_type"

class QueueAssignmentError(AutoModError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Queue assignment failed."
    default_code = "queue_assignment_error"

class QueueEscalationError(AutoModError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Queue escalation failed."
    default_code = "queue_escalation_error"
