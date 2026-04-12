# Offer Rotation Guide

## 4 Rotation Methods

### 1. Weighted Random (default)
Traffic split by weight. Offer A weight=700, Offer B weight=300 → A gets 70%, B gets 30%.
```json
{"rotation_method": "weighted"}
```

### 2. EPC Optimized
Automatically shifts traffic to higher-earning offers based on historical EPC per geo+device.
Updated every 30 minutes by Celery task.
```json
{"rotation_method": "epc_optimized", "rotation": {"auto_optimize_epc": true}}
```

### 3. ML Thompson Sampling (World #1 Unique Feature)
Bayesian bandit algorithm. Learns in real-time which offers convert best.
Balances exploration (trying new offers) vs exploitation (using best known offer).
```json
{"rotation_method": "epc_optimized", "rotation": {"auto_optimize_epc": true, "ml_enabled": true}}
```

### 4. Priority Based
Always send traffic to highest-priority offer. Falls to next if capped.
```json
{"rotation_method": "priority"}
```

### 5. Round Robin
Rotate evenly through all offers in sequence.
```json
{"rotation_method": "round_robin"}
```

---

## Daily Caps
```json
{
  "offers": [
    {"offer_id": 101, "weight": 600, "cap_per_day": 1000},
    {"offer_id": 102, "weight": 400, "cap_per_day": 500}
  ]
}
```
When an offer reaches its daily cap, it's excluded from rotation.
If ALL offers are capped, traffic goes to fallback URL.
Caps reset at midnight UTC (Celery task).

---

## Offer Blacklist
Prevent specific offers from appearing on your SmartLink:
```http
POST /api/smartlink/smartlinks/{id}/blacklist/
{"offer": 456, "reason": "Poor quality landing page"}
```
