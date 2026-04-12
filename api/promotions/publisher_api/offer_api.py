# =============================================================================
# promotions/publisher_api/offer_api.py
# 🟡 MEDIUM — Publisher Offer API
# Developers integrate our offers into their apps via REST API
# CPAlead provides this — devs query offers, show in their app/game
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import hashlib, logging

logger = logging.getLogger(__name__)


class APIKeyAuth:
    """API key authentication for publisher API."""

    def generate_api_key(self, publisher_id: int) -> dict:
        """Generate API key for publisher."""
        import secrets
        api_key = f'pub_{publisher_id}_' + secrets.token_urlsafe(32)
        api_secret = secrets.token_urlsafe(48)
        key_data = {
            'publisher_id': publisher_id,
            'api_key': api_key,
            'created_at': timezone.now().isoformat(),
            'is_active': True,
        }
        cache.set(f'api_key:{api_key}', key_data, timeout=3600 * 24 * 365)
        return {
            'api_key': api_key,
            'api_secret': api_secret,
            'publisher_id': publisher_id,
            'rate_limit': '1000 requests/hour',
            'docs_url': '/api/promotions/docs/',
        }

    def verify_api_key(self, api_key: str) -> dict:
        key_data = cache.get(f'api_key:{api_key}')
        if not key_data or not key_data.get('is_active'):
            return None
        return key_data


class PublisherOfferAPI:
    """
    REST API for publishers to fetch and display offers in their apps.
    Supports JSON + JSONP (for older implementations).
    """

    def get_offers(
        self,
        publisher_id: int,
        country: str = 'US',
        device: str = 'desktop',
        os_name: str = '',
        category: str = None,
        campaign_types: list = None,  # ['cpa', 'cpc', 'cpi', 'survey']
        min_payout: float = 0,
        max_payout: float = 9999,
        limit: int = 25,
        offset: int = 0,
        sort: str = 'payout_desc',
    ) -> dict:
        """Main API endpoint — returns offers for publisher's app/site."""
        from api.promotions.models import Campaign

        qs = Campaign.objects.filter(
            status='active',
            per_task_reward__gte=Decimal(str(min_payout)),
            per_task_reward__lte=Decimal(str(max_payout)),
        ).select_related('category', 'reward_policy')

        if category:
            qs = qs.filter(category__name=category)

        sort_map = {
            'payout_desc': '-per_task_reward',
            'payout_asc': 'per_task_reward',
            'newest': '-created_at',
        }
        qs = qs.order_by(sort_map.get(sort, '-per_task_reward'))

        total = qs.count()
        offers = qs[offset:offset + limit]

        return {
            'status': 'success',
            'publisher_id': publisher_id,
            'country': country,
            'device': device,
            'total': total,
            'offset': offset,
            'limit': limit,
            'offers': [self._format_offer(o, publisher_id, country) for o in offers],
            'has_more': (offset + limit) < total,
            'next_offset': offset + limit if (offset + limit) < total else None,
        }

    def _format_offer(self, campaign, publisher_id: int, country: str) -> dict:
        return {
            'id': campaign.id,
            'name': campaign.title,
            'description': campaign.description[:300] if campaign.description else '',
            'category': campaign.category.name if campaign.category else 'other',
            'type': 'cpa',
            'payout': float(campaign.per_task_reward),
            'payout_usd': float(campaign.per_task_reward),
            'currency': 'USD',
            'countries': ['ALL'],
            'platforms': ['desktop', 'mobile'],
            'icon': '',
            'preview_url': '',
            'offer_url': f'/api/promotions/go/{campaign.id}/?pub={publisher_id}',
            'tracking_url': f'/api/promotions/go/{campaign.id}/?pub={publisher_id}&country={country}',
            'requirements': ['Complete the required action', 'Submit proof'],
            'estimated_time': '2-5 minutes',
            'is_featured': float(campaign.per_task_reward) >= 5.0,
            'created_at': campaign.created_at.isoformat() if campaign.created_at else '',
        }


# ── API Views ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def publisher_api_offers_view(request):
    """
    GET /api/promotions/publisher-api/offers/?api_key=xxx&country=US&limit=25
    Main publisher API endpoint.
    """
    api_key = request.query_params.get('api_key', '')
    if not api_key:
        return Response({'status': 'error', 'message': 'api_key required'}, status=status.HTTP_401_UNAUTHORIZED)

    auth = APIKeyAuth()
    key_data = auth.verify_api_key(api_key)
    if not key_data:
        return Response({'status': 'error', 'message': 'Invalid or inactive API key'}, status=status.HTTP_401_UNAUTHORIZED)

    publisher_id = key_data['publisher_id']
    api = PublisherOfferAPI()
    data = api.get_offers(
        publisher_id=publisher_id,
        country=request.query_params.get('country', 'US').upper(),
        device=request.query_params.get('device', 'desktop'),
        os_name=request.query_params.get('os', ''),
        category=request.query_params.get('category'),
        min_payout=float(request.query_params.get('min_payout', 0)),
        max_payout=float(request.query_params.get('max_payout', 9999)),
        limit=min(int(request.query_params.get('limit', 25)), 100),
        offset=int(request.query_params.get('offset', 0)),
        sort=request.query_params.get('sort', 'payout_desc'),
    )
    return Response(data)


@api_view(['POST'])
@permission_classes([AllowAny])
def generate_api_key_view(request):
    """POST /api/promotions/publisher-api/generate-key/"""
    if not request.user.is_authenticated:
        return Response({'error': 'Login required'}, status=status.HTTP_401_UNAUTHORIZED)
    auth = APIKeyAuth()
    result = auth.generate_api_key(request.user.id)
    return Response(result, status=status.HTTP_201_CREATED)
