"""
Tests for FloatingModelViewSets — 9 previously inaccessible models now wired.
"""
import uuid
import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status as drf_status

User = get_user_model()

from api.smartlink.tests.test_helpers import (
    make_user, make_offer, make_smartlink, make_click,
    make_payout_record, make_profile, make_wallet,
    make_offer_pool_entry, make_batch, auth_client,
    # backwards-compatible aliases (legacy _make_* names)
    _make_user, _make_offer, _make_smartlink, _make_sl,
    _make_click, _make_profile, _make_payout_record, _make_batch,
    _make_offer_pool_entry,
)

def _auth(user):
    c = APIClient()
    c.force_authenticate(user)
    return c

# ═════════════════════════════════════════════════════════════════════════════
# 1. SmartLinkRotation
# ═════════════════════════════════════════════════════════════════════════════

class SmartLinkRotationViewSetTest(TestCase):

    def setUp(self):
        self.pub   = _make_user('rot_pub')
        self.admin = _make_user('rot_admin', is_staff=True)
        self.sl    = _make_sl(self.pub)
        self.url   = f'/api/smartlink/smartlinks/{self.sl.pk}/rotation/'

    def test_get_rotation_auto_creates_default(self):
        """GET rotation/ creates a default rotation config if none exists."""
        from api.smartlink.models.smartlink import SmartLinkRotation
        resp = _auth(self.pub).get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('method', resp.json())
        self.assertEqual(SmartLinkRotation.objects.filter(smartlink=self.sl).count(), 1)

    def test_get_rotation_returns_existing(self):
        """GET rotation/ returns existing SmartLinkRotation."""
        from api.smartlink.models.smartlink import SmartLinkRotation
        from api.smartlink.choices import RotationMethod
        SmartLinkRotation.objects.create(smartlink=self.sl, method=RotationMethod.ROUND_ROBIN)
        resp = _auth(self.pub).get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['method'], RotationMethod.ROUND_ROBIN)

    def test_patch_rotation_updates_method(self):
        """PATCH rotation/ updates the rotation method."""
        _auth(self.pub).get(self.url)  # create default
        resp = _auth(self.pub).patch(
            self.url,
            {'method': 'epc_optimized', 'auto_optimize_epc': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['method'], 'epc_optimized')
        self.assertTrue(resp.json()['auto_optimize_epc'])

    def test_other_publisher_gets_404(self):
        """Publisher cannot read another publisher's rotation config."""
        other = _make_user('rot_other')
        resp = _auth(other).get(self.url)
        self.assertEqual(resp.status_code, 404)

    def test_admin_can_access_any_rotation(self):
        """Admin can read any SmartLink rotation config."""
        resp = _auth(self.admin).get(self.url)
        self.assertEqual(resp.status_code, 200)

# ═════════════════════════════════════════════════════════════════════════════
# 2. SmartLinkFallback
# ═════════════════════════════════════════════════════════════════════════════

class SmartLinkFallbackViewSetTest(TestCase):

    def setUp(self):
        self.pub = _make_user('fb_pub')
        self.sl  = _make_sl(self.pub)
        self.url = f'/api/smartlink/smartlinks/{self.sl.pk}/fallback/'

    def test_get_returns_404_when_not_configured(self):
        resp = _auth(self.pub).get(self.url)
        self.assertEqual(resp.status_code, 404)

    def test_create_fallback(self):
        resp = _auth(self.pub).post(
            self.url, {'url': 'https://fb.example.com', 'reason': 'Default'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['url'], 'https://fb.example.com')

    def test_get_after_create(self):
        _auth(self.pub).post(self.url, {'url': 'https://fb.example.com'}, format='json')
        resp = _auth(self.pub).get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['url'], 'https://fb.example.com')

    def test_patch_fallback_url(self):
        _auth(self.pub).post(self.url, {'url': 'https://old.example.com'}, format='json')
        resp = _auth(self.pub).patch(
            self.url, {'url': 'https://new.example.com'}, format='json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['url'], 'https://new.example.com')

    def test_delete_fallback(self):
        _auth(self.pub).post(self.url, {'url': 'https://del.example.com'}, format='json')
        resp = _auth(self.pub).delete(self.url)
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(_auth(self.pub).get(self.url).status_code, 404)

    def test_toggle_flips_is_active(self):
        _auth(self.pub).post(self.url, {'url': 'https://tog.example.com'}, format='json')
        resp = _auth(self.pub).post(f'{self.url}toggle/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['is_active'])

    def test_duplicate_create_returns_400(self):
        _auth(self.pub).post(self.url, {'url': 'https://fb1.example.com'}, format='json')
        resp = _auth(self.pub).post(self.url, {'url': 'https://fb2.example.com'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_other_publisher_gets_404(self):
        other = _make_user('fb_other')
        resp = _auth(other).get(self.url)
        self.assertEqual(resp.status_code, 404)

# ═════════════════════════════════════════════════════════════════════════════
# 3. SmartLinkVersion
# ═════════════════════════════════════════════════════════════════════════════

class SmartLinkVersionViewSetTest(TestCase):

    def setUp(self):
        self.pub   = _make_user('ver_pub')
        self.admin = _make_user('ver_admin', is_staff=True)
        self.sl    = _make_sl(self.pub)
        self.url   = f'/api/smartlink/smartlinks/{self.sl.pk}/versions/'

    def test_create_version(self):
        resp = _auth(self.pub).post(
            self.url,
            {'name': 'Control', 'traffic_split': 50, 'is_control': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['name'], 'Control')

    def test_list_versions(self):
        _auth(self.pub).post(self.url, {'name': 'A', 'traffic_split': 60}, format='json')
        _auth(self.pub).post(self.url, {'name': 'B', 'traffic_split': 40}, format='json')
        resp = _auth(self.pub).get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 2)

    def test_summary_totals(self):
        _auth(self.pub).post(self.url, {'name': 'A', 'traffic_split': 60}, format='json')
        _auth(self.pub).post(self.url, {'name': 'B', 'traffic_split': 40}, format='json')
        resp = _auth(self.pub).get(f'{self.url}summary/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total_traffic_split'], 100)
        self.assertEqual(resp.json()['remaining_unallocated'], 0)

    def test_mark_winner_requires_admin(self):
        cr = _auth(self.pub).post(self.url, {'name': 'V1', 'traffic_split': 50}, format='json')
        ver_id = cr.json()['id']
        resp = _auth(self.pub).post(f'{self.url}{ver_id}/mark-winner/')
        self.assertEqual(resp.status_code, 403)

    def test_admin_marks_winner(self):
        cr = _auth(self.pub).post(self.url, {'name': 'V1', 'traffic_split': 50}, format='json')
        ver_id = cr.json()['id']
        resp = _auth(self.admin).post(f'{self.url}{ver_id}/mark-winner/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['is_winner'])

    def test_other_publisher_sees_empty_list(self):
        _auth(self.pub).post(self.url, {'name': 'V1', 'traffic_split': 50}, format='json')
        other = _make_user('ver_other')
        resp = _auth(other).get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 0)

# ═════════════════════════════════════════════════════════════════════════════
# 4. ClickSession
# ═════════════════════════════════════════════════════════════════════════════

class ClickSessionViewSetTest(TestCase):

    def setUp(self):
        from api.smartlink.models import ClickSession
        self.pub = _make_user('sess_pub')
        self.sl  = _make_sl(self.pub)
        self.url = f'/api/smartlink/smartlinks/{self.sl.pk}/sessions/'
        ClickSession.objects.create(
            smartlink=self.sl, ip='10.0.0.1', user_agent='Mozilla',
            country='US', device_type='mobile', click_count=3,
        )
        ClickSession.objects.create(
            smartlink=self.sl, ip='10.0.0.2', user_agent='Chrome',
            country='GB', device_type='desktop', click_count=1,
        )

    def test_list_sessions(self):
        resp = _auth(self.pub).get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 2)

    def test_filter_by_country(self):
        resp = _auth(self.pub).get(f'{self.url}?country=US')
        self.assertEqual(resp.status_code, 200)
        for s in resp.json():
            self.assertEqual(s['country'], 'US')

    def test_filter_by_device_type(self):
        resp = _auth(self.pub).get(f'{self.url}?device_type=mobile')
        self.assertEqual(resp.status_code, 200)
        for s in resp.json():
            self.assertEqual(s['device_type'], 'mobile')

    def test_summary_endpoint(self):
        resp = _auth(self.pub).get(f'{self.url}summary/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total_sessions'], 2)
        self.assertIn('US', data['countries'])
        self.assertIn('GB', data['countries'])

    def test_post_not_allowed(self):
        resp = _auth(self.pub).post(self.url, {'ip': '1.1.1.1'}, format='json')
        self.assertEqual(resp.status_code, 405)

    def test_other_publisher_sees_empty(self):
        other = _make_user('sess_other')
        resp = _auth(other).get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 0)

# ═════════════════════════════════════════════════════════════════════════════
# 5. BotClick
# ═════════════════════════════════════════════════════════════════════════════

class BotClickViewSetTest(TestCase):

    def setUp(self):
        from api.smartlink.models import BotClick
        self.pub = _make_user('bot_pub')
        self.sl  = _make_sl(self.pub)
        self.url = f'/api/smartlink/smartlinks/{self.sl.pk}/bot-clicks/'
        BotClick.objects.create(
            smartlink=self.sl, ip='5.6.7.8', user_agent='Googlebot/2.1',
            bot_type='Googlebot', detection_method='ua_pattern', country='US',
        )
        BotClick.objects.create(
            smartlink=self.sl, ip='9.0.1.2', user_agent='SEMrushBot',
            bot_type='SEMrush', detection_method='ip_list', country='DE',
        )

    def test_list_bot_clicks(self):
        resp = _auth(self.pub).get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 2)

    def test_filter_by_bot_type(self):
        resp = _auth(self.pub).get(f'{self.url}?bot_type=Googlebot')
        self.assertEqual(resp.status_code, 200)
        for bc in resp.json():
            self.assertEqual(bc['bot_type'], 'Googlebot')

    def test_filter_by_country(self):
        resp = _auth(self.pub).get(f'{self.url}?country=DE')
        self.assertEqual(resp.status_code, 200)
        for bc in resp.json():
            self.assertEqual(bc['country'], 'DE')

    def test_summary_endpoint(self):
        resp = _auth(self.pub).get(f'{self.url}summary/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total_bot_clicks'], 2)
        self.assertIn('by_bot_type', data)

    def test_post_not_allowed(self):
        resp = _auth(self.pub).post(self.url, {}, format='json')
        self.assertEqual(resp.status_code, 405)

    def test_other_publisher_sees_empty(self):
        other = _make_user('bot_other')
        resp = _auth(other).get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 0)

# ═════════════════════════════════════════════════════════════════════════════
# 6. PublisherAllowList
# ═════════════════════════════════════════════════════════════════════════════

class PublisherAllowListViewSetTest(TestCase):

    def setUp(self):
        self.pub   = _make_user('al_pub')
        self.admin = _make_user('al_admin', is_staff=True)
        self.url   = '/api/smartlink/publisher/allow-list/'

    def test_publisher_can_list_own_allow_list(self):
        resp = _auth(self.pub).get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_publisher_cannot_create(self):
        resp = _auth(self.pub).post(
            self.url, {'publisher': self.pub.pk, 'category': 'gaming'}, format='json'
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_grant_access(self):
        resp = _auth(self.admin).post(
            self.url,
            {'publisher': self.pub.pk, 'category': 'finance', 'is_active': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['category'], 'finance')

    def test_admin_toggle_entry(self):
        cr = _auth(self.admin).post(
            self.url,
            {'publisher': self.pub.pk, 'category': 'health', 'is_active': True},
            format='json',
        )
        entry_id = cr.json()['id']
        resp = _auth(self.admin).post(f'{self.url}{entry_id}/toggle/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['is_active'])

    def test_publisher_cannot_toggle(self):
        """Publisher cannot toggle allow-list entries (admin-only action)."""
        from api.smartlink.models.publisher import PublisherAllowList
        entry = PublisherAllowList.objects.create(
            publisher=self.pub, category='gaming',
            is_active=True, granted_by=self.admin,
        )
        # publisher is not staff → toggle uses IsAdminUser → 403
        resp = _auth(self.pub).post(f'{self.url}{entry.pk}/toggle/')
        self.assertIn(resp.status_code, [403, 405],
                      msg="Publisher must not be able to toggle allow-list entries")

    def test_admin_filter_by_publisher_id(self):
        from api.smartlink.models.publisher import PublisherAllowList
        PublisherAllowList.objects.create(
            publisher=self.pub, category='gaming',
            is_active=True, granted_by=self.admin,
        )
        resp = _auth(self.admin).get(f'{self.url}?publisher_id={self.pub.pk}')
        self.assertEqual(resp.status_code, 200)
        for e in resp.json():
            self.assertEqual(e['publisher'], self.pub.pk)

# ═════════════════════════════════════════════════════════════════════════════
# 7. PublisherBlockList
# ═════════════════════════════════════════════════════════════════════════════

class PublisherBlockListViewSetTest(TestCase):

    def setUp(self):
        self.pub   = _make_user('bl_pub')
        self.admin = _make_user('bl_admin', is_staff=True)
        self.url   = '/api/smartlink/publisher/block-list/'

    def test_publisher_can_list_own_block_list(self):
        resp = _auth(self.pub).get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_publisher_cannot_create(self):
        resp = _auth(self.pub).post(
            self.url, {'publisher': self.pub.pk, 'category': 'adult'}, format='json'
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_block_category(self):
        resp = _auth(self.admin).post(
            self.url,
            {'publisher': self.pub.pk, 'category': 'adult', 'reason': 'Policy'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['category'], 'adult')

    def test_admin_can_delete_entry(self):
        from api.smartlink.models.publisher import PublisherBlockList
        entry = PublisherBlockList.objects.create(
            publisher=self.pub, category='gambling',
            is_active=True, blocked_by=self.admin,
        )
        resp = _auth(self.admin).delete(f'{self.url}{entry.pk}/')
        self.assertEqual(resp.status_code, 204)

    def test_admin_toggle_block_entry(self):
        from api.smartlink.models.publisher import PublisherBlockList
        entry = PublisherBlockList.objects.create(
            publisher=self.pub, category='crypto',
            is_active=True, blocked_by=self.admin,
        )
        resp = _auth(self.admin).post(f'{self.url}{entry.pk}/toggle/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['is_active'])

# ═════════════════════════════════════════════════════════════════════════════
# 8. RedirectChain
# ═════════════════════════════════════════════════════════════════════════════

class RedirectChainViewSetTest(TestCase):

    def setUp(self):
        from api.smartlink.models.redirect import RedirectChain
        self.pub   = _make_user('rc_pub')
        self.admin = _make_user('rc_admin', is_staff=True)
        self.sl    = _make_sl(self.pub)
        self.click = _make_click(self.sl)
        self.url   = f'/api/smartlink/smartlinks/{self.sl.pk}/redirect-chains/'
        from django.utils import timezone as tz
        ts_now = tz.now().isoformat()
        RedirectChain.objects.create(
            smartlink=self.sl, click=self.click,
            chain=[
                {'step': 1, 'type': 'pre_lander', 'url': 'https://pl.example.com', 'ts': ts_now},
                {'step': 2, 'type': 'offer',      'url': 'https://offer.example.com', 'ts': ts_now},
            ],
            hop_count=2,
        )
        RedirectChain.objects.create(
            smartlink=self.sl, click=self.click,
            chain=[{'step': 1, 'type': 'offer', 'url': 'https://direct.example.com', 'ts': ts_now}],
            hop_count=1,
        )

    def test_list_redirect_chains(self):
        resp = _auth(self.pub).get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 2)

    def test_filter_by_click_id(self):
        resp = _auth(self.pub).get(f'{self.url}?click_id={self.click.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 2)

    def test_filter_by_min_hops(self):
        resp = _auth(self.pub).get(f'{self.url}?min_hops=2')
        self.assertEqual(resp.status_code, 200)
        for chain in resp.json():
            self.assertGreaterEqual(chain['hop_count'], 2)

    def test_summary_endpoint(self):
        resp = _auth(self.pub).get(f'{self.url}summary/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total_chains'], 2)
        self.assertEqual(data['max_hop_count'], 2)

    def test_post_not_allowed(self):
        resp = _auth(self.pub).post(self.url, {'chain': []}, format='json')
        self.assertEqual(resp.status_code, 405)

    def test_other_publisher_sees_empty(self):
        other = _make_user('rc_other')
        resp = _auth(other).get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 0)

    def test_admin_sees_all(self):
        resp = _auth(self.admin).get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 2)
