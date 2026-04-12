# AI Engine — Deployment Guide

## 1. Django Settings

```python
# settings.py

INSTALLED_APPS = [
    ...
    'api.ai_engine',
]

AI_ENGINE = {
    'DEFAULT_MODEL_BACKEND': 'xgboost',
    'MODEL_STORAGE_PATH': '/var/ai_models/',
    'ENABLE_GPU': False,
    'MAX_PREDICTION_BATCH': 256,
    'OPENAI_API_KEY': env('OPENAI_API_KEY', default=''),
    'ANTHROPIC_API_KEY': env('ANTHROPIC_API_KEY', default=''),
    'MLFLOW_TRACKING_URI': env('MLFLOW_URI', default=''),
    'FEATURE_STORE_BACKEND': 'django',
    'ENABLE_REAL_TIME_PREDICTION': True,
    'ENABLE_ASYNC_TRAINING': True,
    'CELERY_QUEUE': 'ai_tasks',
}

# Cache (Redis recommended)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379/0'),
    }
}
```

## 2. URL Registration

```python
# config/urls.py
urlpatterns = [
    ...
    path('api/ai-engine/', include('api.ai_engine.urls')),
]
```

## 3. Migrations

```bash
python manage.py makemigrations ai_engine
python manage.py migrate
```

## 4. Celery Tasks (Schedule)

```python
# celery_beat_schedule in settings.py
CELERY_BEAT_SCHEDULE = {
    'batch-churn-prediction': {
        'task': 'api.ai_engine.tasks.task_batch_churn_prediction',
        'schedule': crontab(hour=2, minute=0),
    },
    'daily-insights': {
        'task': 'api.ai_engine.tasks.task_generate_daily_insights',
        'schedule': crontab(hour=7, minute=0),
    },
    'refresh-segments': {
        'task': 'api.ai_engine.tasks.task_refresh_user_segments',
        'schedule': crontab(hour=3, minute=0),
    },
    'precompute-recommendations': {
        'task': 'api.ai_engine.tasks.task_precompute_recommendations',
        'schedule': crontab(minute=0, hour='*/4'),
    },
    'detect-drift': {
        'task': 'api.ai_engine.tasks.task_detect_data_drift',
        'schedule': crontab(minute=0, hour='*/12'),
    },
    'cleanup-predictions': {
        'task': 'api.ai_engine.tasks.task_cleanup_old_predictions',
        'schedule': crontab(day_of_week=0, hour=4),
    },
}
```

## 5. Middleware (Optional)

```python
MIDDLEWARE = [
    ...
    'api.ai_engine.middleware.AIEngineLoggingMiddleware',
    'api.ai_engine.middleware.FraudCheckMiddleware',
]
```

## 6. Fraud Middleware Protected Paths

```python
# middleware.py PROTECTED_PATHS এ add করো
PROTECTED_PATHS = [
    '/api/payment/',
    '/api/withdrawal/',
    '/api/payout/',
]
```

## 7. Health Check

```bash
python -m api.ai_engine.SCRIPTS.health_check
```

## 8. Benchmark

```bash
python -m api.ai_engine.SCRIPTS.benchmark
```

---

# AI Engine — Best Practices

## Model Development

1. **Version সব models** — `ModelVersion` এ সব training run track করো
2. **Evaluate before deploy** — F1 >= 0.70, AUC >= 0.75 না হলে deploy করো না
3. **Monitor drift** — প্রতিদিন `task_detect_data_drift` চালাও
4. **A/B test new models** — direct replace না করে A/B test করো

## Prediction

1. **Cache করো** — same user/entity এর repeated predictions cache করো
2. **Fallback রাখো** — ML model fail করলে rule-based fallback use করো
3. **Log সব predictions** — feedback loop এর জন্য `PredictionLog` দরকার
4. **Batch prefer করো** — single loop এর পরিবর্তে batch prediction use করো

## Feature Engineering

1. **Feature freshness** — features 24 ঘণ্টার বেশি পুরনো হলে refresh করো
2. **Normalize করো** — সব numerical features 0-1 range এ normalize করো
3. **Missing values handle করো** — None/NaN এর জন্য default values দাও

## Security

1. **Fraud check সব payment endpoints এ** — FraudCheckMiddleware use করো
2. **Rate limit করো** — AI endpoints এ rate limiting রাখো
3. **Anomaly alerts** — Critical anomaly এ immediate notification পাঠাও

## Performance

1. **Model in-memory cache** — frequent models RAM এ cache করো
2. **Async training** — training কখনো synchronous করো না
3. **DB index** — `tenant`, `prediction_type`, `created_at` সব index করা আছে
