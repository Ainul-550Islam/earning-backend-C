# api/admin_panel/viewsets/AIEngineAdminViewSet.py
"""
AIEngineAdminViewSet — Admin control for AI/ML Engine.
Only imports from api.ai_engine.models — no duplicate code.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class AIEngineAdminViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.ai_engine.models import AIModel, TrainingJob, PredictionLog
            last_7d = timezone.now() - timedelta(days=7)
            return Response({'success': True, 'data': {
                'total_models': AIModel.objects.count(),
                'active_models': AIModel.objects.filter(is_active=True).count(),
                'training_jobs_7d': TrainingJob.objects.filter(created_at__gte=last_7d).count(),
                'predictions_7d': PredictionLog.objects.filter(created_at__gte=last_7d).count(),
                'model_types': list(AIModel.objects.values('model_type').distinct()),
            }})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def model_list(self, request):
        try:
            from api.ai_engine.models import AIModel
            models = list(AIModel.objects.values(
                'id', 'name', 'model_type', 'version', 'is_active',
                'accuracy', 'last_trained_at', 'description'
            ).order_by('-accuracy'))
            return Response({'success': True, 'data': models})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_model(self, request):
        try:
            from api.ai_engine.models import AIModel
            model_id = request.data.get('model_id')
            m = AIModel.objects.get(pk=model_id)
            m.is_active = not m.is_active
            m.save(update_fields=['is_active'])
            return Response({'success': True, 'model_id': model_id, 'is_active': m.is_active})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def training_jobs(self, request):
        try:
            from api.ai_engine.models import TrainingJob
            jobs = list(TrainingJob.objects.values(
                'id', 'model__name', 'status', 'started_at', 'completed_at',
                'accuracy_improvement', 'error_message'
            ).order_by('-started_at')[:50])
            return Response({'success': True, 'data': jobs})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def trigger_training(self, request):
        try:
            from api.ai_engine.models import AIModel, TrainingJob
            model_id = request.data.get('model_id')
            model = AIModel.objects.get(pk=model_id)
            job = TrainingJob.objects.create(
                model=model,
                status='queued',
                triggered_by=request.user,
            )
            try:
                from celery import current_app
                current_app.send_task('api.ai_engine.tasks.run_training_job', args=[job.pk])
            except Exception:
                pass
            return Response({'success': True, 'job_id': job.pk, 'model': model.name})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def prediction_stats(self, request):
        try:
            from api.ai_engine.models import PredictionLog
            from django.db.models import Count, Avg
            last_7d = timezone.now() - timedelta(days=7)
            stats = {
                'total_7d': PredictionLog.objects.filter(created_at__gte=last_7d).count(),
                'by_model': list(PredictionLog.objects.filter(
                    created_at__gte=last_7d
                ).values('model_name').annotate(count=Count('id'), avg_confidence=Avg('confidence_score')).order_by('-count')),
            }
            return Response({'success': True, 'data': stats})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def anomaly_detections(self, request):
        try:
            from api.ai_engine.models import AnomalyDetectionLog
            last_24h = timezone.now() - timedelta(hours=24)
            anomalies = list(AnomalyDetectionLog.objects.filter(
                created_at__gte=last_24h
            ).values('id', 'anomaly_type', 'severity', 'description', 'entity_id', 'created_at')
            .order_by('-severity', '-created_at')[:50])
            return Response({'success': True, 'data': anomalies})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def churn_risk_users(self, request):
        try:
            from api.ai_engine.models import ChurnRiskProfile
            threshold = float(request.query_params.get('threshold', 0.7))
            at_risk = list(ChurnRiskProfile.objects.filter(
                churn_probability__gte=threshold
            ).values('user_id', 'churn_probability', 'risk_factors', 'predicted_at')
            .order_by('-churn_probability')[:100])
            return Response({'success': True, 'data': at_risk, 'threshold': threshold})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def feature_store(self, request):
        try:
            from api.ai_engine.models import FeatureStore
            features = list(FeatureStore.objects.values(
                'id', 'feature_name', 'feature_type', 'description', 'last_updated'
            ).order_by('-last_updated'))
            return Response({'success': True, 'data': features})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})