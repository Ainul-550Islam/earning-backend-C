"""
Comprehensive view tests covering all SmartLink ViewSets.
Includes previously-missing coverage for:
  AdminSmartLinkViewSet, HeatmapViewSet, LandingPageViewSet,
  MLInsightViewSet, OfferBlacklistViewSet, PreLanderViewSet,
  PublisherAPIViewSet, PublisherSmartLinkViewSet,
  RedirectLogViewSet, ReportViewSet, PostbackLogViewSet.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .factories import (
    SmartLinkFactory, UserFactory, SmartLinkGroupFactory, ClickFactory,
)
from ..models import (
    LandingPage, PreLander, OfferBlacklist, RedirectLog,
)
from ..models.click import ClickHeatmap
from ..models.publisher import PublisherSmartLink
from ..models.postback_log import PostbackLog

User = get_user_model()


# ─── SmartLink CRUD ──────────────────────────────────────────────────────────

class SmartLinkAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.publisher = UserFactory()
        self.client.force_authenticate(user=self.publisher)
        self.sl = SmartLinkFactory(publisher=self.publisher)

    def test_list_smartlinks(self):
        response = self.client.get('/api/smartlink/smartlinks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_create_smartlink(self):
        data = {'name': 'New Link', 'type': 'general'}
        response = self.client.post('/api/smartlink/smartlinks/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('slug', response.data)

    def test_retrieve_smartlink(self):
        response = self.client.get(f'/api/smartlink/smartlinks/{self.sl.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['slug'], self.sl.slug)

    def test_update_smartlink_name(self):
        response = self.client.patch(
            f'/api/smartlink/smartlinks/{self.sl.pk}/',
            {'name': 'Updated Name'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_smartlink_archives(self):
        response = self.client.delete(f'/api/smartlink/smartlinks/{self.sl.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.sl.refresh_from_db()
        self.assertTrue(self.sl.is_archived)

    def test_cannot_access_other_publisher_smartlink(self):
        other = UserFactory()
        other_sl = SmartLinkFactory(publisher=other)
        response = self.client.get(f'/api/smartlink/smartlinks/{other_sl.pk}/')
        self.assertIn(response.status_code, [403, 404])

    def test_toggle_active(self):
        response = self.client.post(f'/api/smartlink/smartlinks/{self.sl.pk}/toggle-active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.sl.refresh_from_db()
        self.assertFalse(self.sl.is_active)

    def test_stats_endpoint(self):
        response = self.client.get(f'/api/smartlink/smartlinks/{self.sl.pk}/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('clicks', response.data)

    def test_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/smartlink/smartlinks/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─── PublicRedirectView ───────────────────────────────────────────────────────

class PublicRedirectViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sl = SmartLinkFactory(is_active=True)

    def test_invalid_slug_returns_404(self):
        response = self.client.get('/go/nonexistentslugxyz/')
        self.assertEqual(response.status_code, 404)

    def test_inactive_link_returns_410(self):
        self.sl.is_active = False
        self.sl.save()
        response = self.client.get(f'/go/{self.sl.slug}/')
        self.assertEqual(response.status_code, 410)


# ─── AdminSmartLinkViewSet ────────────────────────────────────────────────────

class AdminSmartLinkViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(is_staff=True)
        self.publisher = UserFactory()
        self.client.force_authenticate(user=self.admin)
        SmartLinkFactory.create_batch(3, publisher=self.publisher)
        SmartLinkFactory(publisher=self.admin)

    def test_admin_can_list_all_smartlinks(self):
        response = self.client.get('/api/smartlink/admin/smartlinks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        # Admin sees all smartlinks across publishers
        self.assertGreaterEqual(response.data['count'], 4)

    def test_non_admin_denied(self):
        self.client.force_authenticate(user=self.publisher)
        response = self.client.get('/api/smartlink/admin/smartlinks/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/smartlink/admin/smartlinks/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_platform_stats(self):
        response = self.client.get('/api/smartlink/admin/smartlinks/platform-stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_smartlinks', response.data)
        self.assertIn('active_smartlinks', response.data)
        self.assertIn('total_clicks', response.data)

    def test_admin_health_check(self):
        response = self.client.get('/api/smartlink/admin/smartlinks/health-check/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('broken_count', response.data)
        self.assertIn('broken', response.data)

    def test_admin_can_retrieve_any_smartlink(self):
        sl = SmartLinkFactory(publisher=self.publisher)
        response = self.client.get(f'/api/smartlink/admin/smartlinks/{sl.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['slug'], sl.slug)

    def test_admin_warmup_cache(self):
        with patch(
            'smartlink.services.core.SmartLinkCacheService.SmartLinkCacheService.warmup_all_active',
            return_value=5
        ):
            response = self.client.post('/api/smartlink/admin/smartlinks/warmup-cache/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('cached', response.data)

    def test_admin_invalidate_cache(self):
        sl = SmartLinkFactory()
        with patch(
            'smartlink.services.core.SmartLinkCacheService.SmartLinkCacheService.invalidate_smartlink'
        ):
            response = self.client.post(
                f'/api/smartlink/admin/smartlinks/{sl.pk}/invalidate-cache/'
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['slug'], sl.slug)

    def test_admin_can_search_by_publisher_username(self):
        response = self.client.get(
            f'/api/smartlink/admin/smartlinks/?search={self.publisher.username}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ─── HeatmapViewSet ───────────────────────────────────────────────────────────

class HeatmapViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.publisher = UserFactory()
        self.sl = SmartLinkFactory(publisher=self.publisher)
        self.client.force_authenticate(user=self.publisher)
        ClickHeatmap.objects.create(
            smartlink=self.sl,
            country='US',
            date='2024-01-01',
            click_count=500,
            unique_click_count=400,
            conversion_count=20,
            revenue=100,
            epc=0.20,
        )
        ClickHeatmap.objects.create(
            smartlink=self.sl,
            country='BD',
            date='2024-01-01',
            click_count=300,
            unique_click_count=250,
            conversion_count=8,
            revenue=40,
            epc=0.13,
        )

    def test_list_heatmap_data(self):
        response = self.client.get(
            f'/api/smartlink/smartlinks/{self.sl.pk}/heatmap/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_aggregate_endpoint(self):
        with patch(
            'smartlink.services.analytics.HeatmapService.HeatmapService.get_heatmap',
            return_value={'countries': []}
        ):
            response = self.client.get(
                f'/api/smartlink/smartlinks/{self.sl.pk}/heatmap/aggregate/?days=30'
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_top_countries_endpoint(self):
        with patch(
            'smartlink.services.analytics.HeatmapService.HeatmapService.get_top_countries',
            return_value=[{'country': 'US', 'clicks': 500}]
        ):
            response = self.client.get(
                f'/api/smartlink/smartlinks/{self.sl.pk}/heatmap/top-countries/?limit=5'
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(
            f'/api/smartlink/smartlinks/{self.sl.pk}/heatmap/'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_publisher_denied(self):
        other = UserFactory()
        self.client.force_authenticate(user=other)
        response = self.client.get(
            f'/api/smartlink/smartlinks/{self.sl.pk}/heatmap/'
        )
        self.assertIn(response.status_code, [403, 404])


# ─── LandingPageViewSet ───────────────────────────────────────────────────────

class LandingPageViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.publisher = UserFactory()
        self.sl = SmartLinkFactory(publisher=self.publisher)
        self.client.force_authenticate(user=self.publisher)
        self.lp = LandingPage.objects.create(
            smartlink=self.sl,
            name='My LP',
            url='https://lp.example.com/',
            is_active=True,
            is_default=True,
            traffic_split=100,
        )

    def test_list_landing_pages(self):
        response = self.client.get(
            f'/api/smartlink/smartlinks/{self.sl.pk}/landing-pages/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_landing_page(self):
        data = {
            'name': 'LP 2',
            'url': 'https://lp2.example.com/',
            'traffic_split': 50,
        }
        response = self.client.post(
            f'/api/smartlink/smartlinks/{self.sl.pk}/landing-pages/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'LP 2')

    def test_retrieve_landing_page(self):
        response = self.client.get(
            f'/api/smartlink/smartlinks/{self.sl.pk}/landing-pages/{self.lp.pk}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'My LP')

    def test_update_landing_page(self):
        response = self.client.patch(
            f'/api/smartlink/smartlinks/{self.sl.pk}/landing-pages/{self.lp.pk}/',
            {'name': 'Updated LP'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lp.refresh_from_db()
        self.assertEqual(self.lp.name, 'Updated LP')

    def test_delete_landing_page(self):
        response = self.client.delete(
            f'/api/smartlink/smartlinks/{self.sl.pk}/landing-pages/{self.lp.pk}/'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LandingPage.objects.filter(pk=self.lp.pk).exists())

    def test_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(
            f'/api/smartlink/smartlinks/{self.sl.pk}/landing-pages/'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─── PreLanderViewSet ─────────────────────────────────────────────────────────

class PreLanderViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.publisher = UserFactory()
        self.sl = SmartLinkFactory(publisher=self.publisher)
        self.client.force_authenticate(user=self.publisher)
        self.pl = PreLander.objects.create(
            smartlink=self.sl,
            name='Survey',
            url='https://survey.example.com/',
            type='survey',
            is_active=True,
        )

    def test_list_pre_landers(self):
        response = self.client.get(
            f'/api/smartlink/smartlinks/{self.sl.pk}/pre-landers/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_pre_lander(self):
        data = {
            'name': 'Quiz',
            'url': 'https://quiz.example.com/',
            'type': 'quiz',
            'pass_through_params': True,
        }
        response = self.client.post(
            f'/api/smartlink/smartlinks/{self.sl.pk}/pre-landers/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['type'], 'quiz')

    def test_retrieve_pre_lander(self):
        response = self.client.get(
            f'/api/smartlink/smartlinks/{self.sl.pk}/pre-landers/{self.pl.pk}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Survey')

    def test_update_pre_lander(self):
        response = self.client.patch(
            f'/api/smartlink/smartlinks/{self.sl.pk}/pre-landers/{self.pl.pk}/',
            {'name': 'Updated Survey'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_pre_lander(self):
        response = self.client.delete(
            f'/api/smartlink/smartlinks/{self.sl.pk}/pre-landers/{self.pl.pk}/'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(PreLander.objects.filter(pk=self.pl.pk).exists())


# ─── OfferBlacklistViewSet ────────────────────────────────────────────────────

class OfferBlacklistViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.publisher = UserFactory()
        self.sl = SmartLinkFactory(publisher=self.publisher)
        self.client.force_authenticate(user=self.publisher)

    def test_list_blacklist_empty(self):
        response = self.client.get(
            f'/api/smartlink/smartlinks/{self.sl.pk}/blacklist/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_create_blacklist_entry_requires_offer(self):
        """Creating without a valid offer FK should fail validation."""
        data = {'offer': 99999, 'reason': 'Low quality'}
        response = self.client.post(
            f'/api/smartlink/smartlinks/{self.sl.pk}/blacklist/',
            data
        )
        # Expect 400 because offer 99999 does not exist
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(
            f'/api/smartlink/smartlinks/{self.sl.pk}/blacklist/'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_publisher_cannot_see_blacklist(self):
        other = UserFactory()
        other_sl = SmartLinkFactory(publisher=other)
        self.client.force_authenticate(user=self.publisher)
        response = self.client.get(
            f'/api/smartlink/smartlinks/{other_sl.pk}/blacklist/'
        )
        # Returns empty — no cross-publisher leak
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


# ─── RedirectLogViewSet ───────────────────────────────────────────────────────

class RedirectLogViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.publisher = UserFactory()
        self.sl = SmartLinkFactory(publisher=self.publisher)
        self.client.force_authenticate(user=self.publisher)
        # Create redirect log entries
        for _ in range(3):
            RedirectLog.objects.create(
                smartlink=self.sl,
                ip='1.2.3.4',
                country='US',
                device_type='mobile',
                redirect_type='302',
                destination_url='https://offer.example.com/',
                status_code=302,
                response_time_ms=4.2,
            )

    def test_list_redirect_logs(self):
        response = self.client.get(
            f'/api/smartlink/smartlinks/{self.sl.pk}/redirect-logs/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 3)

    def test_cannot_write_redirect_logs(self):
        """RedirectLog is read-only — POST must be rejected."""
        data = {'ip': '9.9.9.9', 'destination_url': 'https://test.com'}
        response = self.client.post(
            f'/api/smartlink/smartlinks/{self.sl.pk}/redirect-logs/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_admin_can_see_all_logs(self):
        admin = UserFactory(is_staff=True)
        other_sl = SmartLinkFactory(publisher=UserFactory())
        RedirectLog.objects.create(
            smartlink=other_sl,
            ip='5.5.5.5',
            country='GB',
            device_type='desktop',
            redirect_type='302',
            destination_url='https://other-offer.example.com/',
            status_code=302,
            response_time_ms=3.1,
        )
        self.client.force_authenticate(user=admin)
        response = self.client.get(
            f'/api/smartlink/smartlinks/{other_sl.pk}/redirect-logs/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_publisher_cannot_see_other_publisher_logs(self):
        other_publisher = UserFactory()
        other_sl = SmartLinkFactory(publisher=other_publisher)
        RedirectLog.objects.create(
            smartlink=other_sl,
            ip='7.7.7.7',
            country='DE',
            device_type='mobile',
            redirect_type='302',
            destination_url='https://other.example.com/',
            status_code=302,
            response_time_ms=2.5,
        )
        response = self.client.get(
            f'/api/smartlink/smartlinks/{other_sl.pk}/redirect-logs/'
        )
        # Publisher sees empty list — no data leak
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    def test_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(
            f'/api/smartlink/smartlinks/{self.sl.pk}/redirect-logs/'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─── PublisherSmartLinkViewSet ────────────────────────────────────────────────

class PublisherSmartLinkViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.publisher = UserFactory()
        self.admin = UserFactory(is_staff=True)
        self.sl = SmartLinkFactory(publisher=self.publisher)
        self.client.force_authenticate(user=self.publisher)
        self.assignment = PublisherSmartLink.objects.create(
            publisher=self.publisher,
            smartlink=self.sl,
            is_active=True,
            assigned_by=self.admin,
        )

    def test_publisher_lists_own_assignments(self):
        response = self.client.get('/api/smartlink/publisher/smartlinks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [item['smartlink'] for item in response.data]
        self.assertIn(self.sl.pk, slugs)

    def test_publisher_cannot_see_other_assignments(self):
        other = UserFactory()
        other_sl = SmartLinkFactory(publisher=other)
        PublisherSmartLink.objects.create(
            publisher=other,
            smartlink=other_sl,
            is_active=True,
        )
        response = self.client.get('/api/smartlink/publisher/smartlinks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only sees own assignments
        self.assertEqual(len(response.data), 1)

    def test_cannot_write_via_publisher_smartlink_viewset(self):
        """PublisherSmartLinkViewSet is read-only."""
        response = self.client.post(
            '/api/smartlink/publisher/smartlinks/',
            {'smartlink': self.sl.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/smartlink/publisher/smartlinks/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─── PublisherAPIViewSet ──────────────────────────────────────────────────────

class PublisherAPIViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.publisher = UserFactory()
        self.client.force_authenticate(user=self.publisher)
        SmartLinkFactory.create_batch(3, publisher=self.publisher, is_active=True)
        # Create inactive to verify filtering
        SmartLinkFactory(publisher=self.publisher, is_active=False)

    def test_my_smartlinks_only_returns_active(self):
        response = self.client.get('/api/smartlink/publisher/api/my-smartlinks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

    def test_my_stats_returns_aggregate_data(self):
        with patch(
            'smartlink.services.analytics.SmartLinkAnalyticsService'
            '.SmartLinkAnalyticsService.get_publisher_summary',
            return_value={'total_clicks': 1000, 'total_revenue': '250.00'}
        ):
            response = self.client.get(
                '/api/smartlink/publisher/api/my-stats/?days=30'
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/smartlink/publisher/api/my-smartlinks/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_publisher_cannot_see_my_smartlinks(self):
        other = UserFactory()
        SmartLinkFactory.create_batch(2, publisher=other, is_active=True)
        # Our publisher still sees only their own 3
        response = self.client.get('/api/smartlink/publisher/api/my-smartlinks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)


# ─── ReportViewSet ────────────────────────────────────────────────────────────

class ReportViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.publisher = UserFactory()
        self.client.force_authenticate(user=self.publisher)

    def _mock_report_service(self, method_name, return_value):
        return patch(
            f'smartlink.reports.PublisherReportService.PublisherReportService.{method_name}',
            return_value=return_value,
        )

    def test_performance_report_default_params(self):
        with self._mock_report_service('performance_report', {'rows': [], 'totals': {}}):
            response = self.client.get('/api/smartlink/reports/performance/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('rows', response.data)

    def test_performance_report_with_date_range(self):
        with self._mock_report_service('performance_report', {'rows': []}):
            response = self.client.get(
                '/api/smartlink/reports/performance/?date_from=2024-01-01&date_to=2024-01-31'
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_quality_report(self):
        with self._mock_report_service('quality_report', {'quality_score': 85}):
            with patch(
                'smartlink.services.antifraud.ClickQualityScore'
                '.ClickQualityScore.get_publisher_quality_report',
                return_value={'fraud_rate': 0.02}
            ):
                response = self.client.get('/api/smartlink/reports/quality/?days=7')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_payout_report_defaults_to_current_month(self):
        with patch(
            'smartlink.services.billing.PublisherPayoutService'
            '.PublisherPayoutService.calculate_period_payout',
            return_value={'total_payout': '500.00', 'currency': 'USD'}
        ):
            response = self.client.get('/api/smartlink/reports/payout/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_payout', response.data)

    def test_payout_report_with_explicit_dates(self):
        with patch(
            'smartlink.services.billing.PublisherPayoutService'
            '.PublisherPayoutService.calculate_period_payout',
            return_value={'total_payout': '200.00', 'currency': 'USD'}
        ):
            response = self.client.get(
                '/api/smartlink/reports/payout/?date_from=2024-01-01&date_to=2024-01-31'
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_top_performers(self):
        with self._mock_report_service('top_performers', [{'slug': 'abc', 'epc': 0.50}]):
            response = self.client.get('/api/smartlink/reports/top-performers/?days=7&limit=5')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_hourly_heatmap(self):
        heatmap = [[0] * 24 for _ in range(7)]
        with self._mock_report_service('hourly_heatmap', heatmap):
            response = self.client.get('/api/smartlink/reports/hourly-heatmap/?days=7')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('heatmap', response.data)

    def test_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/smartlink/reports/performance/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─── MLInsightViewSet ─────────────────────────────────────────────────────────

class MLInsightViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.publisher = UserFactory()
        self.client.force_authenticate(user=self.publisher)

    def test_score_click_returns_fraud_and_quality(self):
        with patch(
            'smartlink.services.ml.FraudMLScorer.FraudMLScorer.score_click',
            return_value=(0.12, ['low_velocity'])
        ):
            with patch(
                'smartlink.services.ml.FraudMLScorer.FraudMLScorer.score_to_100',
                return_value=12
            ):
                with patch(
                    'smartlink.services.antifraud.ClickQualityScore'
                    '.ClickQualityScore.calculate',
                    return_value={'score': 90, 'recommendation': 'allow'}
                ):
                    response = self.client.post(
                        '/api/smartlink/ml/score-click/',
                        {
                            'ip': '8.8.8.8',
                            'user_agent': 'Mozilla/5.0',
                            'country': 'US',
                            'device_type': 'mobile',
                        },
                        format='json',
                    )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('fraud', response.data)
        self.assertIn('quality', response.data)
        self.assertIn('summary', response.data)

    def test_score_click_high_fraud_recommends_block(self):
        with patch(
            'smartlink.services.ml.FraudMLScorer.FraudMLScorer.score_click',
            return_value=(0.92, ['datacenter_asn', 'headless_browser', 'proxy_vpn'])
        ):
            with patch(
                'smartlink.services.ml.FraudMLScorer.FraudMLScorer.score_to_100',
                return_value=92
            ):
                with patch(
                    'smartlink.services.antifraud.ClickQualityScore'
                    '.ClickQualityScore.calculate',
                    return_value={'score': 5, 'recommendation': 'block'}
                ):
                    response = self.client.post(
                        '/api/smartlink/ml/score-click/',
                        {'ip': '1.1.1.1', 'user_agent': 'HeadlessChrome'},
                        format='json',
                    )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['fraud']['action'], 'block')

    def test_confidence_endpoint(self):
        with patch(
            'smartlink.services.ml.SmartRotationMLEngine'
            '.SmartRotationMLEngine.get_offer_confidence_interval',
            return_value={'mean': 0.05, 'lower': 0.03, 'upper': 0.08}
        ):
            with patch(
                'smartlink.services.ml.SmartRotationMLEngine'
                '.SmartRotationMLEngine.detect_performance_anomaly',
                return_value={'is_anomaly': False}
            ):
                response = self.client.get(
                    '/api/smartlink/ml/confidence/?offer_id=1&country=US&device=mobile'
                )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('confidence_interval', response.data)
        self.assertIn('anomaly', response.data)

    def test_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        response = self.client.post('/api/smartlink/ml/score-click/', {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─── PostbackLogViewSet ───────────────────────────────────────────────────────

class PostbackLogViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(is_staff=True)
        self.publisher = UserFactory()
        self.client.force_authenticate(user=self.admin)
        PostbackLog.objects.create(
            click_id='click_abc123',
            offer_id='offer_456',
            event='lead',
            payout='2.5000',
            currency='USD',
            transaction_id='txn_xyz',
        )
        PostbackLog.objects.create(
            click_id='click_def789',
            offer_id='offer_456',
            event='sale',
            payout='15.0000',
            currency='USD',
            transaction_id='txn_uvw',
        )

    def test_admin_can_list_postback_logs(self):
        response = self.client.get('/api/smartlink/postback-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 2)

    def test_postback_log_contains_expected_fields(self):
        response = self.client.get('/api/smartlink/postback-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if response.data['results']:
            first = response.data['results'][0]
            for field in ('click_id', 'offer_id', 'event', 'payout', 'currency'):
                self.assertIn(field, first)

    def test_postback_logs_are_read_only(self):
        response = self.client.post(
            '/api/smartlink/postback-logs/',
            {'click_id': 'new_click', 'event': 'lead'}
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/smartlink/postback-logs/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
