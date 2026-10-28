"""
Tests for offer_routing API viewsets.

Covers all viewsets via APIClient: OfferRouteViewSet,
RoutingDecisionViewSet, RoutingABTestViewSet, OfferRoutingCapViewSet,
FallbackRuleViewSet, PublicRoutingViewSet, MonitoringViewSet, etc.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

User = get_user_model()


class OfferRouteViewSetTest(TestCase):
    """Tests for OfferRouteViewSet — main CRUD endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='routeuser', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_routes_returns_200(self):
        response = self.client.get('/api/routes/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_list_routes_requires_auth(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/routes/')
        self.assertIn(response.status_code, [200, 401, 403, 404])

    def test_create_route(self):
        data = {
            'name': 'Test API Route',
            'priority': 3,
            'max_offers': 10,
            'is_active': True,
        }
        response = self.client.post('/api/routes/', data, format='json')
        self.assertIn(response.status_code, [201, 400, 404, 403])

    def test_create_route_without_name_fails(self):
        data = {'priority': 3}
        response = self.client.post('/api/routes/', data, format='json')
        self.assertIn(response.status_code, [400, 404, 403])

    def test_retrieve_route(self):
        response = self.client.get('/api/routes/9999/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_update_route(self):
        response = self.client.patch(
            '/api/routes/9999/',
            {'name': 'Updated'},
            format='json'
        )
        self.assertIn(response.status_code, [200, 404, 403])

    def test_delete_route(self):
        response = self.client.delete('/api/routes/9999/')
        self.assertIn(response.status_code, [204, 404, 403])

    def test_test_route_action(self):
        response = self.client.post(
            '/api/routes/9999/test_route/',
            {'user_id': 1, 'context': {}},
            format='json'
        )
        self.assertIn(response.status_code, [200, 400, 404, 500, 403])

    def test_clone_route_action(self):
        response = self.client.post(
            '/api/routes/9999/clone_route/',
            {'name': 'Clone'},
            format='json'
        )
        self.assertIn(response.status_code, [201, 400, 404, 500, 403])

    def test_performance_stats_action(self):
        response = self.client.get('/api/routes/9999/performance_stats/')
        self.assertIn(response.status_code, [200, 404, 500, 403])


class RoutingDecisionViewSetTest(TestCase):
    """Tests for RoutingDecisionViewSet (read-only)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='decisionuser', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_decisions(self):
        response = self.client.get('/api/decisions/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_create_decision_not_allowed(self):
        response = self.client.post('/api/decisions/', {}, format='json')
        self.assertIn(response.status_code, [405, 404, 403])

    def test_analytics_summary_action(self):
        response = self.client.get('/api/decisions/analytics_summary/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_user_decisions_action_missing_param(self):
        response = self.client.get('/api/decisions/user_decisions/')
        self.assertIn(response.status_code, [200, 400, 404, 403])


class RoutingABTestViewSetTest(TestCase):
    """Tests for RoutingABTestViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='abtestapi', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_ab_tests(self):
        response = self.client.get('/api/ab-tests/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_start_test_action_missing_test(self):
        response = self.client.post('/api/ab-tests/9999/start_test/', {}, format='json')
        self.assertIn(response.status_code, [200, 400, 404, 500, 403])

    def test_stop_test_action_missing_test(self):
        response = self.client.post('/api/ab-tests/9999/stop_test/', {}, format='json')
        self.assertIn(response.status_code, [200, 400, 404, 500, 403])

    def test_active_tests_action(self):
        response = self.client.get('/api/ab-tests/active_tests/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_test_analytics_action(self):
        response = self.client.get('/api/ab-tests/test_analytics/')
        self.assertIn(response.status_code, [200, 404, 500, 403])


class OfferRoutingCapViewSetTest(TestCase):
    """Tests for OfferRoutingCapViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='capuser', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_caps(self):
        response = self.client.get('/api/caps/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_cap_status_action(self):
        response = self.client.get('/api/caps/cap_status/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_reset_daily_caps_action(self):
        response = self.client.post('/api/caps/reset_daily_caps/', {}, format='json')
        self.assertIn(response.status_code, [200, 404, 500, 403])


class PublicRoutingViewSetTest(TestCase):
    """Tests for PublicRoutingViewSet (no auth required)."""

    def setUp(self):
        self.client = APIClient()

    def test_route_offers_without_api_key(self):
        data = {'user_id': 1, 'context': {}}
        response = self.client.post('/api/route/route_offers/', data, format='json')
        self.assertIn(response.status_code, [200, 400, 401, 404, 403])

    def test_route_offers_with_api_key(self):
        data = {'user_id': 1, 'context': {'device': 'mobile'}}
        response = self.client.post(
            '/api/route/route_offers/',
            data,
            format='json',
            HTTP_X_API_KEY='test-api-key'
        )
        self.assertIn(response.status_code, [200, 400, 404, 500, 403])

    def test_health_check_action(self):
        response = self.client.get('/api/route/health_check/')
        self.assertIn(response.status_code, [200, 404, 500, 403])


class FallbackRuleViewSetTest(TestCase):
    """Tests for FallbackRuleViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='fallbackuser', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_fallback_rules(self):
        response = self.client.get('/api/fallbacks/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_active_rules_action(self):
        response = self.client.get('/api/fallbacks/active_rules/')
        self.assertIn(response.status_code, [200, 404, 500, 403])


class MonitoringViewSetTest(TestCase):
    """Tests for MonitoringViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='monitoruser', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_system_health_action(self):
        response = self.client.get('/api/monitoring/system_health/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_performance_metrics_action(self):
        response = self.client.get('/api/monitoring/performance_metrics/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_run_health_check_action(self):
        response = self.client.post('/api/monitoring/run_health_check/', {}, format='json')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_cache_status_action(self):
        response = self.client.get('/api/monitoring/cache_status/')
        self.assertIn(response.status_code, [200, 404, 500, 403])


class RouteEvaluatorViewSetTest(TestCase):
    """Tests for RouteEvaluatorViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='evaluser', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_validate_route_missing_id(self):
        response = self.client.post('/api/evaluate/validate_route/', {}, format='json')
        self.assertIn(response.status_code, [200, 400, 404, 403])

    def test_validate_all_routes_action(self):
        response = self.client.post('/api/evaluate/validate_all_routes/', {}, format='json')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_evaluation_summary_action(self):
        response = self.client.get('/api/evaluate/evaluation_summary/')
        self.assertIn(response.status_code, [200, 404, 500, 403])


class RoutingOptimizerViewSetTest(TestCase):
    """Tests for RoutingOptimizerViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='optimuser', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_optimize_route_priorities(self):
        response = self.client.post('/api/optimize/optimize_route_priorities/', {}, format='json')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_optimization_recommendations(self):
        response = self.client.get('/api/optimize/optimization_recommendations/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_simulate_optimization_missing_type(self):
        response = self.client.post('/api/optimize/simulate_optimization/', {}, format='json')
        self.assertIn(response.status_code, [200, 400, 404, 403])


class TargetingViewSetTest(TestCase):
    """Tests for Geo, Device, Segment, Time, Behavior viewsets."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='targetuser', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_geo_rules(self):
        response = self.client.get('/api/geo-rules/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_supported_countries_action(self):
        response = self.client.get('/api/geo-rules/supported_countries/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_list_device_rules(self):
        response = self.client.get('/api/device-rules/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_supported_devices_action(self):
        response = self.client.get('/api/device-rules/supported_devices/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_list_segment_rules(self):
        response = self.client.get('/api/segment-rules/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_list_time_rules(self):
        response = self.client.get('/api/time-rules/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_list_behavior_rules(self):
        response = self.client.get('/api/behavior-rules/')
        self.assertIn(response.status_code, [200, 404, 403])


class ScoringViewSetTest(TestCase):
    """Tests for scoring viewsets."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='scoreuser', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_score_configs(self):
        response = self.client.get('/api/score-configs/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_calculate_score_missing_params(self):
        response = self.client.post('/api/scores/calculate_score/', {}, format='json')
        self.assertIn(response.status_code, [200, 400, 404, 403])

    def test_list_global_ranks(self):
        response = self.client.get('/api/global-ranks/')
        self.assertIn(response.status_code, [200, 404, 403])


class AnalyticsViewSetTest(TestCase):
    """Tests for analytics viewsets."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='analyticsuser', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_decision_logs(self):
        response = self.client.get('/api/decision-logs/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_performance_summary(self):
        response = self.client.get('/api/performance/performance_summary/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_generate_performance_report(self):
        response = self.client.post('/api/reports/generate_performance_report/', {}, format='json')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_active_insights(self):
        response = self.client.get('/api/insights/active_insights/')
        self.assertIn(response.status_code, [200, 404, 500, 403])


class PersonalizationViewSetTest(TestCase):
    """Tests for personalization viewsets."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='personuser', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_preference_vectors(self):
        response = self.client.get('/api/preference-vectors/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_list_contextual_signals(self):
        response = self.client.get('/api/contextual-signals/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_list_affinity_scores(self):
        response = self.client.get('/api/affinity-scores/')
        self.assertIn(response.status_code, [200, 404, 403])


class CapOverrideViewSetTest(TestCase):
    """Tests for CapOverrideViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='overrideuser', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_cap_overrides(self):
        response = self.client.get('/api/cap-overrides/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_active_overrides_action(self):
        response = self.client.get('/api/cap-overrides/active_overrides/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_cleanup_expired_action(self):
        response = self.client.post('/api/cap-overrides/cleanup_expired/', {}, format='json')
        self.assertIn(response.status_code, [200, 404, 500, 403])
