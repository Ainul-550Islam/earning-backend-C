# =============================================================================
# promotions/content_locking/content_locker.py
# Content Locker — Gate webpage content / text / videos behind CPA offers
# =============================================================================
import uuid
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status


class ContentLocker:
    """
    Publisher wraps any HTML content.
    Visitor must complete offer to reveal content.
    Use cases: tutorials, coupon codes, spoilers, cheat codes, etc.
    """
    LOCK_PREFIX = 'content_lock:'
    UNLOCK_PREFIX = 'content_unlock:'
    TTL = 3600 * 72

    LOCKER_TYPES = {
        'standard': 'Complete offers to unlock',
        'survey': 'Take a quick survey to unlock',
        'video': 'Watch a short video offer to unlock',
        'app_install': 'Install a free app to unlock',
    }

    def create_content_lock(
        self,
        publisher_id: int,
        locker_type: str = 'standard',
        theme: str = 'dark',
        title: str = 'Unlock Content',
        required_offers: int = 1,
        country_payout: dict = None,
    ) -> dict:
        """Create content locker — returns JS snippet for publisher."""
        lock_id = str(uuid.uuid4()).replace('-', '')
        lock_data = {
            'lock_id': lock_id,
            'publisher_id': publisher_id,
            'locker_type': locker_type,
            'theme': theme,
            'title': title,
            'required_offers': required_offers,
            'country_payout': country_payout or {},
            'created_at': timezone.now().isoformat(),
        }
        cache.set(f'{self.LOCK_PREFIX}{lock_id}', lock_data, timeout=self.TTL * 10)
        return {
            'lock_id': lock_id,
            'embed_script': self._generate_script(lock_id, theme, title),
            'css_class': f'cl-locked-{lock_id[:8]}',
            'dashboard_url': f'/publisher/content-lockers/{lock_id}/',
        }

    def unlock_for_visitor(self, lock_id: str, visitor_id: str) -> bool:
        """Mark content as unlocked for this visitor."""
        unlock_key = f'{self.UNLOCK_PREFIX}{lock_id}:{visitor_id}'
        lock_data = cache.get(f'{self.LOCK_PREFIX}{lock_id}')
        if not lock_data:
            return False
        unlock_data = cache.get(unlock_key, {'completed': 0})
        unlock_data['completed'] = unlock_data.get('completed', 0) + 1
        unlock_data['unlocked_at'] = timezone.now().isoformat()
        cache.set(unlock_key, unlock_data, timeout=self.TTL)
        return unlock_data['completed'] >= lock_data.get('required_offers', 1)

    def check_unlocked(self, lock_id: str, visitor_id: str) -> bool:
        unlock_key = f'{self.UNLOCK_PREFIX}{lock_id}:{visitor_id}'
        lock_data = cache.get(f'{self.LOCK_PREFIX}{lock_id}', {})
        unlock_data = cache.get(unlock_key, {'completed': 0})
        return unlock_data.get('completed', 0) >= lock_data.get('required_offers', 1)

    def get_offers_for_visitor(self, lock_id: str, visitor_country: str, visitor_device: str) -> list:
        """Get relevant offers for visitor based on geo + device."""
        # In production: query Campaign model filtered by geo/device
        return [
            {
                'offer_id': 1,
                'title': 'Free App Install',
                'description': 'Install this free app',
                'payout_display': '$0.50',
                'icon_url': '',
                'cta': 'Install Now',
            }
        ]

    def _generate_script(self, lock_id: str, theme: str, title: str) -> str:
        base_url = getattr(settings, 'SITE_URL', 'https://yoursite.com')
        return f'''<script>
(function() {{
  var cl = document.querySelector('[data-content-lock="{lock_id}"]');
  if (cl) {{
    cl.style.display = 'none';
    var gate = document.createElement('div');
    gate.className = 'content-locker-gate cl-theme-{theme}';
    gate.innerHTML = '<h3>🔒 {title}</h3>' +
      '<p>Complete a free offer to unlock this content instantly.</p>' +
      '<button onclick="ContentLockerSDK.open(\\"{lock_id}\\")">Unlock Free</button>';
    cl.parentNode.insertBefore(gate, cl);
  }}
}})();
</script>
<script src="{base_url}/static/promotions/js/content_locker_sdk.js" 
        data-lock-id="{lock_id}" 
        data-api="{base_url}/api/promotions/" async></script>
'''

    def get_stats(self, lock_id: str) -> dict:
        lock_data = cache.get(f'{self.LOCK_PREFIX}{lock_id}', {})
        return {
            'lock_id': lock_id,
            'publisher_id': lock_data.get('publisher_id'),
            'locker_type': lock_data.get('locker_type'),
            'total_views': 0,      # From analytics DB
            'total_unlocks': 0,
            'unlock_rate': 0.0,
            'total_earnings': '0.00',
        }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_content_locker_view(request):
    locker = ContentLocker()
    result = locker.create_content_lock(
        publisher_id=request.user.id,
        locker_type=request.data.get('locker_type', 'standard'),
        theme=request.data.get('theme', 'dark'),
        title=request.data.get('title', 'Unlock Content'),
        required_offers=int(request.data.get('required_offers', 1)),
    )
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def unlock_content_view(request, lock_id):
    visitor_id = request.data.get('visitor_id', '')
    locker = ContentLocker()
    is_unlocked = locker.unlock_for_visitor(lock_id, visitor_id)
    return Response({'unlocked': is_unlocked})


@api_view(['GET'])
@permission_classes([AllowAny])
def check_content_unlocked_view(request, lock_id):
    visitor_id = request.query_params.get('visitor_id', '')
    locker = ContentLocker()
    return Response({'unlocked': locker.check_unlocked(lock_id, visitor_id)})


@api_view(['GET'])
@permission_classes([AllowAny])
def get_locker_offers_view(request, lock_id):
    locker = ContentLocker()
    country = request.query_params.get('country', 'US')
    device = request.query_params.get('device', 'desktop')
    offers = locker.get_offers_for_visitor(lock_id, country, device)
    return Response({'offers': offers, 'lock_id': lock_id})
