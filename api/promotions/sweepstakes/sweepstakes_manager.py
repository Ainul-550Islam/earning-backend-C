# =============================================================================
# promotions/sweepstakes/sweepstakes_manager.py
# Sweepstakes Campaign — ClickDealer/AdCombo #1 vertical
# User enters info to "win" prize → publisher earns per lead
# Prize: iPhone, PS5, Gift Cards, Cash
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import uuid, hashlib, logging

logger = logging.getLogger(__name__)
User = get_user_model()

PRIZE_TYPES = {
    'iphone':     {'name': 'iPhone 16 Pro', 'value': 1199, 'icon': '📱'},
    'ps5':        {'name': 'PlayStation 5', 'value': 499,  'icon': '🎮'},
    'amazon_gc':  {'name': 'Amazon Gift Card $500', 'value': 500, 'icon': '🎁'},
    'cash_1000':  {'name': '$1,000 Cash', 'value': 1000, 'icon': '💵'},
    'macbook':    {'name': 'MacBook Pro', 'value': 1599, 'icon': '💻'},
    'visa_500':   {'name': 'Visa Gift Card $500', 'value': 500, 'icon': '💳'},
    'google_gc':  {'name': 'Google Play $100', 'value': 100, 'icon': '🎮'},
    'custom':     {'name': 'Custom Prize', 'value': 0, 'icon': '🏆'},
}

SWEEPSTAKE_FLOW = {
    'single_page':   'One page: enter email → done',
    'multi_step':    'Step 1: email → Step 2: name → Step 3: phone',
    'quiz_gate':     'Answer quiz first → then enter info',
    'survey_gate':   'Complete survey → unlock sweepstake entry',
    'instant_win':   'Spin wheel / scratch card effect',
}


class SweepstakesManager:
    """
    Sweepstakes offer management:
    - Advertiser creates sweepstake (prize + lead form)
    - Publisher promotes → gets paid per lead
    - User gets a "chance to win"
    Payout: $0.50 - $5.00 per lead depending on geo + flow
    """

    def create_sweepstake(
        self,
        advertiser_id: int,
        title: str,
        prize_type: str,
        custom_prize_name: str = '',
        flow_type: str = 'single_page',
        payout_tier1: Decimal = Decimal('2.00'),
        payout_tier2: Decimal = Decimal('0.50'),
        payout_tier3: Decimal = Decimal('0.20'),
        required_fields: list = None,
        daily_cap: int = 5000,
        target_countries: list = None,
        landing_page_url: str = '',
        thank_you_url: str = '',
    ) -> dict:
        """Create a sweepstake campaign."""
        sweep_id = str(uuid.uuid4())[:16]
        prize = PRIZE_TYPES.get(prize_type, PRIZE_TYPES['custom'])
        if custom_prize_name:
            prize['name'] = custom_prize_name

        config = {
            'sweep_id':        sweep_id,
            'advertiser_id':   advertiser_id,
            'title':           title,
            'prize_type':      prize_type,
            'prize_name':      prize['name'],
            'prize_value':     prize['value'],
            'prize_icon':      prize['icon'],
            'flow_type':       flow_type,
            'payouts': {
                'tier1': str(payout_tier1),  # US/UK/CA/AU
                'tier2': str(payout_tier2),  # DE/FR/IT/ES
                'tier3': str(payout_tier3),  # Others
            },
            'required_fields': required_fields or ['email'],
            'daily_cap':       daily_cap,
            'today_leads':     0,
            'total_leads':     0,
            'target_countries': target_countries or [],
            'landing_page_url': landing_page_url,
            'thank_you_url':   thank_you_url or '/sweepstakes/thank-you/',
            'status':          'active',
            'created_at':      timezone.now().isoformat(),
        }

        from django.core.cache import cache
        cache.set(f'sweep:{sweep_id}', config, timeout=3600 * 24 * 365)

        return {
            'sweep_id':    sweep_id,
            'title':       title,
            'prize':       f'{prize["icon"]} {prize["name"]}',
            'flow_type':   SWEEPSTAKE_FLOW.get(flow_type, ''),
            'payout_t1':   str(payout_tier1),
            'embed_url':   f'/sweepstakes/{sweep_id}/',
            'api_submit':  f'/api/promotions/sweepstakes/{sweep_id}/enter/',
            'preview_url': f'/api/promotions/sweepstakes/{sweep_id}/preview/',
        }

    def process_entry(
        self,
        sweep_id: str,
        publisher_id: int,
        lead_data: dict,
        country: str,
        ip: str,
        subid: str = '',
    ) -> dict:
        """Process sweepstake entry — validate, dedup, pay publisher."""
        from django.core.cache import cache

        config = cache.get(f'sweep:{sweep_id}')
        if not config or config['status'] != 'active':
            return {'accepted': False, 'reason': 'inactive'}

        # Daily cap
        if config['today_leads'] >= config['daily_cap']:
            return {'accepted': False, 'reason': 'cap_reached'}

        # Required fields validation
        for field in config.get('required_fields', ['email']):
            if field not in lead_data or not str(lead_data[field]).strip():
                return {'accepted': False, 'reason': f'missing_field_{field}'}

        # Email format check
        if 'email' in lead_data:
            email = str(lead_data['email']).strip().lower()
            if '@' not in email or '.' not in email.split('@')[-1]:
                return {'accepted': False, 'reason': 'invalid_email'}
            # Dedup
            email_hash = hashlib.sha256(f'{sweep_id}:{email}'.encode()).hexdigest()
            if cache.get(f'sweep_dedup:{email_hash}'):
                return {'accepted': False, 'reason': 'duplicate_email'}
            cache.set(f'sweep_dedup:{email_hash}', True, timeout=3600 * 24 * 365)

        # IP dedup (per day)
        ip_key = f'sweep_ip:{sweep_id}:{hashlib.sha256(ip.encode()).hexdigest()[:16]}:{timezone.now().date()}'
        if cache.get(ip_key):
            return {'accepted': False, 'reason': 'duplicate_ip'}
        cache.set(ip_key, True, timeout=3600 * 25)

        # Geo-based payout
        tier1 = ['US', 'GB', 'CA', 'AU', 'IE', 'NZ']
        tier2 = ['DE', 'FR', 'IT', 'ES', 'NL', 'BE', 'AT', 'CH', 'SE', 'NO', 'DK', 'FI']
        if country in tier1:
            payout = Decimal(config['payouts']['tier1'])
        elif country in tier2:
            payout = Decimal(config['payouts']['tier2'])
        else:
            payout = Decimal(config['payouts']['tier3'])

        # Update counters
        config['today_leads'] += 1
        config['total_leads'] += 1
        cache.set(f'sweep:{sweep_id}', config, timeout=3600 * 24 * 365)

        # Award publisher
        self._award_payout(publisher_id, sweep_id, payout, country, subid)

        logger.info(f'Sweepstake entry: sweep={sweep_id} pub={publisher_id} ${payout} {country}')

        return {
            'accepted':     True,
            'sweep_id':     sweep_id,
            'payout':       str(payout),
            'country':      country,
            'thank_you_url': config.get('thank_you_url', '/thank-you/'),
            'message':      f'You\'ve entered to win {config["prize_icon"]} {config["prize_name"]}!',
        }

    def get_sweep_for_publisher(self, country: str = 'US', device: str = 'mobile') -> list:
        """Get active sweepstakes for publisher to promote."""
        from api.promotions.models import Campaign
        # In production: query SweepstakeCampaign model
        return [
            {
                'id':          f'sweep_{i}',
                'prize':       f'{p["icon"]} {p["name"]}',
                'payout':      '$2.00' if country in ['US','CA','GB','AU'] else '$0.50',
                'flow':        'single_page',
                'category':    'sweepstakes',
                'cta':         f'Enter to Win {p["icon"]} {p["name"]}!',
                'best_for':    'Social media, TikTok, Instagram',
            }
            for i, p in enumerate(list(PRIZE_TYPES.values())[:4])
        ]

    def _award_payout(self, publisher_id: int, sweep_id: str, amount: Decimal, country: str, subid: str):
        from api.promotions.models import PromotionTransaction
        try:
            PromotionTransaction.objects.create(
                user_id=publisher_id,
                transaction_type='reward',
                amount=amount,
                status='completed',
                notes=f'Sweepstake Lead — {sweep_id[:8]} [{country}]',
                metadata={'sweep_id': sweep_id, 'country': country, 'subid': subid, 'type': 'sweepstake'},
            )
        except Exception as e:
            logger.error(f'Sweepstake payout failed: {e}')


@api_view(['POST'])
@permission_classes([AllowAny])
def sweepstake_entry_view(request, sweep_id):
    """POST /api/promotions/sweepstakes/<sweep_id>/enter/"""
    import hashlib
    manager = SweepstakesManager()
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    if ',' in ip: ip = ip.split(',')[0].strip()
    country = request.META.get('HTTP_CF_IPCOUNTRY', 'US')
    result = manager.process_entry(
        sweep_id=sweep_id,
        publisher_id=int(request.data.get('publisher_id', 0)),
        lead_data=request.data.get('lead_data', {}),
        country=country,
        ip=ip,
        subid=request.data.get('subid', ''),
    )
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_sweepstake_view(request):
    """POST /api/promotions/sweepstakes/create/"""
    manager = SweepstakesManager()
    d = request.data
    result = manager.create_sweepstake(
        advertiser_id=request.user.id,
        title=d.get('title', ''),
        prize_type=d.get('prize_type', 'amazon_gc'),
        custom_prize_name=d.get('custom_prize_name', ''),
        flow_type=d.get('flow_type', 'single_page'),
        payout_tier1=Decimal(str(d.get('payout_tier1', '2.00'))),
        payout_tier2=Decimal(str(d.get('payout_tier2', '0.50'))),
        payout_tier3=Decimal(str(d.get('payout_tier3', '0.20'))),
        required_fields=d.get('required_fields', ['email']),
        daily_cap=int(d.get('daily_cap', 5000)),
        target_countries=d.get('target_countries', []),
    )
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def sweep_offers_view(request):
    """GET /api/promotions/sweepstakes/offers/"""
    manager = SweepstakesManager()
    country = request.META.get('HTTP_CF_IPCOUNTRY', 'US')
    return Response({'offers': manager.get_sweep_for_publisher(country=country)})
