"""
api/ai_engine/repository.py
============================
AI Engine — Database access layer (Repository Pattern)।
Service layer এখান থেকে DB queries করে।
"""

import logging
from typing import Optional, List, Dict, Any
from django.utils import timezone
from django.db.models import Q, Avg, Count, Max
from django.core.exceptions import ObjectDoesNotExist

from .models import (
    AIModel, ModelVersion, TrainingJob, ModelMetric,
    FeatureStore, UserEmbedding, ItemEmbedding,
    PredictionLog, AnomalyDetectionLog, ChurnRiskProfile,
    RecommendationResult, UserSegment, ABTestExperiment,
    TextAnalysisResult, ImageAnalysisResult, ContentModerationLog,
    PersonalizationProfile, InsightModel, DataDriftLog, ExperimentTracking,
)

logger = logging.getLogger(__name__)


# ── AIModel Repository ──────────────────────────────────────────────────

class AIModelRepository:

    @staticmethod
    def get_by_id(model_id: str) -> Optional[AIModel]:
        return AIModel.objects.filter(id=model_id).first()

    @staticmethod
    def get_by_slug(slug: str) -> Optional[AIModel]:
        return AIModel.objects.filter(slug=slug, is_active=True).first()

    @staticmethod
    def get_deployed_models(tenant_id=None) -> List[AIModel]:
        qs = AIModel.objects.filter(status='deployed', is_active=True)
        if tenant_id:
            qs = qs.filter(Q(tenant_id=tenant_id) | Q(tenant__isnull=True))
        return list(qs)

    @staticmethod
    def get_for_task(task_type: str, tenant_id=None) -> Optional[AIModel]:
        qs = AIModel.objects.filter(
            task_type=task_type, status='deployed',
            is_active=True, is_production=True,
        ).order_by('-created_at')
        if tenant_id:
            model = qs.filter(tenant_id=tenant_id).first()
            if model:
                return model
        return qs.filter(tenant__isnull=True).first()

    @staticmethod
    def create(data: dict) -> AIModel:
        return AIModel.objects.create(**data)

    @staticmethod
    def update_status(model_id: str, status: str) -> bool:
        updated = AIModel.objects.filter(id=model_id).update(status=status, updated_at=timezone.now())
        return updated > 0


# ── ModelVersion Repository ─────────────────────────────────────────────

class ModelVersionRepository:

    @staticmethod
    def get_active_version(ai_model_id: str) -> Optional[ModelVersion]:
        return ModelVersion.objects.filter(
            ai_model_id=ai_model_id, is_active=True
        ).first()

    @staticmethod
    def get_all_versions(ai_model_id: str) -> List[ModelVersion]:
        return list(ModelVersion.objects.filter(ai_model_id=ai_model_id).order_by('-trained_at'))

    @staticmethod
    def create(data: dict) -> ModelVersion:
        return ModelVersion.objects.create(**data)

    @staticmethod
    def promote_to_production(version_id: str):
        """একটি version কে production করো, বাকিগুলো staging এ নামাও।"""
        version = ModelVersion.objects.get(id=version_id)
        ModelVersion.objects.filter(
            ai_model=version.ai_model, stage='production'
        ).update(stage='staging', is_active=False)
        version.stage = 'production'
        version.is_active = True
        version.save(update_fields=['stage', 'is_active'])
        return version


# ── TrainingJob Repository ──────────────────────────────────────────────

class TrainingJobRepository:

    @staticmethod
    def get_running_jobs(ai_model_id: str) -> List[TrainingJob]:
        return list(TrainingJob.objects.filter(
            ai_model_id=ai_model_id, status='running'
        ))

    @staticmethod
    def create(data: dict) -> TrainingJob:
        return TrainingJob.objects.create(**data)

    @staticmethod
    def mark_completed(job_id: str, model_version: ModelVersion, duration: float):
        TrainingJob.objects.filter(job_id=job_id).update(
            status='completed',
            finished_at=timezone.now(),
            duration_seconds=duration,
            model_version=model_version,
        )

    @staticmethod
    def mark_failed(job_id: str, error: str):
        TrainingJob.objects.filter(job_id=job_id).update(
            status='failed',
            finished_at=timezone.now(),
            error_message=error,
        )


# ── PredictionLog Repository ────────────────────────────────────────────

class PredictionLogRepository:

    @staticmethod
    def log_prediction(data: dict) -> PredictionLog:
        return PredictionLog.objects.create(**data)

    @staticmethod
    def get_user_predictions(user_id, prediction_type: str = None, limit: int = 50):
        qs = PredictionLog.objects.filter(user_id=user_id)
        if prediction_type:
            qs = qs.filter(prediction_type=prediction_type)
        return list(qs.order_by('-created_at')[:limit])

    @staticmethod
    def update_ground_truth(request_id: str, actual_outcome: str, is_correct: bool):
        PredictionLog.objects.filter(request_id=request_id).update(
            actual_outcome=actual_outcome,
            is_correct=is_correct,
            feedback_at=timezone.now(),
        )

    @staticmethod
    def get_accuracy_stats(ai_model_id: str, days: int = 30) -> dict:
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)
        qs = PredictionLog.objects.filter(
            ai_model_id=ai_model_id,
            created_at__gte=since,
            is_correct__isnull=False,
        )
        total = qs.count()
        correct = qs.filter(is_correct=True).count()
        return {
            'total': total,
            'correct': correct,
            'accuracy': round(correct / total, 4) if total > 0 else 0.0,
        }


# ── AnomalyDetectionLog Repository ─────────────────────────────────────

class AnomalyRepository:

    @staticmethod
    def create(data: dict) -> AnomalyDetectionLog:
        return AnomalyDetectionLog.objects.create(**data)

    @staticmethod
    def get_open_anomalies(tenant_id=None, severity: str = None):
        qs = AnomalyDetectionLog.objects.filter(status='open')
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        if severity:
            qs = qs.filter(severity=severity)
        return qs.order_by('-anomaly_score')

    @staticmethod
    def resolve(anomaly_id: str, resolved_by_id, notes: str = ''):
        AnomalyDetectionLog.objects.filter(id=anomaly_id).update(
            status='resolved',
            resolved_by_id=resolved_by_id,
            resolved_at=timezone.now(),
            resolution_notes=notes,
        )

    @staticmethod
    def count_user_anomalies(user_id, hours: int = 24) -> int:
        from datetime import timedelta
        since = timezone.now() - timedelta(hours=hours)
        return AnomalyDetectionLog.objects.filter(
            user_id=user_id, created_at__gte=since
        ).count()


# ── ChurnRiskProfile Repository ─────────────────────────────────────────

class ChurnRepository:

    @staticmethod
    def get_or_create(user_id, tenant_id=None) -> ChurnRiskProfile:
        obj, _ = ChurnRiskProfile.objects.get_or_create(
            user_id=user_id,
            defaults={'tenant_id': tenant_id}
        )
        return obj

    @staticmethod
    def update_profile(user_id, data: dict):
        ChurnRiskProfile.objects.filter(user_id=user_id).update(**data)

    @staticmethod
    def get_high_risk_users(tenant_id=None, limit: int = 100):
        qs = ChurnRiskProfile.objects.filter(
            risk_level__in=['high', 'very_high']
        ).order_by('-churn_probability')
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return list(qs[:limit])


# ── RecommendationResult Repository ─────────────────────────────────────

class RecommendationRepository:

    @staticmethod
    def save(data: dict) -> RecommendationResult:
        return RecommendationResult.objects.create(**data)

    @staticmethod
    def get_latest_for_user(user_id, item_type: str = 'offer') -> Optional[RecommendationResult]:
        return RecommendationResult.objects.filter(
            user_id=user_id, item_type=item_type
        ).order_by('-created_at').first()

    @staticmethod
    def track_click(request_id: str, clicked_item_id: str):
        RecommendationResult.objects.filter(request_id=request_id).update(
            clicked_item_id=clicked_item_id
        )

    @staticmethod
    def track_conversion(request_id: str, converted_item_id: str):
        RecommendationResult.objects.filter(request_id=request_id).update(
            converted_item_id=converted_item_id
        )


# ── UserSegment Repository ───────────────────────────────────────────────

class SegmentRepository:

    @staticmethod
    def get_active_segments(tenant_id=None) -> List[UserSegment]:
        qs = UserSegment.objects.filter(is_active=True)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return list(qs)

    @staticmethod
    def get_user_segment(user_id, tenant_id=None) -> Optional[UserSegment]:
        """User যে segment এ আছে সেটা বের করো।"""
        qs = UserSegment.objects.filter(is_active=True)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        for segment in qs:
            if str(user_id) in [str(u) for u in segment.user_ids]:
                return segment
        return None


# ── PersonalizationProfile Repository ───────────────────────────────────

class PersonalizationRepository:

    @staticmethod
    def get_or_create(user_id, tenant_id=None) -> PersonalizationProfile:
        obj, _ = PersonalizationProfile.objects.get_or_create(
            user_id=user_id,
            defaults={'tenant_id': tenant_id}
        )
        return obj

    @staticmethod
    def update(user_id, data: dict):
        data['last_refreshed'] = timezone.now()
        PersonalizationProfile.objects.filter(user_id=user_id).update(**data)


# ── InsightModel Repository ─────────────────────────────────────────────

class InsightRepository:

    @staticmethod
    def get_active_insights(tenant_id=None, priority: str = None):
        qs = InsightModel.objects.filter(is_active=True, is_dismissed=False)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        if priority:
            qs = qs.filter(priority=priority)
        return qs.order_by('-priority', '-created_at')

    @staticmethod
    def dismiss(insight_id: str, user_id):
        InsightModel.objects.filter(id=insight_id).update(
            is_dismissed=True,
            dismissed_by_id=user_id,
            dismissed_at=timezone.now(),
        )


# ── FeatureStore Repository ─────────────────────────────────────────────

class FeatureRepository:

    @staticmethod
    def get_features(entity_id: str, feature_type: str) -> Optional[FeatureStore]:
        return FeatureStore.objects.filter(
            entity_id=entity_id, feature_type=feature_type, is_active=True
        ).order_by('-created_at').first()

    @staticmethod
    def upsert(entity_id: str, feature_type: str, features: dict, entity_type: str = 'user', tenant_id=None):
        obj, created = FeatureStore.objects.update_or_create(
            entity_id=entity_id,
            feature_type=feature_type,
            defaults={
                'features': features,
                'feature_count': len(features),
                'entity_type': entity_type,
                'tenant_id': tenant_id,
                'is_active': True,
            }
        )
        return obj, created


# ── DataDriftLog Repository ─────────────────────────────────────────────

class DriftRepository:

    @staticmethod
    def create(data: dict) -> DataDriftLog:
        return DataDriftLog.objects.create(**data)

    @staticmethod
    def get_latest(ai_model_id: str) -> Optional[DataDriftLog]:
        return DataDriftLog.objects.filter(
            ai_model_id=ai_model_id
        ).order_by('-detected_at').first()

    @staticmethod
    def needs_retrain(ai_model_id: str) -> bool:
        latest = DriftRepository.get_latest(ai_model_id)
        if latest and latest.status == 'critical':
            return True
        return False
