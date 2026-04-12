# =============================================================================
# promotions/content_locking/link_locker.py
# Link Locker — CPAlead / OGAds signature feature
# Users must complete an offer to unlock a URL
# =============================================================================
import hashlib
import hmac
import uuid
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


class LinkLocker:
    """
    Publisher adds a link to their site.
    Visitor must complete a CPA offer to unlock the link.
    Supports: URL locker, file locker, page locker.
    """
    LOCK_PREFIX = 'link_lock:'
    UNLOCK_PREFIX = 'link_unlock:'
    TTL_SECONDS = 3600 * 24  # 24 hours unlock window

    def __init__(self, publisher_id: int):
        self.publisher_id = publisher_id

    def create_locked_link(
        self,
        destination_url: str,
        title: str,
        description: str = '',
        required_offers: int = 1,
        geo_restrictions: list = None,
    ) -> dict:
        """
        Create a new locked link.
        Returns embed code + lock token.
        """
        lock_token = str(uuid.uuid4()).replace('-', '')
        lock_data = {
            'token': lock_token,
            'publisher_id': self.publisher_id,
            'destination_url': destination_url,
            'title': title,
            'description': description,
            'required_offers': required_offers,
            'geo_restrictions': geo_restrictions or [],
            'created_at': timezone.now().isoformat(),
            'completed_offers': [],
        }
        cache_key = f'{self.LOCK_PREFIX}{lock_token}'
        cache.set(cache_key, lock_data, timeout=self.TTL_SECONDS * 30)
        embed_code = self._generate_embed_code(lock_token, title, description)
        return {
            'lock_token': lock_token,
            'destination_url': destination_url,
            'embed_code': embed_code,
            'locker_url': f'/promotions/locker/{lock_token}/',
        }

    def check_unlock_status(self, lock_token: str, visitor_id: str) -> dict:
        """Check if visitor has completed required offers."""
        unlock_key = f'{self.UNLOCK_PREFIX}{lock_token}:{visitor_id}'
        lock_key = f'{self.LOCK_PREFIX}{lock_token}'
        lock_data = cache.get(lock_key)
        if not lock_data:
            return {'unlocked': False, 'reason': 'lock_expired'}
        unlock_data = cache.get(unlock_key, {})
        completed = unlock_data.get('completed_offers', 0)
        required = lock_data.get('required_offers', 1)
        if completed >= required:
            return {
                'unlocked': True,
                'destination_url': lock_data['destination_url'],
                'completed': completed,
                'required': required,
            }
        return {
            'unlocked': False,
            'completed': completed,
            'required': required,
            'offers_needed': required - completed,
        }

    def record_offer_completion(self, lock_token: str, visitor_id: str, offer_id: int) -> bool:
        """Record that visitor completed an offer for this lock."""
        unlock_key = f'{self.UNLOCK_PREFIX}{lock_token}:{visitor_id}'
        lock_key = f'{self.LOCK_PREFIX}{lock_token}'
        lock_data = cache.get(lock_key)
        if not lock_data:
            return False
        unlock_data = cache.get(unlock_key, {'completed_offers': 0, 'offer_ids': []})
        # Prevent duplicate offer completions
        if offer_id in unlock_data.get('offer_ids', []):
            return False
        unlock_data['completed_offers'] = unlock_data.get('completed_offers', 0) + 1
        unlock_data.setdefault('offer_ids', []).append(offer_id)
        unlock_data['last_completion'] = timezone.now().isoformat()
        cache.set(unlock_key, unlock_data, timeout=self.TTL_SECONDS)
        return True

    def get_publisher_stats(self) -> dict:
        """Get stats for publisher's lockers."""
        return {
            'publisher_id': self.publisher_id,
            'total_locks': 0,  # In production: query DB
            'total_unlocks': 0,
            'conversion_rate': 0.0,
            'earnings': '0.00',
        }

    def _generate_embed_code(self, lock_token: str, title: str, description: str) -> str:
        """Generate JavaScript embed code for publisher."""
        base_url = getattr(settings, 'SITE_URL', 'https://yoursite.com')
        return f'''<!-- Content Locker by YourPlatform -->
<div id="content-locker-{lock_token}" class="content-locker-widget">
  <div class="locker-overlay">
    <div class="locker-box">
      <h3>🔒 {title}</h3>
      <p>{description}</p>
      <p>Complete <strong>1 free offer</strong> to unlock this content.</p>
      <button onclick="ContentLocker.unlock('{lock_token}')" class="unlock-btn">
        Unlock Now — It&apos;s Free!
      </button>
    </div>
  </div>
</div>
<script src="{base_url}/static/promotions/js/content_locker.js"></script>
<script>
  ContentLocker.init({{
    token: '{lock_token}',
    apiBase: '{base_url}/api/promotions/'
  }});
</script>
'''

    @staticmethod
    def generate_visitor_id(request) -> str:
        """Generate unique visitor ID from request."""
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        ua = request.META.get('HTTP_USER_AGENT', '')
        raw = f'{ip}:{ua}'
        return hashlib.sha256(raw.encode()).hexdigest()[:32]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_locked_link(request):
    """API: Publisher creates a new locked link."""
    data = request.data
    locker = LinkLocker(publisher_id=request.user.id)
    try:
        result = locker.create_locked_link(
            destination_url=data.get('destination_url', ''),
            title=data.get('title', 'Unlock this content'),
            description=data.get('description', ''),
            required_offers=int(data.get('required_offers', 1)),
            geo_restrictions=data.get('geo_restrictions', []),
        )
        return Response(result, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def check_lock_status(request, lock_token):
    """API: Check if visitor has unlocked content."""
    visitor_id = LinkLocker.generate_visitor_id(request)
    locker = LinkLocker(publisher_id=0)
    result = locker.check_unlock_status(lock_token, visitor_id)
    return Response(result)


@api_view(['POST'])
@permission_classes([AllowAny])
def record_unlock(request, lock_token):
    """API: S2S callback — offer completed, unlock content."""
    offer_id = request.data.get('offer_id', 0)
    visitor_id = request.data.get('visitor_id') or LinkLocker.generate_visitor_id(request)
    locker = LinkLocker(publisher_id=0)
    success = locker.record_offer_completion(lock_token, visitor_id, offer_id)
    return Response({'success': success})
