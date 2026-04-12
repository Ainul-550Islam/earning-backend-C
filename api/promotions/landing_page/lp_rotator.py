# =============================================================================
# promotions/landing_page/lp_rotator.py
# Landing Page Rotator — A/B test multiple landing pages
# CPAlead: "Rotate LP to find highest converter automatically"
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
import uuid, random


class LandingPageRotator:
    """
    Rotate multiple landing pages for a campaign.
    Automatically shift traffic to best converter (multi-armed bandit).
    """
    LP_PREFIX = 'lp_rotator:'

    def create_rotator(
        self,
        campaign_id: int,
        advertiser_id: int,
        landing_pages: list,   # [{'url': '...', 'name': '...', 'weight': 1}]
        rotation_type: str = 'weighted',  # weighted / bandit / sequential
    ) -> dict:
        rotator_id = str(uuid.uuid4())[:12]
        lps = []
        for i, lp in enumerate(landing_pages):
            lps.append({
                'lp_id': str(uuid.uuid4())[:8],
                'url': lp.get('url', ''),
                'name': lp.get('name', f'LP #{i+1}'),
                'weight': int(lp.get('weight', 1)),
                'clicks': 0,
                'conversions': 0,
                'is_active': True,
            })
        rotator = {
            'rotator_id': rotator_id,
            'campaign_id': campaign_id,
            'advertiser_id': advertiser_id,
            'landing_pages': lps,
            'rotation_type': rotation_type,
            'created_at': timezone.now().isoformat(),
        }
        cache.set(f'{self.LP_PREFIX}{rotator_id}', rotator, timeout=3600 * 24 * 365)
        return {
            'rotator_id': rotator_id,
            'campaign_id': campaign_id,
            'lp_count': len(lps),
            'rotation_type': rotation_type,
            'redirect_url': f'/api/promotions/lp/{rotator_id}/go/',
        }

    def get_next_lp(self, rotator_id: str) -> dict:
        """Get next landing page URL based on rotation strategy."""
        rotator = cache.get(f'{self.LP_PREFIX}{rotator_id}')
        if not rotator:
            return {'error': 'Rotator not found'}
        active = [lp for lp in rotator['landing_pages'] if lp['is_active']]
        if not active:
            return {'error': 'No active landing pages'}
        if rotator['rotation_type'] == 'weighted':
            weights = [lp['weight'] for lp in active]
            selected = random.choices(active, weights=weights, k=1)[0]
        elif rotator['rotation_type'] == 'bandit':
            # Epsilon-greedy: 90% best CVR, 10% random
            if random.random() < 0.1 or all(lp['clicks'] == 0 for lp in active):
                selected = random.choice(active)
            else:
                best = max(active, key=lambda lp: lp['conversions'] / lp['clicks'] if lp['clicks'] > 0 else 0)
                selected = best
        else:
            selected = active[0]
        return {
            'lp_id': selected['lp_id'],
            'url': selected['url'],
            'name': selected['name'],
            'rotator_id': rotator_id,
        }

    def record_click(self, rotator_id: str, lp_id: str):
        rotator = cache.get(f'{self.LP_PREFIX}{rotator_id}')
        if rotator:
            for lp in rotator['landing_pages']:
                if lp['lp_id'] == lp_id:
                    lp['clicks'] += 1
            cache.set(f'{self.LP_PREFIX}{rotator_id}', rotator, timeout=3600 * 24 * 365)

    def get_stats(self, rotator_id: str, advertiser_id: int) -> dict:
        rotator = cache.get(f'{self.LP_PREFIX}{rotator_id}')
        if not rotator or rotator.get('advertiser_id') != advertiser_id:
            return {'error': 'Not found'}
        lp_stats = []
        for lp in rotator['landing_pages']:
            cvr = lp['conversions'] / lp['clicks'] * 100 if lp['clicks'] > 0 else 0
            lp_stats.append({
                'name': lp['name'],
                'url': lp['url'],
                'clicks': lp['clicks'],
                'conversions': lp['conversions'],
                'cvr_pct': round(cvr, 2),
                'is_winner': False,
            })
        if lp_stats:
            winner_idx = max(range(len(lp_stats)), key=lambda i: lp_stats[i]['cvr_pct'])
            lp_stats[winner_idx]['is_winner'] = True
        return {'rotator_id': rotator_id, 'landing_pages': lp_stats}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_rotator_view(request):
    rotator = LandingPageRotator()
    result = rotator.create_rotator(
        campaign_id=int(request.data.get('campaign_id', 0)),
        advertiser_id=request.user.id,
        landing_pages=request.data.get('landing_pages', []),
        rotation_type=request.data.get('rotation_type', 'weighted'),
    )
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def rotator_redirect_view(request, rotator_id):
    from django.shortcuts import redirect
    rotator = LandingPageRotator()
    lp = rotator.get_next_lp(rotator_id)
    if 'error' in lp:
        return Response(lp, status=status.HTTP_404_NOT_FOUND)
    rotator.record_click(rotator_id, lp['lp_id'])
    return redirect(lp['url'])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rotator_stats_view(request, rotator_id):
    rotator = LandingPageRotator()
    return Response(rotator.get_stats(rotator_id, request.user.id))
