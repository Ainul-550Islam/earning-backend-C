from typing import Dict, List, Any, Optional, Tuple, Union
from api.cms.permissions import IsOwnerOrAdmin, IsCMSAdmin
# api/cms/viewsets/PopupViewSet.py
"""
PopupViewSet: CRUD + stats + A/B test management for popups.
"""
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny

logger = logging.getLogger(__name__)


class PopupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for popup management.

    Endpoints:
        GET    /api/cms/popups/                  - List popups (admin)
        POST   /api/cms/popups/                  - Create popup (admin)
        GET    /api/cms/popups/{id}/             - Popup detail
        PUT    /api/cms/popups/{id}/             - Update popup (admin)
        DELETE /api/cms/popups/{id}/             - Delete popup (admin)
        GET    /api/cms/popups/active/           - Get active popups (public)
        POST   /api/cms/popups/{id}/record_view/  - Record view
        POST   /api/cms/popups/{id}/record_click/ - Record click
        POST   /api/cms/popups/{id}/record_dismiss/ - Record dismissal
        GET    /api/cms/popups/{id}/stats/       - Popup stats (admin)
        POST   /api/cms/popups/{id}/ab_test/     - Create A/B test (admin)
    """
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'title']
    ordering_fields = ['priority', 'created_at', 'total_views']
    ordering = ['-priority', '-created_at']

    def get_permissions(self):
        if self.action in ('active', 'record_view', 'record_click', 'record_dismiss'):
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        from api.cms.models_new.popup import Popup
        return Popup.objects.all().prefetch_related('rules', 'stats')

    def get_serializer_class(self):
        from api.cms.serializers import PopupSerializer
        return PopupSerializer

    def create(self, request, *args, **kwargs):
        from api.cms.services_new.PopupService import PopupService
        popup = PopupService.create_popup(request.data)
        if popup:
            return Response(self.get_serializer(popup).data, status=status.HTTP_201_CREATED)
        return Response({'error': 'Creation failed'}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        from api.cms.services_new.PopupService import PopupService
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        success = PopupService.update_popup(instance, data)
        if success:
            return Response(self.get_serializer(instance).data)
        return Response({'error': 'Update failed'}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        from api.cms.services_new.PopupService import PopupService
        instance = self.get_object()
        hard = request.query_params.get('hard', 'false') == 'true'
        PopupService.delete_popup(instance, hard=hard)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def active(self, request):
        """Get active popups for current page/user."""
        from api.cms.services_new.PopupService import PopupService
        user = request.user if request.user.is_authenticated else None
        page_url = request.query_params.get('page', '')
        popups = PopupService.get_active_popups(user=user, page_url=page_url)
        return Response(self.get_serializer(popups, many=True).data)

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def record_view(self, request, pk=None):
        from api.cms.services_new.PopupService import PopupService
        PopupService.record_view(self.get_object())
        return Response({'recorded': 'view'})

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def record_click(self, request, pk=None):
        from api.cms.services_new.PopupService import PopupService
        PopupService.record_click(self.get_object())
        return Response({'recorded': 'click'})

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def record_dismiss(self, request, pk=None):
        from api.cms.services_new.PopupService import PopupService
        PopupService.record_dismissal(self.get_object())
        return Response({'recorded': 'dismissal'})

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        from api.cms.services_new.PopupService import PopupService
        days = int(request.query_params.get('days', 30))
        return Response(PopupService.get_popup_stats(self.get_object(), days=days))

    @action(detail=True, methods=['post'])
    def ab_test(self, request, pk=None):
        from api.cms.services_new.PopupService import PopupService
        data = request.data
        test = PopupService.create_ab_test(
            popup=self.get_object(),
            name=data.get('name', ''),
            variant_a=data.get('variant_a', ''),
            variant_b=data.get('variant_b', ''),
            split_pct=float(data.get('split_pct', 50)),
        )
        if test:
            return Response({
                'id': test.id, 'name': test.name, 'status': test.status,
                'split_pct': test.split_pct,
            }, status=status.HTTP_201_CREATED)
        return Response({'error': 'A/B test creation failed'}, status=status.HTTP_400_BAD_REQUEST)
