# =============================================================================
# promotions/smartlink/smartlink_router.py
# SmartLink — ClickDealer / CPAlead signature feature
# Auto-routes traffic to highest EPC offer based on: GEO + Device + OS + Browser
# =============================================================================
import hashlib
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Sum, Count, Q, F
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


class SmartLinkRouter:
    """
    SmartLink: One URL → best offer for each visitor.
    Scores offers by: EPC × CVR × Availability × Geo match × Device match
    """
    CACHE_TTL = 60  # Re-score offers every 60 seconds
    VISITOR_HISTORY_TTL = 3600 * 24

    def get_best_offer(
        self,
        publisher_id: int,
        visitor_country: str,
        visitor_device: str,
        visitor_os: str,
        visitor_browser: str,
        visitor_id: str,
    ) -> dict:
        """Find the highest EPC offer for this visitor profile."""
        # Check cache first
        cache_key = f'smartlink:{publisher_id}:{visitor_country}:{visitor_device}:{visitor_os}'
        cached_offer = cache.get(cache_key)
        if cached_offer:
            # Avoid showing same offer twice to same visitor
            if not self._already_seen(visitor_id, cached_offer['offer_id']):
                self._record_impression(publisher_id, cached_offer['offer_id'], visitor_id)
                return cached_offer

        # Get all active campaigns matching visitor profile
        from api.promotions.models import Campaign
        candidates = Campaign.objects.filter(
            status='active',
        ).exclude(
            id__in=self._get_seen_offers(visitor_id)
        ).select_related('reward_policy', 'category')

        # Score each campaign
        scored = []
        for campaign in candidates[:50]:  # Limit to top 50 candidates
            score = self._score_campaign(campaign, visitor_country, visitor_device, visitor_os)
            if score > 0:
                scored.append((score, campaign))

        if not scored:
            return {'error': 'No offers available for your profile', 'redirect_url': None}

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # A/B test: 90% best offer, 10% random from top 5
        import random
        if random.random() < 0.1 and len(scored) >= 3:
            _, best_campaign = random.choice(scored[:5])
        else:
            _, best_campaign = scored[0]

        offer_data = {
            'offer_id': best_campaign.id,
            'offer_title': best_campaign.title,
            'offer_url': f'/promotions/go/{best_campaign.id}/?pub={publisher_id}&vid={visitor_id}',
            'payout': str(best_campaign.per_task_reward),
            'category': best_campaign.category.name if best_campaign.category else '',
            'device': visitor_device,
            'country': visitor_country,
            'matched_at': timezone.now().isoformat(),
        }
        cache.set(cache_key, offer_data, timeout=self.CACHE_TTL)
        self._record_impression(publisher_id, best_campaign.id, visitor_id)
        return offer_data

    def _score_campaign(
        self, campaign, country: str, device: str, os_name: str
    ) -> float:
        """
        Score = EPC × CVR × Geo_match × Device_match × Cap_availability
        """
        from api.promotions.models import TaskSubmission
        # Base EPC from campaign reward
        base_epc = float(campaign.per_task_reward)

        # CVR: historical conversion rate for this campaign
        total = TaskSubmission.objects.filter(campaign=campaign).count()
        approved = TaskSubmission.objects.filter(campaign=campaign, status='approved').count()
        cvr = approved / total if total > 0 else 0.05  # Default 5% CVR for new campaigns

        # Geo match (simplified)
        geo_score = 1.0  # In production: check campaign targeting conditions

        # Device match
        device_score = 1.0

        # Budget availability
        remaining = campaign.total_budget - (campaign.total_budget * Decimal('0.5'))  # Simplified
        cap_score = 1.0 if remaining > 0 else 0.0

        return base_epc * cvr * geo_score * device_score * cap_score

    def _already_seen(self, visitor_id: str, offer_id: int) -> bool:
        seen = cache.get(f'seen_offers:{visitor_id}', [])
        return offer_id in seen

    def _get_seen_offers(self, visitor_id: str) -> list:
        return cache.get(f'seen_offers:{visitor_id}', [])

    def _record_impression(self, publisher_id: int, offer_id: int, visitor_id: str):
        seen = cache.get(f'seen_offers:{visitor_id}', [])
        if offer_id not in seen:
            seen.append(offer_id)
            cache.set(f'seen_offers:{visitor_id}', seen[-20:], timeout=self.VISITOR_HISTORY_TTL)

    def create_publisher_smartlink(self, publisher_id: int, name: str = '') -> dict:
        """Create a SmartLink for a publisher."""
        from django.conf import settings
        base_url = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        link_hash = hashlib.md5(f'{publisher_id}:{name}:{timezone.now().date()}'.encode()).hexdigest()[:12]
        return {
            'smartlink_id': link_hash,
            'publisher_id': publisher_id,
            'name': name or f'SmartLink #{link_hash[:6]}',
            'url': f'{base_url}/go/s/{publisher_id}/{link_hash}/',
            'tracking_url': f'{base_url}/api/promotions/smartlink/{publisher_id}/{link_hash}/',
            'created_at': timezone.now().isoformat(),
            'description': 'This link auto-routes visitors to the highest-converting offer.',
        }


class SmartLinkTrafficMatcher:
    """Extract visitor attributes from request headers."""

    @staticmethod
    def extract_visitor_profile(request) -> dict:
        """Parse User-Agent and headers to get device/OS/browser."""
        ua = request.META.get('HTTP_USER_AGENT', '').lower()
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if isinstance(ip, str) and ',' in ip:
            ip = ip.split(',')[0].strip()

        # Device detection
        if any(x in ua for x in ['iphone', 'android', 'mobile', 'blackberry']):
            device = 'mobile'
        elif any(x in ua for x in ['ipad', 'tablet']):
            device = 'tablet'
        else:
            device = 'desktop'

        # OS detection
        if 'android' in ua:
            os_name = 'Android'
        elif 'iphone' in ua or 'ipad' in ua:
            os_name = 'iOS'
        elif 'windows' in ua:
            os_name = 'Windows'
        elif 'mac' in ua:
            os_name = 'macOS'
        elif 'linux' in ua:
            os_name = 'Linux'
        else:
            os_name = 'Unknown'

        # Browser detection
        if 'chrome' in ua and 'safari' in ua:
            browser = 'Chrome'
        elif 'firefox' in ua:
            browser = 'Firefox'
        elif 'safari' in ua:
            browser = 'Safari'
        elif 'edge' in ua:
            browser = 'Edge'
        else:
            browser = 'Unknown'

        # Visitor ID from IP + UA hash
        visitor_id = hashlib.sha256(f'{ip}:{ua}'.encode()).hexdigest()[:20]

        return {
            'ip': ip,
            'device': device,
            'os': os_name,
            'browser': browser,
            'visitor_id': visitor_id,
            'country': request.META.get('HTTP_CF_IPCOUNTRY', 'US'),  # Cloudflare header
        }


@api_view(['GET'])
@permission_classes([AllowAny])
def smartlink_redirect_view(request, publisher_id, link_hash):
    """
    GET /api/promotions/smartlink/<publisher_id>/<link_hash>/
    → Auto-selects best offer → redirect
    """
    from django.shortcuts import redirect
    matcher = SmartLinkTrafficMatcher()
    profile = matcher.extract_visitor_profile(request)
    router = SmartLinkRouter()
    offer = router.get_best_offer(
        publisher_id=publisher_id,
        visitor_country=profile['country'],
        visitor_device=profile['device'],
        visitor_os=profile['os'],
        visitor_browser=profile['browser'],
        visitor_id=profile['visitor_id'],
    )
    if 'error' in offer or not offer.get('offer_url'):
        return Response({'error': 'No offers available'}, status=404)
    return redirect(offer['offer_url'])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_smartlink_view(request):
    """Publisher creates their SmartLink."""
    router = SmartLinkRouter()
    result = router.create_publisher_smartlink(
        publisher_id=request.user.id,
        name=request.data.get('name', ''),
    )
    return Response(result, status=status.HTTP_201_CREATED)
