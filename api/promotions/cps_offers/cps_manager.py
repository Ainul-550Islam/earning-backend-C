# =============================================================================
# promotions/cps_offers/cps_manager.py
# CPS — Cost Per Sale (eCommerce product commission)
# Publisher earns % of actual sale amount
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import uuid, hashlib, logging

logger = logging.getLogger(__name__)


class CPSManager:
    """Cost Per Sale — publisher earns % of product price."""

    def create_cps_offer(self, advertiser_id: int, product_name: str,
                          commission_pct: Decimal = Decimal('0.10'),
                          min_commission: Decimal = Decimal('2.00'),
                          max_commission: Decimal = Decimal('200.00'),
                          cookie_days: int = 30) -> dict:
        offer_id = str(uuid.uuid4())[:12]
        from django.core.cache import cache
        config = {
            'offer_id': offer_id, 'advertiser_id': advertiser_id,
            'product_name': product_name,
            'commission_pct': str(commission_pct),
            'min_commission': str(min_commission),
            'max_commission': str(max_commission),
            'cookie_days': cookie_days,
            'total_sales': 0, 'total_commission': '0',
            'status': 'active', 'type': 'cps',
        }
        cache.set(f'cps:{offer_id}', config, timeout=3600 * 24 * 365)
        return {
            'offer_id': offer_id, 'product': product_name,
            'commission': f'{float(commission_pct*100):.1f}%',
            'cookie_days': cookie_days,
            'conversion_url': f'/api/promotions/cps/{offer_id}/sale/',
        }

    def record_sale(self, offer_id: str, publisher_id: int, sale_amount: Decimal,
                    order_id: str, country: str, subid: str = '') -> dict:
        from django.core.cache import cache
        config = cache.get(f'cps:{offer_id}')
        if not config: return {'accepted': False}
        # Dedup by order_id
        dedup_key = f'cps_order:{offer_id}:{hashlib.sha256(order_id.encode()).hexdigest()[:16]}'
        if cache.get(dedup_key): return {'accepted': False, 'reason': 'duplicate_order'}
        cache.set(dedup_key, True, timeout=3600 * 24 * 90)
        pct = Decimal(config['commission_pct'])
        commission = (sale_amount * pct).quantize(Decimal('0.0001'))
        commission = max(Decimal(config['min_commission']), min(commission, Decimal(config['max_commission'])))
        self._pay(publisher_id, offer_id, commission, sale_amount, country, subid)
        config['total_sales'] += 1
        config['total_commission'] = str(Decimal(config['total_commission']) + commission)
        cache.set(f'cps:{offer_id}', config, timeout=3600 * 24 * 365)
        return {'accepted': True, 'sale_amount': str(sale_amount), 'commission': str(commission)}

    def _pay(self, publisher_id, offer_id, commission, sale_amount, country, subid):
        from api.promotions.models import PromotionTransaction
        try:
            PromotionTransaction.objects.create(
                user_id=publisher_id, transaction_type='reward', amount=commission,
                status='completed', notes=f'CPS Sale — {offer_id[:8]} ${sale_amount} [{country}]',
                metadata={'type': 'cps', 'offer_id': offer_id, 'sale_amount': str(sale_amount), 'subid': subid},
            )
        except Exception as e:
            logger.error(f'CPS payout failed: {e}')


@api_view(['POST'])
@permission_classes([AllowAny])
def cps_sale_view(request, offer_id):
    mgr = CPSManager()
    result = mgr.record_sale(
        offer_id=offer_id,
        publisher_id=int(request.data.get('publisher_id', 0)),
        sale_amount=Decimal(str(request.data.get('sale_amount', '0'))),
        order_id=request.data.get('order_id', ''),
        country=request.META.get('HTTP_CF_IPCOUNTRY', 'US'),
        subid=request.data.get('subid', ''),
    )
    return Response(result)
