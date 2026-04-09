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

class StreakViewSet(viewsets.ReadOnlyModelViewSet):
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
        customer_id = request.data.get('customer_id')
        customer = get_object_or_404(Customer, pk=customer_id)
        streak = StreakService.record_activity(customer)
        return Response(DailyStreakSerializer(streak).data)
