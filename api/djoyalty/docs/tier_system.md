# Tier System Guide

## 5-Tier Structure

| Tier | Min Points | Multiplier | Color |
|---|---|---|---|
| 🥉 Bronze | 0 | 1.0x | #CD7F32 |
| 🥈 Silver | 500 | 1.2x | #C0C0C0 |
| 🥇 Gold | 2,000 | 1.5x | #FFD700 |
| 💎 Platinum | 10,000 | 2.0x | #E5E4E2 |
| 💠 Diamond | 50,000 | 3.0x | #B9F2FF |

## Seed Default Tiers
```bash
python manage.py seed_tiers
python manage.py seed_tiers --with-benefits  # Also add benefits
python manage.py seed_tiers --reset          # Delete and re-seed
```

## Auto Tier Evaluation

Tier is re-evaluated automatically when points are earned (via signal).

### Manual Evaluation
```bash
python manage.py evaluate_tiers
python manage.py evaluate_tiers --customer-id 123
python manage.py evaluate_tiers --dry-run
```

### API
```http
POST /api/loyalty/user-tiers/evaluate/
{ "customer_id": 123 }

GET /api/loyalty/user-tiers/my_tier/?customer_id=123
GET /api/loyalty/user-tiers/progress/?customer_id=123
GET /api/loyalty/user-tiers/history/?customer_id=123
```

## Tier Benefits

Benefits per tier can be configured in admin or seeded:

```python
# Bronze: Welcome Bonus, Birthday Points
# Silver: 1.2x Multiplier, Priority Support, Free Shipping 500+
# Gold: 1.5x, Account Manager, Always Free Shipping, Exclusive Offers
# Platinum: 2x, VIP Events, Personal Shopper, Quarterly Gift
# Diamond: 3x, Concierge Service, Annual Gift, Invitation-only Events
```

## Force Upgrade/Downgrade (Admin)
```http
POST /api/loyalty/user-tiers/force_upgrade/
{ "customer_id": 1, "tier_name": "gold", "reason": "VIP customer" }

POST /api/loyalty/user-tiers/force_downgrade/
{ "customer_id": 1, "tier_name": "silver", "reason": "Policy change" }
```

## Downgrade Protection

By default, customers are protected from downgrade for `TIER_DOWNGRADE_PROTECTION_MONTHS` (3 months) after tier assignment.

Configure in `TierConfig` per tenant.
