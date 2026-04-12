from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import OfferPool, OfferPoolEntry
from ..serializers.OfferPoolEntrySerializer import OfferPoolEntrySerializer
from ..permissions import IsPublisher


class OfferPoolEntryViewSet(viewsets.ModelViewSet):
    """Manage individual offer entries within a SmartLink pool."""
    serializer_class = OfferPoolEntrySerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        sl_pk = self.kwargs.get('smartlink_pk')
        return OfferPoolEntry.objects.filter(
            pool__smartlink_id=sl_pk
        ).select_related('offer').order_by('-priority', '-weight')

    def perform_create(self, serializer):
        sl_pk = self.kwargs.get('smartlink_pk')
        pool = OfferPool.objects.get(smartlink_id=sl_pk)
        serializer.save(pool=pool)

    @action(detail=True, methods=['post'], url_path='toggle')
    def toggle(self, request, smartlink_pk=None, pk=None):
        """Toggle is_active for an entry."""
        entry = self.get_object()
        entry.is_active = not entry.is_active
        entry.save(update_fields=['is_active', 'updated_at'])
        return Response({'is_active': entry.is_active})

    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request, smartlink_pk=None):
        """Bulk-update priority/weight order for all entries."""
        entries_data = request.data.get('entries', [])
        for item in entries_data:
            OfferPoolEntry.objects.filter(pk=item['id']).update(
                weight=item.get('weight', 100),
                priority=item.get('priority', 0),
            )
        return Response({'status': 'reordered'})
