# Fraud Prevention Guide

## Understanding Invalid Traffic (IVT)

### IVT Types
| Type | Description | Detection Method |
|------|-------------|-----------------|
| Bot Traffic | Automated scripts/bots | User agent analysis |
| Click Fraud | Fake/inflated clicks | Velocity checks |
| Impression Fraud | Hidden/stacked ads | Viewability monitoring |
| Device Farm | Farm of devices clicking | Device fingerprinting |
| VPN/Proxy | Masked IP origins | IP reputation |
| SDK Spoofing | Fake SDK signals | Certificate pinning |

### IVT Thresholds
- **Low** (0-10%): Normal, no action needed
- **Medium** (10-20%): Monitor closely
- **High** (20-40%): Warning issued, revenue deductions may apply
- **Critical** (40%+): Account suspension risk

## Monitoring Your IVT Rate

```bash
GET /api/publisher-tools/traffic-safety-logs/summary/?period=last_30_days
```

Response includes:
- `ivt_rate_pct`: Overall IVT percentage
- `by_type`: Breakdown by fraud type
- `revenue_at_risk`: Potential revenue deductions

## Fraud Detection Dashboard

### Daily Check
1. Review IVT rate — should be <20%
2. Check top source IPs for anomalies
3. Monitor click patterns by country
4. Review high fraud-score events

### Weekly Review
1. Compare IVT rates week-over-week
2. Identify problematic traffic sources
3. Block high-risk IPs
4. Review deduction amounts

## Taking Action on Fraud

### Block Suspicious IPs
```bash
POST /api/publisher-tools/fraud/ip-block/
{
    "ip_address": "1.2.3.4",
    "reason": "High click fraud velocity",
    "hours": 48
}
```

### Mark False Positives
```bash
POST /api/publisher-tools/traffic-safety-logs/{id}/mark_false_positive/
{
    "is_false_positive": true,
    "notes": "Legitimate automated test traffic from our own crawler"
}
```

### Dispute Revenue Deductions
If you believe a deduction is incorrect:
1. Go to Invoices → Dispute
2. Provide evidence (server logs, GA data, traffic source reports)
3. Submit within 5 business days
4. Resolution within 10 business days

## Prevention Best Practices

### For Websites
- Enable ads.txt and keep it updated
- Use a CDN to filter bot traffic
- Implement Google reCAPTCHA on forms
- Monitor Google Analytics for anomalies
- Use verified traffic sources only

### For Mobile Apps
- Enable SDK integrity checks
- Use Play Protect / App Attest (iOS)
- Implement certificate pinning
- Monitor crash rates (high crashes = emulators)
- Enable server-side postback verification for rewarded ads

### Traffic Sources to Avoid
- Traffic exchange networks
- Paid-to-click (PTC) sites
- Social media bot services
- Pop-under networks
- Incentivized traffic (for non-rewarded units)

## Automated Protections
Publisher Tools automatically:
- Blocks IPs with fraud score >80
- Flags click velocity anomalies (>10 clicks/minute)
- Detects headless browsers and emulators
- Validates conversion postbacks (server-side)
- Checks geo consistency
