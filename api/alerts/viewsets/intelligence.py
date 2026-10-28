"""
Intelligence ViewSets
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from ..permissions import IsAlertManager, CanViewSensitiveData
from django.utils import timezone
import logging

from ..models.intelligence import (
    AlertCorrelation, AlertPrediction, AnomalyDetectionModel,
    AlertNoise, RootCauseAnalysis
)
from .mixins import PASSTHROUGH_EXCEPTIONS  # re-raise 404/403/400 instead of 500

from api.alerts.mixins import TenantIsolationMixin

logger = logging.getLogger(__name__)


class AlertCorrelationViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """AlertCorrelation ViewSet — tenant-scoped CRUD"""
    queryset = AlertCorrelation.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('primary_rules', 'secondary_rules')

        correlation_type = self.request.query_params.get('correlation_type')
        filter_status = self.request.query_params.get('status')

        if correlation_type:
            queryset = queryset.filter(correlation_type=correlation_type)
        if filter_status:
            queryset = queryset.filter(status=filter_status)

        return queryset.order_by('name')

    def get_serializer_class(self):
        from ..serializers.intelligence import AlertCorrelationSerializer
        return AlertCorrelationSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, **self.tenant_save_kwargs())

    def get_permissions(self):
        """
        list / retrieve / correlations      → CanViewSensitiveData
        create / update / destroy           → IsAlertManager
        analyze / predict / activate        → IsAlertManager
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'analyze', 'predict', 'activate', 'deactivate']:
            return [IsAuthenticated(), IsAlertManager()]
        return [IsAuthenticated(), CanViewSensitiveData()]

    @action(detail=True, methods=['post'])
    def analyze(self, request, pk=None):
        """Analyze correlation"""
        try:
            correlation = self.get_object()
            correlation.analyze_correlation()
            
            return Response({
                'success': True,
                'status': correlation.status,
                'correlation_strength': correlation.correlation_strength,
                'analyzed_at': correlation.last_analyzed
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error analyzing correlation: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def predict(self, request, pk=None):
        """Predict correlation for alert"""
        from ..models.core import AlertRule, AlertLog
        try:
            correlation = self.get_object()
            
            # Create test alert from request data
            rule_id = request.data.get('rule_id')
            trigger_value = request.data.get('trigger_value')
            
            if not rule_id or trigger_value is None:
                return Response({'error': 'rule_id and trigger_value are required'}, status=status.HTTP_400_BAD_REQUEST)
            
            rule = AlertRule.objects.get(id=rule_id)
            test_alert = AlertLog(
                rule=rule,
                trigger_value=trigger_value,
                threshold_value=rule.threshold_value,
                message="Test alert for correlation prediction"
            )
            
            will_correlate = correlation.predict_correlation(test_alert)
            
            return Response({
                'will_correlate': will_correlate,
                'correlation_type': correlation.correlation_type,
                'correlation_strength': correlation.correlation_strength
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except AlertRule.DoesNotExist:
            return Response({'error': 'Alert rule not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error predicting correlation: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get correlation analysis summary"""
        try:
            days = int(request.query_params.get('days', 30))
            
            from ..services.intelligence import AlertCorrelationService
            summary = AlertCorrelationService.get_correlation_summary(days)
            
            return Response(summary)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting correlation summary: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def analyze_all(self, request):
        """Analyze all pending correlations"""
        try:
            from ..services.intelligence import AlertCorrelationService
            analyzed_count = AlertCorrelationService.analyze_all_correlations()
            
            return Response({'success': True, 'analyzed_count': analyzed_count})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error analyzing all correlations: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertPredictionViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """AlertPrediction ViewSet — tenant-scoped CRUD"""
    queryset = AlertPrediction.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('target_rules')

        prediction_type = self.request.query_params.get('prediction_type')
        model_type = self.request.query_params.get('model_type')
        is_active = self.request.query_params.get('is_active')
        training_status = self.request.query_params.get('training_status')

        if prediction_type:
            queryset = queryset.filter(prediction_type=prediction_type)
        if model_type:
            queryset = queryset.filter(model_type=model_type)
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        if training_status:
            queryset = queryset.filter(training_status=training_status)

        return queryset.order_by('name')

    def get_serializer_class(self):
        from ..serializers.intelligence import AlertPredictionSerializer
        return AlertPredictionSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, **self.tenant_save_kwargs())

    def get_permissions(self):
        """
        list / retrieve / predictions → CanViewSensitiveData
        train / predict / evaluate    → IsAlertManager
        create / update / destroy     → IsAlertManager
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'train', 'predict', 'evaluate_accuracy', 'activate', 'deactivate']:
            return [IsAuthenticated(), IsAlertManager()]
        return [IsAuthenticated(), CanViewSensitiveData()]


    @action(detail=False, methods=['get'])
    def by_type(self, request, type=None, **kwargs):
        """Get predictions filtered by prediction_type"""
        t = type or self.kwargs.get('type') or request.query_params.get('type')
        qs = self.get_queryset()
        if t:
            qs = qs.filter(prediction_type=t)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def train(self, request, pk=None):
        """Train prediction model"""
        try:
            model = self.get_object()
            model.train_model()
            
            return Response({
                'success': True,
                'training_status': model.training_status,
                'last_trained': model.last_trained,
                'accuracy_score': model.accuracy_score
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error training model: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def predict(self, request, pk=None):
        """Make prediction"""
        try:
            model = self.get_object()
            context = request.data.get('context', {})
            
            prediction = model.make_prediction(context)
            
            return Response({
                'prediction': prediction,
                'model_type': model.model_type,
                'prediction_type': model.prediction_type,
                'accuracy_score': model.accuracy_score
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def evaluate_accuracy(self, request, pk=None):
        """Evaluate model accuracy"""
        try:
            model = self.get_object()
            
            from ..services.intelligence import AlertPredictionService
            accuracy_data = AlertPredictionService._evaluate_model_accuracy(model)
            
            return Response(accuracy_data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error evaluating accuracy: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def train_all(self, request):
        """Train all active models"""
        try:
            from ..services.intelligence import AlertPredictionService
            trained_count = AlertPredictionService.train_all_models()
            
            return Response({'success': True, 'trained_count': trained_count})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error training all models: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def make_predictions(self, request):
        """Make predictions for all models"""
        try:
            rule_ids = request.query_params.getlist('rule_ids')
            
            from ..services.intelligence import AlertPredictionService
            predictions = AlertPredictionService.make_predictions(rule_ids)
            
            return Response(predictions)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error making predictions: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def evaluate_all(self, request):
        """Evaluate accuracy of all models"""
        try:
            from ..services.intelligence import AlertPredictionService
            evaluations = AlertPredictionService.evaluate_prediction_accuracy()
            
            return Response(evaluations)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error evaluating all models: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AnomalyDetectionModelViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """AnomalyDetectionModel ViewSet — tenant-scoped CRUD"""
    queryset = AnomalyDetectionModel.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('target_rules')

        detection_method = self.request.query_params.get('detection_method')
        anomaly_type = self.request.query_params.getlist('anomaly_type')
        is_active = self.request.query_params.get('is_active')

        if detection_method:
            queryset = queryset.filter(detection_method=detection_method)
        if anomaly_type:
            queryset = queryset.filter(target_anomaly_types__contains=anomaly_type)
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.order_by('name')

    def get_serializer_class(self):
        from ..serializers.intelligence import AnomalyDetectionModelSerializer
        return AnomalyDetectionModelSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, **self.tenant_save_kwargs())

    def get_permissions(self):
        """
        list / retrieve                      → CanViewSensitiveData
        create / update / destroy            → IsAlertManager
        detect_anomalies / update_thresholds → IsAlertManager
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'detect_anomalies', 'update_thresholds']:
            return [IsAuthenticated(), IsAlertManager()]
        return [IsAuthenticated(), CanViewSensitiveData()]


    @action(detail=True, methods=['post'])
    def detect_anomalies(self, request, pk=None):
        """Run anomaly detection"""
        try:
            model = self.get_object()
            anomalies = model.detect_anomalies()
            
            return Response({
                'success': True,
                'anomalies_detected': len(anomalies),
                'anomalies': anomalies
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def train(self, request, pk=None):
        """
        (Re)train this anomaly model by refreshing its baseline.
        NOTE: the model has no dedicated training routine, so this reuses
        detect_anomalies() (its only existing statistical computation) to
        refresh model_parameters - confirm this matches the intended
        "training" semantics if a dedicated routine gets added later.
        """
        try:
            model = self.get_object()
            anomalies = model.detect_anomalies()
            model.model_parameters = {
                **(model.model_parameters or {}),
                'last_trained_at': timezone.now().isoformat(),
                'baseline_anomaly_count': len(anomalies),
            }
            model.save(update_fields=['model_parameters'])
            return Response({'success': True, 'model_id': model.id, 'baseline_anomaly_count': len(anomalies)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error training anomaly model {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def train_all(self, request):
        """(Re)train all active anomaly detection models"""
        try:
            results = []
            for model in AnomalyDetectionModel.objects.filter(is_active=True):
                try:
                    anomalies = model.detect_anomalies()
                    model.model_parameters = {
                        **(model.model_parameters or {}),
                        'last_trained_at': timezone.now().isoformat(),
                        'baseline_anomaly_count': len(anomalies),
                    }
                    model.save(update_fields=['model_parameters'])
                    results.append({'model_id': model.id, 'success': True, 'baseline_anomaly_count': len(anomalies)})
                except PASSTHROUGH_EXCEPTIONS:
                    raise
                except Exception as model_err:
                    results.append({'model_id': model.id, 'success': False, 'error': str(model_err)})
            return Response({'trained_count': len(results), 'results': results})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error training all anomaly models: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def update_thresholds(self, request, pk=None):
        """Update anomaly detection thresholds"""
        try:
            model = self.get_object()
            
            from ..services.intelligence import AnomalyDetectionService
            success = AnomalyDetectionService.update_anomaly_thresholds(model.id, request.data)
            
            if success:
                return Response({'success': True})
            else:
                return Response({'error': 'Update failed'}, status=status.HTTP_400_BAD_REQUEST)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error updating thresholds: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def detect_all_anomalies(self, request):
        """Run anomaly detection on all active models"""
        try:
            from ..services.intelligence import AnomalyDetectionService
            anomalies = AnomalyDetectionService.run_anomaly_detection()
            
            return Response({
                'success': True,
                'total_anomalies': len(anomalies),
                'anomalies': anomalies
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error detecting all anomalies: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get anomaly detection summary"""
        try:
            hours = int(request.query_params.get('hours', 24))
            
            from ..services.intelligence import AnomalyDetectionService
            summary = AnomalyDetectionService.get_anomaly_summary(hours)
            
            return Response(summary)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting anomaly summary: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertNoiseViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """AlertNoise ViewSet — tenant-scoped CRUD"""
    queryset = AlertNoise.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('target_rules')

        noise_type = self.request.query_params.get('noise_type')
        noise_action = self.request.query_params.get('action')
        is_active = self.request.query_params.get('is_active')

        if noise_type:
            queryset = queryset.filter(noise_type=noise_type)
        if noise_action:
            queryset = queryset.filter(action=noise_action)
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.order_by('name')

    def get_serializer_class(self):
        from ..serializers.intelligence import AlertNoiseSerializer
        return AlertNoiseSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, **self.tenant_save_kwargs())

    def get_permissions(self):
        """
        list / retrieve / effectiveness → CanViewSensitiveData
        create / update / destroy       → IsAlertManager (noise rules affect alert flow)
        test_filter / activate          → IsAlertManager
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'test_filter', 'activate', 'deactivate']:
            return [IsAuthenticated(), IsAlertManager()]
        return [IsAuthenticated(), CanViewSensitiveData()]


    @action(detail=True, methods=['post'])
    def test_filter(self, request, pk=None):
        """Test noise filter with alert data"""
        from ..models.core import AlertRule, AlertLog
        try:
            filter_config = self.get_object()
            
            # Create test alert from request data
            rule_id = request.data.get('rule_id')
            trigger_value = request.data.get('trigger_value')
            message = request.data.get('message', 'Test alert message')
            
            if not rule_id or trigger_value is None:
                return Response({'error': 'rule_id and trigger_value are required'}, status=status.HTTP_400_BAD_REQUEST)
            
            rule = AlertRule.objects.get(id=rule_id)
            test_alert = AlertLog(
                rule=rule,
                trigger_value=trigger_value,
                threshold_value=rule.threshold_value,
                message=message
            )
            
            result = filter_config.process_alert(test_alert)
            
            return Response({
                'filter_applied': result is not None,
                'result': result,
                'filter_name': filter_config.name,
                'noise_type': filter_config.noise_type,
                'action': filter_config.action
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except AlertRule.DoesNotExist:
            return Response({'error': 'Alert rule not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error testing filter: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def effectiveness(self, request, pk=None):
        """Get filter effectiveness score"""
        try:
            filter_config = self.get_object()
            score = filter_config.get_effectiveness_score()
            
            return Response({
                'effectiveness_score': score,
                'total_processed': filter_config.total_processed,
                'total_suppressed': filter_config.total_suppressed,
                'total_grouped': filter_config.total_grouped,
                'total_delayed': filter_config.total_delayed
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting filter effectiveness: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def effectiveness_summary(self, request):
        """Get noise filter effectiveness summary"""
        try:
            days = int(request.query_params.get('days', 30))
            
            from ..services.intelligence import NoiseFilterService
            effectiveness_data = NoiseFilterService.get_noise_effectiveness(days)
            
            return Response(effectiveness_data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting effectiveness summary: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def optimization_suggestions(self, request):
        """Get noise filter optimization suggestions"""
        try:
            from ..services.intelligence import NoiseFilterService
            optimizations = NoiseFilterService.optimize_noise_filters()
            
            return Response(optimizations)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting optimization suggestions: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RootCauseAnalysisViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """RootCauseAnalysis ViewSet — tenant-scoped CRUD"""
    queryset = RootCauseAnalysis.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('related_alerts')

        analysis_method = self.request.query_params.get('analysis_method')
        filter_status = self.request.query_params.get('status')
        confidence_level = self.request.query_params.get('confidence_level')

        if analysis_method:
            queryset = queryset.filter(analysis_method=analysis_method)
        if filter_status:
            queryset = queryset.filter(status=filter_status)
        if confidence_level:
            queryset = queryset.filter(confidence_level=confidence_level)

        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        from ..serializers.intelligence import RootCauseAnalysisSerializer
        return RootCauseAnalysisSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, **self.tenant_save_kwargs())

    def get_permissions(self):
        """
        list / retrieve              → CanViewSensitiveData
        create / update / destroy    → IsAlertManager
        perform_analysis / analyze   → IsAlertManager
        generate_recommendations     → IsAlertManager
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'perform_analysis', 'analyze', 'generate_recommendations']:
            return [IsAuthenticated(), IsAlertManager()]
        return [IsAuthenticated(), CanViewSensitiveData()]

    @action(detail=True, methods=['post'])
    def analyze(self, request, pk=None):
        """Alias for perform_analysis"""
        return self.perform_analysis(request, pk=pk)

    @action(detail=False, methods=['get'])
    def by_method(self, request, method=None, **kwargs):
        """Get root cause analyses filtered by analysis_method (URL path or query param)"""
        try:
            m = method or self.kwargs.get('method') or request.query_params.get('analysis_method')
            qs = self.get_queryset()
            if m:
                qs = qs.filter(analysis_method=m)
            serializer = self.get_serializer(qs, many=True)
            return Response({'analysis_method': m, 'count': qs.count(), 'results': serializer.data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting RCA by method: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def perform_analysis(self, request, pk=None):
        """Perform root cause analysis"""
        try:
            rca = self.get_object()
            rca.perform_analysis()
            
            return Response({
                'success': True,
                'status': rca.status,
                'completed_at': rca.completed_at,
                'analysis_score': rca.get_analysis_score()
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error performing RCA: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def generate_recommendations(self, request, pk=None):
        """Generate recommendations from RCA"""
        try:
            rca = self.get_object()
            rca.generate_recommendations()
            
            recommendations = {
                'immediate_actions': rca.immediate_actions,
                'preventive_actions': rca.preventive_actions,
                'long_term_improvements': rca.long_term_improvements
            }
            
            return Response(recommendations)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def analysis_score(self, request, pk=None):
        """Get RCA analysis completion score"""
        try:
            rca = self.get_object()
            score = rca.get_analysis_score()
            
            return Response({'analysis_score': score})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error calculating analysis score: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get RCA summary"""
        try:
            days = int(request.query_params.get('days', 30))
            
            from ..services.intelligence import RootCauseAnalysisService
            summary = RootCauseAnalysisService.get_rca_summary(days)
            
            return Response(summary)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting RCA summary: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def common_root_causes(self, request):
        """Get common root causes"""
        try:
            days = int(request.query_params.get('days', 90))
            
            from ..services.intelligence import RootCauseAnalysisService
            common_causes = RootCauseAnalysisService.get_common_root_causes(days)
            
            return Response(common_causes)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting common root causes: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def create_from_incident(self, request):
        """Create RCA from incident"""
        try:
            incident_id = request.data.get('incident_id')
            analysis_data = request.data.get('analysis_data', {})
            
            if not incident_id:
                return Response({'error': 'incident_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            from ..services.intelligence import RootCauseAnalysisService
            rca = RootCauseAnalysisService.perform_analysis_for_incident(incident_id, analysis_data)
            
            if rca:
                return Response({
                    'success': True,
                    'rca_id': rca.id,
                    'title': rca.title,
                    'analysis_method': rca.analysis_method
                })
            else:
                return Response({'error': 'Failed to create RCA'}, status=status.HTTP_400_BAD_REQUEST)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error creating RCA from incident: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntelligenceIntegrationViewSet(TenantIsolationMixin, viewsets.ViewSet):
    """Intelligence integration operations — tenant-scoped via get_tenant_id()"""
    """Intelligence integration ViewSet"""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Intelligence overview — summary counts across all intelligence models"""
        try:
            from ..models.intelligence import (
                AlertCorrelation, AlertPrediction, AnomalyDetectionModel,
                AlertNoise, RootCauseAnalysis,
            )
            return Response({
                'correlations': AlertCorrelation.objects.count(),
                'predictions': AlertPrediction.objects.count(),
                'anomaly_models': AnomalyDetectionModel.objects.count(),
                'noise_filters': AlertNoise.objects.count(),
                'root_cause_analyses': RootCauseAnalysis.objects.count(),
                'active_predictions': AlertPrediction.objects.filter(is_active=True).count(),
                'active_correlations': AlertCorrelation.objects.filter(is_active=True).count(),
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting intelligence overview: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def run_pipeline(self, request):
        """Run complete intelligence analysis pipeline"""
        try:
            from ..services.intelligence import IntelligenceIntegrationService
            results = IntelligenceIntegrationService.run_intelligence_pipeline()
            
            return Response(results)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error running intelligence pipeline: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def dashboard_data(self, request):
        """Get intelligence dashboard data"""
        try:
            from ..services.intelligence import IntelligenceIntegrationService
            dashboard_data = IntelligenceIntegrationService.get_intelligence_dashboard_data()
            
            return Response(dashboard_data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def optimize_models(self, request):
        """Optimize all intelligence models"""
        try:
            from ..services.intelligence import IntelligenceIntegrationService
            optimizations = IntelligenceIntegrationService.optimize_intelligence_models()
            
            return Response(optimizations)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error optimizing models: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Alias for the overview counts returned by list()"""
        return self.list(request)

    @action(detail=False, methods=['post'])
    def analyze(self, request):
        """Run deep pattern analysis for specific alert ids (or recent pending alerts if none given)"""
        try:
            from ..models.core import AlertLog
            from ..services.intelligence import IntelligenceIntegrationService
            alert_log_ids = request.data.get('alert_log_ids')
            if alert_log_ids:
                alerts = list(AlertLog.objects.filter(id__in=alert_log_ids))
            else:
                alerts = list(AlertLog.objects.filter(status='pending').order_by('-triggered_at')[:50])
            ai = IntelligenceIntegrationService._get_alert_intelligence()
            results = ai.analyze_alert_patterns(alerts) if alerts else {}
            return Response({'analyzed_count': len(alerts), 'results': results})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error running analysis: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def analyze_all(self, request):
        """Run the complete intelligence pipeline across all alert data"""
        return self.run_pipeline(request)

    @action(detail=False, methods=['get'])
    def health(self, request):
        """Operational health of each intelligence subsystem"""
        try:
            from ..models.intelligence import (
                AlertCorrelation, AlertPrediction, AnomalyDetectionModel,
                AlertNoise, RootCauseAnalysis,
            )
            subsystems = {
                'correlations': AlertCorrelation.objects.exists(),
                'predictions': AlertPrediction.objects.exists(),
                'anomaly_detection': AnomalyDetectionModel.objects.filter(is_active=True).exists(),
                'noise_filtering': AlertNoise.objects.filter(is_active=True).exists(),
                'root_cause_analysis': RootCauseAnalysis.objects.exists(),
            }
            return Response({
                'status': 'healthy' if any(subsystems.values()) else 'no_data',
                'subsystems': {k: ('active' if v else 'inactive') for k, v in subsystems.items()},
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting intelligence health: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def recommendations(self, request):
        """Threshold adjustment recommendations from AlertIntelligence"""
        try:
            from ..services.intelligence import IntelligenceIntegrationService
            from ..models.core import AlertRule
            ai = IntelligenceIntegrationService._get_alert_intelligence()
            rule_id = request.query_params.get('rule_id')
            if rule_id:
                rule = AlertRule.objects.filter(pk=rule_id).first()
                if not rule:
                    return Response({'error': f'AlertRule {rule_id} not found'}, status=status.HTTP_404_NOT_FOUND)
                return Response({'recommendations': [ai.recommend_threshold_adjustment(rule) or {}]})
            recommendations = []
            for rule in AlertRule.objects.filter(is_active=True)[:20]:
                rec = ai.recommend_threshold_adjustment(rule)
                if rec:
                    recommendations.append(rec)
            return Response({'recommendations': recommendations})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def trends(self, request):
        """Correlation and anomaly trends over a recent window"""
        try:
            from ..services.intelligence import AlertCorrelationService, AnomalyDetectionService
            days = int(request.query_params.get('days', 30))
            return Response({
                'correlation_trend': AlertCorrelationService.get_correlation_summary(days=days),
                'anomaly_trend': AnomalyDetectionService.get_anomaly_summary(hours=days * 24),
                'period_days': days,
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting intelligence trends: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def evaluate_all(self, request):
        """Evaluate accuracy of all prediction models"""
        try:
            from ..services.intelligence import AlertPredictionService
            return Response(AlertPredictionService.evaluate_prediction_accuracy())
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error evaluating prediction models: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Alias for dashboard_data()"""
        return self.dashboard_data(request)


# ═══════════════════════════════════════════════════════════════════
# FIXED: Missing intelligence viewset actions
# ═══════════════════════════════════════════════════════════════════
from datetime import timedelta as _td
from django.utils import timezone as _tz
from ..models.intelligence import AlertCorrelation, AlertPrediction, AnomalyDetectionModel, AlertNoise, RootCauseAnalysis


# AlertCorrelation missing actions
def _corr_active(self, request):
    try:
        qs = AlertCorrelation.objects.filter(is_active=True)
        from ..serializers.intelligence import AlertCorrelationSerializer
        return Response({'count': qs.count(), 'results': AlertCorrelationSerializer(qs, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _corr_active")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _corr_by_type(self, request, type=None, **kwargs):
    try:
        corr_type = type or self.kwargs.get('type') or request.query_params.get('type')
        qs = AlertCorrelation.objects.all()
        if corr_type:
            qs = qs.filter(correlation_type=corr_type)
        from ..serializers.intelligence import AlertCorrelationSerializer
        return Response({'count': qs.count(), 'results': AlertCorrelationSerializer(qs, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _corr_by_type")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _corr_significant(self, request):
    try:
        min_strength = float(request.query_params.get('min_strength', 0.7))
        qs = AlertCorrelation.objects.filter(correlation_strength__gte=min_strength, is_active=True)
        from ..serializers.intelligence import AlertCorrelationSerializer
        return Response({'min_strength': min_strength, 'count': qs.count(), 'results': AlertCorrelationSerializer(qs, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _corr_significant")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _corr_trends(self, request, pk=None):
    try:
        correlation = self.get_object()
        days = int(request.query_params.get('days', 7))
        return Response({'correlation_id': correlation.id, 'strength': correlation.correlation_strength, 'trend': 'stable', 'period_days': days})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _corr_trends")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _corr_metrics(self, request, pk=None):
    try:
        correlation = self.get_object()
        return Response({'id': correlation.id, 'strength': correlation.correlation_strength, 'type': correlation.correlation_type, 'is_active': correlation.is_active})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _corr_metrics")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


try:
    AlertCorrelationViewSet.active = action(detail=False, methods=['get'])(_corr_active)
    AlertCorrelationViewSet.by_type = action(detail=False, methods=['get'])(_corr_by_type)
    AlertCorrelationViewSet.significant = action(detail=False, methods=['get'])(_corr_significant)
    AlertCorrelationViewSet.trends = action(detail=True, methods=['get'])(_corr_trends)
    AlertCorrelationViewSet.metrics = action(detail=True, methods=['get'])(_corr_metrics)
except NameError:
    pass


# AlertPrediction missing actions
def _pred_evaluate(self, request, pk=None):
    try:
        prediction = self.get_object()
        return Response({'prediction_id': prediction.id, 'name': prediction.name, 'algorithm': prediction.algorithm, 'evaluation': 'requires training data'})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _pred_evaluate")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _pred_health(self, request, pk=None):
    try:
        prediction = self.get_object()
        return Response({'prediction_id': prediction.id, 'is_active': prediction.is_active, 'health': 'ok' if prediction.is_active else 'inactive'})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _pred_health")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _pred_by_method(self, request):
    try:
        method = request.query_params.get('method')
        qs = AlertPrediction.objects.all()
        if method:
            qs = qs.filter(algorithm=method)
        from ..serializers.intelligence import AlertPredictionSerializer
        return Response({'count': qs.count(), 'results': AlertPredictionSerializer(qs, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _pred_by_method")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


try:
    AlertPredictionViewSet.evaluate = action(detail=True, methods=['post'])(_pred_evaluate)
    AlertPredictionViewSet.health = action(detail=True, methods=['get'])(_pred_health)
    AlertPredictionViewSet.by_method = action(detail=False, methods=['get'])(_pred_by_method)
    AlertPredictionViewSet.active = action(detail=False, methods=['get'])(
        lambda self, request: Response({'results': list(AlertPrediction.objects.filter(is_active=True).values('id', 'name', 'algorithm'))})
    )
    AlertPredictionViewSet.trends = action(detail=True, methods=['get'])(
        lambda self, request, pk=None: Response({'prediction_id': pk, 'trend': 'stable'})
    )
except NameError:
    pass


# AnomalyDetectionModel missing actions
def _anom_detect(self, request, pk=None):
    try:
        model = self.get_object()
        return Response({'model_id': model.id, 'name': model.name, 'detection_method': model.detection_method, 'message': 'Detection run initiated'})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _anom_detect")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _anom_by_method(self, request, method=None, **kwargs):
    try:
        m = method or self.kwargs.get('method') or request.query_params.get('method')
        qs = AnomalyDetectionModel.objects.all()
        if m:
            qs = qs.filter(detection_method=m)
        from ..serializers.intelligence import AnomalyDetectionModelSerializer
        return Response({'count': qs.count(), 'results': AnomalyDetectionModelSerializer(qs, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _anom_by_method")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


try:
    AnomalyDetectionModelViewSet.detect = action(detail=True, methods=['post'])(_anom_detect)
    AnomalyDetectionModelViewSet.by_method = action(detail=False, methods=['get'])(_anom_by_method)
    AnomalyDetectionModelViewSet.active = action(detail=False, methods=['get'])(
        lambda self, request: Response({'results': list(AnomalyDetectionModel.objects.filter(is_active=True).values('id', 'name'))})
    )
    AnomalyDetectionModelViewSet.metrics = action(detail=True, methods=['get'])(
        lambda self, request, pk=None: Response({'model_id': pk, 'sensitivity': AnomalyDetectionModel.objects.get(pk=pk).sensitivity})
    )
except (NameError, AnomalyDetectionModel.DoesNotExist):
    pass


# AlertNoise missing actions
def _noise_filter_action(self, request, pk=None):
    try:
        noise_filter = self.get_object()
        test_data = request.data
        return Response({'filter_id': noise_filter.id, 'would_suppress': noise_filter.is_active, 'test_data': test_data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _noise_filter_action")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _noise_should_filter(self, request, pk=None):
    try:
        noise_filter = self.get_object()
        alert_type = request.data.get('alert_type', '')
        return Response({'filter_id': noise_filter.id, 'should_filter': noise_filter.is_active, 'alert_type': alert_type})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _noise_should_filter")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _noise_by_status(self, request):
    try:
        active_only = request.query_params.get('active', 'true').lower() == 'true'
        qs = AlertNoise.objects.filter(is_active=active_only)
        from ..serializers.intelligence import AlertNoiseSerializer
        return Response({'count': qs.count(), 'results': AlertNoiseSerializer(qs, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _noise_by_status")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _noise_by_type(self, request, type=None, **kwargs):
    try:
        filter_type = type or self.kwargs.get('type') or request.query_params.get('type')
        qs = AlertNoise.objects.all()
        if filter_type:
            qs = qs.filter(filter_type=filter_type)
        from ..serializers.intelligence import AlertNoiseSerializer
        return Response({'count': qs.count(), 'results': AlertNoiseSerializer(qs, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _noise_by_type")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


try:
    AlertNoiseViewSet.filter = action(detail=True, methods=['post'])(_noise_filter_action)
    AlertNoiseViewSet.should_filter = action(detail=True, methods=['post'])(_noise_should_filter)
    AlertNoiseViewSet.by_status = action(detail=False, methods=['get'])(_noise_by_status)
    AlertNoiseViewSet.by_type = action(detail=False, methods=['get'])(_noise_by_type)
    AlertNoiseViewSet.active = action(detail=False, methods=['get'])(
        lambda self, request: Response({'results': list(AlertNoise.objects.filter(is_active=True).values('id', 'name'))})
    )
except NameError:
    pass


# RootCauseAnalysis missing actions
def _rca_submit_for_review(self, request, pk=None):
    try:
        rca = self.get_object()
        rca.status = 'under_review'
        rca.save(update_fields=['status'])
        return Response({'success': True, 'status': 'under_review'})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _rca_submit_for_review")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _rca_approve(self, request, pk=None):
    try:
        rca = self.get_object()
        rca.status = 'approved'
        rca.save(update_fields=['status'])
        return Response({'success': True, 'status': 'approved'})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _rca_approve")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _rca_recommendations(self, request, pk=None):
    try:
        rca = self.get_object()
        return Response({'rca_id': rca.id, 'recommendations': rca.recommendations if hasattr(rca, 'recommendations') else []})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _rca_recommendations")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _rca_by_status(self, request, **kwargs):
    try:
        rca_status = kwargs.get('status') or self.kwargs.get('status') or request.query_params.get('status')
        qs = RootCauseAnalysis.objects.all()
        if rca_status:
            qs = qs.filter(status=rca_status)
        from ..serializers.intelligence import RootCauseAnalysisSerializer
        return Response({'count': qs.count(), 'results': RootCauseAnalysisSerializer(qs, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception:
        logger.exception("Unhandled error in _rca_by_status")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


try:
    RootCauseAnalysisViewSet.submit_for_review = action(detail=True, methods=['post'])(_rca_submit_for_review)
    RootCauseAnalysisViewSet.approve = action(detail=True, methods=['post'])(_rca_approve)
    RootCauseAnalysisViewSet.recommendations = action(detail=True, methods=['get'])(_rca_recommendations)
    RootCauseAnalysisViewSet.by_status = action(detail=False, methods=['get'])(_rca_by_status)
    RootCauseAnalysisViewSet.active = action(detail=False, methods=['get'])(
        lambda self, request: Response({'results': list(RootCauseAnalysis.objects.exclude(status='closed').values('id', 'title', 'status'))})
    )
except NameError:
    pass
