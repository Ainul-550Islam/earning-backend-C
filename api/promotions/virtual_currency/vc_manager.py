# =============================================================================
# promotions/virtual_currency/vc_manager.py
# 🟠 HIGH — Virtual Currency System
# Game devs / app devs set their own virtual currency rate.
# Example: 1000 coins = $1, so completing a $0.50 offer = 500 coins
# CPAlead: "Set your own virtual currency rates and customize UX"
# =============================================================================
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
import uuid


class VirtualCurrencyManager:
    """
    Publisher sets their virtual currency config.
    Offerwall shows payout in VC (coins/gems/points) instead of USD.
    User sees: "Complete this offer — earn 500 Coins!"
    """
    VC_PREFIX = 'vc_config:'

    def create_vc_config(
        self,
        publisher_id: int,
        currency_name: str,          # e.g., "Coins", "Gems", "Points", "Credits"
        currency_icon: str,          # emoji or URL: "🪙", "💎"
        usd_to_vc_rate: Decimal,     # 1 USD = how many VC? e.g., 1000
        min_payout_vc: int = 100,    # Minimum VC to request payout
        rounding: str = 'floor',     # floor / ceil / round
    ) -> dict:
        """Configure virtual currency for publisher's offerwall."""
        config_id = str(uuid.uuid4())[:12]
        config = {
            'config_id': config_id,
            'publisher_id': publisher_id,
            'currency_name': currency_name,
            'currency_icon': currency_icon,
            'usd_to_vc_rate': str(usd_to_vc_rate),
            'min_payout_vc': min_payout_vc,
            'rounding': rounding,
            'created_at': timezone.now().isoformat(),
            'is_active': True,
        }
        cache.set(f'{self.VC_PREFIX}{publisher_id}', config, timeout=3600 * 24 * 365)
        return {
            'config_id': config_id,
            'currency_name': currency_name,
            'currency_icon': currency_icon,
            'rate': f'1 USD = {usd_to_vc_rate} {currency_name}',
            'example': f'$1.00 offer = {usd_to_vc_rate} {currency_name}',
            'embed_param': f'?pub={publisher_id}&vc=1',
            'message': f'Virtual currency configured! Users will see {currency_name} instead of USD.',
        }

    def get_vc_config(self, publisher_id: int) -> dict:
        config = cache.get(f'{self.VC_PREFIX}{publisher_id}')
        if not config:
            return {
                'has_vc': False,
                'publisher_id': publisher_id,
                'message': 'No virtual currency configured. Offerwall shows USD by default.',
            }
        return {'has_vc': True, **config}

    def convert_usd_to_vc(self, publisher_id: int, usd_amount: Decimal) -> dict:
        """Convert USD payout to virtual currency amount."""
        config = cache.get(f'{self.VC_PREFIX}{publisher_id}')
        if not config:
            return {
                'display_amount': f'${usd_amount:.2f}',
                'usd_amount': str(usd_amount),
                'vc_amount': None,
            }
        rate = Decimal(config['usd_to_vc_rate'])
        raw_vc = usd_amount * rate
        if config['rounding'] == 'floor':
            import math
            vc_amount = int(math.floor(raw_vc))
        elif config['rounding'] == 'ceil':
            import math
            vc_amount = int(math.ceil(raw_vc))
        else:
            vc_amount = int(round(raw_vc))
        return {
            'display_amount': f'{config["currency_icon"]} {vc_amount:,} {config["currency_name"]}',
            'usd_amount': str(usd_amount),
            'vc_amount': vc_amount,
            'currency_name': config['currency_name'],
            'currency_icon': config['currency_icon'],
        }

    def get_offerwall_with_vc(self, publisher_id: int, country: str = 'US', limit: int = 20) -> dict:
        """Get offerwall offers with VC amounts displayed."""
        from api.promotions.offerwall.offerwall_backend import OfferwallBackend
        wall = OfferwallBackend()
        offers = wall.get_offers_for_wall(publisher_id=publisher_id, country=country, limit=limit)
        config = cache.get(f'{self.VC_PREFIX}{publisher_id}')
        if config and offers.get('offers'):
            rate = Decimal(config['usd_to_vc_rate'])
            icon = config['currency_icon']
            name = config['currency_name']
            for offer in offers['offers']:
                usd = Decimal(offer['payout'])
                vc = int(usd * rate)
                offer['vc_payout'] = f'{icon} {vc:,} {name}'
                offer['payout_display'] = offer['vc_payout']
        return offers

    def award_vc_to_user(self, publisher_id: int, user_id: int, vc_amount: int, reason: str = '') -> dict:
        """Award VC to user (game/app credits the user)."""
        # In production: call publisher's game API webhook
        award_record = {
            'publisher_id': publisher_id,
            'user_id': user_id,
            'vc_amount': vc_amount,
            'reason': reason,
            'awarded_at': timezone.now().isoformat(),
        }
        config = cache.get(f'{self.VC_PREFIX}{publisher_id}', {})
        return {
            'success': True,
            'user_id': user_id,
            'vc_awarded': vc_amount,
            'currency_name': config.get('currency_name', 'Points'),
            'message': f'{vc_amount} {config.get("currency_name", "Points")} added to user account',
        }


class VirtualCurrencyPostback:
    """S2S postback that sends VC amount to publisher's server."""

    def send_vc_postback(self, publisher_id: int, user_id: str, offer_id: int,
                         usd_amount: Decimal, postback_url: str) -> dict:
        """Send postback to publisher's server with VC amount."""
        manager = VirtualCurrencyManager()
        vc_data = manager.convert_usd_to_vc(publisher_id, usd_amount)
        import urllib.request
        import urllib.parse
        params = {
            'user_id': user_id,
            'offer_id': str(offer_id),
            'usd': str(usd_amount),
            'vc_amount': str(vc_data.get('vc_amount', 0)),
            'currency': vc_data.get('currency_name', 'Points'),
            'status': 'approved',
        }
        url = f'{postback_url}?{urllib.parse.urlencode(params)}'
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                return {'success': True, 'response_code': resp.status, 'vc_amount': vc_data.get('vc_amount')}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ── API Views ────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_vc_config_view(request):
    """POST /api/promotions/virtual-currency/config/"""
    manager = VirtualCurrencyManager()
    data = request.data
    try:
        result = manager.create_vc_config(
            publisher_id=request.user.id,
            currency_name=data.get('currency_name', 'Coins'),
            currency_icon=data.get('currency_icon', '🪙'),
            usd_to_vc_rate=Decimal(str(data.get('usd_to_vc_rate', '1000'))),
            min_payout_vc=int(data.get('min_payout_vc', 100)),
            rounding=data.get('rounding', 'floor'),
        )
        return Response(result, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vc_config_view(request):
    """GET /api/promotions/virtual-currency/config/"""
    manager = VirtualCurrencyManager()
    return Response(manager.get_vc_config(request.user.id))


@api_view(['GET'])
@permission_classes([AllowAny])
def offerwall_with_vc_view(request):
    """GET /api/promotions/offerwall/vc/?pub=123"""
    pub_id = int(request.query_params.get('pub', 0))
    country = request.query_params.get('country', 'US')
    manager = VirtualCurrencyManager()
    data = manager.get_offerwall_with_vc(publisher_id=pub_id, country=country)
    return Response(data)
