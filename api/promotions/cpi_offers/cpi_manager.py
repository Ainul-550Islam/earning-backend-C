# =============================================================================
# promotions/cpi_offers/cpi_manager.py
# 🟠 HIGH — CPI (Cost Per Install) Campaign System
# Mobile app developers pay publishers per app install
# CPAlead: "Direct mobile app offers paying up to $4 per install"
# Integrates with: AppsFlyer, Adjust, Firebase
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
import logging, uuid, hashlib

logger = logging.getLogger(__name__)

SUPPORTED_MMP = ['appsflyer', 'adjust', 'firebase', 'branch', 'kochava', 'singular']


class CPIManager:
    """
    CPI Campaign management:
    - Create CPI campaigns (app developers)
    - Track installs via MMP (AppsFlyer/Adjust)
    - Verify real install (not bot)
    - Pay publisher per verified install
    """

    def create_cpi_campaign(
        self,
        advertiser_id: int,
        app_name: str,
        app_store_url: str,
        bundle_id: str,
        platform: str,          # android / ios
        payout_per_install: Decimal,
        mmp_provider: str,      # appsflyer / adjust / firebase
        mmp_app_id: str,
        target_countries: list = None,
        target_os_version: str = '',
        daily_cap: int = 1000,
    ) -> dict:
        """Advertiser creates a CPI campaign."""
        if mmp_provider not in SUPPORTED_MMP:
            return {'error': f'MMP not supported. Use: {", ".join(SUPPORTED_MMP)}'}

        campaign_id = str(uuid.uuid4())[:12]
        config = {
            'campaign_id': campaign_id,
            'advertiser_id': advertiser_id,
            'app_name': app_name,
            'app_store_url': app_store_url,
            'bundle_id': bundle_id,
            'platform': platform,
            'payout_per_install': str(payout_per_install),
            'mmp_provider': mmp_provider,
            'mmp_app_id': mmp_app_id,
            'target_countries': target_countries or [],
            'target_os_version': target_os_version,
            'daily_cap': daily_cap,
            'today_installs': 0,
            'total_installs': 0,
            'status': 'active',
            'created_at': timezone.now().isoformat(),
        }
        cache.set(f'cpi_campaign:{campaign_id}', config, timeout=3600 * 24 * 365)

        postback_url = self._generate_postback_url(campaign_id, mmp_provider)

        return {
            'campaign_id': campaign_id,
            'app_name': app_name,
            'platform': platform,
            'payout_per_install': str(payout_per_install),
            'mmp_provider': mmp_provider,
            'postback_url': postback_url,
            'setup_instructions': self._get_mmp_setup_instructions(mmp_provider, postback_url),
            'status': 'active',
        }

    def record_install_postback(
        self,
        campaign_id: str,
        mmp_provider: str,
        click_id: str,
        device_id: str,
        country: str,
        install_time: str = None,
    ) -> dict:
        """Receive install postback from MMP (AppsFlyer/Adjust)."""
        campaign = cache.get(f'cpi_campaign:{campaign_id}')
        if not campaign:
            return {'error': 'Campaign not found', 'status': 'rejected'}

        if campaign['status'] != 'active':
            return {'error': 'Campaign not active', 'status': 'rejected'}

        # Daily cap check
        if campaign['today_installs'] >= campaign['daily_cap']:
            return {'error': 'Daily cap reached', 'status': 'rejected'}

        # Country check
        if campaign['target_countries'] and country not in campaign['target_countries']:
            return {'error': 'Country not targeted', 'status': 'rejected'}

        # Duplicate install check
        dedup_key = f'cpi_install:{campaign_id}:{device_id}'
        if cache.get(dedup_key):
            return {'error': 'Duplicate install', 'status': 'rejected'}

        # Get publisher from click tracking
        publisher_id = self._get_publisher_from_click(click_id)

        if publisher_id:
            # Award publisher
            payout = Decimal(campaign['payout_per_install'])
            self._award_install_payout(publisher_id, campaign_id, payout, click_id)

        # Mark install
        cache.set(dedup_key, True, timeout=3600 * 24 * 30)
        campaign['today_installs'] += 1
        campaign['total_installs'] += 1
        cache.set(f'cpi_campaign:{campaign_id}', campaign, timeout=3600 * 24 * 365)

        logger.info(f'CPI install recorded: campaign={campaign_id} pub={publisher_id} country={country}')

        return {
            'status': 'accepted',
            'campaign_id': campaign_id,
            'click_id': click_id,
            'country': country,
            'payout': campaign['payout_per_install'],
            'publisher_id': publisher_id,
        }

    def get_cpi_campaigns_for_publisher(self, country: str = 'US', platform: str = 'android') -> list:
        """Get CPI offers for publisher to promote."""
        from api.promotions.models import Campaign
        offers = Campaign.objects.filter(
            status='active',
            category__name='apps',
        ).order_by('-per_task_reward')[:20]

        return [
            {
                'id': o.id,
                'app_name': o.title,
                'platform': platform,
                'payout': str(o.per_task_reward),
                'payout_display': f'${o.per_task_reward:.2f} per install',
                'category': 'Mobile App Install',
                'cta': f'Download Free App — Earn ${o.per_task_reward:.2f}',
                'tracking_url': f'/api/promotions/cpi/go/{o.id}/',
            }
            for o in offers
        ]

    def generate_publisher_tracking_url(self, campaign_id: str, publisher_id: int, subid: str = '') -> str:
        """Generate publisher's tracking URL for CPI campaign."""
        click_id = hashlib.sha256(f'{campaign_id}:{publisher_id}:{timezone.now().timestamp()}'.encode()).hexdigest()[:16]
        params = f'cid={campaign_id}&pub={publisher_id}&clickid={click_id}'
        if subid:
            params += f'&subid={subid}'
        return f'/api/promotions/cpi/click/?{params}'

    def _generate_postback_url(self, campaign_id: str, mmp_provider: str) -> str:
        from django.conf import settings
        base = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        return f'{base}/api/promotions/cpi/postback/{mmp_provider}/{campaign_id}/'

    def _get_mmp_setup_instructions(self, mmp_provider: str, postback_url: str) -> dict:
        instructions = {
            'appsflyer': {
                'steps': [
                    'Go to AppsFlyer Dashboard → My Apps → Select App',
                    'Click Integration → Integrated Partners → Search "Custom"',
                    f'Add postback URL: ' + postback_url + '&clickid={click_id}&device_id={advertising_id}&country={country_code}',
                    'Set postback trigger: Install',
                    'Save and activate',
                ],
                'doc_url': 'https://support.appsflyer.com/hc/en-us/articles/360001559405',
            },
            'adjust': {
                'steps': [
                    'Go to Adjust Dashboard → Your App → Callbacks',
                    f'Add install callback URL: {postback_url}&clickid={{adid}}&country={{country}}',
                    'Enable Install event callbacks',
                    'Save settings',
                ],
                'doc_url': 'https://help.adjust.com/en/article/callbacks',
            },
            'firebase': {
                'steps': [
                    'Go to Firebase Console → Your Project → Analytics',
                    f'Set up measurement protocol with endpoint: {postback_url}',
                    'Map parameters: click_id, country, device_id',
                    'Test with Firebase DebugView',
                ],
                'doc_url': 'https://firebase.google.com/docs/analytics',
            },
        }
        return instructions.get(mmp_provider, {'steps': ['Contact support for setup instructions']})

    def _get_publisher_from_click(self, click_id: str) -> int:
        click_data = cache.get(f'cpi_click:{click_id}', {})
        return click_data.get('publisher_id', 0)

    def _award_install_payout(self, publisher_id: int, campaign_id: str, payout: Decimal, click_id: str):
        from api.promotions.models import PromotionTransaction
        try:
            PromotionTransaction.objects.create(
                user_id=publisher_id,
                transaction_type='reward',
                amount=payout,
                status='completed',
                notes=f'CPI Install — Campaign #{campaign_id[:8]}',
                metadata={'campaign_id': campaign_id, 'click_id': click_id, 'type': 'cpi'},
            )
        except Exception as e:
            logger.error(f'CPI payout failed: {e}')


@api_view(['GET'])
@permission_classes([AllowAny])
def cpi_postback_view(request, mmp_provider, campaign_id):
    """Receive install postback from AppsFlyer/Adjust."""
    manager = CPIManager()
    result = manager.record_install_postback(
        campaign_id=campaign_id,
        mmp_provider=mmp_provider,
        click_id=request.query_params.get('clickid', ''),
        device_id=request.query_params.get('device_id', request.query_params.get('adid', '')),
        country=request.query_params.get('country', ''),
    )
    if result.get('status') == 'accepted':
        return Response(result)
    return Response(result, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_cpi_campaign_view(request):
    """Advertiser creates CPI campaign."""
    manager = CPIManager()
    data = request.data
    result = manager.create_cpi_campaign(
        advertiser_id=request.user.id,
        app_name=data.get('app_name', ''),
        app_store_url=data.get('app_store_url', ''),
        bundle_id=data.get('bundle_id', ''),
        platform=data.get('platform', 'android'),
        payout_per_install=Decimal(str(data.get('payout_per_install', '1.00'))),
        mmp_provider=data.get('mmp_provider', 'appsflyer'),
        mmp_app_id=data.get('mmp_app_id', ''),
        target_countries=data.get('target_countries', []),
        daily_cap=int(data.get('daily_cap', 1000)),
    )
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def cpi_offers_view(request):
    """GET /api/promotions/cpi/offers/?country=US&platform=android"""
    manager = CPIManager()
    offers = manager.get_cpi_campaigns_for_publisher(
        country=request.query_params.get('country', 'US'),
        platform=request.query_params.get('platform', 'android'),
    )
    return Response({'offers': offers})
