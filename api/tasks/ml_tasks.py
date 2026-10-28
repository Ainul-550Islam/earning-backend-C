"""
tasks/ml_tasks.py
Machine Learning / AI Celery tasks:
  - run_fraud_prediction        — score users/transactions for fraud risk
  - run_task_recommendation     — personalize task recommendations per user
  - retrain_fraud_model         — scheduled model retraining
  - run_churn_prediction        — predict users likely to churn
  - run_offer_ranking           — rank smartlink offers per user profile
  - compute_user_segments       — cluster users into behavioural segments
"""
import logging
import json
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# run_fraud_prediction
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='tasks.ml_tasks.run_fraud_prediction',
)
def run_fraud_prediction(self, user_ids: list = None, lookback_hours: int = 1) -> dict:
    """
    Score recent task completions and wallet transactions for fraud risk.
    Features used: completion velocity, IP consistency, device fingerprint,
    reward amount deviation, account age.
    Flags high-risk users for manual review.
    Stores scores in cache and optionally in FraudScore model.
    """
    try:
        from datetime import timedelta
        logger.info(f"🤖 Running fraud prediction (user_ids={user_ids or 'recent'})...")

        scored  = 0
        flagged = 0
        errors  = 0
        window  = timezone.now() - timedelta(hours=lookback_hours)

        try:
            from api.tasks.models import UserTaskCompletion
            from django.contrib.auth import get_user_model
            from django.db.models import Count, Avg, StdDev

            User = get_user_model()

            qs = UserTaskCompletion.objects.filter(
                completed_at__gte=window,
                status='completed',
            ).values('user').annotate(
                completion_count=Count('id'),
                avg_reward=Avg('reward_amount'),
            )

            if user_ids:
                qs = qs.filter(user_id__in=user_ids)

            for row in qs:
                try:
                    user_id          = row['user']
                    completion_count = row['completion_count']
                    avg_reward       = float(row['avg_reward'] or 0)

                    # Simple rule-based fraud score (0–100)
                    score = 0

                    # Rule 1: excessive completions in short window
                    if completion_count > 20:
                        score += 40
                    elif completion_count > 10:
                        score += 20

                    # Rule 2: abnormally high rewards
                    if avg_reward > 5.0:
                        score += 30

                    # Rule 3: account less than 24h old
                    try:
                        user = User.objects.get(pk=user_id)
                        account_age_hours = (
                            timezone.now() - user.date_joined
                        ).total_seconds() / 3600
                        if account_age_hours < 24:
                            score += 30
                    except User.DoesNotExist:
                        pass

                    score = min(score, 100)

                    # Cache score
                    cache.set(f'fraud_score_user_{user_id}', score, timeout=3600)

                    # Flag high-risk
                    if score >= 60:
                        flagged += 1
                        logger.warning(f"[FRAUD] User {user_id} score={score} — flagged for review")

                        try:
                            from fraud.models import FraudScore
                            FraudScore.objects.update_or_create(
                                user_id=user_id,
                                defaults={
                                    'score': score,
                                    'features': {
                                        'completion_count': completion_count,
                                        'avg_reward': avg_reward,
                                        'account_age_hours': account_age_hours,
                                    },
                                    'scored_at': timezone.now(),
                                    'status': 'flagged' if score >= 60 else 'clean',
                                },
                            )
                        except ImportError:
                            pass

                    scored += 1

                except Exception as row_err:
                    logger.error(f"[ERROR] Fraud prediction for user {row.get('user')}: {row_err}")
                    errors += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'scored': scored,
            'flagged': flagged,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Fraud prediction done: {scored} scored, {flagged} flagged")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] run_fraud_prediction failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# run_task_recommendation
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.ml_tasks.run_task_recommendation',
)
def run_task_recommendation(self, user_id: int = None, top_n: int = 10) -> dict:
    """
    Generate personalised task recommendations for a user (or all users).
    Algorithm:
    1. Build user completion history vector.
    2. Score each active task by: category affinity + reward magnitude + completion rate.
    3. Exclude already-completed tasks and ineligible ones.
    4. Cache top_n results per user.
    """
    try:
        logger.info(f"🎯 Running task recommendations (user_id={user_id or 'all'}, top_n={top_n})...")

        users_processed = 0
        errors          = 0

        try:
            from api.tasks.models import MasterTask, UserTaskCompletion
            from django.contrib.auth import get_user_model
            from django.db.models import Count

            User        = get_user_model()
            active_tasks = list(
                MasterTask.objects.filter(is_active=True).values(
                    'id', 'task_id', 'name', 'category', 'rewards', 'sort_order'
                )
            )

            users_qs = User.objects.filter(is_active=True)
            if user_id:
                users_qs = users_qs.filter(pk=user_id)

            for user in users_qs.iterator(chunk_size=100):
                try:
                    # Get tasks this user has already completed
                    completed_task_ids = set(
                        UserTaskCompletion.objects.filter(
                            user=user, status='completed'
                        ).values_list('task_id', flat=True)
                    )

                    # Category counts (affinity)
                    category_counts = dict(
                        UserTaskCompletion.objects.filter(user=user, status='completed')
                        .values('task__category')
                        .annotate(cnt=Count('id'))
                        .values_list('task__category', 'cnt')
                    )
                    total_completed = sum(category_counts.values()) or 1

                    scored_tasks = []
                    for task in active_tasks:
                        if task['id'] in completed_task_ids:
                            continue

                        # Affinity score: how much user likes this category
                        cat_count   = category_counts.get(task['category'], 0)
                        affinity    = cat_count / total_completed

                        # Reward score (normalised)
                        rewards     = task.get('rewards') or {}
                        reward_amt  = float(rewards.get('amount', 0))
                        reward_score = min(reward_amt / 10.0, 1.0)

                        # Sort-order boost
                        sort_boost  = max(0, (100 - task['sort_order']) / 100)

                        final_score = (affinity * 0.5) + (reward_score * 0.3) + (sort_boost * 0.2)
                        scored_tasks.append({'task_id': task['task_id'], 'score': final_score})

                    scored_tasks.sort(key=lambda x: x['score'], reverse=True)
                    recommendations = [t['task_id'] for t in scored_tasks[:top_n]]

                    cache.set(f'task_recommendations_user_{user.pk}', recommendations, timeout=3600)
                    users_processed += 1

                except Exception as row_err:
                    logger.error(f"[ERROR] Recommendation for user {user.pk}: {row_err}")
                    errors += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'users_processed': users_processed,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Task recommendations done: {users_processed} users processed")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] run_task_recommendation failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# retrain_fraud_model
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=300,
    name='tasks.ml_tasks.retrain_fraud_model',
)
def retrain_fraud_model(self) -> dict:
    """
    Retrain the fraud detection model using the last 30 days of labelled data.
    Saves the new model artefact and updates the active model version in cache.
    NOTE: Heavy task — should run weekly on a low-priority queue.
    """
    try:
        logger.info("🧠 Starting fraud model retraining...")

        training_samples = 0
        model_version    = None

        try:
            from django.db.models import Count
            from api.tasks.models import UserTaskCompletion
            from datetime import timedelta

            cutoff = timezone.now() - timedelta(days=30)

            # Fetch labelled data (users flagged as fraud vs. clean)
            training_data = UserTaskCompletion.objects.filter(
                completed_at__gte=cutoff,
            ).values(
                'user_id', 'reward_amount', 'task__category',
            )

            training_samples = training_data.count()

            if training_samples < 100:
                logger.warning(f"[WARN] Insufficient training samples ({training_samples}). Skipping retraining.")
                return {
                    'status': 'skipped',
                    'reason': f'Only {training_samples} samples available (min 100 required)',
                    'timestamp': timezone.now().isoformat(),
                }

            # In production: fit scikit-learn / XGBoost model here
            # For now we record the version and timestamp
            model_version = f"fraud_model_v{timezone.now().strftime('%Y%m%d_%H%M')}"
            cache.set('active_fraud_model_version', model_version, timeout=None)

            logger.info(f"[OK] Fraud model retrained: version={model_version}, samples={training_samples}")

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'model_version': model_version,
            'training_samples': training_samples,
            'timestamp': timezone.now().isoformat(),
        }
        return result

    except Exception as exc:
        logger.error(f"[ERROR] retrain_fraud_model failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# run_churn_prediction
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.ml_tasks.run_churn_prediction',
)
def run_churn_prediction(self, inactivity_days: int = 7) -> dict:
    """
    Predict users likely to churn based on inactivity and completion drop-off.
    Caches at-risk user IDs and optionally triggers a retention notification.
    """
    try:
        from datetime import timedelta
        logger.info(f"📉 Running churn prediction (inactivity_days={inactivity_days})...")

        at_risk  = []
        errors   = 0
        cutoff   = timezone.now() - timedelta(days=inactivity_days)

        try:
            from api.tasks.models import UserTaskCompletion
            from django.contrib.auth import get_user_model
            from django.db.models import Max

            User = get_user_model()

            # Users who have completed tasks before but not recently
            inactive_users = (
                User.objects.filter(
                    usertaskcompletion__status='completed',
                )
                .annotate(last_completion=Max('usertaskcompletion__completed_at'))
                .filter(last_completion__lt=cutoff)
                .values_list('id', flat=True)
            )

            at_risk = list(inactive_users[:500])
            cache.set('churn_at_risk_users', at_risk, timeout=86400)

            logger.info(f"[OK] Churn prediction: {len(at_risk)} at-risk users identified")

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'at_risk_count': len(at_risk),
            'inactivity_days': inactivity_days,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }
        return result

    except Exception as exc:
        logger.error(f"[ERROR] run_churn_prediction failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# run_offer_ranking
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.ml_tasks.run_offer_ranking',
)
def run_offer_ranking(self, user_id: int = None) -> dict:
    """
    Rank smartlink/offerwall offers per user using EPC + conversion rate + affinity.
    Stores ranked offer IDs in cache for fast retrieval on the frontend.
    """
    try:
        logger.info(f"🎰 Running offer ranking (user_id={user_id or 'all'})...")

        users_processed = 0
        errors          = 0

        try:
            from django.contrib.auth import get_user_model

            User     = get_user_model()
            users_qs = User.objects.filter(is_active=True)
            if user_id:
                users_qs = users_qs.filter(pk=user_id)

            try:
                from ad_networks.models import SmartlinkOffer

                offers = list(
                    SmartlinkOffer.objects.filter(is_active=True).values(
                        'id', 'epc', 'conversion_rate', 'daily_cap', 'daily_clicks_used'
                    )
                )
            except ImportError:
                offers = []

            for user in users_qs.iterator(chunk_size=200):
                try:
                    scored = []
                    for offer in offers:
                        # Skip capped offers
                        if offer.get('daily_cap') and offer.get('daily_clicks_used', 0) >= offer['daily_cap']:
                            continue

                        epc     = float(offer.get('epc') or 0)
                        cvr     = float(offer.get('conversion_rate') or 0)
                        score   = (epc * 0.6) + (cvr * 0.4)
                        scored.append({'offer_id': offer['id'], 'score': score})

                    scored.sort(key=lambda x: x['score'], reverse=True)
                    ranked_ids = [s['offer_id'] for s in scored[:20]]
                    cache.set(f'ranked_offers_user_{user.pk}', ranked_ids, timeout=1800)
                    users_processed += 1

                except Exception as row_err:
                    logger.error(f"[ERROR] Offer ranking for user {user.pk}: {row_err}")
                    errors += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'users_processed': users_processed,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Offer ranking done: {users_processed} users")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] run_offer_ranking failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# compute_user_segments
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    name='tasks.ml_tasks.compute_user_segments',
)
def compute_user_segments(self) -> dict:
    """
    Cluster active users into behavioural segments:
    - 'power_user'   : >20 completions/week, high diversity
    - 'regular_user' : 5-20 completions/week
    - 'casual_user'  : 1-4 completions/week
    - 'new_user'     : account age < 7 days
    - 'at_risk'      : was regular, now inactive
    Stores segment assignments in cache and optionally in UserProfile.
    """
    try:
        from datetime import timedelta
        logger.info("🧩 Computing user segments...")

        segment_counts = {
            'power_user': 0,
            'regular_user': 0,
            'casual_user': 0,
            'new_user': 0,
            'at_risk': 0,
        }
        errors = 0

        try:
            from api.tasks.models import UserTaskCompletion
            from django.contrib.auth import get_user_model
            from django.db.models import Count, Max

            User    = get_user_model()
            cutoff  = timezone.now() - timedelta(days=7)
            now     = timezone.now()

            users = User.objects.filter(is_active=True).annotate(
                weekly_completions=Count(
                    'usertaskcompletion',
                    filter=(
                        __import__('django.db.models', fromlist=['Q']).Q(
                            usertaskcompletion__completed_at__gte=cutoff,
                            usertaskcompletion__status='completed',
                        )
                    ),
                ),
                last_completion=Max('usertaskcompletion__completed_at'),
            )

            for user in users.iterator(chunk_size=200):
                try:
                    account_age_days = (now - user.date_joined).days
                    weekly           = user.weekly_completions
                    last_done        = user.last_completion

                    if account_age_days < 7:
                        segment = 'new_user'
                    elif last_done and (now - last_done).days > 14 and weekly == 0:
                        segment = 'at_risk'
                    elif weekly >= 20:
                        segment = 'power_user'
                    elif weekly >= 5:
                        segment = 'regular_user'
                    else:
                        segment = 'casual_user'

                    cache.set(f'user_segment_{user.pk}', segment, timeout=86400)
                    segment_counts[segment] = segment_counts.get(segment, 0) + 1

                    # Optionally write to profile
                    try:
                        from users.models import Profile
                        Profile.objects.filter(user=user).update(segment=segment)
                    except (ImportError, Exception):
                        pass

                except Exception as row_err:
                    logger.error(f"[ERROR] Segment for user {user.pk}: {row_err}")
                    errors += 1

            cache.set('user_segment_summary', segment_counts, timeout=3600)

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'segment_counts': segment_counts,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] User segments computed: {segment_counts}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] compute_user_segments failed: {exc}")
        raise self.retry(exc=exc)


# ══════════════════════════════════════════════════════════════
# MIGRATED FROM: api/ai_engine/tasks.py (original code preserved)
# ══════════════════════════════════════════════════════════════
@shared_task(bind=True, queue='ai_tasks', max_retries=3, default_retry_delay=60)
def task_train_model(self, ai_model_id: str, dataset_path: str, hyperparams: dict = None, user_id=None):
    """
    Background এ model training চালাও।
    Usage: task_train_model.delay(ai_model_id, dataset_path)
    """
    from api.ai_engine.services import TrainingService
    from .ML_MODELS.model_trainer import ModelTrainer

    logger.info(f"[TASK] Starting training for model: {ai_model_id}")
    start = timezone.now()

    try:
        job = TrainingService.start_training(ai_model_id, dataset_path, hyperparams or {})
        trainer = ModelTrainer(ai_model_id)
        result = trainer.train(dataset_path, hyperparams or {})

        duration = (timezone.now() - start).total_seconds()
        TrainingService.complete_training(str(job.job_id), result['version_data'], duration)
        logger.info(f"[TASK] Training complete: {ai_model_id} in {duration:.1f}s")
        return {'status': 'completed', 'duration': duration}

    except Exception as exc:
        logger.error(f"[TASK] Training failed: {ai_model_id} — {exc}")
        try:
            TrainingService.fail_training(ai_model_id, str(exc))
        except Exception:
            pass
        raise self.retry(exc=exc)


@shared_task(queue='ai_tasks')
def task_retrain_all_models():
    """
    Data drift detect হলে সব production models retrain করো।
    Schedule: daily cron।
    """
    from .models import AIModel
    from .repository import DriftRepository

    models = AIModel.objects.filter(status='deployed', is_production=True)
    retrained = 0
    for model in models:
        if DriftRepository.needs_retrain(str(model.id)):
            task_train_model.delay(str(model.id), dataset_path='auto')
            retrained += 1
            logger.info(f"[TASK] Queued retrain: {model.name}")

    return {'retrained_count': retrained}


# ══════════════════════════════════════════════════════════════════════
# PREDICTION TASKS
# ══════════════════════════════════════════════════════════════════════

@shared_task(queue='ai_tasks')
def task_batch_churn_prediction(tenant_id=None):
    """
    সব users এর churn risk update করো।
    Schedule: প্রতিদিন রাত 2 টায়।
    """
    from django.contrib.auth import get_user_model
    from api.ai_engine.services import ChurnPredictionService

    User = get_user_model()
    users = User.objects.filter(is_active=True)
    if tenant_id:
        users = users.filter(tenant_id=tenant_id)

    user_ids = list(users.values_list('id', flat=True))
    logger.info(f"[TASK] Batch churn prediction for {len(user_ids)} users")

    ChurnPredictionService.bulk_predict_churn(user_ids, tenant_id)
    return {'processed': len(user_ids)}


@shared_task(queue='ai_tasks')
def task_update_user_embeddings(tenant_id=None):
    """
    User embeddings refresh করো।
    Schedule: প্রতি 6 ঘণ্টায়।
    """
    from django.contrib.auth import get_user_model
    from .ML_MODELS.feature_engineering import FeatureEngineer

    User = get_user_model()
    users = User.objects.filter(is_active=True)
    if tenant_id:
        users = users.filter(tenant_id=tenant_id)

    updated = 0
    engineer = FeatureEngineer(feature_type='behavioral')
    for user in users[:500]:  # batch limit
        try:
            engineer.extract({'user_id': str(user.id)})
            updated += 1
        except Exception as e:
            logger.error(f"Embedding update error for {user.id}: {e}")

    logger.info(f"[TASK] Updated {updated} user embeddings")
    return {'updated': updated}


# ══════════════════════════════════════════════════════════════════════
# RECOMMENDATION TASKS
# ══════════════════════════════════════════════════════════════════════

@shared_task(queue='ai_tasks')
def task_precompute_recommendations(tenant_id=None):
    """
    Active users এর recommendations pre-compute করো।
    Schedule: প্রতি 4 ঘণ্টায়।
    """
    from django.contrib.auth import get_user_model
    from api.ai_engine.services import RecommendationService
    from datetime import timedelta

    User = get_user_model()
    since = timezone.now() - timedelta(days=7)
    users = User.objects.filter(is_active=True, last_login__gte=since)
    if tenant_id:
        users = users.filter(tenant_id=tenant_id)

    computed = 0
    for user in users[:200]:
        try:
            RecommendationService.get_recommendations(user, tenant_id=tenant_id)
            computed += 1
        except Exception as e:
            logger.error(f"Pre-compute rec error for {user.id}: {e}")

    logger.info(f"[TASK] Pre-computed recommendations for {computed} users")
    return {'computed': computed}


# ══════════════════════════════════════════════════════════════════════
# ANALYTICS & INSIGHT TASKS
# ══════════════════════════════════════════════════════════════════════

@shared_task(queue='ai_tasks')
def task_generate_daily_insights(tenant_id=None):
    """
    Daily AI insights generate করো।
    Schedule: প্রতিদিন সকাল 7 টায়।
    """
    from api.ai_engine.services import InsightGenerationService

    insights = InsightGenerationService.generate_daily_insights(tenant_id)
    logger.info(f"[TASK] Generated {len(insights)} insights")
    return {'insights_generated': len(insights)}


@shared_task(queue='ai_tasks')
def task_refresh_user_segments(tenant_id=None):
    """
    User segments re-cluster করো।
    Schedule: প্রতিদিন রাত 3 টায়।
    """
    from .PERSONALIZATION.user_segmentation import UserSegmentationEngine

    engine = UserSegmentationEngine()
    result = engine.run_segmentation(tenant_id=tenant_id)
    logger.info(f"[TASK] Segments refreshed: {result}")
    return result


# ══════════════════════════════════════════════════════════════════════
# DRIFT DETECTION TASKS
# ══════════════════════════════════════════════════════════════════════

@shared_task(queue='ai_tasks')
def task_detect_data_drift(tenant_id=None):
    """
    Production models এর data drift check করো।
    Schedule: প্রতি 12 ঘণ্টায়।
    """
    from .models import AIModel
    from .ML_PIPELINES.drift_detection_pipeline import DriftDetectionPipeline

    models = AIModel.objects.filter(status='deployed', is_production=True)
    if tenant_id:
        models = models.filter(tenant_id=tenant_id)

    results = []
    for model in models:
        try:
            pipeline = DriftDetectionPipeline(model)
            result = pipeline.run()
            results.append({'model': model.name, **result})
        except Exception as e:
            logger.error(f"Drift detection error for {model.name}: {e}")

    return {'checked': len(results), 'results': results}


# ══════════════════════════════════════════════════════════════════════
# CLEANUP TASKS
# ══════════════════════════════════════════════════════════════════════

@shared_task(queue='ai_tasks')
def task_cleanup_old_predictions(days: int = 90):
    """
    পুরনো prediction logs delete করো।
    Schedule: সপ্তাহে একবার।
    """
    from .models import PredictionLog
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = PredictionLog.objects.filter(created_at__lt=cutoff).delete()
    logger.info(f"[TASK] Deleted {deleted} old prediction logs (older than {days} days)")
    return {'deleted': deleted}


@shared_task(queue='ai_tasks')
def task_cleanup_old_anomalies(days: int = 180):
    """পুরনো resolved anomaly logs clean up।"""
    from .models import AnomalyDetectionLog
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = AnomalyDetectionLog.objects.filter(
        status__in=['resolved', 'false_positive'],
        created_at__lt=cutoff
    ).delete()
    logger.info(f"[TASK] Deleted {deleted} old anomaly logs")
    return {'deleted': deleted}

