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
from ...mixins import DjoyaltyBaseViewSet

class CampaignViewSet(DjoyaltyBaseViewSet, viewsets.ModelViewSet):
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
            return self.err(str(e))
    @action(detail=True, methods=['get', 'post'], url_path='segments', permission_classes=[IsLoyaltyAdmin])
    def segments(self, request, pk=None):
        """
        GET/POST campaign segments (audience targeting)。
        FIXED: CampaignSegment had NO API endpoint -- segment targeting
        only configurable through Django admin。
        """
        from ...models.campaigns import CampaignSegment
        campaign = get_object_or_404(LoyaltyCampaign, pk=pk)
        if request.method == 'GET':
            qs = CampaignSegment.objects.filter(campaign=campaign)
            return Response([{
                'id': s.id, 'segment_type': s.segment_type,
                'criteria': s.criteria if isinstance(s.criteria, dict) else {},
                'description': getattr(s, 'description', ''),
            } for s in qs])
        seg = CampaignSegment.objects.create(
            campaign=campaign,
            segment_type=request.data.get('segment_type', 'all'),
            criteria=request.data.get('criteria', {}),
        )
        return Response({'id': seg.id, 'segment_type': seg.segment_type},
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='participants')
    def participants(self, request, pk=None):
        """
        FIXED: CampaignParticipant had NO API endpoint -- participation
        data not queryable。 Now returns participation list with status。
        """
        from ...models.campaigns import CampaignParticipant
        campaign = get_object_or_404(LoyaltyCampaign, pk=pk)
        qs = CampaignParticipant.objects.filter(
            campaign=campaign
        ).select_related('customer').order_by('-joined_at')[:200]
        status_f = request.query_params.get('status')
        if status_f: qs = qs.filter(status=status_f)
        return Response({'count': qs.count(), 'participants': [{
            'id': p.id, 'customer_code': p.customer.code if p.customer else '',
            'status': p.status, 'points_earned': str(getattr(p, 'points_earned', 0)),
            'completed_at': str(getattr(p, 'completed_at', '')),
            'joined_at': str(p.joined_at),
        } for p in qs]})

    @action(detail=True, methods=['get'], url_path='stats')
    def campaign_stats(self, request, pk=None):
        """Campaign performance stats -- participants, conversions, points issued。"""
        from ...models.campaigns import CampaignParticipant
        campaign = get_object_or_404(LoyaltyCampaign, pk=pk)
        qs = CampaignParticipant.objects.filter(campaign=campaign)
        return Response({
            'campaign_id':   campaign.pk,
            'campaign_name': campaign.name,
            'total_participants':  qs.count(),
            'completed':          qs.filter(status='completed').count(),
            'in_progress':        qs.filter(status='in_progress').count(),
        })
