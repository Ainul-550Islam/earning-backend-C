# api/djoyalty/services/CharityService.py
"""
CharityService -- Points-to-charity donation service.
World reference: Marriott Bonvoy charity donation, Sephora cause redemption,
Antavo charity redemption as top experiential reward 2024-2025.

Flow:
  1. get_causes()  -> list active charity causes with donation options
  2. donate()      -> customer donates points to a cause (converts to cash donation)
  3. get_history() -> customer's donation history + impact summary
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class CharityService:

    @staticmethod
    def get_causes(tenant=None, active_only: bool = True) -> list:
        """
        Get available charity causes for donation.
        Returns list of causes with min/max donation amounts.
        """
        try:
            from ..models.family_eco import CharityCause
            from django.db.models import Q

            qs = CharityCause.objects.all()
            if active_only:
                qs = qs.filter(is_active=True)
            if tenant:
                qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))

            return list(qs.order_by('sort_order', 'name').values(
                'id', 'name', 'description', 'category',
                'logo_url', 'website_url',
                'min_donation_points', 'max_donation_points',
                'points_to_currency_rate',
                'total_donated_points', 'total_donors',
                'impact_label',
            ))

        except Exception as e:
            logger.error('CharityService.get_causes error: %s', e)
            return []

    @staticmethod
    @transaction.atomic
    def donate(customer, cause_id: int, points: Decimal,
               message: str = '', tenant=None) -> dict:
        """
        Donate loyalty points to a charity cause.
        Deducts points from customer balance, records charity donation.
        Returns: {'success': True, 'donation_id': int, 'cash_equivalent': Decimal}
        """
        try:
            from ..models.family_eco import CharityCause, CharityDonation
            from ..models.points import LoyaltyPoints, PointsLedger
            from ..choices import LEDGER_DEBIT

            try:
                cause = CharityCause.objects.get(id=cause_id, is_active=True)
            except CharityCause.DoesNotExist:
                return {'success': False, 'error': 'Charity cause not found or inactive'}

            points = Decimal(str(points))

            # Validate donation amount
            min_pts = getattr(cause, 'min_donation_points', Decimal('100'))
            max_pts = getattr(cause, 'max_donation_points', None)

            if min_pts and points < min_pts:
                return {'success': False,
                        'error': f'Minimum donation is {min_pts} points'}
            if max_pts and points > max_pts:
                return {'success': False,
                        'error': f'Maximum donation is {max_pts} points'}

            # Check balance
            lp = LoyaltyPoints.objects.select_for_update().filter(
                customer=customer
            ).first()
            if not lp or lp.balance < points:
                balance = lp.balance if lp else Decimal('0')
                return {
                    'success': False,
                    'error': f'Insufficient points: {balance} / {points} required',
                }

            # Convert points to cash equivalent
            rate = getattr(cause, 'points_to_currency_rate', Decimal('0.01'))
            cash_equivalent = (points * Decimal(str(rate))).quantize(Decimal('0.01'))

            # Deduct points
            lp.debit(points)

            # Ledger entry
            PointsLedger.objects.create(
                customer=customer,
                tenant=tenant or getattr(customer, 'tenant', None),
                txn_type=LEDGER_DEBIT,
                source='charity_donation',
                points=points,
                balance_after=lp.balance,
                description=f'Charity donation: {cause.name} ({points} pts = {cash_equivalent})',
            )

            # Record donation
            donation = CharityDonation.objects.create(
                customer=customer,
                cause=cause,
                tenant=tenant or getattr(customer, 'tenant', None),
                points_donated=points,
                cash_equivalent=cash_equivalent,
                message=message or '',
                status='confirmed',
                donated_at=timezone.now(),
            )

            # Update cause totals
            cause.total_donated_points = (cause.total_donated_points or Decimal('0')) + points
            cause.total_donors = (cause.total_donors or 0) + 1
            cause.save(update_fields=['total_donated_points', 'total_donors'])

            # Notify customer
            try:
                from .NotificationService import NotificationService
                NotificationService.send(
                    customer, 'badge_unlocked',
                    title='❤️ ধন্যবাদ আপনার দানের জন্য!',
                    body=f'{cause.name} -- {points} পয়েন্ট = {cash_equivalent} টাকা দান করা হয়েছে।',
                    icon='❤️',
                    metadata={'cause_id': cause_id, 'points': str(points)},
                )
            except Exception:
                pass

            logger.info('CharityService.donate: %s donated %s pts to %s',
                        customer.code, points, cause.name)

            return {
                'success': True,
                'donation_id': donation.id,
                'cause_name': cause.name,
                'points_donated': str(points),
                'cash_equivalent': str(cash_equivalent),
                'new_balance': str(lp.balance),
            }

        except Exception as e:
            logger.error('CharityService.donate error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_history(customer, limit: int = 20) -> dict:
        """
        Customer's donation history with impact summary.
        Returns: {'donations': [...], 'total_points': Decimal, 'total_cash': Decimal}
        """
        try:
            from ..models.family_eco import CharityDonation
            from django.db.models import Sum

            qs = CharityDonation.objects.filter(customer=customer).order_by('-donated_at')

            aggregates = qs.aggregate(
                total_points=Sum('points_donated'),
                total_cash=Sum('cash_equivalent'),
            )

            donations = list(qs[:limit].values(
                'id', 'cause__name', 'cause__category', 'cause__logo_url',
                'points_donated', 'cash_equivalent', 'message',
                'status', 'donated_at',
            ))

            return {
                'donations': donations,
                'total_points': str(aggregates.get('total_points') or Decimal('0')),
                'total_cash_equivalent': str(aggregates.get('total_cash') or Decimal('0')),
                'total_donations': qs.count(),
            }

        except Exception as e:
            logger.error('CharityService.get_history error: %s', e)
            return {'donations': [], 'total_points': '0', 'total_cash_equivalent': '0'}
