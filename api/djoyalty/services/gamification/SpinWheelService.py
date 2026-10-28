# api/djoyalty/services/gamification/SpinWheelService.py
"""
SpinWheelService -- Spin-the-wheel prize selection + award logic.
World reference: Voucherify spin-wheel, WooCommerce gamification.

Weighted random selection: each slice has a probability_weight;
higher weight = more likely to land on that slice.
"""
import logging
import random
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class SpinWheelService:

    @staticmethod
    def get_available_wheels(customer, tenant=None):
        """
        Customer-accessible spin wheels -- active, within validity window,
        and customer has spins remaining today.
        """
        try:
            from ...models.gamification import SpinWheelConfig
            from django.db.models import Q
            from django.utils import timezone as tz

            now = tz.now()
            qs = SpinWheelConfig.objects.filter(is_active=True).filter(
                Q(valid_from__isnull=True) | Q(valid_from__lte=now)
            ).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gte=now)
            )

            if tenant:
                qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))

            result = []
            for wheel in qs:
                spins_used_today = SpinWheelService.get_spins_used_today(customer, wheel)
                spins_remaining = max(0, wheel.spins_per_day - spins_used_today)
                result.append({
                    'wheel': wheel,
                    'spins_remaining': spins_remaining,
                    'spins_per_day': wheel.spins_per_day,
                })
            return result
        except Exception as e:
            logger.error('SpinWheelService.get_available_wheels error: %s', e)
            return []

    @staticmethod
    def get_spins_used_today(customer, wheel) -> int:
        """Count spins used by customer on this wheel today."""
        try:
            from ...models.gamification import SpinWheelResult
            return SpinWheelResult.objects.filter(
                customer=customer,
                wheel=wheel,
                spun_at__date=timezone.now().date(),
            ).count()
        except Exception as e:
            logger.error('SpinWheelService.get_spins_used_today error: %s', e)
            return 0

    @staticmethod
    @transaction.atomic
    def spin(customer, wheel_id: int, tenant=None) -> dict:
        """
        Execute one spin for customer.
        Returns: {'success': True, 'slice': {...}, 'prize_awarded': {...}}
        """
        try:
            from ...models.gamification import SpinWheelConfig, SpinWheelSlice, SpinWheelResult

            try:
                wheel = SpinWheelConfig.objects.get(id=wheel_id, is_active=True)
            except SpinWheelConfig.DoesNotExist:
                return {'success': False, 'error': 'Spin wheel not found or inactive'}

            # Check daily spin limit
            spins_used = SpinWheelService.get_spins_used_today(customer, wheel)
            if spins_used >= wheel.spins_per_day:
                return {
                    'success': False,
                    'error': f'Daily spin limit reached ({wheel.spins_per_day}/day)',
                }

            # Check min spend unlock (if applicable)
            if wheel.min_spend_to_unlock > 0:
                eligible = SpinWheelService._check_spend_unlock(customer, wheel)
                if not eligible:
                    return {
                        'success': False,
                        'error': f'Minimum spend of {wheel.min_spend_to_unlock} required to unlock spin',
                    }

            # Get slices with weights
            slices = list(SpinWheelSlice.objects.filter(wheel=wheel, is_active=True))
            if not slices:
                return {'success': False, 'error': 'No active slices on this wheel'}

            # Weighted random selection
            selected_slice = SpinWheelService._weighted_random_pick(slices)
            if not selected_slice:
                return {'success': False, 'error': 'Could not determine prize'}

            # Award prize
            prize_result = SpinWheelService._award_prize(customer, selected_slice, tenant)

            # Record result
            result = SpinWheelResult.objects.create(
                customer=customer,
                wheel=wheel,
                slice=selected_slice,
                prize_type=selected_slice.prize_type,
                prize_value=selected_slice.prize_value or Decimal('0'),
                points_awarded=prize_result.get('points_awarded', Decimal('0')),
                voucher=prize_result.get('voucher'),
                spun_at=timezone.now(),
            )

            logger.info('SpinWheelService.spin: %s spun wheel %s -> slice "%s"',
                        customer.code, wheel.name, selected_slice.label)

            return {
                'success': True,
                'result_id': result.id,
                'slice': {
                    'id': selected_slice.id,
                    'label': selected_slice.label,
                    'prize_type': selected_slice.prize_type,
                    'prize_value': str(selected_slice.prize_value or 0),
                },
                'prize_awarded': prize_result,
                'spins_remaining': max(0, wheel.spins_per_day - spins_used - 1),
            }

        except Exception as e:
            logger.error('SpinWheelService.spin error: %s', e)
            return {'success': False, 'error': str(e)}

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _weighted_random_pick(slices):
        """Pick a slice using probability_weight as weight."""
        try:
            weights = [float(getattr(s, 'probability_weight', 1) or 1) for s in slices]
            total = sum(weights)
            if total <= 0:
                return random.choice(slices)
            r = random.uniform(0, total)
            cumulative = 0
            for s, w in zip(slices, weights):
                cumulative += w
                if r <= cumulative:
                    return s
            return slices[-1]
        except Exception as e:
            logger.error('SpinWheelService._weighted_random_pick error: %s', e)
            return slices[0] if slices else None

    @staticmethod
    def _check_spend_unlock(customer, wheel) -> bool:
        """Check if customer's recent spend unlocks the wheel."""
        try:
            from ...models.core import Txn
            from django.utils import timezone as tz
            from datetime import timedelta
            recent = Txn.objects.filter(
                customer=customer,
                timestamp__gte=tz.now() - timedelta(days=1),
            ).aggregate(total=__import__('django.db.models', fromlist=['Sum']).Sum('total_amount'))
            total_spend = recent.get('total') or Decimal('0')
            return Decimal(str(total_spend)) >= wheel.min_spend_to_unlock
        except Exception:
            return True  # fail open

    @staticmethod
    def _award_prize(customer, slice_obj, tenant) -> dict:
        """Award the prize for landing on a slice."""
        prize_type = slice_obj.prize_type
        result = {'prize_type': prize_type}

        try:
            if prize_type == 'points':
                pts = slice_obj.prize_value or Decimal('0')
                from ...services.earn.BonusEventService import BonusEventService
                BonusEventService.award_bonus(
                    customer, pts,
                    reason=f'Spin wheel prize: {slice_obj.label}',
                    triggered_by='spin_wheel',
                    tenant=tenant,
                )
                result['points_awarded'] = pts
                result['message'] = f'{pts} পয়েন্ট জিতেছেন!'

            elif prize_type == 'voucher':
                from ...services.redemption.VoucherService import VoucherService
                voucher = VoucherService.create_reward_voucher(
                    customer=customer,
                    discount_value=slice_obj.prize_value or Decimal('0'),
                    source='spin_wheel',
                    tenant=tenant,
                )
                result['voucher'] = voucher
                result['message'] = f'Voucher জিতেছেন: {slice_obj.label}'

            elif prize_type == 'no_prize':
                result['message'] = 'Better luck next time!'

            else:
                result['message'] = f'Prize: {slice_obj.label}'

        except Exception as e:
            logger.error('SpinWheelService._award_prize error for type=%s: %s', prize_type, e)
            result['error'] = str(e)

        return result

    @staticmethod
    def claim_prize(result=None, result_id: int = None, customer=None) -> dict:
        """
        Alias -- after spin, explicitly claim/confirm the prize.
        In our system spin() already awards immediately, so this is a no-op confirm.
        Kept for API compatibility with GamificationViewSet.
        """
        try:
            from ...models.gamification import SpinWheelResult
            rid = result_id or (result.id if hasattr(result, 'id') else None)
            if rid:
                res = SpinWheelResult.objects.filter(id=rid).first()
                if res:
                    return {
                        'success': True,
                        'already_awarded': True,
                        'prize_type': res.prize_type,
                        'prize_value': str(res.prize_value or 0),
                        'points_awarded': str(res.points_awarded or 0),
                    }
            return {'success': True, 'already_awarded': True}
        except Exception as e:
            logger.error('SpinWheelService.claim_prize error: %s', e)
            return {'success': False, 'error': str(e)}
