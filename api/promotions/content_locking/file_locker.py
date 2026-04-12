# =============================================================================
# promotions/content_locking/file_locker.py
# File Locker — Gate file downloads behind CPA offers
# CPAlead / OGAds core monetization feature
# =============================================================================
import os
import uuid
import hashlib
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status


class FileLocker:
    """
    Publisher uploads/links a file.
    Visitor must complete a CPA offer to download it.
    Works for: software, eBooks, templates, game cheats, etc.
    """
    LOCK_PREFIX = 'file_lock:'
    DOWNLOAD_KEY_PREFIX = 'download_key:'
    TTL = 3600 * 48  # 48 hours download link validity

    def create_file_lock(
        self,
        publisher_id: int,
        file_url: str,
        file_name: str,
        file_size_mb: float = 0.0,
        file_description: str = '',
        required_offers: int = 1,
        allow_direct_link: bool = False,
    ) -> dict:
        """Create a locked file download."""
        lock_id = str(uuid.uuid4()).replace('-', '')
        lock_data = {
            'lock_id': lock_id,
            'publisher_id': publisher_id,
            'file_url': file_url,
            'file_name': file_name,
            'file_size_mb': file_size_mb,
            'file_description': file_description,
            'required_offers': required_offers,
            'allow_direct_link': allow_direct_link,
            'created_at': timezone.now().isoformat(),
            'total_downloads': 0,
            'total_unlocks': 0,
        }
        cache.set(f'{self.LOCK_PREFIX}{lock_id}', lock_data, timeout=self.TTL * 30)
        embed_code = self._generate_file_embed(lock_id, file_name, file_description, file_size_mb)
        return {
            'lock_id': lock_id,
            'file_locker_url': f'/promotions/file-locker/{lock_id}/',
            'embed_code': embed_code,
            'stats_url': f'/api/promotions/file-locker/{lock_id}/stats/',
        }

    def generate_download_token(self, lock_id: str, visitor_id: str) -> dict:
        """Generate one-time download token after offer completion."""
        lock_data = cache.get(f'{self.LOCK_PREFIX}{lock_id}')
        if not lock_data:
            return {'error': 'File lock expired or not found'}
        # Verify visitor completed required offers
        unlock_status = self._check_visitor_completion(lock_id, visitor_id)
        if not unlock_status['unlocked']:
            return {'error': 'Offers not completed', 'status': unlock_status}
        # Generate one-time download token
        download_token = str(uuid.uuid4()).replace('-', '')
        token_data = {
            'lock_id': lock_id,
            'file_url': lock_data['file_url'],
            'file_name': lock_data['file_name'],
            'visitor_id': visitor_id,
            'created_at': timezone.now().isoformat(),
            'used': False,
        }
        cache.set(f'{self.DOWNLOAD_KEY_PREFIX}{download_token}', token_data, timeout=3600)
        return {
            'download_token': download_token,
            'download_url': f'/api/promotions/download/{download_token}/',
            'expires_in': 3600,
            'file_name': lock_data['file_name'],
        }

    def consume_download_token(self, download_token: str) -> dict:
        """Use download token — one time only."""
        key = f'{self.DOWNLOAD_KEY_PREFIX}{download_token}'
        token_data = cache.get(key)
        if not token_data:
            return {'error': 'Invalid or expired download token'}
        if token_data.get('used'):
            return {'error': 'Download token already used'}
        # Mark as used
        token_data['used'] = True
        token_data['used_at'] = timezone.now().isoformat()
        cache.set(key, token_data, timeout=300)
        return {
            'file_url': token_data['file_url'],
            'file_name': token_data['file_name'],
            'success': True,
        }

    def record_offer_completion(self, lock_id: str, visitor_id: str, offer_id: int) -> bool:
        """Record offer completion for this file lock."""
        unlock_key = f'file_unlock:{lock_id}:{visitor_id}'
        lock_data = cache.get(f'{self.LOCK_PREFIX}{lock_id}')
        if not lock_data:
            return False
        unlock_data = cache.get(unlock_key, {'completed': 0, 'offer_ids': []})
        if offer_id in unlock_data.get('offer_ids', []):
            return False
        unlock_data['completed'] = unlock_data.get('completed', 0) + 1
        unlock_data.setdefault('offer_ids', []).append(offer_id)
        cache.set(unlock_key, unlock_data, timeout=self.TTL)
        return True

    def _check_visitor_completion(self, lock_id: str, visitor_id: str) -> dict:
        unlock_key = f'file_unlock:{lock_id}:{visitor_id}'
        lock_data = cache.get(f'{self.LOCK_PREFIX}{lock_id}', {})
        unlock_data = cache.get(unlock_key, {'completed': 0})
        required = lock_data.get('required_offers', 1)
        completed = unlock_data.get('completed', 0)
        return {
            'unlocked': completed >= required,
            'completed': completed,
            'required': required,
        }

    def _generate_file_embed(self, lock_id: str, file_name: str, description: str, size_mb: float) -> str:
        base_url = getattr(settings, 'SITE_URL', 'https://yoursite.com')
        size_str = f'{size_mb:.1f} MB' if size_mb > 0 else 'File'
        return f'''<!-- File Locker Widget -->
<div id="file-locker-{lock_id}" class="file-locker-widget">
  <div class="file-info">
    <span class="file-icon">📄</span>
    <div>
      <strong>{file_name}</strong>
      <small>{size_str} · {description}</small>
    </div>
  </div>
  <div class="file-lock-gate">
    <p>🔒 Complete 1 free offer to download</p>
    <button onclick="FileLocker.unlock('{lock_id}')" class="download-btn">
      Get Free Download
    </button>
  </div>
</div>
<script src="{base_url}/static/promotions/js/file_locker.js"></script>
<script>FileLocker.init('{lock_id}', '{base_url}/api/promotions/');</script>
'''


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_file_lock_view(request):
    locker = FileLocker()
    result = locker.create_file_lock(
        publisher_id=request.user.id,
        file_url=request.data.get('file_url', ''),
        file_name=request.data.get('file_name', 'download'),
        file_size_mb=float(request.data.get('file_size_mb', 0)),
        file_description=request.data.get('description', ''),
        required_offers=int(request.data.get('required_offers', 1)),
    )
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_download_token_view(request, lock_id):
    visitor_id = request.query_params.get('visitor_id', '')
    locker = FileLocker()
    result = locker.generate_download_token(lock_id, visitor_id)
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)


@api_view(['GET'])
@permission_classes([AllowAny])
def consume_download_view(request, token):
    locker = FileLocker()
    result = locker.consume_download_token(token)
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)
