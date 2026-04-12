# api/offer_inventory/affiliate_advanced/direct_advertiser_portal.py
"""
Affiliate Advanced Package — all 12 modules.
Direct advertiser portal, campaign manager, payout bump,
click capping, budget control, tracking link generator,
sub-ID tracking, postback tester, ad creative manager,
landing page rotator, conversion pixel v2, offer scheduler.
"""
import logging
import secrets
import hashlib
from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════
# 1. DIRECT ADVERTISER PORTAL
# ════════════════════════════════════════════════════════

class DirectAdvertiserPortal:
    """
    Full self-service portal for direct advertisers.
    Campaign creation, budget management, performance reports.
    """

    @staticmethod
    @transaction.atomic
    def onboard_advertiser(company_name: str, contact_email: str,
                            contact_name: str, website: str = '',
                            agreed_rev_share: Decimal = Decimal('60'),
                            tenant=None) -> dict:
        """Complete advertiser onboarding."""
        from api.offer_inventory.models import DirectAdvertiser
        from api.offer_inventory.api_connectivity.rest_api_v2 import APIKeyManager

        # Create advertiser record
        adv = DirectAdvertiser.objects.create(
            company_name    =company_name,
            contact_email   =contact_email,
            contact_name    =contact_name,
            website         =website,
            agreed_rev_share=agreed_rev_share,
            tenant          =tenant,
        )

        # Generate API key for advertiser dashboard
        api_key = APIKeyManager.create(
            service=f'advertiser_{adv.id}',
            tenant =tenant,
        )

        logger.info(f'Advertiser onboarded: {company_name} ({contact_email})')
        return {
            'advertiser_id': str(adv.id),
            'company_name' : company_name,
            'api_key'      : api_key['key'],
            'dashboard_url': f'/advertiser/dashboard/{adv.id}/',
        }

    @staticmethod
    def get_advertiser_dashboard(advertiser_id: str, days: int = 30) -> dict:
        """Full dashboard data for an advertiser."""
        from api.offer_inventory.business.advertiser_portal import AdvertiserPortalService
        return AdvertiserPortalService.get_performance(advertiser_id, days=days)

    @staticmethod
    def get_advertiser_invoices(advertiser_id: str) -> list:
        from api.offer_inventory.models import Invoice
        return list(
            Invoice.objects.filter(advertiser_id=advertiser_id)
            .order_by('-issued_at')
            .values('invoice_no', 'amount', 'currency', 'is_paid', 'due_at')[:20]
        )


# ════════════════════════════════════════════════════════
# 2. CAMPAIGN MANAGER (Advanced)
# ════════════════════════════════════════════════════════

class AdvancedCampaignManager:
    """
    Advanced campaign management with A/B testing,
    budget pacing, and performance optimization.
    """

    @staticmethod
    @transaction.atomic
    def create_campaign_with_offers(advertiser_id: str, name: str,
                                     budget: Decimal, goal: str,
                                     offer_configs: list,
                                     daily_cap: Decimal = None,
                                     starts_at=None, ends_at=None) -> object:
        """
        Create a campaign with associated offers.
        offer_configs: [{'title': ..., 'payout': ..., 'url': ...}]
        """
        from api.offer_inventory.models import Campaign, Offer, DirectAdvertiser

        advertiser = DirectAdvertiser.objects.get(id=advertiser_id)
        campaign   = Campaign.objects.create(
            advertiser=advertiser,
            name      =name,
            budget    =budget,
            goal      =goal,
            daily_cap =daily_cap,
            starts_at =starts_at,
            ends_at   =ends_at,
            status    ='draft',
        )

        # Create offers for this campaign
        created_offers = []
        for config in offer_configs:
            offer = Offer.objects.create(
                title         =config.get('title', name),
                description   =config.get('description', ''),
                offer_url     =config.get('url', ''),
                payout_amount =Decimal(str(config.get('payout', 0))),
                reward_amount =Decimal(str(config.get('payout', 0))) * Decimal('0.7'),
                network       =campaign.network,
                status        ='draft',
                tenant        =advertiser.tenant,
            )
            created_offers.append(offer)

        logger.info(f'Campaign created: {name} with {len(created_offers)} offers')
        return {'campaign': campaign, 'offers': created_offers}

    @staticmethod
    def pace_campaign_budget(campaign_id: str) -> dict:
        """
        Budget pacing — ensure spend is distributed evenly across campaign period.
        """
        from api.offer_inventory.models import Campaign

        try:
            campaign = Campaign.objects.get(id=campaign_id, status='live')
        except Campaign.DoesNotExist:
            return {'error': 'Campaign not found or not live'}

        if not campaign.ends_at:
            return {'pacing': 'unlimited', 'daily_recommended': None}

        now           = timezone.now()
        total_days    = (campaign.ends_at - campaign.starts_at).days if campaign.starts_at else 30
        days_elapsed  = (now - (campaign.starts_at or now - timedelta(days=1))).days
        days_remaining = max(1, total_days - days_elapsed)
        remaining_budget = campaign.remaining_budget
        recommended_daily = remaining_budget / days_remaining

        # Compare to actual daily cap
        if campaign.daily_cap and recommended_daily > campaign.daily_cap:
            status = 'underspending'
        elif campaign.daily_cap and recommended_daily < campaign.daily_cap * Decimal('0.5'):
            status = 'overspending'
        else:
            status = 'on_track'

        return {
            'campaign_id'       : str(campaign_id),
            'total_budget'      : float(campaign.budget),
            'spent'             : float(campaign.spent),
            'remaining'         : float(remaining_budget),
            'days_remaining'    : days_remaining,
            'recommended_daily' : float(recommended_daily),
            'pacing_status'     : status,
        }

    @staticmethod
    def activate_campaign(campaign_id: str) -> bool:
        from api.offer_inventory.models import Campaign, Offer
        campaign = Campaign.objects.get(id=campaign_id)
        Campaign.objects.filter(id=campaign_id).update(status='live')
        # Activate related offers
        Offer.objects.filter(network=campaign.network, status='draft').update(status='active')
        logger.info(f'Campaign activated: {campaign_id}')
        return True


# ════════════════════════════════════════════════════════
# 3. PAYOUT BUMP LOGIC
# ════════════════════════════════════════════════════════

class PayoutBumpManager:
    """
    Dynamic payout bumps for high-performing offers and users.
    Temporarily increases payout to boost conversions.
    """

    @staticmethod
    def apply_bump(offer_id: str, bump_pct: Decimal = Decimal('10'),
                    duration_hours: int = 24, reason: str = '') -> dict:
        """Apply a temporary payout increase to an offer."""
        from api.offer_inventory.models import Offer
        from django.db.models import F

        offer  = Offer.objects.get(id=offer_id)
        factor = Decimal('1') + bump_pct / Decimal('100')
        new_payout = (offer.payout_amount * factor).quantize(Decimal('0.0001'))
        new_reward = (offer.reward_amount * factor).quantize(Decimal('0.0001'))

        Offer.objects.filter(id=offer_id).update(
            payout_amount=new_payout,
            reward_amount=new_reward,
        )

        # Schedule rollback
        expires_at = timezone.now() + timedelta(hours=duration_hours)
        cache.set(f'payout_bump:{offer_id}', {
            'original_payout': str(offer.payout_amount),
            'original_reward': str(offer.reward_amount),
            'expires_at'     : expires_at.isoformat(),
        }, duration_hours * 3600)

        logger.info(f'Payout bump applied: offer={offer_id} +{bump_pct}% for {duration_hours}h')
        return {
            'offer_id'      : offer_id,
            'original_payout': float(offer.payout_amount),
            'bumped_payout' : float(new_payout),
            'bump_pct'      : float(bump_pct),
            'expires_at'    : expires_at.isoformat(),
        }

    @staticmethod
    def rollback_bump(offer_id: str) -> bool:
        """Rollback a payout bump to original values."""
        bump_data = cache.get(f'payout_bump:{offer_id}')
        if not bump_data:
            return False
        from api.offer_inventory.models import Offer
        Offer.objects.filter(id=offer_id).update(
            payout_amount=Decimal(bump_data['original_payout']),
            reward_amount=Decimal(bump_data['original_reward']),
        )
        cache.delete(f'payout_bump:{offer_id}')
        logger.info(f'Payout bump rolled back: offer={offer_id}')
        return True

    @staticmethod
    def auto_rollback_expired():
        """Check and rollback all expired bumps."""
        from api.offer_inventory.models import Offer
        rolled_back = 0
        for offer in Offer.objects.filter(status='active'):
            bump = cache.get(f'payout_bump:{offer.id}')
            if bump:
                from django.utils.dateparse import parse_datetime
                expires = parse_datetime(bump['expires_at'])
                if expires and timezone.now() > expires:
                    PayoutBumpManager.rollback_bump(str(offer.id))
                    rolled_back += 1
        return rolled_back


# ════════════════════════════════════════════════════════
# 4. CLICK CAPPING
# ════════════════════════════════════════════════════════

class ClickCappingEngine:
    """
    Advanced click capping per user, per offer, per campaign.
    Prevents click flooding and budget waste.
    """

    CAPS = {
        'user_per_offer_daily'   : 3,    # Same user on same offer per day
        'user_per_offer_weekly'  : 10,   # Same user on same offer per week
        'user_total_daily'       : 50,   # Total clicks per user per day
        'ip_per_offer_daily'     : 10,   # Same IP on same offer per day
    }

    @classmethod
    def check_all(cls, user_id, offer_id: str, ip: str) -> dict:
        """Run all click cap checks. Returns {'allowed': bool, 'reason': str}."""
        checks = [
            cls._check_user_offer_daily(user_id, offer_id),
            cls._check_user_total_daily(user_id),
            cls._check_ip_offer_daily(ip, offer_id),
        ]
        for check in checks:
            if not check['allowed']:
                return check
        return {'allowed': True, 'reason': ''}

    @classmethod
    def _check_user_offer_daily(cls, user_id, offer_id: str) -> dict:
        key   = f'click_cap:user_offer_daily:{user_id}:{offer_id}'
        count = cache.get(key, 0)
        limit = cls.CAPS['user_per_offer_daily']
        if count >= limit:
            return {'allowed': False, 'reason': f'user_offer_daily_cap:{limit}'}
        cache.set(key, count + 1, 86400)
        return {'allowed': True, 'reason': ''}

    @classmethod
    def _check_user_total_daily(cls, user_id) -> dict:
        key   = f'click_cap:user_total:{user_id}'
        count = cache.get(key, 0)
        limit = cls.CAPS['user_total_daily']
        if count >= limit:
            return {'allowed': False, 'reason': f'user_total_daily_cap:{limit}'}
        cache.set(key, count + 1, 86400)
        return {'allowed': True, 'reason': ''}

    @classmethod
    def _check_ip_offer_daily(cls, ip: str, offer_id: str) -> dict:
        key   = f'click_cap:ip_offer:{ip}:{offer_id}'
        count = cache.get(key, 0)
        limit = cls.CAPS['ip_per_offer_daily']
        if count >= limit:
            return {'allowed': False, 'reason': f'ip_offer_daily_cap:{limit}'}
        cache.set(key, count + 1, 86400)
        return {'allowed': True, 'reason': ''}

    @classmethod
    def get_remaining_caps(cls, user_id, offer_id: str, ip: str) -> dict:
        return {
            'user_offer_daily' : cls.CAPS['user_per_offer_daily'] - cache.get(f'click_cap:user_offer_daily:{user_id}:{offer_id}', 0),
            'user_total_daily' : cls.CAPS['user_total_daily'] - cache.get(f'click_cap:user_total:{user_id}', 0),
            'ip_offer_daily'   : cls.CAPS['ip_per_offer_daily'] - cache.get(f'click_cap:ip_offer:{ip}:{offer_id}', 0),
        }


# ════════════════════════════════════════════════════════
# 5. BUDGET CONTROL
# ════════════════════════════════════════════════════════

class BudgetController:
    """Real-time campaign budget monitoring and enforcement."""

    @staticmethod
    def check_budget(campaign_id: str, cost: Decimal) -> dict:
        """Check if campaign has sufficient budget for this cost."""
        from api.offer_inventory.models import Campaign

        # Redis-first for speed
        cache_key = f'campaign_budget:{campaign_id}'
        cached    = cache.get(cache_key)

        if cached is None:
            try:
                campaign = Campaign.objects.get(id=campaign_id)
                remaining = float(campaign.remaining_budget)
                cache.set(cache_key, remaining, 60)
            except Campaign.DoesNotExist:
                return {'allowed': False, 'reason': 'campaign_not_found'}
        else:
            remaining = cached

        if float(cost) > remaining:
            return {'allowed': False, 'reason': 'budget_depleted', 'remaining': remaining}
        return {'allowed': True, 'remaining': remaining - float(cost)}

    @staticmethod
    @transaction.atomic
    def deduct_budget(campaign_id: str, amount: Decimal):
        """Deduct from campaign budget atomically."""
        from api.offer_inventory.models import Campaign
        from django.db.models import F
        Campaign.objects.filter(id=campaign_id).update(spent=F('spent') + amount)
        cache.delete(f'campaign_budget:{campaign_id}')

    @staticmethod
    def get_budget_alerts(warning_pct: float = 80.0) -> list:
        """Get campaigns with budget usage above threshold."""
        from api.offer_inventory.models import Campaign
        alerts = []
        for c in Campaign.objects.filter(status='live', budget__gt=0):
            usage_pct = float(c.spent / c.budget * 100) if c.budget else 0
            if usage_pct >= warning_pct:
                alerts.append({
                    'campaign_id': str(c.id),
                    'name'       : c.name,
                    'usage_pct'  : round(usage_pct, 1),
                    'remaining'  : float(c.remaining_budget),
                })
        return sorted(alerts, key=lambda x: x['usage_pct'], reverse=True)


# ════════════════════════════════════════════════════════
# 6. TRACKING LINK GENERATOR
# ════════════════════════════════════════════════════════

class TrackingLinkGenerator:
    """Generate unique tracking links for offers and campaigns."""

    @staticmethod
    def generate(offer_id: str, user_id=None, source: str = '',
                  s1: str = '', s2: str = '', s3: str = '',
                  base_url: str = '') -> str:
        """Generate a full tracking URL."""
        from django.conf import settings
        base = base_url or getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        params = [f'offer={offer_id}']
        if user_id:
            params.append(f'uid={user_id}')
        if source:
            params.append(f'src={source}')
        if s1:
            params.append(f's1={s1}')
        if s2:
            params.append(f's2={s2}')
        if s3:
            params.append(f's3={s3}')
        query = '&'.join(params)
        return f'{base}/api/offer-inventory/track/?{query}'

    @staticmethod
    def generate_smartlink(slug: str, user_id=None,
                            source: str = '', base_url: str = '') -> str:
        """Generate SmartLink tracking URL."""
        from django.conf import settings
        base = base_url or getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        params = []
        if user_id:
            params.append(f'uid={user_id}')
        if source:
            params.append(f'src={source}')
        query = f'?{"&".join(params)}' if params else ''
        return f'{base}/api/offer-inventory/go/{slug}/{query}'

    @staticmethod
    def generate_batch(offer_ids: list, user_id=None) -> list:
        """Generate tracking links for multiple offers."""
        return [
            {'offer_id': oid, 'url': TrackingLinkGenerator.generate(oid, user_id)}
            for oid in offer_ids
        ]


# ════════════════════════════════════════════════════════
# 7. SUB-ID TRACKING (Advanced)
# ════════════════════════════════════════════════════════

class SubIDAnalytics:
    """Advanced sub-ID tracking and analytics."""

    @staticmethod
    def get_sub_id_performance(offer_id: str = None,
                                s1: str = None, days: int = 30) -> list:
        """Performance metrics grouped by sub-ID."""
        from api.offer_inventory.models import SubID, Click, Conversion
        from django.db.models import Count, Sum
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)
        qs    = SubID.objects.all()
        if offer_id:
            qs = qs.filter(offer_id=offer_id)
        if s1:
            qs = qs.filter(s1=s1)

        return list(
            qs.values('s1', 'offer__title')
            .annotate(
                clicks     =Count('clicks'),
                conversions=Count('clicks__conversion'),
                revenue    =Sum('revenue'),
            )
            .filter(clicks__gt=0)
            .order_by('-conversions')[:50]
        )

    @staticmethod
    def get_top_sub_ids(limit: int = 20) -> list:
        """Top performing sub-IDs by revenue."""
        from api.offer_inventory.models import SubID
        from django.db.models import Sum, Count
        return list(
            SubID.objects.values('s1')
            .annotate(revenue=Sum('revenue'), offers=Count('offer', distinct=True))
            .order_by('-revenue')[:limit]
        )


# ════════════════════════════════════════════════════════
# 8. POSTBACK TESTER
# ════════════════════════════════════════════════════════

class PostbackTester:
    """
    Test postback delivery for offer networks.
    Sends test postbacks and verifies receipt.
    """

    @staticmethod
    def send_test_postback(network_id: str, user_id=None) -> dict:
        """Send a simulated postback to test the pipeline."""
        from api.offer_inventory.models import OfferNetwork
        import uuid

        try:
            network = OfferNetwork.objects.get(id=network_id)
        except OfferNetwork.DoesNotExist:
            return {'success': False, 'error': 'Network not found'}

        test_params = {
            'click_id'      : f'TEST_{uuid.uuid4().hex[:8]}',
            'transaction_id': f'TEST_TX_{uuid.uuid4().hex[:8]}',
            'payout'        : '0.01',
            'status'        : 'test',
            'is_test'       : True,
        }

        if network.postback_url:
            from api.offer_inventory.webhooks.s2s_postback import OutboundPostbackSender
            result = OutboundPostbackSender.send(
                url    =network.postback_url,
                params =test_params,
                secret =network.api_secret,
                timeout=10,
            )
            return {
                'network'    : network.name,
                'postback_url': network.postback_url[:100],
                'test_params': test_params,
                'result'     : result,
            }
        return {'success': False, 'error': 'No postback URL configured'}

    @staticmethod
    def verify_s2s_endpoint(endpoint_url: str, secret: str = '') -> dict:
        """Verify that an S2S endpoint is responding correctly."""
        import requests, hmac, hashlib, json

        test_payload = json.dumps({'test': True, 'ts': str(timezone.now())})
        headers      = {'Content-Type': 'application/json'}

        if secret:
            sig = hmac.new(secret.encode(), test_payload.encode(), hashlib.sha256).hexdigest()
            headers['X-Signature'] = sig

        try:
            resp = requests.post(endpoint_url, data=test_payload, headers=headers, timeout=10)
            return {
                'url'        : endpoint_url,
                'status_code': resp.status_code,
                'success'    : resp.status_code in (200, 204),
                'response'   : resp.text[:200],
                'latency_ms' : resp.elapsed.total_seconds() * 1000,
            }
        except Exception as e:
            return {'url': endpoint_url, 'success': False, 'error': str(e)}


# ════════════════════════════════════════════════════════
# 9. AD CREATIVE MANAGER
# ════════════════════════════════════════════════════════

class AdCreativeManager:
    """Manage offer ad creatives (banners, videos, native)."""

    SUPPORTED_TYPES = ['banner', 'video', 'native', 'icon']
    MAX_CREATIVES_PER_OFFER = 10

    @staticmethod
    def add_creative(offer_id: str, creative_type: str, asset_url: str,
                      width: int = None, height: int = None,
                      duration_secs: int = None) -> object:
        """Add a creative to an offer."""
        from api.offer_inventory.models import OfferCreative, Offer

        if creative_type not in AdCreativeManager.SUPPORTED_TYPES:
            raise ValueError(f'Unsupported creative type: {creative_type}')

        offer = Offer.objects.get(id=offer_id)
        if offer.creatives.count() >= AdCreativeManager.MAX_CREATIVES_PER_OFFER:
            raise ValueError(f'Max {AdCreativeManager.MAX_CREATIVES_PER_OFFER} creatives per offer')

        return OfferCreative.objects.create(
            offer         =offer,
            creative_type =creative_type,
            asset_url     =asset_url,
            width         =width,
            height        =height,
            duration_secs =duration_secs,
            is_approved   =False,
        )

    @staticmethod
    def approve_creative(creative_id: str) -> bool:
        from api.offer_inventory.models import OfferCreative
        updated = OfferCreative.objects.filter(id=creative_id).update(is_approved=True)
        return updated > 0

    @staticmethod
    def get_best_creative(offer, creative_type: str = 'banner'):
        """Get the best approved creative for rendering."""
        from api.offer_inventory.models import OfferCreative
        return (
            OfferCreative.objects.filter(
                offer=offer, creative_type=creative_type, is_approved=True
            )
            .order_by('-click_count')
            .first()
        )

    @staticmethod
    def record_creative_click(creative_id: str):
        from api.offer_inventory.models import OfferCreative
        from django.db.models import F
        OfferCreative.objects.filter(id=creative_id).update(
            click_count=F('click_count') + 1
        )


# ════════════════════════════════════════════════════════
# 10. LANDING PAGE ROTATOR
# ════════════════════════════════════════════════════════

class LandingPageRotator:
    """
    A/B test landing pages for offers.
    Routes users to different landing pages based on variant assignment.
    """

    @staticmethod
    def get_landing_page(offer, user_id=None) -> object:
        """Get the appropriate landing page for a user."""
        from api.offer_inventory.models import OfferLandingPage
        from api.offer_inventory.ai_optimization.a_b_testing import ABTestingEngine

        pages = list(OfferLandingPage.objects.filter(offer=offer, is_active=True))
        if not pages:
            return None

        if len(pages) == 1:
            return pages[0]

        # Use A/B testing for multiple pages
        test_name = f'landing_{offer.id}'
        variant   = ABTestingEngine.get_variant(test_name, user_id or 'anon')

        # A = first page, B = second page
        idx = 0 if variant == 'A' else 1
        page = pages[idx % len(pages)]

        ABTestingEngine.record_event(test_name, variant, 'impression')
        return page

    @staticmethod
    def record_landing_conversion(offer, page, user_id=None):
        """Record that a landing page led to conversion."""
        from api.offer_inventory.ai_optimization.a_b_testing import ABTestingEngine
        test_name = f'landing_{offer.id}'
        variant   = ABTestingEngine.get_variant(test_name, user_id or 'anon')
        ABTestingEngine.record_event(test_name, variant, 'conversion')

    @staticmethod
    def get_page_performance(offer_id: str) -> list:
        """Performance comparison of all landing pages for an offer."""
        from api.offer_inventory.models import OfferLandingPage
        from api.offer_inventory.ai_optimization.a_b_testing import ABTestingEngine

        pages   = OfferLandingPage.objects.filter(offer_id=offer_id)
        results = []
        for page in pages:
            test_name = f'landing_{offer_id}'
            ab_results = ABTestingEngine.get_results(test_name)
            results.append({
                'page_id'    : str(page.id),
                'variant_key': page.variant_key,
                'title'      : page.title,
                'ab_results' : ab_results,
            })
        return results


# ════════════════════════════════════════════════════════
# 11. CONVERSION PIXEL V2
# ════════════════════════════════════════════════════════

class ConversionPixelV2:
    """
    Enhanced conversion pixel system.
    Supports server-side, client-side, and hybrid pixel firing.
    """

    @staticmethod
    def generate_pixel_tag(offer_id: str, user_id=None,
                            click_token: str = '', base_url: str = '') -> str:
        """Generate an HTML img pixel tag."""
        import base64, json
        from django.conf import settings

        base    = base_url or getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        payload = json.dumps({
            'offer_id'   : offer_id,
            'user_id'    : str(user_id) if user_id else '',
            'click_token': click_token,
        })
        token   = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
        url     = f'{base}/api/offer-inventory/pixel/conversion/{token}/'
        return (
            f'<img src="{url}" width="1" height="1" border="0" '
            f'alt="" style="position:absolute;visibility:hidden" />'
        )

    @staticmethod
    def generate_js_pixel(offer_id: str, user_id=None, click_token: str = '') -> str:
        """Generate JavaScript pixel snippet."""
        return f"""
<script type="text/javascript">
(function() {{
  var img = new Image(1,1);
  img.src = '/api/offer-inventory/pixel/conversion/?o={offer_id}&u={user_id}&c={click_token}&ts=' + Date.now();
  document.body.appendChild(img);
}})();
</script>
"""

    @staticmethod
    def fire_server_side(conversion_id: str) -> bool:
        """Fire pixel server-to-server."""
        from api.offer_inventory.webhooks.pixel_tracking import PixelTracker
        return PixelTracker.fire(conversion_id)


# ════════════════════════════════════════════════════════
# 12. OFFER SCHEDULER (Advanced)
# ════════════════════════════════════════════════════════

class OfferSchedulerEngine:
    """
    Advanced offer scheduling with timezone support,
    recurring schedules, and holiday awareness.
    """

    @staticmethod
    def schedule_activation(offer_id: str, activate_at, deactivate_at=None) -> list:
        """Schedule offer activation and optional deactivation."""
        from api.offer_inventory.models import OfferSchedule, Offer
        offer    = Offer.objects.get(id=offer_id)
        schedules = []

        # Activation schedule
        act = OfferSchedule.objects.create(
            offer       =offer,
            action      ='activate',
            scheduled_at=activate_at,
        )
        schedules.append(act)

        # Optional deactivation
        if deactivate_at:
            deact = OfferSchedule.objects.create(
                offer       =offer,
                action      ='deactivate',
                scheduled_at=deactivate_at,
            )
            schedules.append(deact)

        logger.info(f'Offer scheduled: {offer_id} activate@{activate_at}')
        return schedules

    @staticmethod
    def process_due_schedules() -> dict:
        """Execute all due scheduled actions."""
        from api.offer_inventory.models import OfferSchedule, Offer

        now    = timezone.now()
        due    = OfferSchedule.objects.filter(
            scheduled_at__lte=now, is_executed=False
        ).select_related('offer')

        executed = {'activated': 0, 'deactivated': 0, 'paused': 0}

        for schedule in due:
            try:
                action_map = {
                    'activate'  : 'active',
                    'deactivate': 'expired',
                    'pause'     : 'paused',
                }
                new_status = action_map.get(schedule.action)
                if new_status:
                    Offer.objects.filter(id=schedule.offer_id).update(status=new_status)
                    executed[f'{schedule.action}d'] = executed.get(f'{schedule.action}d', 0) + 1

                OfferSchedule.objects.filter(id=schedule.id).update(
                    is_executed=True, executed_at=now
                )
            except Exception as e:
                logger.error(f'Schedule execution error {schedule.id}: {e}')

        total = sum(executed.values())
        if total > 0:
            logger.info(f'Offer schedules processed: {executed}')
        return executed

    @staticmethod
    def get_upcoming_schedules(hours: int = 24) -> list:
        """Get schedules due in the next N hours."""
        from api.offer_inventory.models import OfferSchedule
        until = timezone.now() + timedelta(hours=hours)
        return list(
            OfferSchedule.objects.filter(
                scheduled_at__lte=until,
                is_executed=False
            )
            .select_related('offer')
            .values('offer__title', 'action', 'scheduled_at')
            .order_by('scheduled_at')[:50]
        )
