# api/admin_panel/viewsets/FeatureFlagViewSet.py
"""FeatureFlagViewSet — CRUD + toggle + rollout management."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache

from ..models.config import FeatureFlag
from ..pagination import AdminPagination
from ..filters import FeatureFlagFilter, get_filter_for_model


class FeatureFlagViewSet(viewsets.ModelViewSet):
    """Manage feature flags with rollout percentage support."""
    permission_classes = [IsAdminUser]
    pagination_class = AdminPagination
    filterset_class = get_filter_for_model(FeatureFlag, FeatureFlagFilter)

    def get_serializer_class(self):
        from ..serializers.FeatureFlagSerializer import FeatureFlagSerializer
        return FeatureFlagSerializer

    def get_queryset(self):
        return FeatureFlag.objects.all().order_by('flag_key')

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle a feature flag on/off."""
        flag = self.get_object()
        flag.is_enabled = not flag.is_enabled
        flag.updated_by = request.user
        flag.save(update_fields=['is_enabled', 'updated_by', 'updated_at'])
        return Response({
            'success': True,
            'flag_key': flag.flag_key,
            'is_enabled': flag.is_enabled,
        })

    @action(detail=True, methods=['post'])
    def set_rollout(self, request, pk=None):
        """Set rollout percentage for a flag."""
        flag = self.get_object()
        pct = request.data.get('rollout_pct')
        if pct is None:
            return Response({'error': 'rollout_pct is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            pct = int(pct)
            if not (0 <= pct <= 100):
                raise ValueError
        except (ValueError, TypeError):
            return Response({'error': 'rollout_pct must be 0-100.'}, status=status.HTTP_400_BAD_REQUEST)

        flag.rollout_pct = pct
        flag.updated_by = request.user
        flag.save(update_fields=['rollout_pct', 'updated_by', 'updated_at'])
        return Response({'success': True, 'flag_key': flag.flag_key, 'rollout_pct': pct})

    @action(detail=False, methods=['get'])
    def all_states(self, request):
        """Get all flag key→enabled mappings (for client SDKs)."""
        flags = FeatureFlag.objects.filter(is_enabled=True)
        data = {f.flag_key: f.rollout_pct for f in flags}
        return Response({'success': True, 'flags': data})

    @action(detail=True, methods=['post'])
    def check_for_user(self, request, pk=None):
        """Check if flag is active for a specific user ID."""
        flag = self.get_object()
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(pk=user_id)
            is_active = flag.is_active_for_user(user)
            return Response({'flag_key': flag.flag_key, 'user_id': user_id, 'is_active': is_active})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def clear_cache(self, request):
        """Clear all feature flag cache entries."""
        flags = FeatureFlag.objects.values_list('flag_key', flat=True)
        for key in flags:
            cache.delete(f'admin_panel:feature_flag:{key}')
        cache.delete('admin_panel:feature_flags')
        return Response({'success': True, 'message': 'Feature flag cache cleared.'})