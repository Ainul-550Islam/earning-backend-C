# =============================================================================
# promotions/dating/dating_offer.py
# Dating Vertical — ClickDealer/Cpamatica top vertical
# SOI: user signs up → publisher earns $1-3
# DOI: user confirms email → publisher earns $2-8
# RevShare: % of user spend ongoing
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import uuid, hashlib, logging

logger = logging.getLogger(__name__)

DATING_NICHES = ['mainstream', 'casual', 'senior', 'christian', 'muslim',
                 'black', 'lgbtq', 'asian', 'latin', 'bbw', 'millionaire']
DATING_MODELS = ['SOI', 'DOI', 'trial', 'revshare', 'cps']


class DatingOfferManager:
    """Dating vertical offer management — SOI/DOI/RevShare."""

    def create_dating_offer(self, advertiser_id: int, niche: str, model: str,
                             payout_soi: Decimal = Decimal('1.50'),
                             payout_doi: Decimal = Decimal('4.00'),
                             revshare_pct: Decimal = Decimal('0.25'),
                             daily_cap: int = 2000,
                             target_countries: list = None,
                             target_gender: str = 'all') -> dict:
        offer_id = str(uuid.uuid4())[:12]
        from django.core.cache import cache
        config = {
            'offer_id': offer_id, 'advertiser_id': advertiser_id,
            'niche': niche, 'model': model,
            'payout_soi': str(payout_soi), 'payout_doi': str(payout_doi),
            'revshare_pct': str(revshare_pct),
            'daily_cap': daily_cap, 'today_leads': 0, 'total_leads': 0,
            'target_countries': target_countries or ['US', 'GB', 'CA', 'AU'],
            'target_gender': target_gender,
            'status': 'active', 'type': 'dating',
        }
        cache.set(f'dating:{offer_id}', config, timeout=3600 * 24 * 365)
        return {
            'offer_id': offer_id, 'niche': niche, 'model': model,
            'payout': str(payout_soi if model == 'SOI' else payout_doi),
            'submit_url': f'/api/promotions/dating/{offer_id}/signup/',
        }

    def process_soi(self, offer_id: str, publisher_id: int, email: str,
                    country: str, ip: str, gender: str = '', age: int = 0) -> dict:
        from django.core.cache import cache
        config = cache.get(f'dating:{offer_id}')
        if not config: return {'accepted': False}
        if config['today_leads'] >= config['daily_cap']:
            return {'accepted': False, 'reason': 'cap'}
        email = email.lower().strip()
        dedup = hashlib.sha256(f'{offer_id}:{email}'.encode()).hexdigest()[:20]
        if cache.get(f'dating_dedup:{dedup}'): return {'accepted': False, 'reason': 'duplicate'}
        cache.set(f'dating_dedup:{dedup}', True, timeout=3600 * 24 * 365)
        config['today_leads'] += 1
        config['total_leads'] += 1
        cache.set(f'dating:{offer_id}', config, timeout=3600 * 24 * 365)
        payout = Decimal(config['payout_soi'])
        self._pay(publisher_id, offer_id, payout, 'SOI', country)
        return {'accepted': True, 'payout': str(payout), 'model': 'SOI'}

    def _pay(self, publisher_id, offer_id, payout, model, country):
        from api.promotions.models import PromotionTransaction
        try:
            PromotionTransaction.objects.create(
                user_id=publisher_id, transaction_type='reward', amount=payout,
                status='completed',
                notes=f'Dating {model} — {offer_id[:8]} [{country}]',
                metadata={'type': 'dating', 'model': model, 'offer_id': offer_id},
            )
        except Exception as e:
            logger.error(f'Dating payout failed: {e}')


@api_view(['POST'])
@permission_classes([AllowAny])
def dating_signup_view(request, offer_id):
    mgr = DatingOfferManager()
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    result = mgr.process_soi(
        offer_id=offer_id,
        publisher_id=int(request.data.get('publisher_id', 0)),
        email=request.data.get('email', ''),
        country=request.META.get('HTTP_CF_IPCOUNTRY', 'US'),
        ip=ip,
        gender=request.data.get('gender', ''),
        age=int(request.data.get('age', 0)),
    )
    return Response(result)
