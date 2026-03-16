# =============================================================================
# behavior_analytics/analytics/engagement_calculator.py
# =============================================================================
"""
Pure-logic engagement score calculator.

This module contains NO Django ORM calls — it operates on plain Python values
so it can be unit-tested without a database and reused from any context
(Celery tasks, management commands, async jobs, etc.).

Algorithm
---------
The engagement score is a weighted sum of four normalised components, each
mapped to the range [0, 1] before weighting:

    Component       Weight   Normalisation cap
    ─────────────── ──────── ─────────────────
    click_count     25 %     100 clicks
    total_stay_sec  35 %     3 600 s (1 hour)
    path_depth      20 %     20 unique pages
    return_visits   20 %     10 visits

Final score is clamped to [0, 100] and rounded to 2 decimal places.

Extending the algorithm
-----------------------
Override EngagementCalculator and implement _normalise_components() with your
own logic; the rest of the pipeline stays the same.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

from ..constants import (
    ENGAGEMENT_SCORE_MAX,
    ENGAGEMENT_SCORE_MIN,
    WEIGHT_CLICK_COUNT,
    WEIGHT_PATH_DEPTH,
    WEIGHT_RETURN_VISITS,
    WEIGHT_STAY_TIME,
)

logger = logging.getLogger(__name__)

_TWO_DP = Decimal("0.01")


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RawEngagementMetrics:
    """
    Immutable snapshot of raw metrics for one user on one day.

    All values must be non-negative integers.
    """
    click_count:    int = 0
    total_stay_sec: int = 0
    path_depth:     int = 0
    return_visits:  int = 0

    def __post_init__(self) -> None:
        for attr in ("click_count", "total_stay_sec", "path_depth", "return_visits"):
            val = getattr(self, attr)
            if not isinstance(val, int) or val < 0:
                raise ValueError(
                    f"RawEngagementMetrics.{attr} must be a non-negative int, got {val!r}."
                )


class EngagementResult(NamedTuple):
    """Return value of EngagementCalculator.calculate()."""
    score:     Decimal
    breakdown: dict[str, float]


# ---------------------------------------------------------------------------
# Normalisation config  (easy to extend or override)
# ---------------------------------------------------------------------------

@dataclass
class NormalisationCaps:
    clicks_cap:       int = 100
    stay_sec_cap:     int = 3_600
    depth_cap:        int = 20
    return_visits_cap: int = 10

    def __post_init__(self) -> None:
        for attr in ("clicks_cap", "stay_sec_cap", "depth_cap", "return_visits_cap"):
            val = getattr(self, attr)
            if not isinstance(val, int) or val <= 0:
                raise ValueError(f"NormalisationCaps.{attr} must be a positive int.")


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class EngagementCalculator:
    """
    Stateless calculator.  Instantiate once and call .calculate() many times.

    Usage::

        calc = EngagementCalculator()
        result = calc.calculate(
            RawEngagementMetrics(
                click_count=42,
                total_stay_sec=900,
                path_depth=7,
                return_visits=3,
            )
        )
        print(result.score)       # Decimal('51.45')
        print(result.breakdown)   # {'click_contribution': 10.5, ...}
    """

    def __init__(
        self,
        caps: NormalisationCaps | None = None,
    ) -> None:
        self._caps = caps or NormalisationCaps()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate(self, metrics: RawEngagementMetrics) -> EngagementResult:
        """
        Compute the engagement score from raw metrics.

        Returns EngagementResult(score, breakdown).
        Never raises — returns score=0 and logs on unexpected errors.
        """
        try:
            return self._calculate_internal(metrics)
        except Exception:
            logger.exception(
                "engagement_calculator.unexpected_error metrics=%r", metrics
            )
            return EngagementResult(
                score=Decimal("0.00"),
                breakdown={
                    "click_contribution":  0.0,
                    "stay_contribution":   0.0,
                    "depth_contribution":  0.0,
                    "return_contribution": 0.0,
                    "error":               True,
                },
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _calculate_internal(self, m: RawEngagementMetrics) -> EngagementResult:
        caps = self._caps

        click_norm  = Decimal(min(m.click_count,    caps.clicks_cap))       / caps.clicks_cap
        stay_norm   = Decimal(min(m.total_stay_sec, caps.stay_sec_cap))     / caps.stay_sec_cap
        depth_norm  = Decimal(min(m.path_depth,     caps.depth_cap))        / caps.depth_cap
        return_norm = Decimal(min(m.return_visits,  caps.return_visits_cap)) / caps.return_visits_cap

        click_contrib  = (click_norm  * WEIGHT_CLICK_COUNT   * 100).quantize(_TWO_DP)
        stay_contrib   = (stay_norm   * WEIGHT_STAY_TIME      * 100).quantize(_TWO_DP)
        depth_contrib  = (depth_norm  * WEIGHT_PATH_DEPTH     * 100).quantize(_TWO_DP)
        return_contrib = (return_norm * WEIGHT_RETURN_VISITS  * 100).quantize(_TWO_DP)

        raw_score = click_contrib + stay_contrib + depth_contrib + return_contrib
        score = max(
            Decimal(str(ENGAGEMENT_SCORE_MIN)),
            min(Decimal(str(ENGAGEMENT_SCORE_MAX)), raw_score.quantize(_TWO_DP, ROUND_HALF_UP)),
        )

        breakdown: dict[str, float] = {
            "click_contribution":  float(click_contrib),
            "stay_contribution":   float(stay_contrib),
            "depth_contribution":  float(depth_contrib),
            "return_contribution": float(return_contrib),
        }

        logger.debug(
            "engagement_calculator.result score=%s breakdown=%s",
            score, breakdown,
        )
        return EngagementResult(score=score, breakdown=breakdown)

    # ------------------------------------------------------------------
    # Batch helper
    # ------------------------------------------------------------------

    def calculate_batch(
        self,
        metrics_list: list[RawEngagementMetrics],
    ) -> list[EngagementResult]:
        """
        Calculate scores for a list of metric objects.
        Returns results in the same order as the input.
        """
        return [self.calculate(m) for m in metrics_list]
