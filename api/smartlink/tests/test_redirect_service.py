"""
Tests for RedirectService and LandingPageService.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from django.http import HttpResponseRedirect, HttpResponse
from .factories import SmartLinkFactory, UserFactory, ClickFactory
from ..models import LandingPage, PreLander


class RedirectServiceTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        from ..services.redirect.RedirectService import RedirectService
        self.svc = RedirectService()

    def test_302_redirect_sets_correct_status(self):
        result = {
            'url': 'https://offer.example.com/',
            'redirect_type': '302',
            'offer_id': 1,
        }
        response = self.svc.build_response(result)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://offer.example.com/')

    def test_301_redirect_sets_correct_status(self):
        result = {
            'url': 'https://offer.example.com/',
            'redirect_type': '301',
            'offer_id': 2,
        }
        response = self.svc.build_response(result)
        self.assertEqual(response.status_code, 301)

    def test_meta_refresh_redirect_returns_html(self):
        result = {
            'url': 'https://offer.example.com/',
            'redirect_type': 'meta',
            'offer_id': 3,
        }
        response = self.svc.build_response(result)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'meta http-equiv', response.content)
        self.assertIn(b'offer.example.com', response.content)

    def test_javascript_redirect_returns_html(self):
        result = {
            'url': 'https://offer.example.com/',
            'redirect_type': 'js',
            'offer_id': 4,
        }
        response = self.svc.build_response(result)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'window.location.replace', response.content)

    def test_unknown_redirect_type_falls_back_to_302(self):
        result = {
            'url': 'https://offer.example.com/',
            'redirect_type': 'unknown_type',
            'offer_id': 5,
        }
        response = self.svc.build_response(result)
        self.assertEqual(response.status_code, 302)

    def test_security_headers_always_set(self):
        result = {
            'url': 'https://offer.example.com/',
            'redirect_type': '302',
            'offer_id': 1,
        }
        response = self.svc.build_response(result)
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['Pragma'], 'no-cache')

    def test_offer_id_header_set(self):
        result = {
            'url': 'https://offer.example.com/',
            'redirect_type': '302',
            'offer_id': 42,
        }
        response = self.svc.build_response(result)
        self.assertEqual(response['X-SmartLink-Offer'], '42')

    def test_offer_id_empty_string_when_missing(self):
        result = {
            'url': 'https://offer.example.com/',
            'redirect_type': '302',
        }
        response = self.svc.build_response(result)
        self.assertEqual(response['X-SmartLink-Offer'], '')

    def test_meta_refresh_html_escapes_quotes_in_url(self):
        html = self.svc._meta_refresh_html('https://example.com/?a="b"')
        self.assertNotIn('"b"', html)
        self.assertIn('%22b%22', html)

    def test_javascript_redirect_escapes_single_quotes(self):
        html = self.svc._javascript_redirect_html("https://example.com/?q=it's")
        self.assertNotIn("it's", html)
        self.assertIn("it\\'s", html)

    def test_log_redirect_creates_db_record(self):
        sl = SmartLinkFactory()
        click = ClickFactory(smartlink=sl)
        request = self.factory.get(f'/go/{sl.slug}/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        result = {
            'url': 'https://offer.example.com/',
            'offer_id': None,
            'country': 'US',
            'device_type': 'mobile',
            'redirect_type': '302',
            'response_time_ms': 5.2,
            'was_cached': True,
            'was_fallback': False,
            'ip': '1.2.3.4',
        }
        with patch('smartlink.utils.get_client_ip', return_value='1.2.3.4'):
            self.svc.log_redirect(sl, result, request, click=click)

        from ..models import RedirectLog
        self.assertEqual(RedirectLog.objects.filter(smartlink=sl).count(), 1)
        log = RedirectLog.objects.get(smartlink=sl)
        self.assertEqual(log.destination_url, 'https://offer.example.com/')
        self.assertTrue(log.was_cached)
        self.assertFalse(log.was_fallback)

    def test_log_redirect_silently_handles_exception(self):
        """log_redirect must never raise — it is fire-and-forget."""
        sl = SmartLinkFactory()
        result = {'url': 'https://offer.example.com/', 'offer_id': None}
        # Pass None as request — should not raise
        try:
            self.svc.log_redirect(sl, result, request=None)
        except Exception as e:
            self.fail(f"log_redirect raised unexpectedly: {e}")


class LandingPageServiceTest(TestCase):
    def setUp(self):
        from ..services.redirect.LandingPageService import LandingPageService
        self.svc = LandingPageService()
        self.sl = SmartLinkFactory()

    # ── select_landing_page ──────────────────────────────────────────────────

    def test_returns_none_when_no_landing_pages(self):
        result = self.svc.select_landing_page(self.sl)
        self.assertIsNone(result)

    def test_returns_single_active_page(self):
        lp = LandingPage.objects.create(
            smartlink=self.sl, name='LP', url='https://lp.example.com/',
            is_active=True, is_default=True, traffic_split=100,
        )
        result = self.svc.select_landing_page(self.sl)
        self.assertEqual(result, lp)

    def test_ignores_inactive_pages(self):
        LandingPage.objects.create(
            smartlink=self.sl, name='Inactive', url='https://inactive.example.com/',
            is_active=False, traffic_split=100,
        )
        result = self.svc.select_landing_page(self.sl)
        self.assertIsNone(result)

    def test_weighted_selection_produces_valid_result(self):
        lp1 = LandingPage.objects.create(
            smartlink=self.sl, name='LP1', url='https://lp1.example.com/',
            is_active=True, traffic_split=70,
        )
        lp2 = LandingPage.objects.create(
            smartlink=self.sl, name='LP2', url='https://lp2.example.com/',
            is_active=True, traffic_split=30,
        )
        results = set()
        for _ in range(50):
            chosen = self.svc.select_landing_page(self.sl)
            self.assertIsNotNone(chosen)
            results.add(chosen.pk)
        # Both landing pages should be selected at least once in 50 tries
        self.assertIn(lp1.pk, results)
        self.assertIn(lp2.pk, results)

    def test_zero_traffic_split_falls_back_to_first_page(self):
        lp = LandingPage.objects.create(
            smartlink=self.sl, name='Zero Split LP',
            url='https://lp.example.com/', is_active=True, traffic_split=0,
        )
        result = self.svc.select_landing_page(self.sl)
        self.assertEqual(result, lp)

    # ── select_pre_lander ────────────────────────────────────────────────────

    def test_returns_none_when_no_pre_landers(self):
        result = self.svc.select_pre_lander(self.sl)
        self.assertIsNone(result)

    def test_returns_first_active_pre_lander(self):
        pl = PreLander.objects.create(
            smartlink=self.sl, name='Survey',
            url='https://survey.example.com/', type='survey', is_active=True,
        )
        result = self.svc.select_pre_lander(self.sl)
        self.assertEqual(result, pl)

    # ── build_landing_page_url ───────────────────────────────────────────────

    def test_lp_url_appends_sub_params(self):
        lp = LandingPage.objects.create(
            smartlink=self.sl, name='LP', url='https://lp.example.com/',
            is_active=True, traffic_split=100,
        )
        context = {'sub1': 'campaign_123', 'slug': self.sl.slug}
        url = self.svc.build_landing_page_url(lp, context)
        self.assertIn('sub1=campaign_123', url)
        self.assertIn('sl=', url)

    def test_lp_url_skips_empty_subs(self):
        lp = LandingPage.objects.create(
            smartlink=self.sl, name='LP2', url='https://lp2.example.com/',
            is_active=True, traffic_split=100,
        )
        context = {'sub1': '', 'sub2': '', 'slug': self.sl.slug}
        url = self.svc.build_landing_page_url(lp, context)
        self.assertNotIn('sub1=', url)
        self.assertNotIn('sub2=', url)

    # ── build_pre_lander_url ─────────────────────────────────────────────────

    def test_pre_lander_url_passes_params_when_enabled(self):
        pl = PreLander.objects.create(
            smartlink=self.sl, name='Quiz', url='https://quiz.example.com/',
            type='quiz', is_active=True, pass_through_params=True,
        )
        context = {'sub1': 'camp_abc', 'sub2': 'adset_01'}
        url = self.svc.build_pre_lander_url(pl, context)
        self.assertIn('sub1=camp_abc', url)

    def test_pre_lander_url_returns_bare_url_when_disabled(self):
        pl = PreLander.objects.create(
            smartlink=self.sl, name='Video', url='https://video.example.com/',
            type='video', is_active=True, pass_through_params=False,
        )
        context = {'sub1': 'camp_xyz'}
        url = self.svc.build_pre_lander_url(pl, context)
        self.assertEqual(url, 'https://video.example.com/')

    # ── counter updates ──────────────────────────────────────────────────────

    def test_record_landing_page_view_increments_counter(self):
        lp = LandingPage.objects.create(
            smartlink=self.sl, name='LP', url='https://lp.example.com/',
            is_active=True, traffic_split=100, views=10,
        )
        self.svc.record_landing_page_view(lp)
        lp.refresh_from_db()
        self.assertEqual(lp.views, 11)

    def test_record_pre_lander_view_increments_counter(self):
        pl = PreLander.objects.create(
            smartlink=self.sl, name='Survey', url='https://survey.example.com/',
            type='survey', is_active=True, views=5,
        )
        self.svc.record_pre_lander_view(pl)
        pl.refresh_from_db()
        self.assertEqual(pl.views, 6)

    def test_record_pass_through_increments_counter(self):
        pl = PreLander.objects.create(
            smartlink=self.sl, name='Survey2', url='https://survey2.example.com/',
            type='survey', is_active=True, pass_through_count=3,
        )
        self.svc.record_pass_through(pl)
        pl.refresh_from_db()
        self.assertEqual(pl.pass_through_count, 4)
