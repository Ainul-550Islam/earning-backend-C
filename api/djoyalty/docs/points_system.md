# Points System Guide

## Overview
Djoyalty এর points system FIFO (First In, First Out) expiry সহ full double-entry ledger maintain করে।

## Earning Points

### Default Earn Rate
```python
DEFAULT_EARN_RATE = 1  # 1 point per 1 BDT spend
TIER_MULTIPLIERS = {
    'bronze': 1.0, 'silver': 1.2, 'gold': 1.5,
    'platinum': 2.0, 'diamond': 3.0,
}
```

### API: Earn Points
```http
POST /api/loyalty/points/earn/
{
  "customer_id": 123,
  "spend_amount": "500.00"
}
Response: { "points_earned": "500.00", "message": "Earned 500.0 points" }
```

### Earn Sources
| Source | Description |
|---|---|
| `purchase` | Standard purchase earn |
| `bonus` | Manual/campaign bonus |
| `referral` | Referral reward |
| `badge` | Badge unlock reward |
| `streak` | Streak milestone reward |
| `challenge` | Challenge completion |
| `partner` | Coalition partner earn |
| `subscription` | Monthly subscription bonus |

## Points Expiry

Points expire after `DEFAULT_POINTS_EXPIRY_DAYS` (default: 365 days).

### Expiry Warning
Customers receive warnings `POINTS_EXPIRY_WARNING_DAYS` (default: 30 days) before expiry.

### Manual Expiry Run
```bash
python manage.py expire_points
python manage.py expire_points --dry-run
python manage.py expire_points --send-warnings
```

## Points Ledger

Every credit/debit is recorded in `PointsLedger` — immutable audit trail.

```python
# Query ledger
from djoyalty.models.points import PointsLedger
entries = PointsLedger.objects.filter(customer=customer).order_by('-created_at')
```

## Audit Tool
```bash
python manage.py recalculate_balances          # Audit only
python manage.py recalculate_balances --fix    # Apply corrections
```

## Points Transfer (P2P)
```http
POST /api/loyalty/transfers/transfer/
{
  "from_customer_id": 1,
  "to_customer_id": 2,
  "points": "100",
  "note": "Gift"
}
```

## Cashout (Points → Cash)
```http
POST /api/loyalty/cashout/request/
{
  "customer_id": 1,
  "points_to_redeem": "1000",
  "cashout_method": "bkash",
  "mobile_wallet_id": 5
}
```
Default rate: 100 points = 1 BDT.

## Key Models

| Model | Purpose |
|---|---|
| `LoyaltyPoints` | Current balance wallet |
| `PointsLedger` | Immutable transaction log |
| `PointsExpiry` | Expiry schedule |
| `PointsTransfer` | P2P transfer records |
| `PointsReservation` | Hold before redemption |
| `PointsAdjustment` | Admin adjustments |
| `WalletTransaction` | Complete wallet history |
| `CashoutRequest` | Cash withdrawal requests |
