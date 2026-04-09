# Tier System — Djoyalty

## Overview
Tier system customer দের loyalty level অনুযায়ী সুবিধা দেয়।
Bronze থেকে শুরু করে Diamond পর্যন্ত ৫টি tier আছে।

## Default Tiers
| Tier | Min Points (lifetime) | Earn Multiplier | Icon |
|---|---|---|---|
| Bronze | 0 | 1.0× | 🥉 |
| Silver | 500 | 1.25× | 🥈 |
| Gold | 2,000 | 1.5× | 🥇 |
| Platinum | 5,000 | 2.0× | 💎 |
| Diamond | 10,000 | 3.0× | 💠 |

## Key Models

### LoyaltyTier — Tier definition (per tenant)
```python
name           # bronze | silver | gold | platinum | diamond
label          # Display name
min_points     # Minimum lifetime_earned required
earn_multiplier # Points multiplier for this tier
color          # Hex color code
icon           # Emoji icon
rank           # Sort order (1=Bronze, 5=Diamond)
```

### UserTier — Customer's current and history tiers
```python
customer       # ForeignKey to Customer
tier           # ForeignKey to LoyaltyTier
is_current     # True = active tier
assigned_at    # When assigned
points_at_assignment  # lifetime_earned at the time
```

### TierHistory — Upgrade/downgrade audit trail
```python
from_tier      # Previous tier (null for initial)
to_tier        # New tier
change_type    # upgrade | downgrade | initial
points_at_change  # lifetime_earned at the time
```

### TierConfig (per tenant)
```python
evaluation_period_months    # 12 (how far back to look)
downgrade_protection_months # 3 (protection period)
auto_downgrade              # True/False
notify_on_upgrade           # Send notification?
notify_on_downgrade         # Send notification?
```

## Evaluation Logic
Tier `lifetime_earned` points এর উপর ভিত্তি করে assign হয় — NOT current balance।

```
lifetime_earned >= 10000 → Diamond
lifetime_earned >= 5000  → Platinum
lifetime_earned >= 2000  → Gold
lifetime_earned >= 500   → Silver
lifetime_earned >= 0     → Bronze
```

## Service Usage

### Evaluate Tier
```python
from djoyalty.services.tiers.TierEvaluationService import TierEvaluationService
user_tier = TierEvaluationService.evaluate(customer, tenant=tenant)
```

### Force Upgrade (Admin)
```python
from djoyalty.services.tiers.TierUpgradeService import TierUpgradeService
TierUpgradeService.force_upgrade(customer, 'gold', reason='VIP promotion')
```

### Get Upgrade Progress
```python
from djoyalty.services.tiers.TierUpgradeService import TierUpgradeService
progress = TierUpgradeService.get_upgrade_progress(customer)
# {current_tier, next_tier, current_points, points_needed, progress_percent}
```

### Get Tier Benefits
```python
from djoyalty.services.tiers.TierBenefitService import TierBenefitService
benefits = TierBenefitService.get_benefits_for_customer(customer)
```

## Setup Commands
```bash
# Default tiers seed করো
python manage.py seed_tiers

# সব customer এর tier re-evaluate করো
python manage.py evaluate_tiers
```

## API Endpoints
| Method | URL | Description |
|---|---|---|
| GET | `/api/djoyalty/tiers/` | All tier definitions |
| GET | `/api/djoyalty/user-tiers/?customer=1` | Customer's current tier |
| POST | `/api/djoyalty/user-tiers/evaluate/` | Re-evaluate tier |

## Celery Task
```python
# Monthly tier evaluation
'djoyalty.evaluate_all_tiers'  # tier_evaluation_tasks.py
```

## Tier Benefits Examples
- **Bronze**: Standard earn rate
- **Silver**: 1.25× earn, Priority support
- **Gold**: 1.5× earn, Free shipping, Birthday bonus
- **Platinum**: 2.0× earn, Dedicated account manager
- **Diamond**: 3.0× earn, VIP lounge access, Annual gift
