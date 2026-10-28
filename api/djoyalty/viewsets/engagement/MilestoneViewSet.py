import logging

logger = logging.getLogger(__name__)

# api/djoyalty/viewsets/engagement/MilestoneViewSet.py
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from decimal import Decimal
from ...models.engagement import Milestone, UserMilestone
from ...models.core import Customer
from ...serializers.MilestoneSerializer import MilestoneSerializer, UserMilestoneSerializer
from ...services.engagement.MilestoneService import MilestoneService
from ...pagination import DjoyaltyPagePagination
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet


class MilestoneViewSet(DjoyaltyBaseViewSet, viewsets.ModelViewSet):
    """
    Milestone CRUD + customer milestone check।
    GET /milestones/ -- all milestones
    GET /milestones/{id}/ -- milestone detail
    POST /milestones/ -- create (admin)
    POST /milestones/check/ -- check customer milestones
    GET /milestones/my_milestones/ -- customer's earned milestones
    """
    permission_classes = [IsAuthenticated]
    queryset = Milestone.objects.all().order_by('milestone_type', 'threshold')
    serializer_class = MilestoneSerializer
    pagination_class = DjoyaltyPagePagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'milestone_type']
    ordering_fields = ['threshold', 'points_reward', 'created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        milestone_type = self.request.query_params.get('milestone_type')
        is_active = self.request.query_params.get('is_active')
        if milestone_type:
            qs = qs.filter(milestone_type=milestone_type)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        return qs

    @action(detail=False, methods=['get'])
    def active(self, request):
        """All active milestones।"""
        try:
            qs = self.get_queryset().filter(is_active=True)
            return Response(self.get_serializer(qs, many=True).data)
        except Exception as e:
            logger.error('MilestoneViewSet.active error: %s', e)
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'])
    def check(self, request):
        """
        Customer এর milestones check করো।
        POST body: { customer_id, milestone_type, current_value }
        """
        customer_id = request.data.get('customer_id')
        milestone_type = request.data.get('milestone_type')
        current_value = request.data.get('current_value', 0)
        if not customer_id or not milestone_type:
            return self.err('customer_id and milestone_type required')
        try:
            customer = get_object_or_404(Customer, pk=customer_id)
            MilestoneService.check_milestones(customer, milestone_type, Decimal(str(current_value)))
            earned = UserMilestone.objects.filter(customer=customer).select_related('milestone')
            return Response({
                'message': 'Milestones checked.',
                'earned_milestones': UserMilestoneSerializer(earned, many=True).data,
            })
        except Exception as e:
            logger.error('MilestoneViewSet.check error: %s', e)
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'])
    def my_milestones(self, request):
        """Customer এর earned milestones।"""
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return self.err('customer_id required')
        try:
            customer = get_object_or_404(Customer, pk=customer_id)
            qs = UserMilestone.objects.filter(customer=customer).select_related('milestone').order_by('-achieved_at')
            page = self.paginate_queryset(qs)
            if page is not None:
                return self.get_paginated_response(UserMilestoneSerializer(page, many=True).data)
            return Response(UserMilestoneSerializer(qs, many=True).data)
        except Exception as e:
            logger.error('MilestoneViewSet.my_milestones error: %s', e)
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def award(self, request, pk=None):
        """Admin: manually award a milestone to a customer।"""
        customer_id = request.data.get('customer_id')
        try:
            customer = get_object_or_404(Customer, pk=customer_id)
            milestone = self.get_object()
            um, created = UserMilestone.objects.get_or_create(
                customer=customer,
                milestone=milestone,
                defaults={'points_awarded': milestone.points_reward},
            )
            if created and milestone.points_reward > 0:
                from ...services.earn.BonusEventService import BonusEventService
                BonusEventService.award_bonus(
                    customer, milestone.points_reward,
                    reason=f'Admin: Milestone awarded -- {milestone.name}',
                    triggered_by=str(request.user),
                )
            return Response(UserMilestoneSerializer(um).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        except Exception as e:
            logger.error('MilestoneViewSet.award error: %s', e)
            return Response({'error': str(e)}, status=500)
