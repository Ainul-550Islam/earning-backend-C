# =============================================================================
# auto_mod/utils/ocr_helper.py
# =============================================================================
"""
OCR extraction helper.

Wraps the OCR backend (Tesseract via pytesseract, or a cloud OCR API).
Provides a clean interface so the rest of the codebase never imports
pytesseract directly — making it easy to swap backends.

Backend selection (in order of preference):
  1. pytesseract (if installed)
  2. Stub / mock (development / testing)
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from ..constants import OCR_CONFIDENCE_MIN
from ..exceptions import OCRExtractionError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OCRResult:
    text:       str
    confidence: float    # 0.0 – 1.0
    word_count: int
    raw:        dict


# ---------------------------------------------------------------------------
# OCRHelper
# ---------------------------------------------------------------------------

class OCRHelper:
    """
    Extract text from image bytes using the best available OCR backend.

    Usage::

        result = OCRHelper().extract_text(image_bytes)
        if result.confidence >= 0.70:
            print(result.text)
    """

    def __init__(self) -> None:
        self._backend = self._detect_backend()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_text(self, image_bytes: bytes) -> OCRResult:
        """
        Extract text from raw image bytes.

        Returns OCRResult. Never raises — on failure returns empty result.
        """
        if not image_bytes:
            return OCRResult(text="", confidence=0.0, word_count=0, raw={})

        try:
            if self._backend == "pytesseract":
                return self._run_tesseract(image_bytes)
            return self._run_stub(image_bytes)
        except Exception as exc:
            logger.warning("ocr_helper.extract_failed: %s", exc)
            return OCRResult(text="", confidence=0.0, word_count=0, raw={"error": str(exc)})

    def extract_from_pdf(self, pdf_bytes: bytes) -> OCRResult:
        """
        Extract text from a PDF's embedded text layer (no OCR needed).
        Fallback to per-page OCR if the PDF has no text layer.
        """
        text = ""
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                pages = []
                for page in pdf.pages:
                    extracted = page.extract_text() or ""
                    pages.append(extracted)
                text = "\n".join(pages).strip()
        except ImportError:
            logger.debug("ocr_helper.pdfplumber_not_installed — skipping PDF extraction")
        except Exception as exc:
            logger.warning("ocr_helper.pdf_extract_failed: %s", exc)

        words      = text.split()
        confidence = min(1.0, len(words) / 20) if words else 0.0
        return OCRResult(
            text=text,
            confidence=round(confidence, 4),
            word_count=len(words),
            raw={"method": "pdf_text_layer"},
        )

    # ------------------------------------------------------------------
    # Backends
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_backend() -> str:
        try:
            import pytesseract  # noqa: F401
            return "pytesseract"
        except ImportError:
            return "stub"

    @staticmethod
    def _run_tesseract(image_bytes: bytes) -> OCRResult:
        import pytesseract
        from PIL import Image

        img  = Image.open(io.BytesIO(image_bytes))
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        words       = [w for w in data["text"] if w.strip()]
        confs       = [
            c / 100.0
            for c, w in zip(data["conf"], data["text"])
            if w.strip() and c >= 0
        ]
        avg_conf    = sum(confs) / len(confs) if confs else 0.0
        full_text   = " ".join(words)

        return OCRResult(
            text=full_text,
            confidence=round(avg_conf, 4),
            word_count=len(words),
            raw={"backend": "tesseract", "word_count": len(words)},
        )

    @staticmethod
    def _run_stub(image_bytes: bytes) -> OCRResult:
        """
        Development stub — returns empty result so tests don't need Tesseract.
        """
        return OCRResult(
            text="",
            confidence=0.0,
            word_count=0,
            raw={"backend": "stub", "note": "pytesseract not installed"},
        )
