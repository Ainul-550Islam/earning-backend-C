# Optimization Guide

## Revenue Optimization Framework

### 1. Floor Price Optimization
**Goal**: Set floors at 70-80% of average eCPM

```bash
GET /api/publisher-tools/ad-units/{unit_id}/performance/?period=last_30_days
# Check avg_ecpm

PATCH /api/publisher-tools/ad-units/{unit_id}/
{
    "floor_price": "calculated_optimal_floor"
}
```

**Formula**: `optimal_floor = avg_ecpm × 0.75`

### 2. Waterfall Optimization
Run auto-optimization every 24 hours:
```bash
POST /api/publisher-tools/mediation-groups/{id}/optimize/
```

**Best practices**:
- Keep networks sorted by eCPM (highest first)
- Remove networks with <10% fill rate (after 1000+ requests)
- Move high-latency networks (>800ms) to lower priority

### 3. Ad Refresh Optimization
For sticky/header ads, enable refresh:
```bash
PATCH /api/publisher-tools/placements/{id}/
{
    "refresh_type": "time_based",
    "refresh_interval_seconds": 30
}
```

Expected uplift: +20-30% impressions, +15-20% revenue

### 4. Viewability Optimization
Target 70%+ viewability for display, 50%+ for video.

**Position recommendations by viewability**:
| Position | Avg Viewability | eCPM Multiplier |
|----------|----------------|----------------|
| Above fold | 85% | 1.5x |
| Header | 82% | 1.4x |
| In-content | 75% | 1.3x |
| Sticky bottom | 68% | 1.25x |
| Below fold | 40% | 0.7x |

### 5. Geographic Optimization
Set higher floors for premium geos:

| Country | Suggested Floor Multiple |
|---------|------------------------|
| US | 5x base |
| GB/AU/CA | 4x base |
| DE/FR | 3x base |
| IN/BD | 1x base |

### 6. Time-Based Optimization
eCPM typically peaks:
- **Peak hours**: 6PM-10PM local time (+40-50% eCPM)
- **Best days**: Tuesday-Friday
- **Worst**: Sunday morning, early AM

### 7. A/B Testing
Always test before full rollout:

```bash
POST /api/publisher-tools/ab-tests/
{
    "name": "Floor Price Test",
    "ad_unit_id": "UNIT000001",
    "test_type": "floor_price",
    "variants": [
        {"name": "Control", "is_control": true, "traffic_split": 50, "config": {"floor_price": 0.50}},
        {"name": "Higher Floor", "is_control": false, "traffic_split": 50, "config": {"floor_price": 1.00}}
    ]
}
```

Run for minimum 7 days, minimum 1000 impressions per variant.

### Quick Win Checklist
- [ ] All ad units have floor prices set (>$0)
- [ ] Waterfall has 3+ active networks
- [ ] Sticky placements have refresh enabled
- [ ] Above-fold placements prioritized
- [ ] High-value geo floor prices configured
- [ ] Header bidding enabled (if Premium/Enterprise)
- [ ] IVT rate below 20%
- [ ] All sites have ads.txt verified
