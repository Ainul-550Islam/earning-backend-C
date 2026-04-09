# api/djoyalty/services/points/PointsConversionService.py
import logging
from decimal import Decimal
from ...utils import calculate_points_value
from ...constants import DEFAULT_POINT_VALUE

logger = logging.getLogger(__name__)

class PointsConversionService:
    @staticmethod
    def points_to_currency(points: Decimal, point_value: Decimal = None) -> Decimal:
        pv = point_value or DEFAULT_POINT_VALUE
        return calculate_points_value(points, pv)

    @staticmethod
    def currency_to_points(amount: Decimal, earn_rate: Decimal = None) -> Decimal:
        from ...constants import DEFAULT_EARN_RATE
        rate = earn_rate or DEFAULT_EARN_RATE
        return (amount * rate).quantize(Decimal('0.01'))
