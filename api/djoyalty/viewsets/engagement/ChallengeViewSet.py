# api/djoyalty/viewsets/engagement/ChallengeViewSet.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from decimal import Decimal
from ...models.engagement import Challenge
from ...models.core import Customer
from ...serializers.ChallengeSerializer import ChallengeSerializer, ChallengeParticipantSerializer
from ...services.engagement.ChallengeService import ChallengeService
from ...pagination import DjoyaltyPagePagination

class ChallengeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Challenge.objects.all().order_by('-start_date')
    serializer_class = ChallengeSerializer
    pagination_class = DjoyaltyPagePagination

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        customer_id = request.data.get('customer_id')
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            participant = ChallengeService.join(customer, int(pk))
            return Response(ChallengeParticipantSerializer(participant).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        customer_id = request.data.get('customer_id')
        value = request.data.get('value', 0)
        customer = get_object_or_404(Customer, pk=customer_id)
        participant = ChallengeService.update_progress(customer, int(pk), Decimal(str(value)))
        if participant:
            return Response(ChallengeParticipantSerializer(participant).data)
        return Response({'error': 'Not a participant'}, status=status.HTTP_404_NOT_FOUND)
