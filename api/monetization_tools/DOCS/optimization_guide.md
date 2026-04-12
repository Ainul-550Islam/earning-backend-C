# Ad Optimization Guide

## Overview

monetization_tools includes built-in optimization engines for
maximizing ad revenue through yield optimization, A/B testing,
geo/device targeting, and waterfall management.

---

## 1. Waterfall Optimization

### Auto-Rerank by eCPM
```bash
python SCRIPTS/optimize_waterfall.py --action rerank --days 7
```

This script:
1. Calculates avg eCPM per network over last 7 days
2. Re-orders waterfall so highest-eCPM networks are tried first
3. Updates WaterfallConfig.priority for all ad units

### Auto Floor Price Setting
```bash
python SCRIPTS/optimize_waterfall.py --action floors --days 14
```

Sets floor eCPM at the p25 (25th percentile) of recent eCPM,
so we only serve ads that beat historical minimums.

### View Current Waterfall
```bash
python SCRIPTS/optimize_waterfall.py --action report --unit 42
```

---

## 2. Bid Optimization

### Floor Price by Country
Configure country-tier floor prices:
```python
from api.monetization_tools.OPTIMIZATION_ENGINES.floor_price_manager import FloorPriceManager

FloorPriceManager.set_floor(network_id=1, ecpm=Decimal("3.50"),
                             country="US", ad_format="rewarded_video")
FloorPriceManager.set_floor(network_id=1, ecpm=Decimal("0.30"),
                             country="BD", ad_format="banner")
```

### Header Bidding Auction
```python
from api.monetization_tools.OPTIMIZATION_ENGINES.header_bidding import HeaderBiddingEngine

engine = HeaderBiddingEngine(timeout_ms=500)
bids   = engine.collect_bids(ad_unit_id=42, floor=Decimal("1.0"))
winner = engine.auction(bids, floor=Decimal("1.0"))
```

### Time-of-Day Bid Adjustment
```python
from api.monetization_tools.OPTIMIZATION_ENGINES.time_optimizer import TimeOptimizer

multiplier = TimeOptimizer.multiplier(hour=20)  # 8PM = 1.8x
adjusted   = TimeOptimizer.adjust_bid(Decimal("2.00"), hour=20)
# = 3.6000
```

### Geographic Bid Adjustment
```python
from api.monetization_tools.OPTIMIZATION_ENGINES.geo_optimizer import GeoOptimizer

adjusted = GeoOptimizer.adjust_bid(Decimal("1.00"), country="US")
# = 3.0000 (Tier 1 multiplier)
```

---

## 3. A/B Testing

### Create and Run a Test
```python
from api.monetization_tools.A_B_TESTING.test_creator import ABTestCreator

test = ABTestCreator.create(
    name="Rewarded vs Interstitial",
    variants=[
        {"name": "rewarded", "weight": 50, "ad_unit_id": 42},
        {"name": "interstitial", "weight": 50, "ad_unit_id": 43},
    ],
    traffic_split=80,      # 80% of users included
    winner_criteria="ctr",
    min_sample_size=1000,
    duration_days=14,
)
ABTestCreator.start(test.id)
```

### Assign User to Variant
```python
from api.monetization_tools.A_B_TESTING.test_allocator import TestAllocator

variant, created = TestAllocator.assign(test, user)
# variant = "rewarded" or "interstitial" (deterministic per user)
```

### Check Statistical Significance
```python
from api.monetization_tools.A_B_TESTING.hypothesis_tester import HypothesisTester

result = HypothesisTester.is_significant(
    p1=0.12,  n1=5000,   # variant A: 12% CVR, 5000 assigned
    p2=0.15,  n2=5000,   # variant B: 15% CVR, 5000 assigned
    alpha=0.05,
)
# {"significant": True, "p_value": 0.0012, "winner": "B"}
```

---

## 4. Creative Optimization

### Dynamic Creative Optimization (DCO)
```python
from api.monetization_tools.AD_CREATIVES.dynamic_creative import DynamicCreativeOptimizer

best_creative = DynamicCreativeOptimizer.select(
    ad_unit_id=42,
    user=request.user,
    context={"country": "BD", "device": "mobile"},
)
```

### Seasonal Creative Switching
```python
from api.monetization_tools.AD_CREATIVES.seasonal_creative import SeasonalCreativeManager

season      = SeasonalCreativeManager.active_season()  # e.g. "eid_ul_fitr"
multiplier  = SeasonalCreativeManager.get_multiplier()  # e.g. 1.8
config      = SeasonalCreativeManager.apply_seasonal_theme(creative_config)
```

---

## 5. User Monetization Optimization

### User Value Tier
```python
from api.monetization_tools.USER_MONETIZATION.user_value_tier import UserValueTier

tier = UserValueTier.classify(Decimal("15000"))
# {"tier": "whale", "multiplier": 2.0}

multiplier = UserValueTier.reward_multiplier(user)
```

### Churn Prevention
```python
from api.monetization_tools.USER_MONETIZATION.user_retention_engine import UserRetentionEngine

at_risk = UserRetentionEngine.at_risk_users(inactive_days=7)
score   = UserRetentionEngine.churn_risk_score(user)
UserRetentionEngine.apply_win_back_bonus(user, Decimal("100"), reason="win_back")
```

---

## 6. Yield Analysis

### Check Revenue Uplift from Floor Change
```python
from api.monetization_tools.OPTIMIZATION_ENGINES.yield_optimizer import YieldOptimizer

uplift = YieldOptimizer.revenue_uplift(
    old_floor=Decimal("0.50"),
    new_floor=Decimal("1.00"),
    avg_ecpm=Decimal("2.50"),
    impressions=100000,
)
```

### Find Unfilled Inventory Value
```python
from api.monetization_tools.OPTIMIZATION_ENGINES.inventory_optimizer import InventoryOptimizer

missed_rev = InventoryOptimizer.unfilled_revenue_estimate(ad_unit_id=42, days=7)
# Revenue we're losing from unfilled requests
```
