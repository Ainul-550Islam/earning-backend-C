# AI Engine — Training Guide

## Quick Start: Train Your First Model

### 1. Register a Model
```python
from api.ai_engine.services import ModelManagementService

model = ModelManagementService.register_model({
    'name': 'Fraud Detector v1',
    'algorithm': 'xgboost',
    'task_type': 'classification',
    'hyperparameters': {
        'n_estimators': 200,
        'max_depth': 6,
        'learning_rate': 0.1,
    },
    'target_column': 'is_fraud',
})
```

### 2. Start Training (Sync)
```python
from api.ai_engine.ML_PIPELINES.training_pipeline import TrainingPipeline

pipeline = TrainingPipeline(str(model.id))
result = pipeline.run('/data/fraud_training.csv')
print(f"F1 Score: {result['version_data']['f1_score']}")
```

### 3. Start Training (Async via Celery)
```python
from api.ai_engine.tasks import task_train_model

task_train_model.delay(
    ai_model_id=str(model.id),
    dataset_path='/data/fraud_training.csv',
    hyperparams={'n_estimators': 200}
)
```

### 4. Deploy
```python
ModelManagementService.deploy_model(str(model.id))
```

## Training Parameters Reference

### XGBoost
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| n_estimators | 100 | 50-1000 | Number of trees |
| max_depth | 6 | 3-10 | Max tree depth |
| learning_rate | 0.1 | 0.01-0.3 | Step size |
| subsample | 0.8 | 0.5-1.0 | Row sampling |
| colsample_bytree | 0.8 | 0.5-1.0 | Column sampling |

### LightGBM
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| n_estimators | 100 | 50-1000 | Number of trees |
| num_leaves | 31 | 15-255 | Max leaf nodes |
| learning_rate | 0.05 | 0.01-0.2 | Step size |
| min_child_samples | 20 | 5-100 | Min samples in leaf |

## Feature Engineering Reference

### User Features
- `account_age_days` — Account age (0-365)
- `days_since_login` — Inactivity days (0-90)
- `coin_balance` — Current balance (normalized)
- `total_earned` — Cumulative earnings
- `offers_completed` — Number of completed offers
- `referral_count` — Referrals made
- `streak_days` — Current streak length

### Fraud Features
- `is_vpn` — VPN detected (0/1)
- `is_proxy` — Proxy detected (0/1)
- `is_tor` — Tor network (0/1)
- `device_count` — Registered devices (0-10)
- `clicks_per_hour` — Click velocity (0-200)
- `ip_risk_score` — IP risk (0.0-1.0)
- `same_ip_accounts` — Shared IP accounts (0-20)

---

# AI Engine — Evaluation Metrics

## Classification Metrics
| Metric | Formula | Good Value | Used For |
|--------|---------|-----------|---------|
| Accuracy | TP+TN / Total | ≥ 0.80 | Balanced datasets |
| Precision | TP / (TP+FP) | ≥ 0.75 | Fraud detection |
| Recall | TP / (TP+FN) | ≥ 0.70 | Churn prediction |
| F1 Score | 2×P×R / (P+R) | ≥ 0.70 | Overall balance |
| AUC-ROC | Area under ROC | ≥ 0.75 | Ranking quality |

## Regression Metrics
| Metric | Formula | Good Value | Used For |
|--------|---------|-----------|---------|
| MAE | Mean Absolute Error | Lower is better | LTV, Revenue |
| RMSE | Root MSE | Lower is better | Revenue forecast |
| R² | Correlation² | ≥ 0.70 | Fit quality |

## Business Metrics
| Metric | Description | Target |
|--------|-------------|--------|
| Fraud Block Rate | % fraud correctly blocked | ≥ 90% |
| Churn Recall | % churners correctly identified | ≥ 75% |
| Rec CTR | Recommendation click-through | ≥ 8% |
| Rec CVR | Recommendation conversion | ≥ 15% |
| Latency P99 | 99th percentile inference time | ≤ 500ms |

---

# AI Engine — Changelog

## v1.0.0 (2025-01-01)
### Added
- Initial AI Engine release
- 21 Django DB models
- 14 DRF ViewSets
- Fraud Detection Service
- Churn Prediction Service
- Hybrid Recommendation Engine
- NLP: Sentiment, Spam, Intent analysis
- Anomaly Detection System
- Personalization Profiles
- A/B Test Framework
- Celery async tasks (8 tasks)
- Health check scripts
- Full API documentation

### Models
- AIModel + ModelVersion + TrainingJob + ModelMetric
- FeatureStore + UserEmbedding + ItemEmbedding
- PredictionLog + AnomalyDetectionLog + ChurnRiskProfile
- RecommendationResult + UserSegment + ABTestExperiment
- TextAnalysisResult + ImageAnalysisResult + ContentModerationLog
- PersonalizationProfile + InsightModel + DataDriftLog + ExperimentTracking

### Integrations
- OpenAI GPT-4 / Embeddings
- Anthropic Claude
- XGBoost, LightGBM, Scikit-learn
- Hugging Face Transformers
- MLflow Experiment Tracking
- Google Vertex AI
- AWS SageMaker
- KubeFlow Pipelines
