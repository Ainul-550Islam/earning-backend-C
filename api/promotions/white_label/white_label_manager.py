# =============================================================================
# promotions/white_label/white_label_manager.py
# White Label Offerwall — Publisher can brand as their own
# "CPAlead provides white-label offerwall solutions"
# Publisher gets: custom domain + logo + colors + currency name
# =============================================================================
from django.core.cache import cache
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import uuid


class WhiteLabelManager:
    """Configure white-label offerwall for publisher."""
    WL_PREFIX = 'white_label:'

    def create_white_label(
        self,
        publisher_id: int,
        brand_name: str,
        logo_url: str = '',
        primary_color: str = '#6C63FF',
        secondary_color: str = '#FF6584',
        custom_domain: str = '',
        currency_name: str = 'Coins',
        currency_icon: str = '🪙',
        welcome_message: str = '',
        footer_text: str = '',
        show_powered_by: bool = True,
    ) -> dict:
        """Create white-label configuration."""
        wl_id = str(uuid.uuid4())[:12]
        config = {
            'wl_id': wl_id,
            'publisher_id': publisher_id,
            'brand_name': brand_name,
            'logo_url': logo_url,
            'primary_color': primary_color,
            'secondary_color': secondary_color,
            'custom_domain': custom_domain,
            'currency_name': currency_name,
            'currency_icon': currency_icon,
            'welcome_message': welcome_message or f'Complete offers and earn {currency_name}!',
            'footer_text': footer_text,
            'show_powered_by': show_powered_by,
            'created_at': timezone.now().isoformat(),
            'is_active': True,
        }
        cache.set(f'{self.WL_PREFIX}{publisher_id}', config, timeout=3600 * 24 * 365)
        from django.conf import settings
        base = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        return {
            'wl_id': wl_id,
            'brand_name': brand_name,
            'offerwall_url': custom_domain or f'{base}/offerwall/{publisher_id}/',
            'embed_iframe': self._generate_iframe(publisher_id, custom_domain or base),
            'embed_js': self._generate_js_embed(publisher_id, custom_domain or base),
            'css_variables': self._generate_css(primary_color, secondary_color),
            'preview_url': f'{base}/offerwall/preview/{publisher_id}/',
            'status': 'active',
        }

    def get_white_label_config(self, publisher_id: int) -> dict:
        config = cache.get(f'{self.WL_PREFIX}{publisher_id}')
        if not config:
            return {
                'has_white_label': False,
                'message': 'No white-label configured. Using default branding.',
            }
        return {'has_white_label': True, **config}

    def get_themed_offerwall_response(self, publisher_id: int, offers: list) -> dict:
        """Wrap offers with white-label theme."""
        config = cache.get(f'{self.WL_PREFIX}{publisher_id}', {})
        return {
            'brand': {
                'name': config.get('brand_name', 'Offer Wall'),
                'logo': config.get('logo_url', ''),
                'primary_color': config.get('primary_color', '#6C63FF'),
                'secondary_color': config.get('secondary_color', '#FF6584'),
                'currency': config.get('currency_name', 'Coins'),
                'currency_icon': config.get('currency_icon', '🪙'),
                'welcome_message': config.get('welcome_message', 'Complete offers and earn!'),
                'show_powered_by': config.get('show_powered_by', True),
            },
            'offers': offers,
            'publisher_id': publisher_id,
        }

    def _generate_iframe(self, publisher_id: int, base: str) -> str:
        return f'<iframe src="{base}/offerwall/{publisher_id}/" width="100%" height="600" frameborder="0" style="border-radius:12px;"></iframe>'

    def _generate_js_embed(self, publisher_id: int, base: str) -> str:
        return f'<script src="{base}/static/promotions/js/offerwall-wl.js" data-pub="{publisher_id}"></script>'

    def _generate_css(self, primary: str, secondary: str) -> str:
        return f':root {{ --ow-primary: {primary}; --ow-secondary: {secondary}; --ow-btn-bg: {primary}; }}'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_white_label_view(request):
    manager = WhiteLabelManager()
    result = manager.create_white_label(
        publisher_id=request.user.id,
        brand_name=request.data.get('brand_name', ''),
        logo_url=request.data.get('logo_url', ''),
        primary_color=request.data.get('primary_color', '#6C63FF'),
        secondary_color=request.data.get('secondary_color', '#FF6584'),
        custom_domain=request.data.get('custom_domain', ''),
        currency_name=request.data.get('currency_name', 'Coins'),
        currency_icon=request.data.get('currency_icon', '🪙'),
        welcome_message=request.data.get('welcome_message', ''),
        show_powered_by=request.data.get('show_powered_by', True),
    )
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_white_label_view(request):
    manager = WhiteLabelManager()
    return Response(manager.get_white_label_config(request.user.id))
