# =============================================================================
# promotions/postback_tools/postback_debugger.py
# Real-time postback log viewer — see all incoming postbacks
# =============================================================================
from django.core.cache import cache
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
import json


class PostbackDebugger:
    """Log and display all incoming postbacks for debugging."""
    INCOMING_PREFIX = 'incoming_postback:'

    def log_incoming(self, campaign_id: int, publisher_id: int, params: dict, ip: str, is_valid: bool):
        """Log an incoming postback for debugging."""
        entry = {
            'campaign_id': campaign_id,
            'publisher_id': publisher_id,
            'params': params,
            'ip': ip,
            'is_valid': is_valid,
            'received_at': timezone.now().isoformat(),
        }
        key = f'{self.INCOMING_PREFIX}{publisher_id}'
        logs = cache.get(key, [])
        logs.insert(0, entry)
        cache.set(key, logs[:100], timeout=3600 * 24 * 3)

    def get_publisher_postback_log(self, publisher_id: int, limit: int = 50) -> list:
        return cache.get(f'{self.INCOMING_PREFIX}{publisher_id}', [])[:limit]

    def get_all_recent_postbacks(self, limit: int = 100) -> list:
        """Admin: view all recent incoming postbacks."""
        return cache.get('admin_postback_log', [])[:limit]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_postback_log_view(request):
    debugger = PostbackDebugger()
    logs = debugger.get_publisher_postback_log(
        publisher_id=request.user.id,
        limit=int(request.query_params.get('limit', 50)),
    )
    return Response({'postbacks': logs, 'count': len(logs)})
