import logging

logger = logging.getLogger(__name__)

# api/djoyalty/viewsets/core/EventViewSet.py
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
from ...models.core import Event
from ...serializers.EventSerializer import EventSerializer
from ...pagination import DjoyaltyPagePagination
from ...mixins import DjoyaltyBaseViewSet

class EventViewSet(DjoyaltyBaseViewSet, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Event.objects.all().order_by('-timestamp')
    serializer_class = EventSerializer
    pagination_class = DjoyaltyPagePagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['action', 'description', 'customer__code']
    ordering_fields = ['timestamp', 'action']

    def get_queryset(self):
        qs = super().get_queryset()
        action_filter = self.request.query_params.get('action')
        customer_id = self.request.query_params.get('customer')
        anonymous = self.request.query_params.get('anonymous')
        if action_filter:
            qs = qs.filter(action__icontains=action_filter)
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if anonymous == 'true':
            qs = qs.filter(customer=None)
        return qs.select_related('customer')

    @action(detail=False, methods=['get'])
    def by_action(self, request):
        """Events grouped and counted by action type।"""
        try:
            data = Event.objects.values('action').annotate(count=Count('id')).order_by('-count')
            return Response(list(data))
        except Exception as e:
            logger.error('EventViewSet.by_action error: %s', e)
            return Response({'error': str(e)}, status=500)
