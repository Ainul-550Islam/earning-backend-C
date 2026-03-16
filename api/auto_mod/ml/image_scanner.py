# =============================================================================
# auto_mod/ml/image_scanner.py
# =============================================================================
"""
Image scanner ML module.

Responsibilities:
  - Download / load image from URL or bytes
  - Run inference using the configured image classification model
  - Run OCR extraction (delegated to OCRHelper)
  - Return a structured ScanResult

The actual model backend is pluggable:
  - Default: rule-based heuristic (no GPU required, for development)
  - Production: swap _load_model() to load a real TF/PyTorch/ONNX model
"""

from __future__ import annotations

import hashlib
import io
import logging
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from ..constants import (
    IMAGE_SCAN_TIMEOUT_SEC,
    MAX_IMAGE_DIMENSION_PX,
    ML_IMAGE_MODEL_NAME,
    OCR_CONFIDENCE_MIN,
    SUPPORTED_IMAGE_FORMATS,
)
from ..exceptions import MLModelLoadError, ScanFailedError, UnsupportedFileTypeError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImageScanResult:
    confidence:    float
    is_flagged:    bool
    labels:        list[str]      = field(default_factory=list)
    ocr_text:      str            = ""
    model_version: str            = ""
    raw:           dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ImageScanner
# ---------------------------------------------------------------------------

class ImageScanner:
    """
    Scan an image (by URL or raw bytes) for policy violations.

    Usage::

        scanner = ImageScanner()
        result  = scanner.scan("https://example.com/proof.jpg")
        if result.is_flagged:
            print(result.labels)
    """

    _instance: "ImageScanner | None" = None   # module-level singleton

    def __init__(self) -> None:
        self._model         = None
        self._model_version = "unloaded"
        self._load_model()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self, source: str | bytes) -> ImageScanResult:
        """
        Scan an image from a URL string or raw bytes.

        Returns ImageScanResult. Never raises — errors are encoded in
        the result (confidence=0, is_flagged=False, raw={'error': ...}).
        """
        start = time.monotonic()
        try:
            image_bytes = (
                self._fetch_url(source)
                if isinstance(source, str)
                else source
            )
            return self._run_inference(image_bytes, source_hint=str(source)[:80])
        except (ScanFailedError, UnsupportedFileTypeError):
            raise
        except Exception as exc:
            logger.exception("image_scanner.scan_error source=%s", str(source)[:80])
            return ImageScanResult(
                confidence=0.0,
                is_flagged=False,
                labels=[],
                raw={"error": str(exc), "duration_ms": int((time.monotonic() - start) * 1000)},
            )

    def scan_bytes(self, data: bytes, filename: str = "") -> ImageScanResult:
        """Scan raw bytes directly."""
        self._validate_format(filename)
        return self._run_inference(data, source_hint=filename)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """
        Load the image classification model.

        In development this is a no-op heuristic.
        In production, replace with:
            import onnxruntime as rt
            self._model = rt.InferenceSession("path/to/model.onnx")
        """
        try:
            # Stub: record model version from registry
            self._model_version = f"{ML_IMAGE_MODEL_NAME}:heuristic-v1"
            logger.info("image_scanner.model_loaded version=%s", self._model_version)
        except Exception as exc:
            raise MLModelLoadError(str(exc)) from exc

    def _fetch_url(self, url: str) -> bytes:
        """Download image bytes from URL with timeout."""
        self._validate_url_extension(url)
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "AutoMod-Scanner/1.0"},
            )
            with urllib.request.urlopen(req, timeout=IMAGE_SCAN_TIMEOUT_SEC) as resp:
                content_length = resp.headers.get("Content-Length")
                if content_length and int(content_length) > 20 * 1024 * 1024:
                    raise ScanFailedError("Image exceeds 20 MB limit.")
                return resp.read()
        except ScanFailedError:
            raise
        except Exception as exc:
            raise ScanFailedError(f"Failed to fetch image from URL: {exc}") from exc

    def _validate_url_extension(self, url: str) -> None:
        lower = url.lower().split("?")[0]
        ext   = lower.rsplit(".", 1)[-1]
        if ext not in SUPPORTED_IMAGE_FORMATS:
            raise UnsupportedFileTypeError(
                f"Extension '.{ext}' is not supported. "
                f"Supported: {', '.join(SUPPORTED_IMAGE_FORMATS)}"
            )

    def _validate_format(self, filename: str) -> None:
        if filename:
            ext = filename.lower().rsplit(".", 1)[-1]
            if ext not in SUPPORTED_IMAGE_FORMATS:
                raise UnsupportedFileTypeError(f"Extension '.{ext}' not supported.")

    def _run_inference(
        self,
        image_bytes: bytes,
        source_hint: str = "",
    ) -> ImageScanResult:
        """
        Run the actual model inference.

        Current implementation: deterministic heuristic based on image hash
        (development mode). Replace with real model inference in production.
        """
        if not image_bytes:
            raise ScanFailedError("Empty image data received.")

        # ------- OCR extraction (best-effort, never blocks decision) -------
        ocr_text = ""
        try:
            from ..utils.ocr_helper import OCRHelper
            ocr_result = OCRHelper().extract_text(image_bytes)
            if ocr_result.confidence >= OCR_CONFIDENCE_MIN:
                ocr_text = ocr_result.text
        except Exception:
            logger.debug("image_scanner.ocr_failed source=%s", source_hint)

        # ------- Heuristic inference (replace with real model) -------
        digest     = hashlib.md5(image_bytes).hexdigest()
        confidence = self._heuristic_confidence(image_bytes, digest)
        labels, is_flagged = self._heuristic_labels(confidence, ocr_text)

        return ImageScanResult(
            confidence=confidence,
            is_flagged=is_flagged,
            labels=labels,
            ocr_text=ocr_text,
            model_version=self._model_version,
            raw={
                "digest":         digest,
                "size_bytes":     len(image_bytes),
                "ocr_char_count": len(ocr_text),
                "source_hint":    source_hint,
            },
        )

    @staticmethod
    def _heuristic_confidence(data: bytes, digest: str) -> float:
        """
        Deterministic pseudo-confidence from image hash.
        Replace entirely with real model output in production.
        """
        score = int(digest[:4], 16) / 0xFFFF   # 0.0 – 1.0
        size_factor = min(len(data) / (500 * 1024), 1.0)   # larger → slightly higher
        return round(min(0.98, score * 0.6 + size_factor * 0.4), 4)

    @staticmethod
    def _heuristic_labels(confidence: float, ocr_text: str) -> tuple[list[str], bool]:
        labels:     list[str] = []
        is_flagged: bool      = False

        if confidence < 0.4:
            labels.append("low_quality")
            is_flagged = True
        elif confidence > 0.85:
            labels.append("clear_image")

        SUSPICIOUS_OCR_KEYWORDS = {"fake", "photoshop", "edited", "manipulated"}
        ocr_lower = ocr_text.lower()
        for kw in SUSPICIOUS_OCR_KEYWORDS:
            if kw in ocr_lower:
                labels.append("suspicious_text")
                is_flagged = True
                break

        return labels, is_flagged
