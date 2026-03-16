# =============================================================================
# auto_mod/utils/ai_validator.py
# =============================================================================
"""
Validation utilities used by services and serializers to ensure that
AI-generated data (confidence scores, labels, scan results) is sane
before it is persisted or acted on.
"""

from __future__ import annotations

import re
from typing import Any

from ..constants import CONFIDENCE_MAX, CONFIDENCE_MIN, ML_IMAGE_MODEL_NAME, ML_TEXT_MODEL_NAME
from ..exceptions import InvalidConfidenceScoreError, InvalidSubmissionError


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

def validate_confidence(value: Any, field_name: str = "confidence") -> float:
    """
    Coerce and validate a confidence score.

    - Accepts int or float
    - Must be in [CONFIDENCE_MIN, CONFIDENCE_MAX]
    - Returns a rounded float(4 dp)

    Raises InvalidConfidenceScoreError on failure.
    """
    try:
        score = float(value)
    except (TypeError, ValueError):
        raise InvalidConfidenceScoreError(
            f"{field_name} must be a numeric value, got: {value!r}"
        )

    if not (CONFIDENCE_MIN <= score <= CONFIDENCE_MAX):
        raise InvalidConfidenceScoreError(
            f"{field_name} must be between {CONFIDENCE_MIN} and {CONFIDENCE_MAX}, "
            f"got: {score}"
        )
    return round(score, 4)


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

_VALID_LABEL_RE = re.compile(r"^[a-z][a-z0-9_]{0,49}$")
MAX_LABELS = 50


def validate_labels(labels: Any, field_name: str = "labels") -> list[str]:
    """
    Validate a list of label strings returned by an ML model.

    Rules:
      - Must be a list (or tuple/set — coerced to list)
      - At most MAX_LABELS items
      - Each label: lowercase alphanumeric + underscores, 1–50 chars
    """
    if not isinstance(labels, (list, tuple, set)):
        raise InvalidSubmissionError(
            f"{field_name} must be a list, got {type(labels).__name__}"
        )

    labels = [str(l).strip() for l in labels]

    if len(labels) > MAX_LABELS:
        raise InvalidSubmissionError(
            f"{field_name} may not contain more than {MAX_LABELS} items."
        )

    invalid = [l for l in labels if not _VALID_LABEL_RE.match(l)]
    if invalid:
        raise InvalidSubmissionError(
            f"{field_name} contains invalid label(s): {invalid[:5]!r}. "
            "Labels must be lowercase alphanumeric + underscores, 1–50 chars."
        )

    return labels


# ---------------------------------------------------------------------------
# Scan result
# ---------------------------------------------------------------------------

def validate_scan_result(result: Any) -> dict[str, Any]:
    """
    Validate the raw dict returned by an ML scan before persisting.

    Required fields: confidence, is_flagged, labels
    Optional: ocr_text, model_version, raw
    """
    if not isinstance(result, dict):
        raise InvalidSubmissionError("scan result must be a dict.")

    # confidence
    result["confidence"] = validate_confidence(
        result.get("confidence"), "scan_result.confidence"
    )

    # is_flagged
    if "is_flagged" not in result:
        raise InvalidSubmissionError("scan result missing 'is_flagged' field.")
    result["is_flagged"] = bool(result["is_flagged"])

    # labels
    result["labels"] = validate_labels(result.get("labels", []), "scan_result.labels")

    # ocr_text (optional)
    if "ocr_text" in result:
        result["ocr_text"] = str(result["ocr_text"])[:10_000]

    # model_version (optional)
    if "model_version" in result:
        result["model_version"] = str(result["model_version"])[:64]

    return result


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------

def validate_file_url(url: str) -> str:
    """
    Validate that a URL is a well-formed https URL pointing to a supported
    file extension.
    """
    from urllib.parse import urlparse
    from ..constants import SUPPORTED_IMAGE_FORMATS, SUPPORTED_DOC_FORMATS

    url = url.strip()
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise InvalidSubmissionError(
            f"File URL must use http or https scheme. Got: {parsed.scheme!r}"
        )

    if not parsed.netloc:
        raise InvalidSubmissionError("File URL is missing a host.")

    path_lower = parsed.path.lower().split("?")[0]
    ext = path_lower.rsplit(".", 1)[-1] if "." in path_lower else ""
    allowed = set(SUPPORTED_IMAGE_FORMATS) | set(SUPPORTED_DOC_FORMATS)

    if ext and ext not in allowed:
        raise InvalidSubmissionError(
            f"File extension '.{ext}' is not supported for AI scanning. "
            f"Allowed: {', '.join(sorted(allowed))}"
        )

    return url


# ---------------------------------------------------------------------------
# Model version
# ---------------------------------------------------------------------------

_KNOWN_MODELS = frozenset([ML_IMAGE_MODEL_NAME, ML_TEXT_MODEL_NAME])
_MODEL_VERSION_RE = re.compile(r"^[a-zA-Z0-9_\-:]{1,64}$")


def validate_model_version(version: str) -> str:
    version = str(version).strip()
    if not version:
        return ""
    if not _MODEL_VERSION_RE.match(version):
        raise InvalidSubmissionError(
            f"model_version contains invalid characters: {version!r}"
        )
    return version
