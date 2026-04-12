# =============================================================================
# promotions/performance_bonus/milestone_bonus.py
# Milestone Bonuses — MaxBounty style performance rewards
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


MILESTONES = [
    {'name': 'First Conversion', 'conversions': 1,    'bonus': Decimal('1.00'),    'badge': '🌟'},
    {'name': '10 Conversions',   'conversions': 10,   'bonus': Decimal('5.00'),    'badge': '⭐'},
    {'name': '50 Conversions',   'conversions': 50,   'bonus': Decimal('15.00'),   'badge': '🥉'},
    {'name': '100 Conversions',  'conversions': 100,  'bonus': Decimal('30.00'),   'badge': '🥈'},
    {'name': '500 Conversions',  'conversions': 500,  'bonus': Decimal('100.00'),  'badge': '🥇'},
    {'name': '1K Conversions',   'conversions': 1000, 'bonus': Decimal('250.00'),  'badge': '💎'},
    {'name': '5K Conversions',   'conversions': 5000, 'bonus': Decimal('1000.00'), 'badge': '👑'},

    {'name': '$10 Earned',       'earnings': Decimal('10'),    'bonus': Decimal('1.00'),   'badge': '💰'},
    {'name': '$100 Earned',      'earnings': Decimal('100'),   'bonus': Decimal('5.00'),   'badge': '💵'},
    {'name': '$500 Earned',      'earnings': Decimal('500'),   'bonus': Decimal('25.00'),  'badge': '💳'},
    {'name': '$1K Earned',       'earnings': Decimal('1000'),  'bonus': Decimal('50.00'),  'badge': '🏆'},
    {'name': '$5K Earned',       'earnings': Decimal('5000'),  'bonus': Decimal('200.00'), 'badge': '💎'},
    {'name': '$10K Earned',      'earnings': Decimal('10000'), 'bonus': Decimal('500.00'), 'badge': '👑'},
]


class MilestoneBonus:
    """Check and award milestone bonuses."""

    def check_and_award(self, user_id: int) -> list:
        """Check all milestones and award any newly reached ones."""
        from api.promotions.models import PromotionTransaction, TaskSubmission
        # Get current stats
        total_conversions = TaskSubmission.objects.filter(
            user_id=user_id, status='approved'
        ).count()
        total_earnings = PromotionTransaction.objects.filter(
            user_id=user_id, transaction_type='reward'
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        awarded = []
        for milestone in MILESTONES:
            if not self._is_already_awarded(user_id, milestone['name']):
                if 'conversions' in milestone and total_conversions >= milestone['conversions']:
                    self._award_bonus(user_id, milestone)
                    awarded.append(milestone)
                elif 'earnings' in milestone and total_earnings >= milestone['earnings']:
                    self._award_bonus(user_id, milestone)
                    awarded.append(milestone)
        return awarded

    def get_milestone_progress(self, user_id: int) -> dict:
        """Get all milestones with progress bars."""
        from api.promotions.models import PromotionTransaction, TaskSubmission
        total_conversions = TaskSubmission.objects.filter(
            user_id=user_id, status='approved'
        ).count()
        total_earnings = PromotionTransaction.objects.filter(
            user_id=user_id, transaction_type='reward'
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        result = []
        for m in MILESTONES:
            if 'conversions' in m:
                progress = min(total_conversions / m['conversions'] * 100, 100)
                current = total_conversions
                target = m['conversions']
                unit = 'conversions'
            else:
                progress = min(float(total_earnings / m['earnings'] * 100), 100)
                current = float(total_earnings)
                target = float(m['earnings'])
                unit = 'USD earned'

            result.append({
                'name': m['name'],
                'badge': m['badge'],
                'bonus': str(m['bonus']),
                'progress_pct': round(progress, 1),
                'current': current,
                'target': target,
                'unit': unit,
                'completed': progress >= 100,
                'awarded': self._is_already_awarded(user_id, m['name']),
            })
        return {
            'user_id': user_id,
            'milestones': result,
            'total_conversions': total_conversions,
            'total_earnings': str(total_earnings),
        }

    def _is_already_awarded(self, user_id: int, milestone_name: str) -> bool:
        from api.promotions.models import PromotionTransaction
        return PromotionTransaction.objects.filter(
            user_id=user_id,
            transaction_type='bonus',
            notes__icontains=milestone_name,
        ).exists()

    def _award_bonus(self, user_id: int, milestone: dict):
        from api.promotions.models import PromotionTransaction
        PromotionTransaction.objects.create(
            user_id=user_id,
            transaction_type='bonus',
            amount=milestone['bonus'],
            status='completed',
            notes=f"Milestone Bonus: {milestone['name']} {milestone['badge']}",
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def milestone_progress_view(request):
    bonus = MilestoneBonus()
    return Response(bonus.get_milestone_progress(request.user.id))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_milestones_view(request):
    bonus = MilestoneBonus()
    awarded = bonus.check_and_award(request.user.id)
    return Response({
        'newly_awarded': len(awarded),
        'milestones': [{'name': m['name'], 'bonus': str(m['bonus']), 'badge': m['badge']} for m in awarded],
    })
