# api/djoyalty/viewsets/engagement/BadgeViewSet.py
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ...models.engagement import Badge, UserBadge
from ...serializers.BadgeSerializer import BadgeSerializer, UserBadgeSerializer
from ...pagination import DjoyaltyPagePagination

class BadgeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Badge.objects.all().order_by('name')
    serializer_class = BadgeSerializer
    pagination_class = DjoyaltyPagePagination
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'trigger']

    @action(detail=False, methods=['get'])
    def my_badges(self, request):
        customer_id = request.query_params.get('customer_id')
        qs = UserBadge.objects.filter(customer_id=customer_id).select_related('badge') if customer_id else UserBadge.objects.none()
        return Response(UserBadgeSerializer(qs, many=True).data)
