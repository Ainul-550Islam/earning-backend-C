import logging

logger = logging.getLogger(__name__)

# api/djoyalty/viewsets/engagement/StreakViewSet.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from ...models.engagement import DailyStreak
from ...models.core import Customer
from ...serializers.StreakSerializer import DailyStreakSerializer
from ...services.engagement.StreakService import StreakService
from ...pagination import DjoyaltyPagePagination
from ...mixins import DjoyaltyBaseViewSet

class StreakViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = DailyStreak.objects.all().select_related('customer').order_by('-current_streak')
    serializer_class = DailyStreakSerializer
    pagination_class = DjoyaltyPagePagination

    def get_queryset(self):
        qs = super().get_queryset()
        customer_id = self.request.query_params.get('customer')
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        return qs

    @action(detail=False, methods=['post'])
    def record_activity(self, request):
        """Customer এর daily activity record করো -- streak update।"""
        try:
            customer_id = request.data.get('customer_id')
            if not customer_id:
                return self.err('customer_id required')
            customer = get_object_or_404(Customer, pk=customer_id)
            streak = StreakService.record_activity(customer)
            return Response(DailyStreakSerializer(streak).data)
        except Exception as e:
            logger.error('StreakViewSet.record_activity error: %s', e)
            return Response({'error': str(e)}, status=500)
    @action(detail=False, methods=['get'], url_path='rewards')
    def rewards(self, request):
        """
        FIXED: StreakReward had NO API endpoint -- customers could not
        see what rewards await them at streak milestones.
        """
        from ...models.engagement import StreakReward
        qs = StreakReward.objects.filter(is_active=True).order_by('required_streak_days')
        return Response({'rewards': [{
            'id': r.id, 'required_streak_days': r.required_streak_days,
            'reward_type': r.reward_type,
            'points_reward': str(getattr(r, 'points_reward', 0)),
            'description': getattr(r, 'description', ''),
        } for r in qs]})

    @action(detail=False, methods=['get'], url_path='my-progress')
    def my_progress(self, request):
        """Customer's current streak + next milestone reward."""
        from ...models.engagement import StreakReward, DailyStreak
        cid = request.query_params.get('customer_id')
        if not cid:
            return self.err('customer_id required')
        streak = DailyStreak.objects.filter(customer_id=cid).first()
        current_days = streak.current_streak if streak else 0
        next_reward  = StreakReward.objects.filter(
            is_active=True, required_streak_days__gt=current_days
        ).order_by('required_streak_days').first()
        return Response({
            'current_streak_days': current_days,
            'next_milestone': {
                'required_days': next_reward.required_streak_days if next_reward else None,
                'reward_type':   next_reward.reward_type if next_reward else None,
                'days_needed':   (next_reward.required_streak_days - current_days) if next_reward else None,
            } if next_reward else None,
        })
