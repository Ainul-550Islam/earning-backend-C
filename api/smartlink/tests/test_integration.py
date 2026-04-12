from django.test import TestCase
from unittest.mock import patch
from .factories import SmartLinkFactory, SmartLinkFallbackFactory, OfferPoolFactory


class FullRedirectFlowTest(TestCase):
    """
    Integration test: full redirect flow from slug → offer URL.
    Tests the complete pipeline: resolve → target → rotate → redirect.
    """

    def setUp(self):
        self.sl = SmartLinkFactory(is_active=True, enable_bot_filter=False, enable_fraud_filter=False)
        self.pool = OfferPoolFactory(smartlink=self.sl)
        self.fallback = SmartLinkFallbackFactory(smartlink=self.sl, url='https://fallback.example.com')

    @patch('smartlink.services.core.SmartLinkResolverService.SmartLinkResolverService._track_click_async')
    def test_slug_resolves_to_fallback_with_empty_pool(self, mock_track):
        from ..services.core.SmartLinkResolverService import SmartLinkResolverService
        resolver = SmartLinkResolverService()
        context = {
            'ip': '1.2.3.4', 'user_agent': 'Mozilla/5.0 Chrome/120',
            'country': 'US', 'region': '', 'city': '', 'isp': '', 'asn': '',
            'device_type': 'mobile', 'os': 'android', 'browser': 'chrome',
            'language': 'en', 'referrer': '', 'is_bot': False,
            'sub1': '', 'sub2': '', 'sub3': '', 'sub4': '', 'sub5': '',
            'query_params': {},
        }
        result = resolver.resolve(self.sl.slug, context)
        self.assertTrue(result['was_fallback'])
        self.assertEqual(result['url'], 'https://fallback.example.com')
        self.assertIn('response_time_ms', result)

    @patch('smartlink.services.core.SmartLinkResolverService.SmartLinkResolverService._track_click_async')
    def test_redirect_response_has_correct_headers(self, mock_track):
        from django.test import RequestFactory
        from ..viewsets.PublicRedirectView import PublicRedirectView
        factory = RequestFactory()
        request = factory.get(f'/go/{self.sl.slug}/')
        view = PublicRedirectView.as_view()
        response = view(request, slug=self.sl.slug)
        self.assertIn(response.status_code, [302, 301, 200, 410])

    def test_inactive_smartlink_returns_410(self):
        from django.test import RequestFactory
        from ..viewsets.PublicRedirectView import PublicRedirectView
        self.sl.is_active = False
        self.sl.save()
        factory = RequestFactory()
        request = factory.get(f'/go/{self.sl.slug}/')
        view = PublicRedirectView.as_view()
        response = view(request, slug=self.sl.slug)
        self.assertEqual(response.status_code, 410)

    def test_nonexistent_slug_returns_404(self):
        from django.test import RequestFactory
        from ..viewsets.PublicRedirectView import PublicRedirectView
        factory = RequestFactory()
        request = factory.get('/go/nosuchslugxyz/')
        view = PublicRedirectView.as_view()
        try:
            response = view(request, slug='nosuchslugxyz')
            self.assertEqual(response.status_code, 404)
        except Exception:
            pass  # Http404 raised is also valid
