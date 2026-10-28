# api/djoyalty/services/ExperienceService.py
"""
ExperienceService -- Experiential reward booking and registration.
World reference: Antavo #1 differentiator 2024-2025 -- VIP events, early access,
exclusive experiences. Marriott Bonvoy hotel experiences, Starbucks reserve events.

Flow:
  1. get_experiences()  -> list available experiential rewards
  2. register()         -> customer redeems points to register for an experience
  3. cancel()           -> customer cancels registration (refunds points if policy allows)
  4. get_registrations()-> customer's current/past registrations
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class ExperienceService:

    @staticmethod
    def get_experiences(customer=None, tenant=None,
                         category: str = '', upcoming_only: bool = True) -> list:
        """
        Get available experiential rewards.
        Filters by tier eligibility, capacity, and date.
        """
        try:
            from ..models.family_eco import ExperientialReward
            from django.db.models import Q

            qs = ExperientialReward.objects.filter(is_active=True)
            if tenant:
                qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))
            if category:
                qs = qs.filter(category=category)
            if upcoming_only:
                qs = qs.filter(
                    Q(event_date__isnull=True) | Q(event_date__gte=timezone.now())
                )

            result = []
            for exp in qs.order_by('event_date', '-is_featured', 'points_cost'):
                # Capacity check
                registered = ExperienceService._get_registered_count(exp)
                capacity = getattr(exp, 'capacity', None)
                is_full = capacity is not None and registered >= capacity

                # Tier check
                tier_eligible = True
                if customer and getattr(exp, 'min_tier', None):
                    current_tier = customer.user_tiers.filter(
                        is_current=True
                    ).select_related('tier').first()
                    if current_tier:
                        tier_eligible = current_tier.tier.rank >= exp.min_tier.rank
                    else:
                        tier_eligible = False

                result.append({
                    'id': exp.id,
                    'name': exp.name,
                    'description': getattr(exp, 'description', ''),
                    'category': getattr(exp, 'category', ''),
                    'event_date': exp.event_date.isoformat() if exp.event_date else None,
                    'location': getattr(exp, 'location', ''),
                    'points_cost': str(exp.points_cost),
                    'capacity': capacity,
                    'registered_count': registered,
                    'is_full': is_full,
                    'is_featured': getattr(exp, 'is_featured', False),
                    'image_url': getattr(exp, 'image_url', ''),
                    'tier_eligible': tier_eligible,
                    'can_register': not is_full and tier_eligible,
                })

            return result

        except Exception as e:
            logger.error('ExperienceService.get_experiences error: %s', e)
            return []

    @staticmethod
    @transaction.atomic
    def register(customer, experience_id: int, tenant=None) -> dict:
        """
        Register customer for an experiential reward by spending points.
        Returns: {'success': True, 'registration_id': int, 'confirmation_code': str}
        """
        try:
            from ..models.family_eco import ExperientialReward, ExperientialRegistration
            from ..models.points import LoyaltyPoints, PointsLedger
            from ..choices import LEDGER_DEBIT
            import uuid

            try:
                exp = ExperientialReward.objects.select_for_update().get(
                    id=experience_id, is_active=True
                )
            except ExperientialReward.DoesNotExist:
                return {'success': False, 'error': 'Experience not found or inactive'}

            # Already registered?
            already = ExperientialRegistration.objects.filter(
                customer=customer,
                experience=exp,
                status__in=['confirmed', 'waitlisted'],
            ).exists()
            if already:
                return {'success': False, 'error': 'Already registered for this experience'}

            # Capacity check
            registered_count = ExperienceService._get_registered_count(exp)
            capacity = getattr(exp, 'capacity', None)
            waitlist_enabled = getattr(exp, 'waitlist_enabled', False)

            if capacity and registered_count >= capacity and not waitlist_enabled:
                return {'success': False, 'error': 'Experience is fully booked'}

            status = 'confirmed'
            if capacity and registered_count >= capacity and waitlist_enabled:
                status = 'waitlisted'

            # Check and deduct points
            points_cost = exp.points_cost or Decimal('0')
            if points_cost > 0:
                lp = LoyaltyPoints.objects.select_for_update().filter(
                    customer=customer
                ).first()
                if not lp or lp.balance < points_cost:
                    balance = lp.balance if lp else Decimal('0')
                    return {
                        'success': False,
                        'error': f'Insufficient points: {balance} / {points_cost} required',
                    }
                lp.debit(points_cost)

                PointsLedger.objects.create(
                    customer=customer,
                    tenant=tenant or getattr(customer, 'tenant', None),
                    txn_type=LEDGER_DEBIT,
                    source='experience_registration',
                    points=points_cost,
                    balance_after=lp.balance,
                    description=f'Experience registration: {exp.name}',
                )

            confirmation_code = f'EXP-{uuid.uuid4().hex[:8].upper()}'
            registration = ExperientialRegistration.objects.create(
                customer=customer,
                experience=exp,
                tenant=tenant or getattr(customer, 'tenant', None),
                confirmation_code=confirmation_code,
                points_paid=points_cost,
                status=status,
                registered_at=timezone.now(),
            )

            # Notify
            try:
                from .NotificationService import NotificationService
                NotificationService.send(
                    customer,
                    'badge_unlocked',
                    title='🎉 রেজিস্ট্রেশন নিশ্চিত!' if status == 'confirmed' else '⏳ ওয়েটলিস্টে যোগ দিয়েছেন',
                    body=f'{exp.name} -- কনফার্মেশন কোড: {confirmation_code}',
                    icon='🎟️',
                    metadata={'experience_id': experience_id, 'code': confirmation_code},
                )
            except Exception:
                pass

            logger.info('ExperienceService.register: %s -> %s status=%s',
                        customer.code, exp.name, status)

            return {
                'success': True,
                'registration_id': registration.id,
                'confirmation_code': confirmation_code,
                'status': status,
                'experience_name': exp.name,
                'event_date': exp.event_date.isoformat() if exp.event_date else None,
                'points_paid': str(points_cost),
            }

        except Exception as e:
            logger.error('ExperienceService.register error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    @transaction.atomic
    def cancel(customer, registration_id: int, tenant=None) -> dict:
        """
        Cancel an experience registration. Refunds points if within cancellation window.
        Returns: {'success': True, 'points_refunded': Decimal}
        """
        try:
            from ..models.family_eco import ExperientialRegistration

            try:
                reg = ExperientialRegistration.objects.select_for_update().get(
                    id=registration_id, customer=customer
                )
            except ExperientialRegistration.DoesNotExist:
                return {'success': False, 'error': 'Registration not found'}

            if reg.status == 'cancelled':
                return {'success': False, 'error': 'Already cancelled'}
            if reg.status == 'attended':
                return {'success': False, 'error': 'Cannot cancel after attending'}

            # Check refund policy -- refund if event is > 24h away
            points_refunded = Decimal('0')
            exp = reg.experience
            if exp.event_date and exp.event_date > timezone.now() + __import__('datetime').timedelta(hours=24):
                if reg.points_paid and reg.points_paid > 0:
                    from ..services.earn.BonusEventService import BonusEventService
                    BonusEventService.award_bonus(
                        customer, reg.points_paid,
                        reason=f'Experience cancellation refund: {exp.name}',
                        triggered_by='experience_cancel',
                        tenant=tenant,
                    )
                    points_refunded = reg.points_paid

            reg.status = 'cancelled'
            reg.cancelled_at = timezone.now()
            reg.save(update_fields=['status', 'cancelled_at'])

            logger.info('ExperienceService.cancel: %s cancelled %s, refunded %s pts',
                        customer.code, exp.name, points_refunded)

            return {
                'success': True,
                'registration_id': registration_id,
                'points_refunded': str(points_refunded),
                'refund_policy': 'full' if points_refunded > 0 else 'no_refund',
            }

        except Exception as e:
            logger.error('ExperienceService.cancel error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_registrations(customer, upcoming_only: bool = False) -> list:
        """Customer's experience registration history."""
        try:
            from ..models.family_eco import ExperientialRegistration
            qs = ExperientialRegistration.objects.filter(
                customer=customer
            ).select_related('experience').order_by('-registered_at')

            if upcoming_only:
                qs = qs.filter(
                    experience__event_date__gte=timezone.now(),
                    status='confirmed',
                )

            return list(qs.values(
                'id', 'experience__name', 'experience__event_date',
                'experience__location', 'confirmation_code',
                'points_paid', 'status', 'registered_at',
            ))
        except Exception as e:
            logger.error('ExperienceService.get_registrations error: %s', e)
            return []

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _get_registered_count(exp) -> int:
        """Count confirmed registrations for an experience."""
        try:
            from ..models.family_eco import ExperientialRegistration
            return ExperientialRegistration.objects.filter(
                experience=exp, status='confirmed',
            ).count()
        except Exception:
            return 0
