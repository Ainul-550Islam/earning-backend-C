# =============================================================================
# auto_mod/ml/text_analyzer.py
# =============================================================================
"""
Text analysis ML module.

Responsibilities:
  - Tokenise and classify submission text
  - Detect spam, policy violations, fake content, inappropriate language
  - Return a structured TextAnalysisResult

Backend is pluggable:
  - Default: keyword + heuristic engine (no GPU, dev mode)
  - Production: swap _load_model() for a real NLP model
    (e.g. transformers BertForSequenceClassification, OpenAI moderation API)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from ..constants import (
    ML_MAX_TEXT_TOKENS,
    ML_TEXT_MODEL_NAME,
    MAX_SUBMISSION_TEXT_LENGTH,
)
from ..exceptions import MLModelLoadError, ScanFailedError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Heuristic keyword lists (extend in production via DB or config)
# ---------------------------------------------------------------------------

_SPAM_PATTERNS: list[str] = [
    r"\bclick\s+here\b", r"\bfree\s+money\b", r"\bmake\s+\$\d+",
    r"\bwork\s+from\s+home\b", r"\burgent\b.*\bwire\b",
    r"\bcongratulations\b.*\bwon\b",
]

_FAKE_PROOF_PATTERNS: list[str] = [
    r"\bphotoshopped?\b", r"\bedited\b.*\bscreenshot\b",
    r"\bmanipulated\b", r"\bfake\b.*\bproof\b",
]

_INAPPROPRIATE_PATTERNS: list[str] = [
    r"\bnsfw\b", r"\b18\+\b.*\bcontent\b",
]

_LOW_QUALITY_SIGNALS = frozenset(["n/a", "na", "none", "ok", "done", "yes", "no", "...", "test"])


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TextAnalysisResult:
    confidence:    float
    is_flagged:    bool
    labels:        list[str]      = field(default_factory=list)
    model_version: str            = ""
    raw:           dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# TextAnalyzer
# ---------------------------------------------------------------------------

class TextAnalyzer:
    """
    Analyse text for policy violations.

    Usage::

        analyzer = TextAnalyzer()
        result   = analyzer.analyze("I completed the task, see proof below.")
        if result.is_flagged:
            print(result.labels)
    """

    def __init__(self) -> None:
        self._model         = None
        self._model_version = "unloaded"
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        self._load_model()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, text: str) -> TextAnalysisResult:
        """
        Analyse `text` for moderation flags.

        Never raises — errors are returned in the result.
        """
        if not text or not text.strip():
            return TextAnalysisResult(
                confidence=1.0,
                is_flagged=False,
                labels=["empty_text"],
                model_version=self._model_version,
                raw={"token_count": 0},
            )

        # Truncate to model token limit
        text = self._truncate(text)

        try:
            return self._run_inference(text)
        except Exception as exc:
            logger.exception("text_analyzer.inference_error")
            return TextAnalysisResult(
                confidence=0.0,
                is_flagged=False,
                labels=[],
                raw={"error": str(exc)},
            )

    def analyze_batch(
        self, texts: list[str]
    ) -> list[TextAnalysisResult]:
        """Analyse multiple texts. Per-item errors do not abort the batch."""
        results = []
        for t in texts:
            try:
                results.append(self.analyze(t))
            except Exception as exc:
                logger.warning("text_analyzer.batch_item_error: %s", exc)
                results.append(
                    TextAnalysisResult(
                        confidence=0.0,
                        is_flagged=False,
                        raw={"error": str(exc)},
                    )
                )
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """
        Load / initialise the text classification model.

        Production replacement::
            from transformers import pipeline
            self._model = pipeline("text-classification", model="...")
        """
        try:
            self._compiled_patterns = {
                "spam":          [re.compile(p, re.I) for p in _SPAM_PATTERNS],
                "fake_proof":    [re.compile(p, re.I) for p in _FAKE_PROOF_PATTERNS],
                "inappropriate": [re.compile(p, re.I) for p in _INAPPROPRIATE_PATTERNS],
            }
            self._model_version = f"{ML_TEXT_MODEL_NAME}:heuristic-v1"
            logger.info("text_analyzer.model_loaded version=%s", self._model_version)
        except Exception as exc:
            raise MLModelLoadError(str(exc)) from exc

    def _truncate(self, text: str) -> str:
        """Truncate to MAX_SUBMISSION_TEXT_LENGTH characters."""
        if len(text) > MAX_SUBMISSION_TEXT_LENGTH:
            return text[:MAX_SUBMISSION_TEXT_LENGTH]
        return text

    def _run_inference(self, text: str) -> TextAnalysisResult:
        """
        Run classification.

        Current: deterministic keyword heuristic.
        Replace with real model call in production.
        """
        labels:       list[str] = []
        is_flagged:   bool      = False
        penalty:      float     = 0.0

        cleaned = text.strip().lower()

        # --- Pattern matching ---
        for category, patterns in self._compiled_patterns.items():
            for pat in patterns:
                if pat.search(cleaned):
                    labels.append(category)
                    is_flagged  = True
                    penalty    += 0.20
                    break

        # --- Low-quality signal ---
        word_count = len(cleaned.split())
        if word_count < 3 or cleaned in _LOW_QUALITY_SIGNALS:
            labels.append("low_quality")
            penalty += 0.15

        # --- Length penalty ---
        if word_count < 5:
            penalty += 0.10

        # --- Repetition detection ---
        if self._is_repetitive(cleaned):
            labels.append("repetitive_content")
            is_flagged = True
            penalty   += 0.25

        # Confidence = how "clean" the text appears
        confidence = round(max(0.0, min(1.0, 1.0 - penalty)), 4)

        # High-confidence clean result
        if not labels:
            labels.append("clean_text")

        return TextAnalysisResult(
            confidence=confidence,
            is_flagged=is_flagged,
            labels=labels,
            model_version=self._model_version,
            raw={
                "word_count":   word_count,
                "char_count":   len(text),
                "penalty":      round(penalty, 4),
            },
        )

    @staticmethod
    def _is_repetitive(text: str) -> bool:
        """Detect copy-pasted or bot-generated repetitive content."""
        words = text.split()
        if len(words) < 6:
            return False
        unique_ratio = len(set(words)) / len(words)
        return unique_ratio < 0.25
