"""
Point Calculator — Computes adjusted point values applying ContestCycle multipliers.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from ..constants import MIN_POINTS_VALUE, MAX_POINTS_VALUE
from ..exceptions import InvalidPointsError

logger = logging.getLogger(__name__)


class PointCalculator:
    """
    Stateless calculator for computing effective points within a ContestCycle.

    Usage:
        calc = PointCalculator(cycle)
        effective = calc.calculate(base_points=100)
    """

    def __init__(self, cycle: Any) -> None:
        """
        Args:
            cycle: A ContestCycle instance.

        Raises:
            ValueError: If cycle is None or lacks a points_multiplier.
        """
        if cycle is None:
            raise ValueError("cycle must not be None.")
        multiplier = getattr(cycle, "points_multiplier", None)
        if multiplier is None:
            raise ValueError(
                f"cycle (id={getattr(cycle, 'id', '?')}) has no points_multiplier attribute."
            )
        try:
            self._multiplier = Decimal(str(multiplier))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid points_multiplier '{multiplier}' on cycle id={getattr(cycle, 'id', '?')}: {exc}"
            ) from exc

        if self._multiplier <= 0:
            raise ValueError(
                f"points_multiplier must be positive, got {self._multiplier}."
            )
        self._cycle = cycle

    @property
    def multiplier(self) -> Decimal:
        return self._multiplier

    def calculate(self, base_points: Any) -> int:
        """
        Apply the cycle multiplier to *base_points* and return the result as an int.

        The result is clamped to [MIN_POINTS_VALUE, MAX_POINTS_VALUE].

        Args:
            base_points: Raw integer points before multiplier.

        Returns:
            Effective integer points after multiplier and clamping.

        Raises:
            InvalidPointsError: If base_points is not numeric or is out of range.
        """
        if base_points is None:
            raise InvalidPointsError("base_points must not be None.")

        try:
            raw = Decimal(str(base_points))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise InvalidPointsError(
                f"base_points must be numeric, got {base_points!r}: {exc}"
            ) from exc

        if raw < MIN_POINTS_VALUE:
            raise InvalidPointsError(
                f"base_points={base_points} is below the minimum of {MIN_POINTS_VALUE}."
            )

        effective = (raw * self._multiplier).to_integral_value(rounding=ROUND_HALF_UP)
        # Clamp to allowed range
        effective = max(Decimal(MIN_POINTS_VALUE), min(Decimal(MAX_POINTS_VALUE), effective))
        result = int(effective)

        logger.debug(
            "PointCalculator: base=%s × multiplier=%s = %s (clamped=%s)",
            base_points,
            self._multiplier,
            effective,
            result,
        )
        return result

    def calculate_bulk(self, base_points_list: list[Any]) -> list[int]:
        """
        Apply multiplier to a list of base point values.

        Args:
            base_points_list: List of numeric point values.

        Returns:
            List of effective integer points in the same order.

        Raises:
            ValueError:        If base_points_list is not a list.
            InvalidPointsError: On any individual calculation failure.
        """
        if not isinstance(base_points_list, list):
            raise ValueError(
                f"base_points_list must be a list, got {type(base_points_list).__name__}."
            )
        return [self.calculate(bp) for bp in base_points_list]
