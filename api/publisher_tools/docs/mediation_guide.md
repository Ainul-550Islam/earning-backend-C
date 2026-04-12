# Mediation Guide

## What is Mediation?
Mediation connects multiple ad networks to compete for your inventory, maximizing eCPM.

## Mediation Types

### 1. Waterfall (Traditional)
Networks are called in priority order until one fills.
- Predictable fill order
- Simple to set up
- Lower eCPM than header bidding

### 2. Header Bidding (Prebid)
All networks bid simultaneously, highest bid wins.
- Higher eCPM (+20-40% vs waterfall)
- More complex setup
- Requires Prebid.js integration

### 3. Hybrid (Recommended)
Header bidding for premium demand, waterfall as fallback.
- Best of both worlds
- Maximum revenue

## Setting Up Waterfall

```bash
POST /api/publisher-tools/mediation-groups/
{
    "ad_unit_id": "UNIT000001",
    "name": "Homepage Banner Mediation",
    "mediation_type": "waterfall",
    "auto_optimize": true
}
```

## Adding Networks to Waterfall

```bash
POST /api/publisher-tools/waterfall-items/
{
    "mediation_group": "GROUP_ID",
    "network": "NETWORK_ID",
    "name": "AdMob Tier 1",
    "priority": 1,
    "floor_ecpm": "1.50",
    "bidding_type": "dynamic"
}
```

## Waterfall Priority Rules
1. Higher eCPM networks should be higher priority
2. Lower latency = better user experience
3. Minimum 3 networks recommended
4. Always have a fallback (house ad or passback)

## Auto-Optimization
When enabled, the system automatically:
- Reorders waterfall based on last 7 days eCPM
- Pauses consistently failing networks
- Suggests floor price adjustments

```bash
POST /api/publisher-tools/mediation-groups/{id}/optimize/
```

## Waterfall Performance Metrics

| Metric | Good | Needs Attention |
|--------|------|----------------|
| Fill Rate | > 80% | < 50% |
| eCPM | Category dependent | < $0.50 |
| Latency | < 600ms | > 1500ms |
| Timeout Rate | < 5% | > 15% |

## Header Bidding Setup (Prebid.js)

```html
<script>
var pbjs = pbjs || {};
pbjs.que = pbjs.que || [];

pbjs.que.push(function() {
    pbjs.addAdUnits([{
        code: 'UNIT000001',
        mediaTypes: { banner: { sizes: [[728, 90]] } },
        bids: [{
            bidder: 'appnexus',
            params: { placementId: '13144370' }
        }, {
            bidder: 'rubicon',
            params: { accountId: '1001', siteId: '2001', zoneId: '3001' }
        }]
    }]);
    pbjs.requestBids({ bidsBackHandler: sendAdServerRequest });
});
</script>
```

## Troubleshooting Low Fill Rate
1. Check floor prices (may be too high)
2. Verify network credentials
3. Check geo targeting rules
4. Review device targeting
5. Add more networks to waterfall
6. Reduce bid timeout (if high latency)
