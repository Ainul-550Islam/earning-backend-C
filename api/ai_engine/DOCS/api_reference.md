# AI Engine — API Reference

## Base URL
```
/api/ai-engine/
```

## Authentication
সব endpoint এ `Authorization: Bearer <token>` header দরকার।

---

## 1. AI Models

### List Models
```
GET /api/ai-engine/models/
```

### Create Model
```
POST /api/ai-engine/models/
{
  "name": "Fraud Detector v2",
  "algorithm": "xgboost",
  "task_type": "classification",
  "hyperparameters": {"n_estimators": 200, "max_depth": 6},
  "target_column": "is_fraud"
}
```

### Deploy Model
```
POST /api/ai-engine/models/{id}/deploy/
```

### Model Summary
```
GET /api/ai-engine/models/{id}/summary/
```

---

## 2. Predictions

### Single Prediction
```
POST /api/ai-engine/predict/
{
  "prediction_type": "fraud",
  "input_data": {
    "is_vpn": false,
    "device_count": 1,
    "account_age_days": 30
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "fraud_score": 0.12,
    "is_fraud": false,
    "confidence": 0.88,
    "request_id": "uuid",
    "inference_ms": 12.5
  }
}
```

### Fraud Score
```
POST /api/ai-engine/predict/fraud/
{
  "action_type": "click",
  "metadata": {
    "is_vpn": false,
    "ip_address": "1.2.3.4",
    "device_count": 1
  }
}
```

### Churn Prediction
```
POST /api/ai-engine/predict/churn/
{
  "user_id": "uuid"
}
```

### Batch Prediction
```
POST /api/ai-engine/predict/batch/
{
  "prediction_type": "churn",
  "items": [
    {"user_id": "1", "days_since_login": 15},
    {"user_id": "2", "days_since_login": 45}
  ]
}
```

---

## 3. Recommendations

### Get Recommendations
```
POST /api/ai-engine/recommend/
{
  "engine": "hybrid",
  "item_type": "offer",
  "count": 10,
  "context": {"country": "BD", "device": "mobile"}
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "items": [
      {"item_id": "uuid", "item_type": "offer", "score": 0.92, "engine": "hybrid"}
    ],
    "count": 10,
    "engine": "hybrid",
    "request_id": "uuid"
  }
}
```

### Track Click
```
POST /api/ai-engine/recommend/click/
{"request_id": "uuid", "item_id": "uuid"}
```

### Track Conversion
```
POST /api/ai-engine/recommend/convert/
{"request_id": "uuid", "item_id": "uuid"}
```

---

## 4. NLP Analysis

### Analyze Text
```
POST /api/ai-engine/nlp/
{
  "text": "This app is amazing! Love it.",
  "analysis_type": "sentiment"
}
```

### Sentiment Only
```
POST /api/ai-engine/nlp/sentiment/
{"text": "Your text here"}
```

### Spam Detection
```
POST /api/ai-engine/nlp/spam/
{"text": "CLICK NOW! WIN FREE MONEY!!!"}
```

### Intent Classification
```
POST /api/ai-engine/nlp/intent/
{"text": "I need help with my withdrawal"}
```

---

## 5. Anomaly Detection

### List Anomalies
```
GET /api/ai-engine/anomalies/?status=open&severity=critical
```

### Resolve Anomaly
```
POST /api/ai-engine/anomalies/{id}/resolve/
{"notes": "Verified — false positive"}
```

### Manual Detection Trigger
```
POST /api/ai-engine/anomalies/detect/
{
  "anomaly_type": "fraud_click",
  "entity_id": "user-uuid",
  "data": {"clicks_per_hour": 500, "is_vpn": true}
}
```

---

## 6. Churn Risk

### High Risk Users
```
GET /api/ai-engine/churn/high_risk/
```

### Predict My Churn
```
POST /api/ai-engine/churn/predict_me/
```

---

## 7. Insights

### List Active Insights
```
GET /api/ai-engine/insights/
```

### Dismiss Insight
```
POST /api/ai-engine/insights/{id}/dismiss/
```

### Force Generate
```
POST /api/ai-engine/insights/generate/
```

---

## 8. Personalization

### My Profile
```
GET /api/ai-engine/personalization/me/
```

### Refresh Profile
```
POST /api/ai-engine/personalization/refresh/
```

---

## 9. A/B Tests

### Create Experiment
```
POST /api/ai-engine/ab-tests/
{
  "name": "New Recommendation Algorithm",
  "control_traffic": 50,
  "treatment_traffic": 50,
  "target_metric": "conversion_rate"
}
```

### Start Experiment
```
POST /api/ai-engine/ab-tests/{id}/start/
```

---

## 10. Training

### Start Training Job
```
POST /api/ai-engine/training/
{
  "ai_model": "model-uuid",
  "dataset_path": "/data/fraud_dataset.csv",
  "hyperparameters": {"n_estimators": 200}
}
```

---

## Error Responses

```json
{
  "success": false,
  "message": "Error description",
  "errors": {}
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict (training in progress) |
| 422 | Unprocessable (insufficient data) |
| 503 | Model not deployed |
