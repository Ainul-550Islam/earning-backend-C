"""
Flag Variant viewset for Feature Flags & A/B Testing.

FIX: added authentication/permissions (was missing) and pagination/filtering.
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from ..models.flag_variant import FlagVariant
from ..serializers.flag_variant_serializer import FlagVariantSerializer, FlagVariantListSerializer
from ..permissions import IsAuthenticated, CanViewFlags, CanEditFlags


class FlagVariantViewSet(viewsets.ModelViewSet):
    """
    Viewset for FlagVariant model.
    """

    queryset = FlagVariant.objects.all()
    serializer_class = FlagVariantSerializer
    permission_classes = [IsAuthenticated, CanViewFlags, CanEditFlags]

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['flag', 'is_active', 'is_control']
    ordering_fields = ['created_at', 'weight']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return FlagVariantListSerializer
        return FlagVariantSerializer

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a variant."""
        variant = self.get_object()
        variant.is_active = True
        variant.save()

        return Response({'success': True, 'message': f'Variant {variant.name} activated successfully'})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a variant."""
        variant = self.get_object()
        variant.is_active = False
        variant.save()

        return Response({'success': True, 'message': f'Variant {variant.name} deactivated successfully'})

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active variants."""
        flag_id = request.query_params.get('flag_id')

        if flag_id:
            variants = self.get_queryset().filter(flag_id=flag_id, is_active=True)
        else:
            variants = self.get_queryset().filter(is_active=True)

        page = self.paginate_queryset(variants)
        serializer = self.get_serializer(page if page is not None else variants, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def rebalance(self, request):
        """
        NEW: rebalance variant weights for a flag so they sum to 100
        proportionally to their current weights (previously documented in
        the audit as missing — Missing Endpoint: variant weight rebalance).
        """
        flag_id = request.data.get('flag_id')
        if not flag_id:
            return Response({'error': 'flag_id is required'}, status=400)

        variants = list(FlagVariant.objects.filter(flag_id=flag_id, is_active=True))
        total = sum(v.weight for v in variants)

        if total == 0 or not variants:
            return Response({'error': 'No active variants with nonzero weight to rebalance'}, status=400)

        updated = []
        for v in variants:
            v.weight = round(v.weight / total * 100)
            v.save(update_fields=['weight'])
            updated.append({'id': v.id, 'name': v.name, 'weight': v.weight})

        return Response({'success': True, 'variants': updated})
