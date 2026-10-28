# api/support/viewset_cap.py
import logging
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import OfferDispute, WithdrawalDispute, NetworkAnnouncement
from .throttling import DisputeSubmitThrottle

logger = logging.getLogger(__name__)


class OfferDisputeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    throttle_classes   = [DisputeSubmitThrottle]

    def get_queryset(self):
        if self.request.user.is_staff:
            return OfferDispute.objects.all().select_related('user', 'ticket')
        return OfferDispute.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        from .serializers import OfferDisputeSerializer
        return OfferDisputeSerializer

    def create(self, request, *args, **kwargs):
        from .services import offer_dispute_service
        result = offer_dispute_service.create(request.user, request.data)
        return Response({'success': 'error' not in result, **result}, status=201)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def approve(self, request, pk=None):
        dispute = self.get_object()
        if dispute.status == 'approved':
            return Response({'detail': 'Already approved.'}, status=400)
        from .integrations.integ_handler import integ_handler
        ok = integ_handler._auto_approve_dispute(dispute, dispute.ticket)
        return Response({'success': ok})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def reject(self, request, pk=None):
        from django.utils import timezone
        dispute = self.get_object()
        dispute.status      = 'rejected'
        dispute.resolved_at = timezone.now()
        dispute.agent_notes = request.data.get('reason', '')
        dispute.save(update_fields=['status', 'resolved_at', 'agent_notes'])
        return Response({'success': True})

    @action(detail=False, methods=['get'])
    def my(self, request):
        disputes = OfferDispute.objects.filter(user=request.user).order_by('-created_at')[:20]
        from .serializers import OfferDisputeSerializer
        return Response(OfferDisputeSerializer(disputes, many=True).data)


class NetworkAnnouncementViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = []

    def get_queryset(self):
        from django.utils import timezone
        from django.db.models import Q
        now = timezone.now()
        return NetworkAnnouncement.objects.filter(
            is_active=True
        ).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now)
        ).filter(
            Q(ends_at__isnull=True) | Q(ends_at__gte=now)
        ).order_by('-created_at')

    def get_serializer_class(self):
        from .serializers import NetworkAnnouncementSerializer
        return NetworkAnnouncementSerializer

    @action(detail=False, methods=['get'])
    def active(self, request):
        data = self.get_queryset()[:5]
        from .serializers import NetworkAnnouncementSerializer
        return Response(NetworkAnnouncementSerializer(data, many=True).data)