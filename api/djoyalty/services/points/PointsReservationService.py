# api/djoyalty/services/points/PointsReservationService.py
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from ...models.points import PointsReservation
from ...exceptions import InsufficientPointsError, PointsReservationError

logger = logging.getLogger(__name__)

class PointsReservationService:
    @staticmethod
    @transaction.atomic
    def reserve(customer, points: Decimal, reference: str, hold_minutes: int = 30, tenant=None) -> PointsReservation:
        lp = customer.loyalty_points.first()
        if not lp or lp.balance < points:
            raise InsufficientPointsError(available=lp.balance if lp else 0, required=points)
        expires_at = timezone.now() + timedelta(minutes=hold_minutes)
        reservation = PointsReservation.objects.create(
            tenant=tenant or customer.tenant,
            customer=customer, points=points, reference=reference, expires_at=expires_at,
        )
        lp.balance -= points
        lp.save(update_fields=['balance', 'updated_at'])
        return reservation

    @staticmethod
    @transaction.atomic
    def release(reference: str):
        reservation = PointsReservation.objects.filter(reference=reference, is_released=False).first()
        if not reservation:
            return False
        lp = reservation.customer.loyalty_points.first()
        if lp:
            lp.balance += reservation.points
            lp.save(update_fields=['balance', 'updated_at'])
        reservation.is_released = True
        reservation.released_at = timezone.now()
        reservation.save(update_fields=['is_released', 'released_at'])
        return True

    @staticmethod
    @transaction.atomic
    def confirm(reference: str):
        reservation = PointsReservation.objects.filter(reference=reference, is_released=False).first()
        if not reservation:
            raise PointsReservationError('Reservation not found.')
        reservation.is_confirmed = True
        reservation.is_released = True
        reservation.released_at = timezone.now()
        reservation.save(update_fields=['is_confirmed', 'is_released', 'released_at'])
        return reservation
