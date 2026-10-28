"""
api/tasks/endpoint.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Custom DRF APIView endpoints for one-off task system actions.
Not viewsets — these are single-purpose function-based views.
"""

import logging
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from api.tasks.permissions import CanCompleteTask, IsNotSuspended
from api.tasks.dependencies import get_client_ip, get_country_code, get_device_type

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def offerwall_view(request):
    """
    GET /tasks/offerwall/
    Returns ranked offer wall for the current user.
    """
    from api.tasks.offer_tasks import refresh_offer_feed
    from django.core.cache import cache

    country = get_country_code(request)
    device  = get_device_type(request)

    # Try cache first
    feed = cache.get(f'offer_feed_{country}_{device}')
    if feed is None:
        result = refresh_offer_feed.apply(kwargs={'country': country, 'device': device}).get()
        feed   = cache.get(f'offer_feed_{country}_{device}', [])

    # Personalize order for user
    user_id = request.user.pk
    try:
        from api.tasks.ml_tasks import run_offer_ranking
        ranked_ids = cache.get(f'ranked_offers_user_{user_id}')
        if ranked_ids:
            id_order = {oid: i for i, oid in enumerate(ranked_ids)}
            feed = sorted(feed, key=lambda o: id_order.get(o.get('id'), 9999))
    except Exception:
        pass

    return Response({
        'country': country,
        'device':  device,
        'offers':  feed[:50],
        'count':   len(feed),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, CanCompleteTask])
def complete_task_view(request, task_id: str):
    """
    POST /tasks/{task_id}/complete/
    Complete a specific task.
    """
    user_id    = request.user.pk
    ip_address = get_client_ip(request)
    device     = get_device_type(request)
    country    = get_country_code(request)

    try:
        from api.tasks.services.TaskService import TaskService
        result = TaskService().complete_task(
            task_id=task_id,
            user_id=user_id,
            ip_address=ip_address,
            device=device,
            country=country,
        )
        return Response(result)
    except Exception as e:
        return Response({'error': str(e)}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard_view(request):
    """
    GET /tasks/dashboard/
    Returns all user data in one call for the dashboard.
    """
    try:
        from api.tasks.integration.shared_context import SharedContext
        ctx    = SharedContext.for_user(request.user.pk)
        return Response(ctx.to_dict())
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_platform_stats_view(request):
    """
    GET /tasks/admin/stats/
    Returns comprehensive platform statistics.
    """
    try:
        from api.tasks.integration.data_bridge import DataBridge
        from django.core.cache import cache
        return Response({
            'platform':  DataBridge.get_platform_snapshot(),
            'workers':   cache.get('worker_health_all', {}),
            'dlq':       cache.get('dlq_stats', {}),
            'timestamp': timezone.now().isoformat(),
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)


class OfferWallAPIView(APIView):
    """Class-based offer wall view."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return offerwall_view(request._request)


__all__ = [
    'offerwall_view', 'complete_task_view', 'user_dashboard_view',
    'admin_platform_stats_view', 'OfferWallAPIView',
]
