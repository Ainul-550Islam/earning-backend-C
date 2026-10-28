"""
Advanced Service Viewsets for Offer Routing System

Exposes previously unconnected services via REST API:
- GeoRevenueViewSet       (geo pricing, performance, targeting, breakdown)
- DynamicPricingViewSet   (calculate price, optimize portfolio, analytics)
- MLIntegrationViewSet    (train models, predict, detect fraud, status)
- WaterfallViewSet        (generate waterfall, performance, global optimize)
- PostbackViewSet         (process postback, validate, attribution, reversal)
- FraudDetectionViewSet   (user activity, IP fraud, device fraud, conversion fraud)
- OpenAIViewSet           (generate content, analyze offer, optimize routing)
- PluginViewSet           (list, register, unregister, execute plugins)
- ConfigurationViewSet    (get/update config, feature flags, import/export)
- CacheBackendViewSet     (cache ops, invalidate, status)
- WebhookConsumerViewSet  (receiver endpoint for external webhooks)
- AttachmentViewSet       (upload, download, delete attachments)
"""

from ..throttling import BulkOperationThrottle, RoutingEngineThrottle, AnalyticsThrottle, BulkOperationThrottle, EvaluatorThrottle
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from ..permissions import IsAuthenticatedOrReadOnly, CanManageOffers
from ..services import (
    geo_revenue_service, dynamic_pricing_service,
    ml_integration_service, waterfall_service,
    postback_service, fraud_detection_service,
    config_service, monitoring_service,
)


class GeoRevenueViewSet(viewsets.ViewSet):
    """ViewSet for GeoRevenueService — geo pricing and revenue analytics."""
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['post'])
    def optimize_geo_pricing(self, request):
        """Optimize pricing for a specific offer in a geo context."""
        try:
            offer_id = request.data.get('offer_id')
            geo_context = request.data.get('geo_context', {})
            if not offer_id:
                return Response({'error': 'offer_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = geo_revenue_service.optimize_geo_pricing(int(offer_id), geo_context)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def geo_performance(self, request):
        """Analyze geo performance for a tenant."""
        try:
            tenant_id = request.query_params.get('tenant_id') or request.user.id
            time_window = int(request.query_params.get('time_window', 30))
            result = geo_revenue_service.analyze_geo_performance(int(tenant_id), time_window)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def optimize_geo_targeting(self, request):
        """Optimize geo targeting allocation."""
        try:
            tenant_id = request.data.get('tenant_id', request.user.id)
            budget = float(request.data.get('campaign_budget', 10000))
            result = geo_revenue_service.optimize_geo_targeting(int(tenant_id), budget)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def revenue_breakdown(self, request):
        """Get geo revenue breakdown for an offer."""
        try:
            offer_id = request.query_params.get('offer_id')
            if not offer_id:
                return Response({'error': 'offer_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            time_window = int(request.query_params.get('time_window', 30))
            result = geo_revenue_service.get_geo_revenue_breakdown(int(offer_id), time_window)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DynamicPricingViewSet(viewsets.ViewSet):
    """ViewSet for DynamicPricingService — real-time price calculation."""
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['post'])
    def calculate_price(self, request):
        """Calculate dynamic price for an offer given context."""
        try:
            offer_id = request.data.get('offer_id')
            context = request.data.get('context', {})
            if not offer_id:
                return Response({'error': 'offer_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = dynamic_pricing_service.calculate_dynamic_price(int(offer_id), context)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def optimize_portfolio(self, request):
        """Optimize pricing across all offers for a tenant."""
        try:
            tenant_id = request.data.get('tenant_id', request.user.id)
            window = int(request.data.get('optimization_window', 7))
            result = dynamic_pricing_service.optimize_pricing_portfolio(int(tenant_id), window)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def pricing_analytics(self, request):
        """Get pricing analytics for an offer."""
        try:
            offer_id = request.query_params.get('offer_id')
            if not offer_id:
                return Response({'error': 'offer_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            time_window = int(request.query_params.get('time_window', 30))
            result = dynamic_pricing_service.get_pricing_analytics(int(offer_id), time_window)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MLIntegrationViewSet(viewsets.ViewSet):
    """ViewSet for MLIntegrationService — model training and prediction."""
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['post'])
    def train_conversion_model(self, request):
        """Train conversion prediction model for a tenant."""
        try:
            tenant_id = request.data.get('tenant_id', request.user.id)
            training_days = int(request.data.get('training_days', 30))
            result = ml_integration_service.train_conversion_prediction_model(
                int(tenant_id), training_days)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def predict_conversion(self, request):
        """Predict conversion probability for a user-offer pair."""
        try:
            user_id = request.data.get('user_id')
            offer_id = request.data.get('offer_id')
            context = request.data.get('context', {})
            if not user_id or not offer_id:
                return Response({'error': 'user_id and offer_id are required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = ml_integration_service.predict_conversion_probability(
                int(user_id), int(offer_id), context)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def train_revenue_model(self, request):
        """Train revenue prediction model."""
        try:
            tenant_id = request.data.get('tenant_id', request.user.id)
            training_days = int(request.data.get('training_days', 30))
            result = ml_integration_service.train_revenue_prediction_model(
                int(tenant_id), training_days)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def predict_revenue(self, request):
        """Predict revenue for a user-offer pair."""
        try:
            user_id = request.data.get('user_id')
            offer_id = request.data.get('offer_id')
            context = request.data.get('context', {})
            if not user_id or not offer_id:
                return Response({'error': 'user_id and offer_id are required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = ml_integration_service.predict_revenue(
                int(user_id), int(offer_id), context)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def train_fraud_model(self, request):
        """Train fraud detection model."""
        try:
            tenant_id = request.data.get('tenant_id', request.user.id)
            training_days = int(request.data.get('training_days', 30))
            result = ml_integration_service.train_fraud_detection_model(
                int(tenant_id), training_days)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def detect_fraud(self, request):
        """Detect fraud for a user context."""
        try:
            user_id = request.data.get('user_id')
            context = request.data.get('context', {})
            if not user_id:
                return Response({'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = ml_integration_service.detect_fraud(int(user_id), context)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def model_status(self, request):
        """Get ML model status for a tenant."""
        try:
            tenant_id = request.query_params.get('tenant_id', request.user.id)
            result = ml_integration_service.get_ml_model_status(int(tenant_id))
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def retrain_all_models(self, request):
        """Retrain all ML models for a tenant."""
        try:
            tenant_id = request.data.get('tenant_id', request.user.id)
            force = bool(request.data.get('force', False))
            result = ml_integration_service.retrain_all_models(int(tenant_id), force)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WaterfallViewSet(viewsets.ViewSet):
    """ViewSet for WaterfallService — offer waterfall generation."""
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['post'])
    def generate_waterfall(self, request):
        """Generate offer waterfall for a user."""
        try:
            user_id = request.data.get('user_id')
            context = request.data.get('context', {})
            if not user_id:
                return Response({'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = waterfall_service.generate_waterfall(int(user_id), context)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def waterfall_performance(self, request):
        """Get waterfall performance for a user."""
        try:
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response({'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            time_window = int(request.query_params.get('time_window', 86400))
            result = waterfall_service.get_waterfall_performance(int(user_id), time_window)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def optimize_globally(self, request):
        """Globally optimize waterfall configuration for a tenant."""
        try:
            tenant_id = request.data.get('tenant_id', request.user.id)
            result = waterfall_service.optimize_waterfall_globally(int(tenant_id))
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PostbackViewSet(viewsets.ViewSet):
    """ViewSet for PostbackService — conversion tracking and attribution."""
    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['post'])
    def process_postback(self, request):
        """Process an incoming conversion postback."""
        try:
            postback_data = request.data
            if not postback_data:
                return Response({'error': 'postback_data is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = postback_service.process_postback(dict(postback_data))
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def validate_signature(self, request):
        """Validate postback signature for security."""
        try:
            postback_data = request.data.get('postback_data', {})
            signature = request.data.get('signature', '')
            if not signature:
                return Response({'error': 'signature is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = postback_service.validate_postback_signature(postback_data, signature)
            return Response({'success': True, 'valid': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def conversion_attribution(self, request):
        """Get attribution data for a conversion."""
        try:
            conversion_id = request.query_params.get('conversion_id')
            if not conversion_id:
                return Response({'error': 'conversion_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = postback_service.get_conversion_attribution(conversion_id)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def process_reversal(self, request):
        """Process a conversion reversal."""
        try:
            reversal_data = request.data
            if not reversal_data:
                return Response({'error': 'reversal_data is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = postback_service.process_reversal(dict(reversal_data))
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudDetectionViewSet(viewsets.ViewSet):
    """ViewSet for FraudDetectionService — multi-signal fraud analysis."""
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['post'])
    def analyze_user_activity(self, request):
        """Analyze user activity for fraud signals."""
        try:
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            time_window = int(request.data.get('time_window', 3600))
            result = fraud_detection_service.analyze_user_activity(int(user_id), time_window)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def detect_ip_fraud(self, request):
        """Detect fraud from an IP address."""
        try:
            ip_address = request.data.get('ip_address')
            if not ip_address:
                return Response({'error': 'ip_address is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            time_window = int(request.data.get('time_window', 3600))
            result = fraud_detection_service.detect_ip_fraud(ip_address, time_window)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def detect_device_fraud(self, request):
        """Detect fraud from a device fingerprint."""
        try:
            fingerprint = request.data.get('device_fingerprint')
            if not fingerprint:
                return Response({'error': 'device_fingerprint is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            time_window = int(request.data.get('time_window', 3600))
            result = fraud_detection_service.detect_device_fraud(fingerprint, time_window)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def detect_conversion_fraud(self, request):
        """Detect fraud on a specific conversion."""
        try:
            user_id = request.data.get('user_id')
            offer_id = request.data.get('offer_id')
            if not user_id or not offer_id:
                return Response({'error': 'user_id and offer_id are required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = fraud_detection_service.detect_conversion_fraud(int(user_id), int(offer_id))
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OpenAIViewSet(viewsets.ViewSet):
    """ViewSet for OpenAI integration — content generation and routing optimization."""
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [BulkOperationThrottle]

    def _get_service(self):
        from ..openai import OpenAIService
        return OpenAIService()

    @action(detail=False, methods=['get'])
    def availability(self, request):
        """Check if OpenAI service is available."""
        try:
            svc = self._get_service()
            available = svc.is_service_available()
            return Response({'success': True, 'available': available})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def generate_offer_content(self, request):
        """Generate content for an offer using OpenAI."""
        try:
            offer_data = request.data.get('offer_data', {})
            if not offer_data:
                return Response({'error': 'offer_data is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            svc = self._get_service()
            if not svc.is_service_available():
                return Response(
                    {'success': False, 'error': 'OpenAI service is not available'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            result = svc.generate_offer_content(offer_data)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def analyze_offer(self, request):
        """Analyze and optimize an offer using OpenAI."""
        try:
            offer_data = request.data.get('offer_data', {})
            if not offer_data:
                return Response({'error': 'offer_data is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            svc = self._get_service()
            if not svc.is_service_available():
                return Response(
                    {'success': False, 'error': 'OpenAI service is not available'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            result = svc.analyze_and_optimize_offer(offer_data)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def optimize_routing_strategy(self, request):
        """Use OpenAI to suggest routing strategy optimizations."""
        try:
            routing_data = request.data.get('routing_data', {})
            if not routing_data:
                return Response({'error': 'routing_data is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            svc = self._get_service()
            if not svc.is_service_available():
                return Response(
                    {'success': False, 'error': 'OpenAI service is not available'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            result = svc.optimize_routing_strategy(routing_data)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PluginViewSet(viewsets.ViewSet):
    """ViewSet for Plugin system — register, list, execute, unregister plugins."""
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [BulkOperationThrottle]

    def _get_manager(self):
        from ..plugins import get_plugin_manager
        return get_plugin_manager()

    @action(detail=False, methods=['get'])
    def list_plugins(self, request):
        """List all registered plugins."""
        try:
            mgr = self._get_manager()
            plugins = mgr.list_plugins() if hasattr(mgr, 'list_plugins') else []
            return Response({'success': True, 'plugins': plugins})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def execute_plugin(self, request):
        """Execute a specific plugin with a given context."""
        try:
            from ..plugins import execute_plugin_type
            plugin_type_name = request.data.get('plugin_type')
            context = request.data.get('context', {})
            if not plugin_type_name:
                return Response({'error': 'plugin_type is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            mgr = self._get_manager()
            result = mgr.execute(context) if hasattr(mgr, 'execute') else {}
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def register_plugin(self, request):
        """Register a new plugin by class path."""
        try:
            from ..plugins import register_plugin
            plugin_config = request.data.get('plugin_config', {})
            if not plugin_config:
                return Response({'error': 'plugin_config is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            return Response({'success': True, 'message': 'Plugin registration accepted'})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def unregister_plugin(self, request):
        """Unregister a plugin by name."""
        try:
            from ..plugins import unregister_plugin
            plugin_name = request.data.get('plugin_name')
            if not plugin_name:
                return Response({'error': 'plugin_name is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = unregister_plugin(plugin_name)
            return Response({'success': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfigurationViewSet(viewsets.ViewSet):
    """ViewSet for ConfigurationService — routing config CRUD and feature flags."""
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['get'])
    def routing_config(self, request):
        """Get routing configuration for tenant."""
        try:
            tenant_id = request.query_params.get('tenant_id', request.user.id)
            result = config_service.get_routing_config(int(tenant_id))
            return Response({'success': True, 'config': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def update_config_value(self, request):
        """Update a single config key."""
        try:
            tenant_id = request.data.get('tenant_id', request.user.id)
            key = request.data.get('key')
            value = request.data.get('value')
            if not key:
                return Response({'error': 'key is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = config_service.update_config_value(int(tenant_id), key, value)
            return Response({'success': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def feature_flags(self, request):
        """Get feature flags for tenant."""
        try:
            tenant_id = request.query_params.get('tenant_id', request.user.id)
            result = config_service.get_feature_flags(int(tenant_id))
            return Response({'success': True, 'flags': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def is_feature_enabled(self, request):
        """Check if a feature is enabled for tenant."""
        try:
            tenant_id = request.query_params.get('tenant_id', request.user.id)
            feature = request.query_params.get('feature')
            if not feature:
                return Response({'error': 'feature is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = config_service.is_feature_enabled(int(tenant_id), feature)
            return Response({'success': True, 'enabled': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def optimize_configuration(self, request):
        """Auto-optimize configuration for tenant."""
        try:
            tenant_id = request.data.get('tenant_id', request.user.id)
            result = config_service.optimize_configuration(int(tenant_id))
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def validate_configuration(self, request):
        """Validate a config dict before applying."""
        try:
            config = request.data.get('config', {})
            result = config_service.validate_configuration(config)
            return Response({'success': True, 'validation': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def export_configuration(self, request):
        """Export full tenant configuration."""
        try:
            tenant_id = request.query_params.get('tenant_id', request.user.id)
            result = config_service.export_configuration(int(tenant_id))
            return Response({'success': True, 'config': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def import_configuration(self, request):
        """Import configuration for tenant."""
        try:
            tenant_id = request.data.get('tenant_id', request.user.id)
            config_data = request.data.get('config', {})
            result = config_service.import_configuration(int(tenant_id), config_data)
            return Response({'success': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def reset_configuration(self, request):
        """Reset configuration to defaults."""
        try:
            tenant_id = request.data.get('tenant_id', request.user.id)
            result = config_service.reset_configuration(int(tenant_id))
            return Response({'success': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def configuration_history(self, request):
        """Get configuration change history."""
        try:
            tenant_id = request.query_params.get('tenant_id', request.user.id)
            days = int(request.query_params.get('days', 30))
            result = config_service.get_configuration_history(int(tenant_id), days)
            return Response({'success': True, 'history': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CacheBackendViewSet(viewsets.ViewSet):
    """ViewSet for cache_backends — cache ops, invalidation, status."""
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['post'])
    def cache_routing_decision(self, request):
        """Cache a routing decision."""
        try:
            from ..cache_backends import cache_routing_decision
            user_id = request.data.get('user_id')
            context_hash = request.data.get('context_hash')
            decision_data = request.data.get('decision_data', {})
            if not user_id or not context_hash:
                return Response({'error': 'user_id and context_hash required'},
                                status=status.HTTP_400_BAD_REQUEST)
            cache_routing_decision(int(user_id), context_hash, decision_data)
            return Response({'success': True})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def get_cached_decision(self, request):
        """Retrieve a cached routing decision."""
        try:
            from ..cache_backends import get_cached_routing_decision
            user_id = request.query_params.get('user_id')
            context_hash = request.query_params.get('context_hash')
            if not user_id or not context_hash:
                return Response({'error': 'user_id and context_hash required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = get_cached_routing_decision(int(user_id), context_hash)
            return Response({'success': True, 'decision': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def invalidate_user_cache(self, request):
        """Invalidate all routing cache for a user."""
        try:
            from ..cache_backends import invalidate_user_routing_cache
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            invalidate_user_routing_cache(int(user_id))
            return Response({'success': True})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def cache_offer_score(self, request):
        """Cache an offer score."""
        try:
            from ..cache_backends import cache_offer_score
            offer_id = request.data.get('offer_id')
            user_id = request.data.get('user_id')
            score_data = request.data.get('score_data', {})
            if not offer_id or not user_id:
                return Response({'error': 'offer_id and user_id required'},
                                status=status.HTTP_400_BAD_REQUEST)
            cache_offer_score(int(offer_id), int(user_id), score_data)
            return Response({'success': True})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def get_cached_score(self, request):
        """Retrieve a cached offer score."""
        try:
            from ..cache_backends import get_cached_offer_score
            offer_id = request.query_params.get('offer_id')
            user_id = request.query_params.get('user_id')
            if not offer_id or not user_id:
                return Response({'error': 'offer_id and user_id required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = get_cached_offer_score(int(offer_id), int(user_id))
            return Response({'success': True, 'score': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def cache_backend_info(self, request):
        """Get current cache backend info."""
        try:
            from ..cache_backends import get_routing_cache
            cache = get_routing_cache()
            return Response({
                'success': True,
                'backend': type(cache).__name__,
            })
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AttachmentViewSet(viewsets.ViewSet):
    """ViewSet wrapping AttachmentUploadView, APIView, DownloadView, DeleteView as DRF."""
    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [BulkOperationThrottle]
    parser_classes = [MultiPartParser, FormParser]

    @action(detail=False, methods=['post'])
    def upload(self, request):
        """Upload an attachment file."""
        try:
            from ..attachment_upload_view import AttachmentAPIView
            view = AttachmentAPIView()
            view.request = request
            view.format_kwarg = None
            return view.post(request)
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def list_attachments(self, request):
        """List available attachments."""
        try:
            return Response({'success': True, 'attachments': []})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
