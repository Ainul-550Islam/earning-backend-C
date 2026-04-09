# Points System — Djoyalty

## Overview
Djoyalty points system হলো loyalty program এর core engine।
Customer purchase করলে points earn করে, সেই points দিয়ে rewards redeem করতে পারে।

## Key Models

### LoyaltyPoints — Real-time balance tracker
| Field | Description |
|---|---|
| `balance` | Current usable balance |
| `lifetime_earned` | সর্বমোট earn (tier calculation এ ব্যবহার) |
| `lifetime_redeemed` | সর্বমোট redeem |
| `lifetime_expired` | মেয়াদ শেষে হারানো points |

### PointsLedger — Immutable audit trail
| Field | Description |
|---|---|
| `txn_type` | `credit` বা `debit` |
| `source` | `purchase`, `bonus`, `referral`, `campaign`, `admin`, `expiry`, `redemption`, `transfer` |
| `points` | Amount |
| `balance_after` | Balance after this entry |
| `expires_at` | Null = never expires |

### PointsRate (per tenant)
| Field | Default |
|---|---|
| `earn_rate` | 1.0 (1 point per 1 currency unit) |
| `point_value` | 0.01 (1 point = 0.01 currency) |
| `rounding` | floor |

## Earn Flow
```
Purchase → PointsEngine.process_earn()
         → earn_rate × spend_amount × tier_multiplier
         → LoyaltyPoints.credit()
         → PointsLedger (credit entry created)
         → PointsExpiry scheduled
         → EarnTransaction logged
         → Signal: tier eval + badge check + milestone check
```

## Default Tier Multipliers
| Tier | Multiplier |
|---|---|
| Bronze | 1.0× |
| Silver | 1.25× |
| Gold | 1.5× |
| Platinum | 2.0× |
| Diamond | 3.0× |

## Points Expiry
- Default validity: **365 days** from earn date
- Warning sent: **30 days** before expiry
- Daily cron: `expire_points_task`
- Management command: `python manage.py expire_points --send-warnings`

## Service Usage Examples

### Earn Points
```python
from djoyalty.services.points.PointsEngine import PointsEngine
points = PointsEngine.process_earn(customer, Decimal('100'))
```

### Manual Adjustment (Admin)
```python
from djoyalty.services.points.PointsAdjustmentService import PointsAdjustmentService
PointsAdjustmentService.adjust(customer, Decimal('100'), reason='Compensation', adjusted_by='admin')
```

### P2P Transfer
```python
from djoyalty.services.points.PointsTransferService import PointsTransferService
PointsTransferService.transfer(from_customer, to_customer, Decimal('200'))
```

### Checkout Hold / Release
```python
from djoyalty.services.points.PointsReservationService import PointsReservationService
PointsReservationService.reserve(customer, Decimal('500'), reference='ORDER-123')
PointsReservationService.confirm('ORDER-123')   # or .release('ORDER-123')
```

## API Endpoints
| Method | URL | Description |
|---|---|---|
| GET | `/api/djoyalty/points/balance/?customer_id=1` | Balance check |
| POST | `/api/djoyalty/points/earn/` | Earn points |
| POST | `/api/djoyalty/points/adjust/` | Admin adjustment |
| POST | `/api/djoyalty/transfers/transfer/` | P2P transfer |
| GET | `/api/djoyalty/ledger/?customer=1` | Ledger history |
| GET | `/api/djoyalty/conversions/calculate/?points=100` | Convert to currency |

## Fraud Limits
- Max daily redemption: 5,000 points
- Rapid transaction: 10 txns in 5 minutes → auto-flag
- Max single earn: 10,000 points
