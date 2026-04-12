"""
api/ai_engine/services.py
==========================
AI Engine — Core Business Logic / Service Layer।
ViewSet → Service → Repository → DB
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from datetime import timedelta

from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import (
    AIModel, ModelVersion, TrainingJob, PredictionLog,
    AnomalyDetectionLog, ChurnRiskProfile, RecommendationResult,
    UserSegment, TextAnalysisResult, PersonalizationProfile,
    InsightModel, DataDriftLog,
)
from .repository import (
    AIModelRepository, ModelVersionRepository, TrainingJobRepository,
    PredictionLogRepository, AnomalyRepository, ChurnRepository,
    RecommendationRepository, SegmentRepository, PersonalizationRepository,
    InsightRepository, FeatureRepository, DriftRepository,
)
from .exceptions import (
    ModelNotFoundError, InsufficientDataError, PredictionError,
    RecommendationError, TrainingInProgressError,
)
from .utils import (
    get_churn_risk_level, get_ltv_segment, days_since,
    generate_request_id, normalize_score,
)
from .constants import (
    DEFAULT_FRAUD_THRESHOLD, DEFAULT_CHURN_THRESHOLD,
    DEFAULT_ANOMALY_THRESHOLD, DEFAULT_RECOMMENDATIONS,
    BATCH_SIZE_INFERENCE,
)
from . import cache as ai_cache

User = get_user_model()
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# MODEL MANAGEMENT SERVICE
# ══════════════════════════════════════════════════════════════════════

class ModelManagementService:
    """AI Model lifecycle management।"""

    @staticmethod
    def register_model(data: dict, created_by=None) -> AIModel:
        """নতুন AI Model register করো।"""
        if created_by:
            data['created_by'] = created_by
        model = AIModelRepository.create(data)
        logger.info(f"AI Model registered: {model.name} [{model.id}]")
        return model

    @staticmethod
    def deploy_model(model_id: str) -> AIModel:
        """Model কে deployed status এ নিয়ে যাও।"""
        model = AIModelRepository.get_by_id(model_id)
        if not model:
            raise ModelNotFoundError(f"Model not found: {model_id}")

        # শুধু trained model deploy করা যাবে
        if model.status not in ['trained', 'evaluating']:
            raise PredictionError(f"Cannot deploy model in status: {model.status}")

        AIModelRepository.update_status(model_id, 'deployed')
        model.refresh_from_db()
        ai_cache.invalidate_model_meta(str(model_id))
        logger.info(f"Model deployed: {model.name}")
        return model

    @staticmethod
    def deprecate_model(model_id: str):
        """Model কে deprecated করো।"""
        AIModelRepository.update_status(model_id, 'deprecated')
        ai_cache.invalidate_model_meta(str(model_id))

    @staticmethod
    def get_model_summary(model_id: str) -> dict:
        """Model এর সম্পূর্ণ summary।"""
        model = AIModelRepository.get_by_id(model_id)
        if not model:
            raise ModelNotFoundError()

        versions = ModelVersionRepository.get_all_versions(model_id)
        active_version = next((v for v in versions if v.is_active), None)

        return {
            'model': {
                'id': str(model.id),
                'name': model.name,
                'algorithm': model.algorithm,
                'task_type': model.task_type,
                'status': model.status,
            },
            'active_version': {
                'version': active_version.version if active_version else None,
                'f1_score': active_version.f1_score if active_version else 0.0,
                'auc_roc': active_version.auc_roc if active_version else 0.0,
                'trained_at': active_version.trained_at if active_version else None,
            } if active_version else None,
            'total_versions': len(versions),
            'drift_status': DriftRepository.get_latest(model_id),
        }


# ══════════════════════════════════════════════════════════════════════
# TRAINING SERVICE
# ══════════════════════════════════════════════════════════════════════

class TrainingService:
    """Model training orchestration।"""

    @staticmethod
    def start_training(ai_model_id: str, dataset_path: str, hyperparams: dict = None, triggered_by=None) -> TrainingJob:
        """Training job শুরু করো।"""
        # চলমান training আছে কিনা চেক করো
        running = TrainingJobRepository.get_running_jobs(ai_model_id)
        if running:
            raise TrainingInProgressError()

        # Model status → training
        AIModelRepository.update_status(ai_model_id, 'training')

        job = TrainingJobRepository.create({
            'ai_model_id': ai_model_id,
            'dataset_path': dataset_path,
            'hyperparameters': hyperparams or {},
            'status': 'running',
            'started_at': timezone.now(),
            'triggered_by': triggered_by,
        })

        logger.info(f"Training job started: {job.job_id}")
        return job

    @staticmethod
    def complete_training(job_id: str, version_data: dict, duration: float) -> ModelVersion:
        """Training সফলভাবে শেষ হলে।"""
        job = TrainingJob.objects.get(job_id=job_id)

        # নতুন version তৈরি করো
        version = ModelVersionRepository.create({
            'ai_model': job.ai_model,
            'trained_at': timezone.now(),
            **version_data,
        })

        TrainingJobRepository.mark_completed(job_id, version, duration)
        AIModelRepository.update_status(str(job.ai_model_id), 'trained')

        logger.info(f"Training completed: {job_id} → version {version.version}")
        return version

    @staticmethod
    def fail_training(job_id: str, error: str):
        """Training fail হলে।"""
        job = TrainingJob.objects.get(job_id=job_id)
        TrainingJobRepository.mark_failed(job_id, error)
        AIModelRepository.update_status(str(job.ai_model_id), 'failed')
        logger.error(f"Training failed: {job_id} — {error}")


# ══════════════════════════════════════════════════════════════════════
# PREDICTION SERVICE
# ══════════════════════════════════════════════════════════════════════

class PredictionService:
    """Real-time ও batch prediction।"""

    @staticmethod
    def predict(prediction_type: str, input_data: dict, user=None, tenant_id=None) -> dict:
        """
        Single prediction করো।
        Model খুঁজে → features build → inference → log করো।
        """
        start_time = time.time()
        request_id = generate_request_id()

        # Model খুঁজো
        model = AIModelRepository.get_for_task(prediction_type, tenant_id)
        if not model:
            # Fallback: rule-based prediction
            return PredictionService._rule_based_prediction(prediction_type, input_data, request_id)

        try:
            # Feature engineering
            from .ML_MODELS.feature_engineering import FeatureEngineer
            engineer = FeatureEngineer(feature_type=prediction_type)
            features = engineer.extract(input_data)

            # Model inference
            from .PREDICTION_ENGINES.real_time_predictor import RealTimePredictor
            predictor = RealTimePredictor(model)
            result = predictor.predict(features)

        except Exception as e:
            logger.error(f"Prediction error [{prediction_type}]: {e}")
            result = PredictionService._rule_based_prediction(prediction_type, input_data, request_id)

        inference_ms = (time.time() - start_time) * 1000

        # Log করো
        PredictionLogRepository.log_prediction({
            'ai_model': model,
            'model_version': model.active_version,
            'prediction_type': prediction_type,
            'user': user,
            'input_data': input_data,
            'prediction': result,
            'confidence': result.get('confidence', 0.0),
            'predicted_class': result.get('predicted_class', ''),
            'predicted_value': result.get('predicted_value'),
            'inference_ms': inference_ms,
            'request_id': request_id,
            'tenant_id': tenant_id,
        })

        result['request_id'] = request_id
        result['inference_ms'] = round(inference_ms, 2)
        return result

    @staticmethod
    def _rule_based_prediction(prediction_type: str, input_data: dict, request_id: str) -> dict:
        """ML model নেই হলে rule-based fallback।"""
        result = {
            'prediction_type': prediction_type,
            'confidence': 0.5,
            'predicted_class': 'unknown',
            'predicted_value': None,
            'method': 'rule_based_fallback',
        }

        if prediction_type == 'fraud':
            # Simple rules
            score = 0.1
            if input_data.get('is_vpn'):
                score += 0.3
            if input_data.get('is_proxy'):
                score += 0.3
            if input_data.get('multiple_accounts'):
                score += 0.4
            result['predicted_value'] = min(1.0, score)
            result['predicted_class'] = 'fraud' if score >= DEFAULT_FRAUD_THRESHOLD else 'legit'
            result['confidence'] = 0.6

        elif prediction_type == 'churn':
            days_inactive = input_data.get('days_since_last_login', 0)
            score = min(1.0, days_inactive / 30)
            result['predicted_value'] = score
            result['risk_level'] = get_churn_risk_level(score)
            result['confidence'] = 0.55

        return result

    @staticmethod
    def batch_predict(prediction_type: str, items: List[dict], tenant_id=None) -> List[dict]:
        """Batch prediction।"""
        results = []
        for i in range(0, len(items), BATCH_SIZE_INFERENCE):
            batch = items[i:i + BATCH_SIZE_INFERENCE]
            for item in batch:
                try:
                    result = PredictionService.predict(prediction_type, item, tenant_id=tenant_id)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Batch prediction error: {e}")
                    results.append({'error': str(e), 'input': item})
        return results


# ══════════════════════════════════════════════════════════════════════
# FRAUD DETECTION SERVICE
# ══════════════════════════════════════════════════════════════════════

class FraudDetectionService:
    """Real-time fraud scoring।"""

    @staticmethod
    def score_user_action(user, action_type: str, metadata: dict, tenant_id=None) -> dict:
        """
        ইউজারের কোনো action কতটা fraudulent সেটা score করো।
        """
        input_data = {
            'user_id': str(user.id),
            'action_type': action_type,
            'is_vpn': metadata.get('is_vpn', False),
            'is_proxy': metadata.get('is_proxy', False),
            'is_tor': metadata.get('is_tor', False),
            'ip_country': metadata.get('ip_country', ''),
            'device_count': metadata.get('device_count', 1),
            'account_age_days': days_since(user.date_joined),
            **metadata,
        }

        result = PredictionService.predict('fraud', input_data, user=user, tenant_id=tenant_id)

        # High fraud score → anomaly log করো
        fraud_score = result.get('predicted_value', 0.0) or 0.0
        if fraud_score >= DEFAULT_FRAUD_THRESHOLD:
            AnomalyRepository.create({
                'tenant_id': tenant_id,
                'anomaly_type': f'fraud_{action_type}',
                'severity': 'high' if fraud_score >= 0.9 else 'medium',
                'status': 'open',
                'user': user,
                'anomaly_score': fraud_score,
                'threshold': DEFAULT_FRAUD_THRESHOLD,
                'evidence_data': metadata,
                'auto_action_taken': 'flagged',
                'ip_address': metadata.get('ip_address'),
            })

        return {
            'fraud_score': fraud_score,
            'is_fraud': fraud_score >= DEFAULT_FRAUD_THRESHOLD,
            'action_type': action_type,
            **result,
        }


# ══════════════════════════════════════════════════════════════════════
# CHURN PREDICTION SERVICE
# ══════════════════════════════════════════════════════════════════════

class ChurnPredictionService:
    """User churn prediction ও retention।"""

    @staticmethod
    def predict_churn(user, tenant_id=None) -> dict:
        """একটি user এর churn risk predict করো।"""
        cached = ai_cache.get_churn_profile(str(user.id))
        if cached:
            return cached

        # Features collect করো
        input_data = {
            'user_id': str(user.id),
            'days_since_last_login': days_since(user.last_login),
            'account_age_days': days_since(user.date_joined),
            'coin_balance': float(getattr(user, 'coin_balance', 0)),
            'total_earned': float(getattr(user, 'total_earned', 0)),
        }

        result = PredictionService.predict('churn', input_data, user=user, tenant_id=tenant_id)
        prob = result.get('predicted_value') or result.get('confidence', 0.3)
        risk_level = get_churn_risk_level(float(prob))

        # DB update করো
        ChurnRepository.update_profile(str(user.id), {
            'churn_probability': prob,
            'risk_level': risk_level,
            'days_since_login': input_data['days_since_last_login'],
        })

        response = {
            'user_id': str(user.id),
            'churn_probability': prob,
            'risk_level': risk_level,
            'retention_actions': ChurnPredictionService._get_retention_actions(risk_level),
        }
        ai_cache.set_churn_profile(str(user.id), response)
        return response

    @staticmethod
    def _get_retention_actions(risk_level: str) -> List[str]:
        actions = {
            'very_high': [
                'Send urgent win-back offer',
                'Personal outreach via SMS',
                'Give bonus coins',
                'Show referral bonus reminder',
            ],
            'high': [
                'Send retention email',
                'Show limited-time offer',
                'Activate daily streak reminder',
            ],
            'medium': [
                'Send weekly digest email',
                'Show new offers notification',
            ],
            'low': ['Continue normal engagement'],
            'very_low': [],
        }
        return actions.get(risk_level, [])

    @staticmethod
    def bulk_predict_churn(user_ids: List, tenant_id=None) -> List[dict]:
        """Bulk churn prediction।"""
        results = []
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                result = ChurnPredictionService.predict_churn(user, tenant_id)
                results.append(result)
            except Exception as e:
                logger.error(f"Churn prediction error for {user_id}: {e}")
        return results


# ══════════════════════════════════════════════════════════════════════
# RECOMMENDATION SERVICE
# ══════════════════════════════════════════════════════════════════════

class RecommendationService:
    """Personalized offer/product recommendation।"""

    @staticmethod
    def get_recommendations(user, item_type: str = 'offer', engine: str = 'hybrid',
                             count: int = DEFAULT_RECOMMENDATIONS, context: dict = None,
                             tenant_id=None) -> dict:
        """User এর জন্য recommendations generate করো।"""
        # Cache check
        cached = ai_cache.get_recommendations(str(user.id), item_type)
        if cached:
            return {'items': cached, 'source': 'cache', 'engine': engine}

        request_id = generate_request_id()

        try:
            engine_obj = __import__(
                f'api.ai_engine.RECOMMENDATION_ENGINES.hybrid_recommender',
                fromlist=['HybridRecommender']
            ).HybridRecommender()
            items = engine_obj.recommend(user, item_type=item_type, count=count, context=context or {})
        except Exception as e:
            logger.error(f"Recommendation engine error: {e}")
            items = RecommendationService._popularity_fallback(item_type, count, tenant_id)

        # Save করো
        RecommendationRepository.save({
            'user': user,
            'engine': engine,
            'item_type': item_type,
            'recommended_items': items,
            'item_count': len(items),
            'context_data': context or {},
            'request_id': request_id,
            'tenant_id': tenant_id,
        })

        # Cache করো
        ai_cache.set_recommendations(str(user.id), item_type, items)

        return {
            'items': items,
            'count': len(items),
            'engine': engine,
            'item_type': item_type,
            'request_id': request_id,
        }

    @staticmethod
    def _popularity_fallback(item_type: str, count: int, tenant_id=None) -> List[dict]:
        """Engine fail হলে popularity-based fallback।"""
        # Simple fallback — top offers by conversion
        try:
            from api.ad_networks.models import Offer
            offers = Offer.objects.filter(
                status='active'
            ).order_by('-created_at')[:count]
            return [{'item_id': str(o.id), 'item_type': item_type, 'score': 0.5} for o in offers]
        except Exception:
            return []

    @staticmethod
    def track_click(request_id: str, item_id: str):
        RecommendationRepository.track_click(request_id, item_id)
        ai_cache.invalidate_recommendations  # invalidate on click

    @staticmethod
    def track_conversion(request_id: str, item_id: str):
        RecommendationRepository.track_conversion(request_id, item_id)


# ══════════════════════════════════════════════════════════════════════
# NLP SERVICE
# ══════════════════════════════════════════════════════════════════════

class NLPService:
    """Text analysis — sentiment, spam, intent।"""

    @staticmethod
    def analyze_text(text: str, analysis_type: str = 'sentiment',
                     source_type: str = '', source_id: str = '',
                     user=None, tenant_id=None) -> TextAnalysisResult:
        """Text analyze করো এবং result save করো।"""
        start_time = time.time()

        result_data = {
            'analysis_type': analysis_type,
            'input_text': text[:5000],
            'detected_language': 'en',
            'source_type': source_type,
            'source_id': source_id,
            'user': user,
            'tenant_id': tenant_id,
        }

        try:
            if analysis_type == 'sentiment':
                analysis = NLPService._analyze_sentiment(text)
            elif analysis_type == 'spam':
                analysis = NLPService._detect_spam(text)
            elif analysis_type == 'intent':
                analysis = NLPService._classify_intent(text)
            elif analysis_type == 'profanity':
                analysis = NLPService._detect_profanity(text)
            else:
                analysis = NLPService._analyze_sentiment(text)

            result_data.update(analysis)
        except Exception as e:
            logger.error(f"NLP analysis error [{analysis_type}]: {e}")

        result_data['inference_ms'] = round((time.time() - start_time) * 1000, 2)
        return TextAnalysisResult.objects.create(**result_data)

    @staticmethod
    def _analyze_sentiment(text: str) -> dict:
        """Simple rule-based sentiment (ML model না থাকলে fallback)।"""
        positive_words = {'good', 'great', 'excellent', 'amazing', 'love', 'wonderful', 'thanks', 'ধন্যবাদ', 'ভালো'}
        negative_words = {'bad', 'terrible', 'horrible', 'hate', 'awful', 'worst', 'খারাপ', 'বাজে'}

        text_lower = text.lower()
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)

        if pos_count > neg_count:
            sentiment, score = 'positive', min(0.9, 0.5 + pos_count * 0.1)
        elif neg_count > pos_count:
            sentiment, score = 'negative', max(-0.9, -0.5 - neg_count * 0.1)
        else:
            sentiment, score = 'neutral', 0.0

        return {
            'sentiment': sentiment,
            'sentiment_score': score,
        }

    @staticmethod
    def _detect_spam(text: str) -> dict:
        spam_indicators = ['click here', 'free money', 'urgent', 'win now', 'limited time', 'act now']
        text_lower = text.lower()
        spam_count = sum(1 for ind in spam_indicators if ind in text_lower)
        spam_confidence = min(1.0, spam_count * 0.3)
        return {
            'is_spam': spam_confidence >= 0.5,
            'spam_confidence': spam_confidence,
        }

    @staticmethod
    def _classify_intent(text: str) -> dict:
        intents = {
            'complaint': ['problem', 'issue', 'not working', 'broken', 'error'],
            'inquiry': ['how', 'what', 'when', 'where', 'why', 'can i'],
            'request': ['please', 'help', 'need', 'want', 'request'],
            'feedback': ['suggest', 'improve', 'feedback', 'opinion'],
        }
        text_lower = text.lower()
        for intent, keywords in intents.items():
            if any(kw in text_lower for kw in keywords):
                return {'intent': intent, 'intent_confidence': 0.7}
        return {'intent': 'general', 'intent_confidence': 0.5}

    @staticmethod
    def _detect_profanity(text: str) -> dict:
        # Placeholder — production এ proper library use করো
        return {'has_profanity': False, 'is_flagged': False}


# ══════════════════════════════════════════════════════════════════════
# ANOMALY DETECTION SERVICE
# ══════════════════════════════════════════════════════════════════════

class AnomalyDetectionService:
    """Real-time anomaly detection।"""

    @staticmethod
    def detect(anomaly_type: str, entity_id: str, data: dict,
               user=None, tenant_id=None) -> Optional[AnomalyDetectionLog]:
        """
        Anomaly আছে কিনা check করো।
        Score >= threshold হলে log করো।
        """
        score = AnomalyDetectionService._score(anomaly_type, data)

        if score < DEFAULT_ANOMALY_THRESHOLD:
            return None  # Normal — log করার দরকার নেই

        severity = 'critical' if score >= 0.95 else 'high' if score >= 0.85 else 'medium'

        anomaly = AnomalyRepository.create({
            'tenant_id': tenant_id,
            'anomaly_type': anomaly_type,
            'severity': severity,
            'user': user,
            'entity_id': entity_id,
            'anomaly_score': score,
            'threshold': DEFAULT_ANOMALY_THRESHOLD,
            'evidence_data': data,
            'auto_action_taken': AnomalyDetectionService._auto_action(severity),
            'ip_address': data.get('ip_address'),
        })

        logger.warning(f"Anomaly detected: {anomaly_type} score={score:.2f} severity={severity}")
        return anomaly

    @staticmethod
    def _score(anomaly_type: str, data: dict) -> float:
        """Rule-based scoring — production এ ML model দিয়ে replace করো।"""
        score = 0.0

        if anomaly_type in ['fraud_click', 'fraud_conversion']:
            if data.get('is_vpn'):        score += 0.25
            if data.get('is_proxy'):      score += 0.25
            if data.get('is_tor'):        score += 0.35
            if data.get('click_rate', 0) > 100: score += 0.3
            if data.get('device_count', 1) > 3: score += 0.2

        elif anomaly_type == 'unusual_login':
            if data.get('new_country'):   score += 0.3
            if data.get('new_device'):    score += 0.2
            if data.get('odd_hours'):     score += 0.2

        elif anomaly_type == 'bulk_request':
            rps = data.get('requests_per_second', 0)
            if rps > 10:  score = min(1.0, rps / 100)

        return min(1.0, score)

    @staticmethod
    def _auto_action(severity: str) -> str:
        actions = {
            'critical': 'block_and_flag',
            'high':     'flag_for_review',
            'medium':   'warn_user',
            'low':      'log_only',
        }
        return actions.get(severity, 'log_only')


# ══════════════════════════════════════════════════════════════════════
# INSIGHT GENERATION SERVICE
# ══════════════════════════════════════════════════════════════════════

class InsightGenerationService:
    """AI-driven business insights auto-generation।"""

    @staticmethod
    def generate_daily_insights(tenant_id=None) -> List[InsightModel]:
        """প্রতিদিনের insights generate করো।"""
        insights = []

        # Churn risk insight
        high_risk = ChurnRepository.get_high_risk_users(tenant_id, limit=1000)
        if len(high_risk) > 50:
            insight = InsightModel.objects.create(
                tenant_id=tenant_id,
                title=f"{len(high_risk)} users at high churn risk",
                description=f"AI analysis shows {len(high_risk)} users may leave soon. Immediate retention action recommended.",
                insight_type='risk',
                priority='high',
                supporting_data={'high_risk_count': len(high_risk)},
                recommended_actions=[
                    'Send retention campaign to high-risk users',
                    'Offer bonus coins to inactive users',
                    'Analyze top exit points',
                ],
                confidence_score=0.82,
            )
            insights.append(insight)

        # Cache invalidate করো
        if tenant_id:
            ai_cache.invalidate_insights(str(tenant_id))

        return insights

    @staticmethod
    def dismiss_insight(insight_id: str, user_id):
        InsightRepository.dismiss(insight_id, user_id)
        return True


# ══════════════════════════════════════════════════════════════════════
# PERSONALIZATION SERVICE
# ══════════════════════════════════════════════════════════════════════

class PersonalizationService:
    """User personalization profile management।"""

    @staticmethod
    def get_or_build_profile(user, tenant_id=None) -> PersonalizationProfile:
        """User এর personalization profile নিয়ে আসো বা তৈরি করো।"""
        profile = PersonalizationRepository.get_or_create(str(user.id), tenant_id)

        # Stale হলে refresh করো (24 ঘণ্টার বেশি পুরনো)
        needs_refresh = (
            profile.last_refreshed is None or
            (timezone.now() - profile.last_refreshed).seconds > 86400
        )

        if needs_refresh:
            PersonalizationService.refresh_profile(user, profile, tenant_id)

        return profile

    @staticmethod
    def refresh_profile(user, profile: PersonalizationProfile, tenant_id=None):
        """Profile data refresh করো।"""
        try:
            update_data = {
                'activity_score': PersonalizationService._calc_activity_score(user),
                'is_mobile_first': True,
                'last_refreshed': timezone.now(),
            }
            PersonalizationRepository.update(str(user.id), update_data)
        except Exception as e:
            logger.error(f"Profile refresh error for {user.id}: {e}")

    @staticmethod
    def _calc_activity_score(user) -> float:
        score = 0.0
        if user.last_login:
            days = days_since(user.last_login)
            score = max(0.0, 1.0 - (days / 30))
        return round(score, 3)
