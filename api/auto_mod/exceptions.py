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
