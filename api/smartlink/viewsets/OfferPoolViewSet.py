from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import OfferPool, OfferPoolEntry
from ..serializers.OfferPoolSerializer import OfferPoolSerializer
from ..serializers.OfferPoolEntrySerializer import OfferPoolEntrySerializer
from ..permissions import IsPublisher, IsSmartLinkOwner
from ..services.rotation.CapTrackerService import CapTrackerService


class OfferPoolViewSet(viewsets.ModelViewSet):
    """Manage the offer pool for a SmartLink."""
    serializer_class = OfferPoolSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        sl_pk = self.kwargs.get('smartlink_pk')
        return OfferPool.objects.filter(smartlink_id=sl_pk)

    def perform_create(self, serializer):
        sl_pk = self.kwargs.get('smartlink_pk')
        serializer.save(smartlink_id=sl_pk)

    @action(detail=True, methods=['get'], url_path='cap-usage')
    def cap_usage(self, request, smartlink_pk=None, pk=None):
        """GET cap usage for all entries in this pool."""
        pool = self.get_object()
        cap_service = CapTrackerService()
        usage = [cap_service.get_usage(e) for e in pool.get_active_entries()]
        return Response(usage)


class OfferPoolEntryViewSet(viewsets.ModelViewSet):
    """Manage individual offer entries within a pool."""
    serializer_class = OfferPoolEntrySerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        sl_pk = self.kwargs.get('smartlink_pk')
        return OfferPoolEntry.objects.filter(pool__smartlink_id=sl_pk).select_related('offer')

    def perform_create(self, serializer):
        sl_pk = self.kwargs.get('smartlink_pk')
        pool = OfferPool.objects.get(smartlink_id=sl_pk)
        serializer.save(pool=pool)

    @action(detail=True, methods=['post'], url_path='toggle')
    def toggle(self, request, smartlink_pk=None, pk=None):
        entry = self.get_object()
        entry.is_active = not entry.is_active
        entry.save(update_fields=['is_active', 'updated_at'])
        return Response({'is_active': entry.is_active})
