# =============================================================================
# promotions/performance_bonus/tier_rewards.py
# Tier Rewards — Streak bonuses, approval rate bonuses, speed bonuses
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Count, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class TierRewardSystem:
    """
    Bonus rewards:
    - Streak bonus: consecutive days with approved submissions
    - Quality bonus: high approval rate
    - Speed bonus: fast submission turnaround
    - Loyalty bonus: years on platform
    """

    def calculate_streak_bonus(self, user_id: int) -> dict:
        """Check consecutive day activity streak."""
        from api.promotions.models import TaskSubmission
        streak = 0
        check_date = timezone.now().date()
        for i in range(90):  # Check up to 90 days back
            day_start = timezone.datetime.combine(check_date, timezone.datetime.min.time())
            day_end = day_start + timezone.timedelta(days=1)
            has_approval = TaskSubmission.objects.filter(
                user_id=user_id,
                status='approved',
                updated_at__gte=timezone.make_aware(day_start),
                updated_at__lt=timezone.make_aware(day_end),
            ).exists()
            if has_approval:
                streak += 1
                check_date -= timezone.timedelta(days=1)
            else:
                break
        bonus_amount = self._streak_to_bonus(streak)
        return {
            'streak_days': streak,
            'bonus_rate': str(bonus_amount),
            'bonus_description': f'{streak}-day streak bonus',
            'next_milestone': self._next_streak_milestone(streak),
        }

    def calculate_quality_bonus(self, user_id: int) -> dict:
        """Bonus for high approval rate."""
        from api.promotions.models import TaskSubmission
        subs = TaskSubmission.objects.filter(user_id=user_id)
        total = subs.count()
        approved = subs.filter(status='approved').count()
        if total == 0:
            return {'approval_rate': 0, 'bonus_rate': '0%', 'eligible': False}
        rate = approved / total * 100
        bonus_pct = 0
        if rate >= 95:
            bonus_pct = 15
        elif rate >= 90:
            bonus_pct = 10
        elif rate >= 85:
            bonus_pct = 5
        elif rate >= 80:
            bonus_pct = 2
        return {
            'approval_rate': round(rate, 2),
            'bonus_pct': bonus_pct,
            'bonus_description': f'{bonus_pct}% quality bonus on rewards',
            'eligible': bonus_pct > 0,
            'total_submissions': total,
            'approved': approved,
        }

    def get_full_bonus_summary(self, user_id: int) -> dict:
        """All bonuses combined."""
        streak = self.calculate_streak_bonus(user_id)
        quality = self.calculate_quality_bonus(user_id)
        total_bonus_pct = float(streak['bonus_rate'].replace('$', '')) + quality['bonus_pct']
        return {
            'user_id': user_id,
            'streak_bonus': streak,
            'quality_bonus': quality,
            'total_bonus_pct': total_bonus_pct,
            'summary': f'You are earning {total_bonus_pct:.1f}% extra on all rewards',
        }

    def _streak_to_bonus(self, streak: int) -> Decimal:
        if streak >= 30:
            return Decimal('0.15')
        elif streak >= 14:
            return Decimal('0.10')
        elif streak >= 7:
            return Decimal('0.05')
        elif streak >= 3:
            return Decimal('0.02')
        return Decimal('0')

    def _next_streak_milestone(self, current: int) -> dict:
        milestones = [3, 7, 14, 30]
        for m in milestones:
            if current < m:
                return {'days': m, 'days_remaining': m - current}
        return {'days': 30, 'days_remaining': 0}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bonus_summary_view(request):
    system = TierRewardSystem()
    return Response(system.get_full_bonus_summary(request.user.id))
