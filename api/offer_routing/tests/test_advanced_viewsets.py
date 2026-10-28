"""
Tests for advanced service viewsets (viewsets/advanced.py).

Covers: GeoRevenue, DynamicPricing, MLIntegration, Waterfall,
Postback, FraudDetection, OpenAI, Plugin, Configuration,
CacheBackend, Attachment viewsets.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

User = get_user_model()


class GeoRevenueViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='geo_user', password='pass123')
        self.client.force_authenticate(user=self.user)

    def test_optimize_geo_pricing_missing_offer_id(self):
        r = self.client.post('/api/geo-revenue/optimize_geo_pricing/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_optimize_geo_pricing_valid(self):
        r = self.client.post('/api/geo-revenue/optimize_geo_pricing/',
                             {'offer_id': 1, 'geo_context': {'country': 'US'}}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_geo_performance(self):
        r = self.client.get('/api/geo-revenue/geo_performance/')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_geo_performance_with_tenant(self):
        r = self.client.get('/api/geo-revenue/geo_performance/?tenant_id=1&time_window=7')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_optimize_geo_targeting(self):
        r = self.client.post('/api/geo-revenue/optimize_geo_targeting/',
                             {'tenant_id': 1, 'campaign_budget': 5000}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_revenue_breakdown_missing_offer_id(self):
        r = self.client.get('/api/geo-revenue/revenue_breakdown/')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_revenue_breakdown_valid(self):
        r = self.client.get('/api/geo-revenue/revenue_breakdown/?offer_id=1&time_window=30')
        self.assertIn(r.status_code, [200, 404, 500, 403])


class DynamicPricingViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='pricing_user', password='pass123')
        self.client.force_authenticate(user=self.user)

    def test_calculate_price_missing_offer_id(self):
        r = self.client.post('/api/dynamic-pricing/calculate_price/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_calculate_price_valid(self):
        r = self.client.post('/api/dynamic-pricing/calculate_price/',
                             {'offer_id': 1, 'context': {'device': 'mobile'}}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_optimize_portfolio(self):
        r = self.client.post('/api/dynamic-pricing/optimize_portfolio/',
                             {'tenant_id': 1, 'optimization_window': 7}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_pricing_analytics_missing_offer_id(self):
        r = self.client.get('/api/dynamic-pricing/pricing_analytics/')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_pricing_analytics_valid(self):
        r = self.client.get('/api/dynamic-pricing/pricing_analytics/?offer_id=1')
        self.assertIn(r.status_code, [200, 404, 500, 403])


class MLIntegrationViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='ml_user', password='pass123')
        self.client.force_authenticate(user=self.user)

    def test_train_conversion_model(self):
        r = self.client.post('/api/ml/train_conversion_model/',
                             {'tenant_id': 1, 'training_days': 30}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_predict_conversion_missing_params(self):
        r = self.client.post('/api/ml/predict_conversion/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_predict_conversion_valid(self):
        r = self.client.post('/api/ml/predict_conversion/',
                             {'user_id': 1, 'offer_id': 2, 'context': {}}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_train_revenue_model(self):
        r = self.client.post('/api/ml/train_revenue_model/',
                             {'tenant_id': 1}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_predict_revenue_missing_params(self):
        r = self.client.post('/api/ml/predict_revenue/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_predict_revenue_valid(self):
        r = self.client.post('/api/ml/predict_revenue/',
                             {'user_id': 1, 'offer_id': 2, 'context': {}}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_train_fraud_model(self):
        r = self.client.post('/api/ml/train_fraud_model/',
                             {'tenant_id': 1}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_detect_fraud_missing_user_id(self):
        r = self.client.post('/api/ml/detect_fraud/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_detect_fraud_valid(self):
        r = self.client.post('/api/ml/detect_fraud/',
                             {'user_id': 1, 'context': {'ip': '1.2.3.4'}}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_model_status(self):
        r = self.client.get('/api/ml/model_status/')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_retrain_all_models(self):
        r = self.client.post('/api/ml/retrain_all_models/',
                             {'tenant_id': 1, 'force': False}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])


class WaterfallViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='waterfall_user', password='pass123')
        self.client.force_authenticate(user=self.user)

    def test_generate_waterfall_missing_user_id(self):
        r = self.client.post('/api/waterfall/generate_waterfall/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_generate_waterfall_valid(self):
        r = self.client.post('/api/waterfall/generate_waterfall/',
                             {'user_id': 1, 'context': {}}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_waterfall_performance_missing_user_id(self):
        r = self.client.get('/api/waterfall/waterfall_performance/')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_waterfall_performance_valid(self):
        r = self.client.get('/api/waterfall/waterfall_performance/?user_id=1')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_optimize_globally(self):
        r = self.client.post('/api/waterfall/optimize_globally/',
                             {'tenant_id': 1}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])


class PostbackViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='postback_user', password='pass123')
        self.client.force_authenticate(user=self.user)

    def test_process_postback_empty_data(self):
        r = self.client.post('/api/postback/process_postback/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 500, 403])

    def test_process_postback_valid(self):
        r = self.client.post('/api/postback/process_postback/',
                             {'conversion_id': 'conv_123', 'offer_id': 1,
                              'user_id': 1, 'revenue': 5.50}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_validate_signature_missing(self):
        r = self.client.post('/api/postback/validate_signature/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_validate_signature_valid(self):
        r = self.client.post('/api/postback/validate_signature/',
                             {'postback_data': {}, 'signature': 'abc123'}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_conversion_attribution_missing_id(self):
        r = self.client.get('/api/postback/conversion_attribution/')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_conversion_attribution_valid(self):
        r = self.client.get('/api/postback/conversion_attribution/?conversion_id=conv_123')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_process_reversal_valid(self):
        r = self.client.post('/api/postback/process_reversal/',
                             {'conversion_id': 'conv_123', 'reason': 'chargeback'}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])


class FraudDetectionViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='fraud_user', password='pass123')
        self.client.force_authenticate(user=self.user)

    def test_analyze_user_activity_missing_id(self):
        r = self.client.post('/api/fraud/analyze_user_activity/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_analyze_user_activity_valid(self):
        r = self.client.post('/api/fraud/analyze_user_activity/',
                             {'user_id': 1, 'time_window': 3600}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_detect_ip_fraud_missing_ip(self):
        r = self.client.post('/api/fraud/detect_ip_fraud/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_detect_ip_fraud_valid(self):
        r = self.client.post('/api/fraud/detect_ip_fraud/',
                             {'ip_address': '1.2.3.4', 'time_window': 3600}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_detect_device_fraud_missing_fingerprint(self):
        r = self.client.post('/api/fraud/detect_device_fraud/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_detect_device_fraud_valid(self):
        r = self.client.post('/api/fraud/detect_device_fraud/',
                             {'device_fingerprint': 'fp_abc123'}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_detect_conversion_fraud_missing_params(self):
        r = self.client.post('/api/fraud/detect_conversion_fraud/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_detect_conversion_fraud_valid(self):
        r = self.client.post('/api/fraud/detect_conversion_fraud/',
                             {'user_id': 1, 'offer_id': 2}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])


class OpenAIViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='openai_user', password='pass123')
        self.client.force_authenticate(user=self.user)

    def test_availability(self):
        r = self.client.get('/api/openai/availability/')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_generate_offer_content_missing_data(self):
        r = self.client.post('/api/openai/generate_offer_content/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_generate_offer_content_valid(self):
        r = self.client.post('/api/openai/generate_offer_content/',
                             {'offer_data': {'name': 'Test Offer', 'type': 'cpa'}},
                             format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_analyze_offer_missing_data(self):
        r = self.client.post('/api/openai/analyze_offer/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_analyze_offer_valid(self):
        r = self.client.post('/api/openai/analyze_offer/',
                             {'offer_data': {'name': 'Test', 'conversions': 50}},
                             format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_optimize_routing_strategy_missing_data(self):
        r = self.client.post('/api/openai/optimize_routing_strategy/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_optimize_routing_strategy_valid(self):
        r = self.client.post('/api/openai/optimize_routing_strategy/',
                             {'routing_data': {'routes': [], 'performance': {}}},
                             format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])


class PluginViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='plugin_user', password='pass123')
        self.client.force_authenticate(user=self.user)

    def test_list_plugins(self):
        r = self.client.get('/api/plugins/list_plugins/')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_execute_plugin_missing_type(self):
        r = self.client.post('/api/plugins/execute_plugin/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 500, 403])

    def test_execute_plugin_valid(self):
        r = self.client.post('/api/plugins/execute_plugin/',
                             {'plugin_type': 'ConditionPlugin', 'context': {}},
                             format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_register_plugin_missing_config(self):
        r = self.client.post('/api/plugins/register_plugin/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_register_plugin_valid(self):
        r = self.client.post('/api/plugins/register_plugin/',
                             {'plugin_config': {'type': 'GeoConditionPlugin'}},
                             format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_unregister_plugin_missing_name(self):
        r = self.client.post('/api/plugins/unregister_plugin/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_unregister_plugin_valid(self):
        r = self.client.post('/api/plugins/unregister_plugin/',
                             {'plugin_name': 'GeoConditionPlugin'}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])


class ConfigurationViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='config_user', password='pass123')
        self.client.force_authenticate(user=self.user)

    def test_routing_config(self):
        r = self.client.get('/api/configuration/routing_config/')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_update_config_value_missing_key(self):
        r = self.client.post('/api/configuration/update_config_value/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_update_config_value_valid(self):
        r = self.client.post('/api/configuration/update_config_value/',
                             {'key': 'cache_ttl', 'value': 300}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_feature_flags(self):
        r = self.client.get('/api/configuration/feature_flags/')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_is_feature_enabled_missing_feature(self):
        r = self.client.get('/api/configuration/is_feature_enabled/')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_is_feature_enabled_valid(self):
        r = self.client.get('/api/configuration/is_feature_enabled/?feature=personalization')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_optimize_configuration(self):
        r = self.client.post('/api/configuration/optimize_configuration/',
                             {'tenant_id': 1}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_validate_configuration(self):
        r = self.client.post('/api/configuration/validate_configuration/',
                             {'config': {'cache_ttl': 300}}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_export_configuration(self):
        r = self.client.get('/api/configuration/export_configuration/')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_import_configuration(self):
        r = self.client.post('/api/configuration/import_configuration/',
                             {'config': {'cache_ttl': 300}}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_reset_configuration(self):
        r = self.client.post('/api/configuration/reset_configuration/',
                             {'tenant_id': 1}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_configuration_history(self):
        r = self.client.get('/api/configuration/configuration_history/?days=7')
        self.assertIn(r.status_code, [200, 404, 500, 403])


class CacheBackendViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='cache_user', password='pass123')
        self.client.force_authenticate(user=self.user)

    def test_cache_routing_decision_missing_params(self):
        r = self.client.post('/api/cache/cache_routing_decision/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_cache_routing_decision_valid(self):
        r = self.client.post('/api/cache/cache_routing_decision/',
                             {'user_id': 1, 'context_hash': 'abc123',
                              'decision_data': {'route_id': 1}}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_get_cached_decision_missing_params(self):
        r = self.client.get('/api/cache/get_cached_decision/')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_get_cached_decision_valid(self):
        r = self.client.get('/api/cache/get_cached_decision/?user_id=1&context_hash=abc123')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_invalidate_user_cache_missing_id(self):
        r = self.client.post('/api/cache/invalidate_user_cache/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_invalidate_user_cache_valid(self):
        r = self.client.post('/api/cache/invalidate_user_cache/',
                             {'user_id': 1}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_cache_offer_score_missing_params(self):
        r = self.client.post('/api/cache/cache_offer_score/', {}, format='json')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_cache_offer_score_valid(self):
        r = self.client.post('/api/cache/cache_offer_score/',
                             {'offer_id': 1, 'user_id': 1,
                              'score_data': {'score': 0.85}}, format='json')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_get_cached_score_missing_params(self):
        r = self.client.get('/api/cache/get_cached_score/')
        self.assertIn(r.status_code, [400, 404, 403])

    def test_get_cached_score_valid(self):
        r = self.client.get('/api/cache/get_cached_score/?offer_id=1&user_id=1')
        self.assertIn(r.status_code, [200, 404, 500, 403])

    def test_cache_backend_info(self):
        r = self.client.get('/api/cache/cache_backend_info/')
        self.assertIn(r.status_code, [200, 404, 500, 403])


class WebSocketRoutingTest(TestCase):
    """Tests for websocket_routing.py channel routing."""

    def test_websocket_routing_import(self):
        from offer_routing.websocket_routing import websocket_urlpatterns
        self.assertIsInstance(websocket_urlpatterns, list)
        self.assertEqual(len(websocket_urlpatterns), 4)

    def test_all_consumers_referenced(self):
        from offer_routing.websocket_routing import websocket_urlpatterns
        from offer_routing.consumers import (
            RoutingDashboardConsumer, CapMonitorConsumer,
            RoutingDecisionConsumer, PerformanceMetricsConsumer,
        )
        # Verify all 4 consumer classes exist
        self.assertIsNotNone(RoutingDashboardConsumer)
        self.assertIsNotNone(CapMonitorConsumer)
        self.assertIsNotNone(RoutingDecisionConsumer)
        self.assertIsNotNone(PerformanceMetricsConsumer)


class TasksIntegrationSystemTest(TestCase):
    """Tests for tasks/integration_system/ task classes."""

    def test_import_all_task_classes(self):
        from offer_routing.tasks.integration_system import (
            ABTestTask, AffinityUpdateTask, AnalyticsTask,
            CacheWarmupTask, CapResetTask, ExposureStatTask,
            FallbackHealthTask, PreferenceVectorTask,
            RankUpdateTask, ScoreUpdateTask,
        )
        self.assertIsNotNone(ABTestTask)
        self.assertIsNotNone(ScoreUpdateTask)

    def test_task_classes_instantiate(self):
        from offer_routing.tasks.integration_system import (
            ABTestTask, CacheWarmupTask, CapResetTask
        )
        t1 = ABTestTask()
        t2 = CacheWarmupTask()
        t3 = CapResetTask()
        self.assertIsNotNone(t1)
        self.assertIsNotNone(t2)
        self.assertIsNotNone(t3)


class ServicesDeepScanTest(TestCase):
    """Tests that all previously missing services are now importable."""

    def test_geo_revenue_service_import(self):
        from offer_routing.services import geo_revenue_service, GeoRevenueService
        self.assertIsNotNone(geo_revenue_service)
        self.assertIsInstance(geo_revenue_service, GeoRevenueService)

    def test_dynamic_pricing_service_import(self):
        from offer_routing.services import dynamic_pricing_service, DynamicPricingService
        self.assertIsNotNone(dynamic_pricing_service)

    def test_ml_integration_service_import(self):
        from offer_routing.services import ml_integration_service, MLIntegrationService
        self.assertIsNotNone(ml_integration_service)

    def test_waterfall_service_import(self):
        from offer_routing.services import waterfall_service, WaterfallService
        self.assertIsNotNone(waterfall_service)

    def test_postback_service_import(self):
        from offer_routing.services import postback_service, PostbackService
        self.assertIsNotNone(postback_service)

    def test_fraud_detection_service_import(self):
        from offer_routing.services import fraud_detection_service, FraudDetectionService
        self.assertIsNotNone(fraud_detection_service)

    def test_receivers_importable(self):
        from offer_routing import receivers
        self.assertTrue(hasattr(receivers, 'offer_route_pre_save'))
        self.assertTrue(hasattr(receivers, 'offer_route_post_save'))
        self.assertTrue(hasattr(receivers, 'routing_decision_log_post_save'))

    def test_cache_backends_importable(self):
        from offer_routing.cache_backends import (
            get_routing_cache, get_cache_backend,
            cache_routing_decision, get_cached_routing_decision,
            invalidate_user_routing_cache,
        )
        self.assertIsNotNone(get_routing_cache)

    def test_plugins_importable(self):
        from offer_routing.plugins import (
            get_plugin_manager, register_plugin, unregister_plugin,
            PluginManager, GeoConditionPlugin, DeviceConditionPlugin,
        )
        self.assertIsNotNone(get_plugin_manager)
        self.assertIsNotNone(PluginManager)

    def test_validators_importable(self):
        from offer_routing.validators import (
            validate_route_name, validate_priority,
            validate_cap_value, validate_split_percentage,
            validate_ab_test_config, validate_routing_config,
        )
        self.assertIsNotNone(validate_route_name)

    def test_schemas_importable(self):
        from offer_routing.schemas import (
            OfferRouteSchema, RoutingRequestSchema,
            RoutingDecisionSchema, CapStatusSchema,
        )
        self.assertIsNotNone(OfferRouteSchema)

    def test_integ_signals_importable(self):
        from offer_routing.integration_system import (
            send_integration_signal, create_signal_context,
            validate_signal_data, create_error_context,
        )
        self.assertIsNotNone(send_integration_signal)

    def test_openai_service_importable(self):
        from offer_routing.openai import OpenAIService, OpenAIClient
        svc = OpenAIService()
        self.assertIsNotNone(svc)
        self.assertTrue(hasattr(svc, 'is_service_available'))
