# =============================================================================
# promotions/legal/tos_manager.py
# Terms of Service versioning — publisher must accept TOS to withdraw
# =============================================================================
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

CURRENT_TOS_VERSION = '3.0'
CURRENT_PRIVACY_VERSION = '2.0'


class TOSManager:
    def accept_tos(self, user_id: int, tos_version: str = None, ip: str = '') -> dict:
        version = tos_version or CURRENT_TOS_VERSION
        record = {
            'user_id': user_id, 'tos_version': version,
            'accepted_at': timezone.now().isoformat(), 'ip': ip,
        }
        cache.set(f'tos_accept:{user_id}', record, timeout=3600 * 24 * 365 * 10)
        return {'accepted': True, 'version': version, 'accepted_at': record['accepted_at']}

    def has_accepted_current_tos(self, user_id: int) -> bool:
        record = cache.get(f'tos_accept:{user_id}')
        return record is not None and record.get('tos_version') == CURRENT_TOS_VERSION

    def get_tos_status(self, user_id: int) -> dict:
        record = cache.get(f'tos_accept:{user_id}')
        return {
            'current_version': CURRENT_TOS_VERSION,
            'accepted': record is not None,
            'accepted_version': record.get('tos_version') if record else None,
            'needs_update': record is None or record.get('tos_version') != CURRENT_TOS_VERSION,
            'accepted_at': record.get('accepted_at') if record else None,
        }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_tos_view(request):
    mgr = TOSManager()
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    return Response(mgr.accept_tos(request.user.id, ip=ip))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tos_status_view(request):
    mgr = TOSManager()
    return Response(mgr.get_tos_status(request.user.id))
