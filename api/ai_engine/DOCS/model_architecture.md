# AI Engine — Model Architecture

## System Overview

```
Request → ViewSet (routes.py)
           ↓
       Service Layer (services.py)
           ↓
     Repository (repository.py)  ←→  Cache (cache.py)
           ↓
       Database (models.py)

     ML Pipeline:
     Feature Engineering → Model Inference → Prediction Log
```

## Module Structure

```
api/ai_engine/
├── Core
│   ├── models.py           → 21 DB models
│   ├── schemas.py          → DRF serializers
│   ├── routes.py           → ViewSets (14)
│   ├── services.py         → Business logic
│   ├── repository.py       → DB access layer
│   ├── cache.py            → Redis cache layer
│   ├── utils.py            → Helpers
│   ├── enums.py            → TextChoices
│   ├── constants.py        → Config constants
│   └── tasks.py            → Celery async tasks
│
├── ML_MODELS/              → Training & inference
├── PREDICTION_ENGINES/     → Fraud, Churn, LTV, etc.
├── RECOMMENDATION_ENGINES/ → CF, Content-Based, Hybrid
├── PERSONALIZATION/        → Segmentation, Profiling
├── NLP_ENGINES/            → Sentiment, Spam, Intent
├── CV_ENGINES/             → OCR, Face, Quality
├── ANOMALY_DETECTION/      → Real-time anomaly
├── ANALYTICS_INSIGHTS/     → Trend, Cohort, Attribution
├── OPTIMIZATION_ENGINES/   → A/B test, Pricing, Bidding
├── AUTOMATION_AGENTS/      → Intelligent agents
├── INTEGRATIONS/           → OpenAI, Anthropic, XGBoost
├── ML_PIPELINES/           → End-to-end pipelines
├── MODEL_STORAGE/          → Registry, serialization
└── TESTING_EVALUATION/     → Model tests, fairness
```

## Data Flow

### Prediction Request
1. API receives `POST /api/ai-engine/predict/`
2. `PredictionViewSet.create()` → validates input
3. `PredictionService.predict()` → business logic
4. `AIModelRepository.get_for_task()` → finds deployed model
5. `FeatureEngineer.extract()` → builds ML features
6. `RealTimePredictor.predict()` → runs inference
7. `PredictionLogRepository.log_prediction()` → saves to DB
8. Response returned with `request_id`

### Recommendation Flow
1. `POST /api/ai-engine/recommend/`
2. Cache check → if hit, return cached
3. `HybridRecommender.recommend()` → CF + CB + Popularity
4. `RecommendationRepository.save()` → log to DB
5. Cache result
6. Return top-N items

### Training Flow
1. `POST /api/ai-engine/training/`
2. `TrainingService.start_training()` → creates job
3. Celery task: `task_train_model.delay()`
4. `ModelTrainer.train()` → data → features → fit → evaluate
5. `TrainingService.complete_training()` → saves version
6. Model deployed via `ModelManagementService.deploy_model()`
