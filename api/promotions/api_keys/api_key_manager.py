# =============================================================================
# promotions/api_keys/api_key_manager.py
# API Key Management — Create, rotate, revoke API keys for publishers
# =============================================================================
import secrets
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


class APIKeyManager:
    KEY_PREFIX = 'apikey:'
    USER_KEYS_PREFIX = 'user_apikeys:'

    def create_key(self, user_id: int, name: str, permissions: list = None, rate_limit: int = 1000) -> dict:
        key = 'pk_live_' + secrets.token_urlsafe(40)
        key_hash = self._hash_key(key)
        key_data = {
            'key_hash': key_hash,
            'user_id': user_id,
            'name': name,
            'permissions': permissions or ['offers:read', 'stats:read'],
            'rate_limit_per_hour': rate_limit,
            'created_at': timezone.now().isoformat(),
            'last_used': None,
            'is_active': True,
            'total_requests': 0,
        }
        cache.set(f'{self.KEY_PREFIX}{key_hash}', key_data, timeout=3600 * 24 * 365 * 5)
        user_keys = cache.get(f'{self.USER_KEYS_PREFIX}{user_id}', [])
        user_keys.append({'name': name, 'key_hash': key_hash, 'created_at': key_data['created_at']})
        cache.set(f'{self.USER_KEYS_PREFIX}{user_id}', user_keys[-20:], timeout=3600 * 24 * 365 * 5)
        return {
            'api_key': key,
            'key_name': name,
            'permissions': key_data['permissions'],
            'rate_limit': f'{rate_limit} req/hour',
            'warning': 'Store this key securely — it will NOT be shown again!',
        }

    def verify_key(self, api_key: str) -> dict:
        key_hash = self._hash_key(api_key)
        key_data = cache.get(f'{self.KEY_PREFIX}{key_hash}')
        if not key_data or not key_data.get('is_active'):
            return None
        key_data['last_used'] = timezone.now().isoformat()
        key_data['total_requests'] += 1
        cache.set(f'{self.KEY_PREFIX}{key_hash}', key_data, timeout=3600 * 24 * 365 * 5)
        return key_data

    def revoke_key(self, user_id: int, key_hash: str) -> dict:
        key_data = cache.get(f'{self.KEY_PREFIX}{key_hash}')
        if not key_data or key_data.get('user_id') != user_id:
            return {'error': 'Key not found'}
        key_data['is_active'] = False
        key_data['revoked_at'] = timezone.now().isoformat()
        cache.set(f'{self.KEY_PREFIX}{key_hash}', key_data, timeout=3600 * 24 * 30)
        return {'success': True, 'key_hash': key_hash, 'status': 'revoked'}

    def list_user_keys(self, user_id: int) -> list:
        return cache.get(f'{self.USER_KEYS_PREFIX}{user_id}', [])

    def _hash_key(self, key: str) -> str:
        import hashlib
        return hashlib.sha256(key.encode()).hexdigest()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_api_key_view(request):
    manager = APIKeyManager()
    result = manager.create_key(
        user_id=request.user.id,
        name=request.data.get('name', 'My API Key'),
        permissions=request.data.get('permissions', ['offers:read', 'stats:read']),
        rate_limit=int(request.data.get('rate_limit', 1000)),
    )
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_api_keys_view(request):
    manager = APIKeyManager()
    keys = manager.list_user_keys(request.user.id)
    # Don't return actual key values
    return Response({'api_keys': [{'name': k['name'], 'created': k['created_at']} for k in keys]})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def revoke_api_key_view(request, key_hash):
    manager = APIKeyManager()
    return Response(manager.revoke_key(request.user.id, key_hash))
