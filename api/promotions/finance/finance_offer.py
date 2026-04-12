# =============================================================================
# promotions/finance/finance_offer.py
# Finance Vertical — MaxBounty #1 vertical ($50-$500 per action)
# Loan applications, insurance quotes, crypto signups, credit card
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging, uuid

logger = logging.getLogger(__name__)

FINANCE_NICHES = {
    'personal_loan':  {'payout_range': (20, 150),  'required': ['name','email','phone','dob','income']},
    'auto_loan':      {'payout_range': (15, 100),  'required': ['name','email','phone','zip','vehicle_year']},
    'mortgage':       {'payout_range': (50, 300),  'required': ['name','email','phone','zip','property_value']},
    'insurance_auto': {'payout_range': (10, 80),   'required': ['name','email','zip','vehicle_year']},
    'insurance_home': {'payout_range': (20, 120),  'required': ['name','email','zip','property_type']},
    'insurance_life': {'payout_range': (30, 200),  'required': ['name','email','age','coverage_amount']},
    'credit_card':    {'payout_range': (30, 150),  'required': ['name','email','income','credit_score']},
    'crypto_signup':  {'payout_range': (20, 100),  'required': ['name','email','phone']},
    'debt_relief':    {'payout_range': (25, 180),  'required': ['name','email','phone','debt_amount']},
    'tax_prep':       {'payout_range': (15, 60),   'required': ['name','email','zip','filing_status']},
}


class FinanceOfferManager:
    """High-value finance lead generation offers."""

    def create_finance_offer(
        self,
        advertiser_id: int,
        niche: str,
        title: str,
        payout: Decimal,
        target_countries: list = None,
        exclusive: bool = False,
        daily_cap: int = 500,
    ) -> dict:
        offer_id = str(uuid.uuid4())[:12]
        niche_config = FINANCE_NICHES.get(niche, FINANCE_NICHES['personal_loan'])
        from django.core.cache import cache
        config = {
            'offer_id': offer_id,
            'advertiser_id': advertiser_id,
            'niche': niche,
            'title': title,
            'payout': str(payout),
            'required_fields': niche_config['required'],
            'target_countries': target_countries or ['US', 'GB', 'CA'],
            'exclusive': exclusive,
            'daily_cap': daily_cap,
            'today_leads': 0,
            'total_leads': 0,
            'status': 'active',
            'type': 'finance',
        }
        cache.set(f'finance_offer:{offer_id}', config, timeout=3600 * 24 * 365)
        return {
            'offer_id': offer_id, 'niche': niche, 'payout': str(payout),
            'required_fields': niche_config['required'],
            'submit_url': f'/api/promotions/finance/{offer_id}/submit/',
        }

    def process_lead(self, offer_id: str, publisher_id: int, lead_data: dict,
                     country: str, ip: str, subid: str = '') -> dict:
        from django.core.cache import cache
        import hashlib
        config = cache.get(f'finance_offer:{offer_id}')
        if not config: return {'accepted': False, 'reason': 'not_found'}
        if config['today_leads'] >= config['daily_cap']:
            return {'accepted': False, 'reason': 'cap_reached'}
        # Validate required fields
        for field in config.get('required_fields', []):
            if not lead_data.get(field):
                return {'accepted': False, 'reason': f'missing_{field}'}
        # Dedup
        email = lead_data.get('email', '').lower()
        dedup_key = f'finance_dedup:{offer_id}:{hashlib.sha256(email.encode()).hexdigest()[:16]}'
        if cache.get(dedup_key): return {'accepted': False, 'reason': 'duplicate'}
        cache.set(dedup_key, True, timeout=3600 * 24 * 90)
        config['today_leads'] += 1
        config['total_leads'] += 1
        cache.set(f'finance_offer:{offer_id}', config, timeout=3600 * 24 * 365)
        payout = Decimal(config['payout'])
        self._pay(publisher_id, offer_id, payout, country, subid)
        return {'accepted': True, 'payout': str(payout), 'offer_id': offer_id}

    def _pay(self, publisher_id, offer_id, payout, country, subid):
        from api.promotions.models import PromotionTransaction
        try:
            PromotionTransaction.objects.create(
                user_id=publisher_id, transaction_type='reward', amount=payout,
                status='completed', notes=f'Finance Lead — {offer_id[:8]} [{country}]',
                metadata={'type': 'finance', 'offer_id': offer_id, 'subid': subid},
            )
        except Exception as e:
            logger.error(f'Finance payout failed: {e}')


@api_view(['POST'])
@permission_classes([AllowAny])
def finance_submit_view(request, offer_id):
    mgr = FinanceOfferManager()
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    result = mgr.process_lead(
        offer_id=offer_id,
        publisher_id=int(request.data.get('publisher_id', 0)),
        lead_data=request.data.get('lead_data', {}),
        country=request.META.get('HTTP_CF_IPCOUNTRY', 'US'),
        ip=ip,
        subid=request.data.get('subid', ''),
    )
    return Response(result)


@api_view(['GET'])
@permission_classes([AllowAny])
def finance_offers_list_view(request):
    niches = [{'niche': k, 'payout_range': f'${v["payout_range"][0]}-${v["payout_range"][1]}',
               'required_fields': v['required']} for k, v in FINANCE_NICHES.items()]
    return Response({'niches': niches})
