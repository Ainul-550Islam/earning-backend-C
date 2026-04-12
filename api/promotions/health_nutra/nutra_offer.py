# =============================================================================
# promotions/health_nutra/nutra_offer.py
# Health/Nutra Vertical — AdCombo COD model, straight sale
# Weight loss, supplements, beauty — big payouts $25-80
# COD = Cash on Delivery (popular in non-US geos)
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import uuid, hashlib, logging

logger = logging.getLogger(__name__)

NUTRA_MODELS = {
    'cod':          'Cash on Delivery — pay on delivery',
    'straight_sale': 'Direct credit card sale',
    'trial':        '$1/$5 trial → auto-rebill',
    'cpl':          'Lead only — name + phone',
}

NUTRA_CATEGORIES = [
    'weight_loss', 'testosterone', 'keto', 'muscle', 'hair_growth',
    'skin_care', 'anti_aging', 'cbd', 'joint_pain', 'blood_sugar',
    'male_enhancement', 'nootropics', 'vision', 'hearing',
]


class NutraOfferManager:
    """Health/Nutra offer management — COD + straight sale."""

    def create_nutra_offer(self, advertiser_id: int, product_name: str,
                           category: str, model: str, payout: Decimal,
                           daily_cap: int = 200, target_countries: list = None) -> dict:
        offer_id = str(uuid.uuid4())[:12]
        from django.core.cache import cache
        config = {
            'offer_id': offer_id, 'advertiser_id': advertiser_id,
            'product_name': product_name, 'category': category, 'model': model,
            'payout': str(payout), 'daily_cap': daily_cap,
            'today_orders': 0, 'total_orders': 0,
            'target_countries': target_countries or ['US', 'GB', 'AU', 'CA'],
            'status': 'active', 'type': 'nutra',
        }
        cache.set(f'nutra:{offer_id}', config, timeout=3600 * 24 * 365)
        return {
            'offer_id': offer_id, 'product': product_name,
            'model': NUTRA_MODELS.get(model, model), 'payout': str(payout),
            'submit_url': f'/api/promotions/nutra/{offer_id}/order/',
        }

    def process_order(self, offer_id: str, publisher_id: int, order_data: dict,
                      country: str, ip: str, subid: str = '') -> dict:
        from django.core.cache import cache
        config = cache.get(f'nutra:{offer_id}')
        if not config: return {'accepted': False}
        if config['today_orders'] >= config['daily_cap']:
            return {'accepted': False, 'reason': 'cap'}
        phone = str(order_data.get('phone', '')).strip()
        if not phone or len(phone) < 7:
            return {'accepted': False, 'reason': 'invalid_phone'}
        dedup = hashlib.sha256(f'{offer_id}:{phone}'.encode()).hexdigest()[:16]
        if cache.get(f'nutra_dedup:{dedup}'): return {'accepted': False, 'reason': 'duplicate'}
        cache.set(f'nutra_dedup:{dedup}', True, timeout=3600 * 24 * 30)
        config['today_orders'] += 1
        config['total_orders'] += 1
        cache.set(f'nutra:{offer_id}', config, timeout=3600 * 24 * 365)
        payout = Decimal(config['payout'])
        self._pay(publisher_id, offer_id, payout, country, subid)
        return {'accepted': True, 'payout': str(payout), 'model': config['model']}

    def _pay(self, publisher_id, offer_id, payout, country, subid):
        from api.promotions.models import PromotionTransaction
        try:
            PromotionTransaction.objects.create(
                user_id=publisher_id, transaction_type='reward', amount=payout,
                status='completed', notes=f'Nutra Order — {offer_id[:8]} [{country}]',
                metadata={'type': 'nutra', 'offer_id': offer_id, 'subid': subid},
            )
        except Exception as e:
            logger.error(f'Nutra payout failed: {e}')


@api_view(['POST'])
@permission_classes([AllowAny])
def nutra_order_view(request, offer_id):
    mgr = NutraOfferManager()
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    result = mgr.process_order(
        offer_id=offer_id,
        publisher_id=int(request.data.get('publisher_id', 0)),
        order_data=request.data.get('order_data', {}),
        country=request.META.get('HTTP_CF_IPCOUNTRY', 'US'),
        ip=ip,
        subid=request.data.get('subid', ''),
    )
    return Response(result)
