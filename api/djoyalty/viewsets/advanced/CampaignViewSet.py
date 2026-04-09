# api/djoyalty/viewsets/advanced/CampaignViewSet.py
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from ...models.campaigns import LoyaltyCampaign
from ...models.core import Customer
from ...serializers.CampaignSerializer import LoyaltyCampaignSerializer
from ...services.advanced.CampaignService import CampaignService
from ...pagination import DjoyaltyPagePagination
from ...permissions import IsLoyaltyAdmin

class CampaignViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = LoyaltyCampaign.objects.all().order_by('-start_date')
    serializer_class = LoyaltyCampaignSerializer
    pagination_class = DjoyaltyPagePagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'campaign_type', 'status']

    @action(detail=False, methods=['get'])
    def active(self, request):
        tenant = getattr(request, 'tenant', None)
        campaigns = CampaignService.get_active_campaigns(tenant=tenant)
        return Response(LoyaltyCampaignSerializer(campaigns, many=True).data)

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        customer_id = request.data.get('customer_id')
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            participant = CampaignService.join_campaign(customer, int(pk))
            return Response({'message': 'Joined campaign'}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
