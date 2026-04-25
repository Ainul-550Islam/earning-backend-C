# earning_backend/api/notifications/viewsets/NotificationCampaignViewSet.py
"""
NotificationCampaignViewSet — full CRUD + lifecycle actions for campaigns.

Endpoints:
  GET    /new-campaigns/                — list campaigns
  POST   /new-campaigns/                — create campaign
  GET    /new-campaigns/{id}/           — retrieve
  PUT    /new-campaigns/{id}/           — update (draft only)
  DELETE /new-campaigns/{id}/           — delete (draft/cancelled only)
  POST   /new-campaigns/{id}/start/     — start campaign
  POST   /new-campaigns/{id}/pause/     — pause running campaign
  POST   /new-campaigns/{id}/cancel/    — cancel campaign
  GET    /new-campaigns/{id}/stats/     — campaign stats
  POST   /new-campaigns/{id}/process/  — trigger processing (admin)
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone


class NotificationCampaignViewSet(viewsets.ModelViewSet):
    """ViewSet for the new NotificationCampaign model (models/campaign.py)."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'send_at', 'status', 'sent_count']
    ordering = ['-created_at']

    class _Pagination(PageNumberPagination):
        page_size = 20
        page_size_query_param = 'page_size'
        max_page_size = 100

    pagination_class = _Pagination

    def get_queryset(self):
        from notifications.models.campaign import NotificationCampaign
        qs = NotificationCampaign.objects.all().select_related('template', 'segment', 'created_by')

        campaign_status = self.request.query_params.get('status')
        if campaign_status:
            qs = qs.filter(status=campaign_status)

        return qs

    def get_serializer_class(self):
        from rest_framework import serializers
        from notifications.models.campaign import NotificationCampaign

        class CampaignSerializer(serializers.ModelSerializer):
            progress_pct = serializers.FloatField(read_only=True)
            created_by_name = serializers.SerializerMethodField()

            class Meta:
                model = NotificationCampaign
                fields = [
                    'id', 'name', 'description', 'status', 'send_at',
                    'total_users', 'sent_count', 'failed_count', 'progress_pct',
                    'context', 'started_at', 'completed_at', 'celery_task_id',
                    'created_by', 'created_by_name', 'created_at', 'updated_at',
                ]
                read_only_fields = [
                    'id', 'status', 'total_users', 'sent_count', 'failed_count',
                    'progress_pct', 'started_at', 'completed_at', 'celery_task_id',
                    'created_by', 'created_at', 'updated_at',
                ]

            def get_created_by_name(self, obj):
                return str(obj.created_by) if obj.created_by else ''

        return CampaignSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start a campaign."""
        from notifications.services.CampaignService import campaign_service
        result = campaign_service.start_campaign(int(pk))
        code = status.HTTP_200_OK if result['success'] else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause a running campaign."""
        from notifications.services.CampaignService import campaign_service
        result = campaign_service.pause_campaign(int(pk))
        code = status.HTTP_200_OK if result['success'] else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a campaign."""
        from notifications.services.CampaignService import campaign_service
        result = campaign_service.cancel_campaign(int(pk))
        code = status.HTTP_200_OK if result['success'] else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get campaign performance stats."""
        from notifications.services.CampaignService import campaign_service
        result = campaign_service.get_campaign_stats(int(pk))
        return Response(result)

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Manually trigger campaign processing (admin only)."""
        from notifications.tasks import process_campaign_task
        process_campaign_task.delay(int(pk))
        return Response({'success': True, 'message': 'Campaign processing task queued.'})
