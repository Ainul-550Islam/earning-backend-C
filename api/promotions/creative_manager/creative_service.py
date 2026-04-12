# =============================================================================
# promotions/creative_manager/creative_service.py
# Ad Creative Manager — Banners, images, videos for campaigns
# MaxBounty: "Promotional toolkits including banners and creatives"
# =============================================================================
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import uuid

STANDARD_SIZES = {
    'leaderboard':   (728, 90),
    'medium_rect':   (300, 250),
    'large_rect':    (336, 280),
    'half_page':     (300, 600),
    'wide_sky':      (160, 600),
    'mobile_banner': (320, 50),
    'mobile_inter':  (320, 480),
    'square':        (250, 250),
}

CREATIVE_TYPES = ['banner', 'image', 'video', 'native', 'pop', 'push']


class CreativeService:
    """Manage ad creatives for campaigns."""
    CREATIVE_PREFIX = 'creative:'

    def upload_creative(
        self,
        advertiser_id: int,
        campaign_id: int,
        creative_type: str,
        name: str,
        file_url: str,
        size: str = 'medium_rect',
        click_url: str = '',
        is_default: bool = False,
    ) -> dict:
        creative_id = str(uuid.uuid4())[:12]
        dimensions = STANDARD_SIZES.get(size, (300, 250))
        creative = {
            'creative_id': creative_id,
            'advertiser_id': advertiser_id,
            'campaign_id': campaign_id,
            'creative_type': creative_type,
            'name': name,
            'file_url': file_url,
            'size': size,
            'width': dimensions[0],
            'height': dimensions[1],
            'click_url': click_url,
            'is_default': is_default,
            'is_approved': False,
            'rejection_reason': None,
            'impressions': 0,
            'clicks': 0,
            'created_at': timezone.now().isoformat(),
        }
        cache.set(f'{self.CREATIVE_PREFIX}{creative_id}', creative, timeout=3600 * 24 * 365)
        self._add_to_campaign(campaign_id, creative_id)
        return {
            'creative_id': creative_id,
            'name': name,
            'size': f'{dimensions[0]}×{dimensions[1]}',
            'status': 'pending_review',
            'estimated_review': '2-4 hours',
            'preview_url': file_url,
        }

    def get_campaign_creatives(self, campaign_id: int, advertiser_id: int) -> list:
        campaign_key = f'campaign_creatives:{campaign_id}'
        creative_ids = cache.get(campaign_key, [])
        creatives = []
        for cid in creative_ids:
            c = cache.get(f'{self.CREATIVE_PREFIX}{cid}')
            if c and c.get('advertiser_id') == advertiser_id:
                creatives.append({
                    'creative_id': c['creative_id'],
                    'name': c['name'],
                    'type': c['creative_type'],
                    'size': c['size'],
                    'dimensions': f'{c["width"]}×{c["height"]}',
                    'is_approved': c['is_approved'],
                    'is_default': c['is_default'],
                    'ctr': round(c['clicks'] / c['impressions'] * 100, 2) if c['impressions'] > 0 else 0,
                    'preview_url': c['file_url'],
                })
        return creatives

    def approve_creative(self, creative_id: str) -> dict:
        c = cache.get(f'{self.CREATIVE_PREFIX}{creative_id}')
        if not c:
            return {'error': 'Creative not found'}
        c['is_approved'] = True
        c['approved_at'] = timezone.now().isoformat()
        cache.set(f'{self.CREATIVE_PREFIX}{creative_id}', c, timeout=3600 * 24 * 365)
        return {'creative_id': creative_id, 'status': 'approved'}

    def get_standard_sizes(self) -> list:
        return [
            {'name': name, 'width': w, 'height': h, 'label': f'{w}×{h}'}
            for name, (w, h) in STANDARD_SIZES.items()
        ]

    def _add_to_campaign(self, campaign_id: int, creative_id: str):
        key = f'campaign_creatives:{campaign_id}'
        ids = cache.get(key, [])
        if creative_id not in ids:
            ids.append(creative_id)
        cache.set(key, ids, timeout=3600 * 24 * 365)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_creative_view(request):
    service = CreativeService()
    result = service.upload_creative(
        advertiser_id=request.user.id,
        campaign_id=int(request.data.get('campaign_id', 0)),
        creative_type=request.data.get('creative_type', 'banner'),
        name=request.data.get('name', ''),
        file_url=request.data.get('file_url', ''),
        size=request.data.get('size', 'medium_rect'),
        click_url=request.data.get('click_url', ''),
        is_default=bool(request.data.get('is_default', False)),
    )
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campaign_creatives_view(request, campaign_id):
    service = CreativeService()
    return Response({'creatives': service.get_campaign_creatives(campaign_id, request.user.id)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def standard_sizes_view(request):
    service = CreativeService()
    return Response({'sizes': service.get_standard_sizes()})
