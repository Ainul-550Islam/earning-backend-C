# api/payment_gateways/locker/LockerEngine.py
# Content locker unlock orchestration

import uuid
import logging
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class LockerEngine:
    """
    Orchestrates content locker interactions.

    Flow:
        1. Visitor hits publisher's page
        2. JS calls /locker/show/{key}/ → returns offers to show
        3. Visitor completes offer → advertiser fires postback
        4. PostbackEngine triggers LockerEngine.unlock()
        5. Locker marks session as unlocked
        6. JS unhides / redirects to locked content
    """

    def show(self, locker_key: str, visitor_ip: str, user_agent: str = '',
             country: str = '', device: str = 'desktop') -> dict:
        """
        Called when a visitor hits the locker.
        Returns the best offer(s) to display.
        """
        from .models import ContentLocker, LockerSession
        from api.payment_gateways.rtb.BiddingEngine import BiddingEngine

        try:
            locker = ContentLocker.objects.get(locker_key=locker_key, status='active')
        except ContentLocker.DoesNotExist:
            return {'error': 'Locker not found', 'locked': False}

        # Check if visitor already unlocked (via cookie/session cache)
        session_cache_key = f'locker_unlocked:{locker_key}:{visitor_ip}'
        if cache.get(session_cache_key):
            return {'locked': False, 'already_unlocked': True}

        # Select best offers via RTB engine
        engine   = BiddingEngine()
        offers   = engine.find_offers_for_offerwall(
            publisher = locker.publisher,
            country   = country,
            device    = device,
            limit     = locker.show_offer_count,
        )

        if locker.require_specific_offer:
            offers = [locker.require_specific_offer]

        # Create session
        session_id = uuid.uuid4().hex

        # Calculate unlock expiry
        hours = int(locker.unlock_duration_hours) if locker.unlock_duration_hours != 'never' else None
        expires = timezone.now() + timezone.timedelta(hours=hours) if hours else None

        click_ids = []
        for offer in offers:
            from api.payment_gateways.tracking.ClickTracker import ClickTracker

            class _FakeRequest:
                META = {
                    'HTTP_USER_AGENT': user_agent,
                    'REMOTE_ADDR':     visitor_ip,
                }
                def get(self, key, default=''):
                    return self.META.get(key, default)

            tracker = ClickTracker()
            try:
                click, redirect_url = tracker.track(
                    offer=offer,
                    publisher=locker.publisher,
                    request=_FakeRequest(),
                    extra_params={'sub1': locker_key, 'sub2': session_id}
                )
                click_ids.append({'offer_id': offer.id, 'click_id': click.click_id,
                                   'redirect_url': redirect_url})
            except Exception as e:
                logger.warning(f'Click tracking failed: {e}')
                click_ids.append({'offer_id': offer.id, 'click_id': '', 'redirect_url': '#'})

        # Update impressions
        ContentLocker.objects.filter(id=locker.id).update(
            total_impressions=locker.total_impressions + 1
        )

        return {
            'locked':       True,
            'session_id':   session_id,
            'locker_type':  locker.locker_type,
            'title':        locker.title,
            'description':  locker.description,
            'theme':        locker.theme,
            'primary_color':locker.primary_color,
            'offers':       [
                {
                    'id':           o.id,
                    'name':         o.name,
                    'description':  o.short_desc or o.description[:100],
                    'payout':       str(o.publisher_payout),
                    'offer_type':   o.offer_type,
                    'click_url':    next((c['redirect_url'] for c in click_ids if c['offer_id'] == o.id), '#'),
                    'app_icon':     o.app_icon_url or '',
                    'category':     o.category,
                }
                for o in offers
            ],
            'unlock_after_seconds': 30,  # Wait before allowing unlock claim
        }

    def unlock(self, locker_key: str, click_id: str, conversion_id: str = '') -> dict:
        """
        Called by PostbackEngine after successful conversion.
        Marks the locker session as unlocked.
        """
        from .models import ContentLocker, LockerSession

        try:
            locker = ContentLocker.objects.get(locker_key=locker_key, status='active')
        except ContentLocker.DoesNotExist:
            return {'success': False, 'message': 'Locker not found'}

        # Get original session from click
        from api.payment_gateways.tracking.models import Click
        try:
            click    = Click.objects.get(click_id=click_id)
            visitor_ip = click.ip_address
            payout   = click.payout
        except Click.DoesNotExist:
            payout   = Decimal('0')
            visitor_ip = ''

        # Cache unlock status
        duration_hours = int(locker.unlock_duration_hours) if locker.unlock_duration_hours not in ('0','never') else None
        if duration_hours:
            ttl = duration_hours * 3600
            cache.set(f'locker_unlocked:{locker_key}:{visitor_ip}', True, ttl)
        elif locker.unlock_duration_hours == 'never':
            cache.set(f'locker_unlocked:{locker_key}:{visitor_ip}', True, 86400 * 365)

        # Update earnings
        ContentLocker.objects.filter(id=locker.id).update(
            total_unlocks=locker.total_unlocks + 1,
            total_earnings=locker.total_earnings + payout,
        )

        # Return what to show the user after unlock
        unlock_data = {
            'success':          True,
            'locker_type':      locker.locker_type,
            'destination_url':  locker.destination_url if locker.locker_type == 'url_locker' else '',
            'file_url':         locker.file_upload.url if locker.file_upload else '',
            'overlay_selector': locker.overlay_selector,
            'message':          'Content unlocked!',
        }

        logger.info(f'Locker unlocked: {locker_key} click_id={click_id}')
        return unlock_data

    def check_unlock_status(self, locker_key: str, visitor_ip: str) -> bool:
        """Check if a visitor has already unlocked this locker."""
        return bool(cache.get(f'locker_unlocked:{locker_key}:{visitor_ip}'))


class OfferWallEngine:
    """
    Orchestrates offerwall interactions with virtual currency rewards.
    """

    def get_offers(self, wall_key: str, user_id: str, country: str = '',
                   device: str = 'mobile') -> dict:
        """
        Get ranked offers for an offerwall display.
        Called by publisher's app/website.
        """
        from .models import OfferWall, UserVirtualBalance
        from api.payment_gateways.rtb.BiddingEngine import BiddingEngine
        from django.contrib.auth import get_user_model

        try:
            wall = OfferWall.objects.get(wall_key=wall_key, status='active')
        except OfferWall.DoesNotExist:
            return {'error': 'Offerwall not found'}

        # Get or create user virtual balance
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
            balance_obj, _ = UserVirtualBalance.objects.get_or_create(
                user=user, offer_wall=wall,
                defaults={'balance': Decimal('0')}
            )
            user_balance = float(balance_obj.balance)
        except (User.DoesNotExist, ValueError):
            user_balance = 0

        # Get ranked offers
        engine = BiddingEngine()

        class _FakePublisher:
            id = wall.publisher_id
            is_staff = False
            def is_authenticated(self): return True

        offers = engine.find_offers_for_offerwall(
            publisher=wall.publisher,
            country=country,
            device=device,
            limit=20,
        )

        return {
            'wall_name':      wall.name,
            'currency_name':  wall.currency_name,
            'currency_icon':  wall.currency_icon_url,
            'user_balance':   user_balance,
            'exchange_rate':  float(wall.exchange_rate),
            'offers': [
                {
                    'id':          o.id,
                    'name':        o.name,
                    'description': o.short_desc or '',
                    'reward':      float(wall.usd_to_virtual(o.publisher_payout)),
                    'currency':    wall.currency_name,
                    'offer_type':  o.offer_type,
                    'icon':        o.app_icon_url or '',
                    'category':    o.category,
                    'cta':         self._get_cta(o.offer_type),
                }
                for o in offers
            ],
        }

    def credit_reward(self, wall_key: str, user_id: str,
                      payout_usd: Decimal, offer_id: int = None,
                      conversion_id: str = None) -> dict:
        """
        Credit virtual currency to a user after offer completion.
        Called by PostbackEngine on successful conversion.
        """
        from .models import OfferWall, UserVirtualBalance, VirtualReward
        from django.contrib.auth import get_user_model
        from django.db import transaction as db_txn

        try:
            wall = OfferWall.objects.get(wall_key=wall_key, status='active')
        except OfferWall.DoesNotExist:
            return {'success': False, 'error': 'Offerwall not found'}

        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except (User.DoesNotExist, ValueError):
            return {'success': False, 'error': 'User not found'}

        virtual_amount = wall.usd_to_virtual(payout_usd)

        with db_txn.atomic():
            balance_obj, _ = UserVirtualBalance.objects.get_or_create(
                user=user, offer_wall=wall,
                defaults={'balance': Decimal('0')}
            )
            balance_obj.balance     += virtual_amount
            balance_obj.total_earned+= virtual_amount
            balance_obj.save()

            VirtualReward.objects.create(
                user=user,
                offer_wall=wall,
                reward_type='earned',
                amount=virtual_amount,
                usd_equivalent=payout_usd,
                offer_id=offer_id,
                description=f'Offer completion reward',
            )

            # Update offerwall stats
            OfferWall.objects.filter(id=wall.id).update(
                total_completions=wall.total_completions + 1,
                total_earnings=wall.total_earnings + payout_usd,
            )

            # Fire publisher postback if configured
            if wall.postback_url:
                self._fire_postback(wall, user_id, virtual_amount, payout_usd)

        logger.info(f'OfferWall reward: user={user_id} wall={wall_key} +{virtual_amount} {wall.currency_name}')
        return {
            'success':        True,
            'reward':         float(virtual_amount),
            'currency':       wall.currency_name,
            'new_balance':    float(balance_obj.balance),
            'usd_equivalent': float(payout_usd),
        }

    def _get_cta(self, offer_type: str) -> str:
        return {
            'cpi': 'Install App',
            'cpa': 'Complete Action',
            'cpc': 'Click & Earn',
            'cpl': 'Submit Form',
            'cps': 'Shop & Earn',
        }.get(offer_type, 'Earn Reward')

    def _fire_postback(self, wall, user_id: str, virtual_amount: Decimal, usd: Decimal):
        """Fire publisher's server-side postback to credit user."""
        import threading
        import requests

        def fire():
            url = wall.postback_url
            url = url.replace('{user_id}', str(user_id))
            url = url.replace('{amount}', str(virtual_amount))
            url = url.replace('{currency}', wall.currency_name)
            url = url.replace('{usd}', str(usd))
            try:
                requests.get(url, timeout=10)
            except Exception as e:
                logger.warning(f'Offerwall postback failed: {e}')

        threading.Thread(target=fire, daemon=True).start()
