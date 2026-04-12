# Publisher Guide

## Getting Started as a Publisher

### Registration
```bash
POST /api/publisher-tools/publishers/
{
    "display_name": "My Media Company",
    "business_type": "company",
    "contact_email": "contact@mymedia.com",
    "country": "Bangladesh",
    "agree_to_terms": true
}
```

### Publisher Tiers

| Tier | Revenue Share | Min Payout | Features |
|------|--------------|------------|---------|
| Standard | 70% | $100 | Basic analytics, 5 sites |
| Premium | 75% | $50 | Advanced analytics, 20 sites, header bidding |
| Enterprise | 80%+ | $25 | Custom terms, unlimited sites, dedicated manager |

### Publisher Status Flow
- `pending` → Registration submitted
- `under_review` → Admin reviewing application
- `active` → Approved, can monetize
- `suspended` → Temporarily disabled
- `banned` → Permanent termination

### KYC Verification
KYC is required for:
- Payouts above $500/month
- Premium tier access
- API access with elevated limits

Required documents (Bangladesh):
- **Individual**: National ID card (front + back) + selfie
- **Business**: Trade license + TIN certificate + NID of owner

### Revenue Share Calculation
```
Gross Revenue × Revenue Share % = Publisher Revenue
Publisher Revenue - IVT Deduction - Processing Fee - Tax = Net Payable
```

### Dashboard Metrics
- **eCPM**: Earnings per 1,000 impressions
- **Fill Rate**: % of ad requests that resulted in an impression
- **CTR**: Click-through rate (clicks / impressions × 100)
- **RPM**: Revenue per 1,000 pageviews
- **IVT Rate**: Invalid traffic percentage (lower is better)

### Payout Process
1. Earnings are estimated daily
2. Confirmed at month end
3. Invoice generated on the 2nd
4. Payment processed on the 15th
5. Funds arrive within 3-5 business days

### Support
- Email: publisher-support@publishertools.io
- Dashboard: publishertools.io/publisher/support
- Response time: Standard 48h, Premium 24h, Enterprise 4h
