"""
Intelligence ViewSets
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
import logging

from ..models.intelligence import (
    AlertCorrelation, AlertPrediction, AnomalyDetectionModel, 
    AlertNoise, RootCauseAnalysis
)

logger = logging.getLogger(__name__)


class AlertCorrelationViewSet(viewsets.ModelViewSet):
    """AlertCorrelation ViewSet for CRUD operations"""
    queryset = AlertCorrelation.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('primary_rules', 'secondary_rules')
        
        # Apply filters
        correlation_type = self.request.query_params.get('correlation_type')
        status = self.request.query_params.get('status')
        
        if correlation_type:
            queryset = queryset.filter(correlation_type=correlation_type)
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('name')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.intelligence import AlertCorrelationSerializer
        return AlertCorrelationSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def get_permissions(self):
        if self.action in ['analyze', 'predict']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
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
        except Exception as e:
            logger.error(f"Error analyzing correlation: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def predict(self, request, pk=None):
        """Predict correlation for alert"""
        try:
            correlation = self.get_object()
            
            # Create test alert from request data
            from ..models.core import AlertRule, AlertLog
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
        except AlertRule.DoesNotExist:
            return Response({'error': 'Alert rule not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error predicting correlation: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get correlation analysis summary"""
        try:
            days = int(request.query_params.get('days', 30))
            
            from ..services.intelligence import AlertCorrelationService
            summary = AlertCorrelationService.get_correlation_summary(days)
            
            return Response(summary)
        except Exception as e:
            logger.error(f"Error getting correlation summary: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def analyze_all(self, request):
        """Analyze all pending correlations"""
        try:
            from ..services.intelligence import AlertCorrelationService
            analyzed_count = AlertCorrelationService.analyze_all_correlations()
            
            return Response({'success': True, 'analyzed_count': analyzed_count})
        except Exception as e:
            logger.error(f"Error analyzing all correlations: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertPredictionViewSet(viewsets.ModelViewSet):
    """AlertPrediction ViewSet for CRUD operations"""
    queryset = AlertPrediction.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('target_rules')
        
        # Apply filters
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
        # Will be defined in serializers
        from ..serializers.intelligence import AlertPredictionSerializer
        return AlertPredictionSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def get_permissions(self):
        if self.action in ['train', 'predict', 'evaluate_accuracy']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
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
        except Exception as e:
            logger.error(f"Error training model: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def evaluate_accuracy(self, request, pk=None):
        """Evaluate model accuracy"""
        try:
            model = self.get_object()
            
            from ..services.intelligence import AlertPredictionService
            accuracy_data = AlertPredictionService._evaluate_model_accuracy(model)
            
            return Response(accuracy_data)
        except Exception as e:
            logger.error(f"Error evaluating accuracy: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def train_all(self, request):
        """Train all active models"""
        try:
            from ..services.intelligence import AlertPredictionService
            trained_count = AlertPredictionService.train_all_models()
            
            return Response({'success': True, 'trained_count': trained_count})
        except Exception as e:
            logger.error(f"Error training all models: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def make_predictions(self, request):
        """Make predictions for all models"""
        try:
            rule_ids = request.query_params.getlist('rule_ids')
            
            from ..services.intelligence import AlertPredictionService
            predictions = AlertPredictionService.make_predictions(rule_ids)
            
            return Response(predictions)
        except Exception as e:
            logger.error(f"Error making predictions: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def evaluate_all(self, request):
        """Evaluate accuracy of all models"""
        try:
            from ..services.intelligence import AlertPredictionService
            evaluations = AlertPredictionService.evaluate_prediction_accuracy()
            
            return Response(evaluations)
        except Exception as e:
            logger.error(f"Error evaluating all models: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AnomalyDetectionModelViewSet(viewsets.ModelViewSet):
    """AnomalyDetectionModel ViewSet for CRUD operations"""
    queryset = AnomalyDetectionModel.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('target_rules')
        
        # Apply filters
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
        # Will be defined in serializers
        from ..serializers.intelligence import AnomalyDetectionModelSerializer
        return AnomalyDetectionModelSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def get_permissions(self):
        if self.action in ['detect_anomalies', 'update_thresholds']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
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
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error updating thresholds: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error detecting all anomalies: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get anomaly detection summary"""
        try:
            hours = int(request.query_params.get('hours', 24))
            
            from ..services.intelligence import AnomalyDetectionService
            summary = AnomalyDetectionService.get_anomaly_summary(hours)
            
            return Response(summary)
        except Exception as e:
            logger.error(f"Error getting anomaly summary: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertNoiseViewSet(viewsets.ModelViewSet):
    """AlertNoise ViewSet for CRUD operations"""
    queryset = AlertNoise.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('target_rules')
        
        # Apply filters
        noise_type = self.request.query_params.get('noise_type')
        action = self.request.query_params.get('action')
        is_active = self.request.query_params.get('is_active')
        
        if noise_type:
            queryset = queryset.filter(noise_type=noise_type)
        if action:
            queryset = queryset.filter(action=action)
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('name')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.intelligence import AlertNoiseSerializer
        return AlertNoiseSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def test_filter(self, request, pk=None):
        """Test noise filter with alert data"""
        try:
            filter_config = self.get_object()
            
            # Create test alert from request data
            from ..models.core import AlertRule, AlertLog
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
        except AlertRule.DoesNotExist:
            return Response({'error': 'Alert rule not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error testing filter: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error getting filter effectiveness: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def effectiveness_summary(self, request):
        """Get noise filter effectiveness summary"""
        try:
            days = int(request.query_params.get('days', 30))
            
            from ..services.intelligence import NoiseFilterService
            effectiveness_data = NoiseFilterService.get_noise_effectiveness(days)
            
            return Response(effectiveness_data)
        except Exception as e:
            logger.error(f"Error getting effectiveness summary: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def optimization_suggestions(self, request):
        """Get noise filter optimization suggestions"""
        try:
            from ..services.intelligence import NoiseFilterService
            optimizations = NoiseFilterService.optimize_noise_filters()
            
            return Response(optimizations)
        except Exception as e:
            logger.error(f"Error getting optimization suggestions: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RootCauseAnalysisViewSet(viewsets.ModelViewSet):
    """RootCauseAnalysis ViewSet for CRUD operations"""
    queryset = RootCauseAnalysis.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('related_alerts')
        
        # Apply filters
        analysis_method = self.request.query_params.get('analysis_method')
        status = self.request.query_params.get('status')
        confidence_level = self.request.query_params.get('confidence_level')
        
        if analysis_method:
            queryset = queryset.filter(analysis_method=analysis_method)
        if status:
            queryset = queryset.filter(status=status)
        if confidence_level:
            queryset = queryset.filter(confidence_level=confidence_level)
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.intelligence import RootCauseAnalysisSerializer
        return RootCauseAnalysisSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def get_permissions(self):
        if self.action in ['perform_analysis', 'generate_recommendations']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
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
        except Exception as e:
            logger.error(f"Error performing RCA: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def analysis_score(self, request, pk=None):
        """Get RCA analysis completion score"""
        try:
            rca = self.get_object()
            score = rca.get_analysis_score()
            
            return Response({'analysis_score': score})
        except Exception as e:
            logger.error(f"Error calculating analysis score: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get RCA summary"""
        try:
            days = int(request.query_params.get('days', 30))
            
            from ..services.intelligence import RootCauseAnalysisService
            summary = RootCauseAnalysisService.get_rca_summary(days)
            
            return Response(summary)
        except Exception as e:
            logger.error(f"Error getting RCA summary: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def common_root_causes(self, request):
        """Get common root causes"""
        try:
            days = int(request.query_params.get('days', 90))
            
            from ..services.intelligence import RootCauseAnalysisService
            common_causes = RootCauseAnalysisService.get_common_root_causes(days)
            
            return Response(common_causes)
        except Exception as e:
            logger.error(f"Error getting common root causes: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error creating RCA from incident: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntelligenceIntegrationViewSet(viewsets.ViewSet):
    """Intelligence integration ViewSet"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def run_pipeline(self, request):
        """Run complete intelligence analysis pipeline"""
        try:
            from ..services.intelligence import IntelligenceIntegrationService
            results = IntelligenceIntegrationService.run_intelligence_pipeline()
            
            return Response(results)
        except Exception as e:
            logger.error(f"Error running intelligence pipeline: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def dashboard_data(self, request):
        """Get intelligence dashboard data"""
        try:
            from ..services.intelligence import IntelligenceIntegrationService
            dashboard_data = IntelligenceIntegrationService.get_intelligence_dashboard_data()
            
            return Response(dashboard_data)
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def optimize_models(self, request):
        """Optimize all intelligence models"""
        try:
            from ..services.intelligence import IntelligenceIntegrationService
            optimizations = IntelligenceIntegrationService.optimize_intelligence_models()
            
            return Response(optimizations)
        except Exception as e:
            logger.error(f"Error optimizing models: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
